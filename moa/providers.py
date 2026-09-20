"""Explicit providers. The default is a deterministic baseline, never a cloud call."""

import http.client
import re
from .contracts import Rejected, canonical, strict_json, MAX_BYTES
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
    name = "deterministic-baseline-v1"

    def respond(self, messages):
        results = [strict_json(m["content"]) for m in messages if m["role"] == "user"]
        reads = {r["tool"]: r["result"] for r in results if "tool" in r}
        if "read_snapshot" not in reads:
            return {"kind": "tool", "name": "read_snapshot", "arguments": {}}
        if "read_policy" not in reads:
            return {"kind": "tool", "name": "read_policy", "arguments": {}}
        findings, checks, evidence, _ = eligible(reads["read_snapshot"])
        return {"kind": "advice", "finding_ids": findings, "check_ids": checks, "evidence": evidence}


class Ollama:
    """Fixed numeric loopback, no proxy/redirect, no pull, no retries or fallback.

    The local daemon is trusted infrastructure. Disable its cloud features and
    restrict its egress separately. A client cannot prove server isolation.
    """
    def __init__(self, model, port=11434):
        if not isinstance(model, str) or len(model) > 120 or not re.fullmatch(r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", model) or "cloud" in model.lower():
            raise ValueError("Choose an explicit installed local model, not a cloud model.")
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Invalid local Ollama port.")
        self.model, self.port = model, port
        self.name = f"ollama:{model}"
        self.receipt = None

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
        tags = self.request("GET", "/api/tags")
        if not isinstance(tags, dict) or not isinstance(tags.get("models"), list) or any(not isinstance(m, dict) for m in tags["models"]):
            raise Rejected("provider_error", "Malformed installed-model listing.")
        matches = [m for m in tags.get("models", []) if m.get("name") == self.model]
        if len(matches) != 1 or not re.fullmatch(r"[a-f0-9]{64}", matches[0].get("digest", "")):
            raise Rejected("model_unavailable", "Exact model name and digest must exist locally. No model was downloaded.")
        info = self.request("POST", "/api/show", {"model": self.model})
        if not isinstance(info, dict):
            raise Rejected("provider_error", "Malformed model metadata.")
        if info.get("remote_host") or info.get("remote_model") or matches[0].get("remote_host") or matches[0].get("remote_model"):
            raise Rejected("scope", "Remote-backed models are excluded.")
        self.receipt = {"name": self.model, "digest": matches[0]["digest"], "details": matches[0].get("details", {}),
                        "endpoint": f"http://127.0.0.1:{self.port}", "server_isolation": "operator_responsibility"}
        return self.receipt

    def respond(self, messages):
        if not self.receipt:
            raise Rejected("provider_error", "Provider was not prepared.")
        response = self.request("POST", "/api/chat", {
            "model": self.model, "messages": messages, "format": RESPONSE_SCHEMA, "stream": False,
            "options": {"temperature": 0, "num_predict": 768, "num_ctx": 8192}, "keep_alive": "5m",
        })
        if not isinstance(response, dict) or response.get("done") is not True or response.get("done_reason") == "length":
            raise Rejected("provider_error", "Local model response was incomplete.")
        try:
            return strict_json(response["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise Rejected("provider_error", "Malformed local model response.") from exc
