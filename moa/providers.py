"""Explicit providers. The default is a deterministic baseline, never a cloud call."""

import http.client
import re
import time
from .contracts import Rejected, canonical, digest, strict_json, MAX_BYTES
from .knowledge import eligible

RESPONSE_SCHEMA = {
    "type": "object",
    "oneOf": [
        {"type": "object", "additionalProperties": False, "required": ["kind", "name", "arguments"],
         "properties": {"kind": {"const": "tool"}, "name": {"type": "string"}, "arguments": {"type": "object"}}},
        {"type": "object", "additionalProperties": False, "required": ["kind", "finding_ids", "check_ids", "evidence"],
         "properties": {"kind": {"const": "advice"}, "finding_ids": {"type": "array", "items": {"type": "string"}},
                        "check_ids": {"type": "array", "items": {"type": "string"}}, "evidence": {"type": "array", "items": {"type": "string"}}}},
        {"type": "object", "additionalProperties": False, "required": ["kind", "reason"],
         "properties": {"kind": {"const": "abstain"}, "reason": {"enum": ["insufficient_evidence"]}}},
    ],
}


class Baseline:
    name = "deterministic-baseline-v2"

    def respond(self, messages):
        results = [strict_json(m["content"]) for m in messages if m["role"] == "user"]
        reads = {r["tool"]: r["result"] for r in results if "tool" in r}
        if "read_snapshot" not in reads:
            return {"kind": "tool", "name": "read_snapshot", "arguments": {}}
        if "read_policy" not in reads:
            return {"kind": "tool", "name": "read_policy", "arguments": {}}
        snapshot = reads["read_snapshot"]
        if snapshot["profile"] == "ess-u1-window-v1":
            if "read_history" not in reads:
                return {"kind": "tool", "name": "read_history", "arguments": {}}
            snapshot = dict(snapshot, history=reads["read_history"])
        findings, checks, evidence, _ = eligible(snapshot)
        return {"kind": "advice", "finding_ids": findings, "check_ids": checks, "evidence": evidence}


class Ollama:
    """Fixed numeric loopback, no proxy/redirect, no pull, no retries or fallback.

    The local daemon is trusted infrastructure. Disable its cloud features and
    restrict its egress separately. A client cannot prove server isolation.
    """
    def __init__(self, model, port=11434, expected_digest=None):
        if not isinstance(model, str) or len(model) > 120 or not re.fullmatch(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", model) or "cloud" in model.lower():
            raise ValueError("Choose an explicit installed local model, not a cloud model.")
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Invalid local Ollama port.")
        if expected_digest is not None and (not isinstance(expected_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_digest)):
            raise ValueError("Expected digest must be 64 lowercase hexadecimal characters.")
        self.model, self.port = model, port
        self.expected_digest = expected_digest
        self.name = f"ollama:{model}"
        self.receipt = None
        self.call_receipts = []
        self.settings = {"temperature": 0, "seed": 0, "num_predict": 768, "num_ctx": 8192}

    def drain_receipts(self):
        receipts, self.call_receipts = self.call_receipts, []
        return receipts

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            encoded = canonical(body).encode() if body is not None else None
            connection.request(method, path, body=encoded, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            content = response.read(MAX_BYTES + 1)
            if response.status != 200:
                raise Rejected("provider_error", "Local model request failed. No fallback attempted.")
            return strict_json(content)
        except (OSError, http.client.HTTPException) as exc:
            raise Rejected("provider_error", "Local model unavailable or timed out. No fallback attempted.") from exc
        finally:
            connection.close()

    def prepare(self):
        self.receipt = None
        tags = self.request("GET", "/api/tags")
        if not isinstance(tags, dict) or not isinstance(tags.get("models"), list) or any(not isinstance(m, dict) for m in tags["models"]):
            raise Rejected("provider_error", "Malformed installed-model listing.")
        matches = [m for m in tags.get("models", []) if m.get("name") == self.model]
        if len(matches) != 1 or not re.fullmatch(r"[a-f0-9]{64}", matches[0].get("digest", "")):
            raise Rejected("model_unavailable", "Exact model name and digest must exist locally. No model was downloaded.")
        if self.expected_digest is not None and matches[0]["digest"] != self.expected_digest:
            raise Rejected("model_changed", "Installed artifact differs from the pinned digest.")
        info = self.request("POST", "/api/show", {"model": self.model})
        if not isinstance(info, dict):
            raise Rejected("provider_error", "Malformed model metadata.")
        if info.get("remote_host") or info.get("remote_model") or matches[0].get("remote_host") or matches[0].get("remote_model"):
            raise Rejected("scope", "Remote-backed models are excluded.")
        self.expected_digest = matches[0]["digest"]
        self.receipt = {"name": self.model, "digest": matches[0]["digest"], "details": matches[0].get("details", {}),
                        "template_sha256": digest(info.get("template")), "parameters_sha256": digest(info.get("parameters")),
                        "settings": dict(self.settings), "think": False, "stream": False, "keep_alive": "5m",
                        "response_schema_sha256": digest(RESPONSE_SCHEMA), "socket_timeout_s": 20,
                        "endpoint": f"http://127.0.0.1:{self.port}", "server_isolation": "operator_responsibility"}
        return self.receipt

    def respond(self, messages):
        if not self.receipt:
            raise Rejected("provider_error", "Provider was not prepared.")
        body = {
            "model": self.model, "messages": messages, "format": RESPONSE_SCHEMA, "stream": False,
            "options": dict(self.settings), "think": False, "keep_alive": "5m",
        }
        started = time.monotonic()
        receipt = {"request_sha256": digest(body), "model_digest": self.receipt["digest"]}
        try:
            response = self.request("POST", "/api/chat", body)
            receipt["response_sha256"] = digest(response)
            if isinstance(response, dict):
                receipt["reported"] = {k: response[k] for k in (
                    "model", "done", "done_reason", "total_duration", "load_duration", "prompt_eval_count",
                    "prompt_eval_cached_count", "prompt_eval_duration", "eval_count", "eval_duration") if k in response}
                message = response.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    receipt["content"] = message["content"][:32768]
                    receipt["content_truncated"] = len(message["content"]) > 32768
        except Rejected as exc:
            receipt["error"] = exc.code
            raise
        finally:
            receipt["wall_ms"] = round((time.monotonic() - started) * 1000, 2)
            self.call_receipts.append(receipt)
        if not isinstance(response, dict) or response.get("done") is not True or response.get("done_reason") == "length":
            raise Rejected("provider_error", "Local model response was incomplete.")
        if response.get("model", self.model) != self.model:
            raise Rejected("model_changed", "Server returned an unexpected model identity.")
        try:
            return strict_json(response["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise Rejected("provider_error", "Malformed local model response.") from exc
