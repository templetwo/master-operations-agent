"""Bounded loopback diagnostic: identical JSON values, different property order.

No tools are executed. The expected response is a request to read evidence.
"""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from moa.contracts import MAX_BYTES, canonical, digest, stamp, strict_json
from moa.engine import ENTRY, SYSTEM
from moa.providers import Ollama, RESPONSE_SCHEMA


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    provider = Ollama(args.model, expected_digest=args.expected_digest)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    metadata = {"started_at": stamp(), "artifact": provider.prepare(),
                "server_version": provider.request("GET", "/api/version"),
                "purpose": "Only response-schema properties order varies. No observation, process labels, or tool execution.",
                "sequence": ["sorted", "declared", "declared", "sorted"]}
    (output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    body = {"model": args.model, "messages": [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": canonical(ENTRY)}], "format": RESPONSE_SCHEMA, "stream": False,
            "options": dict(provider.settings), "think": False, "keep_alive": "5m"}
    results = []
    for index, order in enumerate(metadata["sequence"], 1):
        wire_body = strict_json(canonical(body))
        if order == "declared":
            for original, branch in zip(RESPONSE_SCHEMA["oneOf"], wire_body["format"]["oneOf"]):
                branch["properties"] = original["properties"]
        encoded = json.dumps(wire_body, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        (output / f"{index}-{order}.request.json").write_bytes(encoded)
        receipt = {"order": order, "semantic_sha256": digest(body), "wire_sha256": hashlib.sha256(encoded).hexdigest()}
        connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=20)
        started = time.monotonic()
        try:
            connection.request("POST", "/api/chat", body=encoded, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            receipt["status"] = response.status
            data = strict_json(response.read(MAX_BYTES + 1))
            receipt["response_sha256"] = digest(data)
            receipt["response"] = {k: v for k, v in data.items() if k != "message"}
            receipt["content"] = data.get("message", {}).get("content")
            receipt["candidate"] = strict_json(receipt["content"])
            receipt["requested_read"] = receipt["candidate"] == {"kind": "tool", "name": "read_snapshot", "arguments": {}}
        finally:
            connection.close()
            receipt["wall_ms"] = round((time.monotonic() - started) * 1000, 2)
            (output / f"{index}-{order}.response.json").write_text(json.dumps(receipt, indent=2) + "\n")
        results.append(receipt)
        print(order, receipt["candidate"], flush=True)
    metadata["artifact_after"] = provider.prepare()
    metadata["artifact_unchanged"] = metadata["artifact"] == metadata["artifact_after"]
    metadata["semantic_requests_identical"] = len({r["semantic_sha256"] for r in results}) == 1
    metadata["completed_at"] = stamp()
    (output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__": main()
