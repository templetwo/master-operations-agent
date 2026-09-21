"""Explicit DeepSeek client for operator-invoked synthetic comparisons only."""

import copy
import hashlib
import http.client
import json
import re
import time
from pathlib import Path

from .contracts import MAX_BYTES, Rejected, digest, strict_json
from .providers import wire_json

MODEL = "deepseek-flash"


def read_api_key(path):
    """Read one literal dotenv assignment. Never source a shell or expand values."""
    try:
        with Path(path).open("rb") as file:
            content = file.read(65537)
        if len(content) > 65536: raise ValueError("Credential file exceeds the size limit.")
        text = content.decode("utf-8")
    except (OSError, UnicodeError):
        raise ValueError("Cannot read the explicitly selected credential file.") from None
    matches = []
    for line in text.splitlines():
        match = re.match(r"\s*(?:export\s+)?DEEPSEEK_API_KEY\s*=\s*(.*?)\s*$", line)
        if not match: continue
        value = match[1]
        if value.startswith(('"', "'")):
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0 or (value[end + 1:].strip() and not value[end + 1:].strip().startswith('#')):
                raise ValueError("Invalid literal DEEPSEEK_API_KEY assignment.")
            value = value[1:end]
        else:
            value = value.split(" #", 1)[0].strip()
        if not re.fullmatch(r"sk-[A-Za-z0-9_-]{16,197}", value):
            raise ValueError("DEEPSEEK_API_KEY must be a literal API token.")
        matches.append(value)
    if len(matches) != 1:
        raise ValueError("Expected exactly one DEEPSEEK_API_KEY assignment.")
    return matches[0]


class DeepSeek:
    name = "deepseek:deepseek-flash"

    def __init__(self, api_key, *, allow_cloud_synthetic=False, max_calls=61):
        if allow_cloud_synthetic is not True:
            raise ValueError("Cloud synthetic comparison must be explicitly enabled.")
        if not isinstance(api_key, str) or not re.fullmatch(r"sk-[A-Za-z0-9_-]{16,197}", api_key):
            raise ValueError("Invalid DeepSeek credential.")
        if type(max_calls) is not int or not 1 <= max_calls <= 145:
            raise ValueError("Inference call limit must be an integer from 1 to 145.")
        self._api_key = api_key
        self.model = MODEL
        self.receipt = None
        self.call_receipts = []
        self.calls = 0
        self.max_calls = max_calls

    def drain_receipts(self):
        rows, self.call_receipts = self.call_receipts, []
        return rows

    def _request(self, method, path, body=None):
        if (method, path) not in {("GET", "/models"), ("POST", "/chat/completions")}:
            raise Rejected("provider_scope", "DeepSeek route is outside the comparison protocol.")
        connection = http.client.HTTPSConnection("api.deepseek.com", timeout=20)
        try:
            connection.request(method, path, body=wire_json(body) if body is not None else None,
                               headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._api_key})
            response = connection.getresponse()
            if response.status != 200:
                # Never log remote error bodies or authentication headers.
                raise Rejected("provider_http_error", f"DeepSeek returned HTTP {response.status}. No retry or fallback attempted.")
            content = response.read(MAX_BYTES + 1)
            if self._api_key.encode() in content:
                raise Rejected("provider_error", "Credential echoed by provider; response discarded.")
            return strict_json(content)
        except (OSError, http.client.HTTPException):
            raise Rejected("provider_error", "DeepSeek connection failed or timed out. No retry or fallback attempted.") from None
        finally:
            connection.close()

    def inspect_models(self):
        listing = self._request("GET", "/models")
        if not isinstance(listing, dict) or not isinstance(listing.get("data"), list):
            raise Rejected("provider_error", "Malformed DeepSeek model listing.")
        ids = [m.get("id") for m in listing["data"] if isinstance(m, dict)]
        if self.model not in ids:
            raise Rejected("model_unavailable", "Requested deepseek-flash alias is not available. No substitution attempted.")
        return {"requested_model": self.model, "listed": True,
                "identity_limit": "Provider-reported mutable API alias; no weight digest or immutable deployment pin."}

    def prepare(self):
        if self.receipt is None:
            self.receipt = {**self.inspect_models(), "endpoint": "https://api.deepseek.com/chat/completions",
                            "settings": {"temperature": 0, "max_tokens": 768, "thinking": {"type": "disabled"},
                                         "response_format": {"type": "json_object"}, "stream": False},
                            "socket_timeout_s": 20, "maximum_inference_calls": self.max_calls,
                            "scope": "explicit-cloud-synthetic-comparison", "credential": "not_recorded"}
        return copy.deepcopy(self.receipt)

    def respond(self, messages):
        if self.receipt is None: raise Rejected("provider_error", "Provider was not prepared.")
        if self.calls >= self.max_calls: raise Rejected("provider_budget", "Cloud inference call budget exhausted.")
        body = {"model": self.model, "messages": messages, **copy.deepcopy(self.receipt["settings"])}
        encoded = wire_json(body)
        if len(encoded) > MAX_BYTES or self._api_key.encode() in encoded:
            raise Rejected("provider_scope", "Request exceeds the cloud boundary or contains a credential.")
        self.calls += 1
        started = time.monotonic()
        receipt = {"request_sha256": digest(body), "request_wire_sha256": hashlib.sha256(encoded).hexdigest(),
                   "requested_model": self.model, "call_number": self.calls}
        try:
            response = self._request("POST", "/chat/completions", body)
            receipt["response_sha256"] = digest(response)
            if not isinstance(response, dict): raise Rejected("provider_error", "Malformed DeepSeek response.")
            receipt["reported"] = {k: response[k] for k in ("id", "model", "system_fingerprint", "usage") if k in response}
            if response.get("model") not in {self.model, "deepseek-v4.1-flash"}:
                raise Rejected("model_changed", "DeepSeek returned an unexpected model identity.")
            choices = response.get("choices")
            if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
                raise Rejected("provider_error", "Expected one DeepSeek completion.")
            choice = choices[0]
            receipt["finish_reason"] = choice.get("finish_reason")
            message = choice.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise Rejected("provider_error", "Missing DeepSeek completion content.")
            receipt["content"] = message["content"][:32768]
            receipt["content_truncated"] = len(message["content"]) > 32768
            if choice.get("finish_reason") != "stop" or message.get("tool_calls"):
                raise Rejected("provider_error", "Incomplete or incompatible DeepSeek completion.")
            return strict_json(message["content"])
        except Rejected as exc:
            receipt["error"] = exc.code
            # These details are locally authored, never a remote error body.
            receipt["error_detail"] = exc.detail
            raise
        finally:
            receipt["wall_ms"] = round((time.monotonic() - started) * 1000, 2)
            self.call_receipts.append(receipt)
