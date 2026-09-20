import json
import unittest
from unittest.mock import patch
from moa.contracts import Rejected
from moa.providers import Ollama


class FakeConnection:
    replies = []
    requests = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout

    def request(self, method, path, body=None, headers=None):
        self.requests.append({"host": self.host, "port": self.port, "method": method, "path": path,
                              "body": json.loads(body) if body else None})

    def getresponse(self):
        status, body = self.replies.pop(0)
        class Response:
            def read(self, limit): return json.dumps(body).encode()[:limit]
        result = Response(); result.status = status
        return result

    def close(self): pass


class ProviderTests(unittest.TestCase):
    def setUp(self):
        FakeConnection.requests = []; FakeConnection.replies = []
        self.patch = patch('moa.providers.http.client.HTTPConnection', FakeConnection)
        self.patch.start(); self.addCleanup(self.patch.stop)

    def prepare_responses(self, **extra):
        FakeConnection.replies = [(200, {"models": [{"name": "local:1b", "digest": "a" * 64, **extra}]}), (200, {"details": {"format": "gguf"}})]

    def test_exact_local_model_schema_and_explicit_loopback(self):
        self.prepare_responses()
        provider = Ollama("local:1b")
        self.assertEqual(provider.prepare()["digest"], "a" * 64)
        FakeConnection.replies.append((200, {"done": True, "message": {"content": '{"kind":"abstain","reason":"insufficient_evidence"}'}}))
        self.assertEqual(provider.respond([])["kind"], "abstain")
        calls = FakeConnection.requests
        self.assertEqual([r["path"] for r in calls], ["/api/tags", "/api/show", "/api/chat"])
        self.assertTrue(all(r["host"] == "127.0.0.1" for r in calls))
        self.assertFalse(calls[-1]["body"]["stream"])
        self.assertIn("oneOf", calls[-1]["body"]["format"])
        self.assertFalse(calls[-1]["body"]["think"])
        self.assertEqual(calls[-1]["body"]["options"]["seed"], 0)
        receipt = provider.drain_receipts()[0]
        self.assertEqual(receipt["model_digest"], "a" * 64)
        self.assertIn("request_sha256", receipt)
        self.assertEqual(provider.drain_receipts(), [])

    def test_digest_pin_and_tag_drift_block_inference(self):
        self.prepare_responses()
        provider = Ollama("local:1b", expected_digest="b" * 64)
        with self.assertRaises(Rejected) as caught: provider.prepare()
        self.assertEqual(caught.exception.code, "model_changed")
        self.assertEqual(len(FakeConnection.requests), 1)
        self.prepare_responses()
        provider = Ollama("local:1b"); provider.prepare()
        self.prepare_responses(digest="b" * 64)
        with self.assertRaises(Rejected): provider.prepare()
        with self.assertRaises(Rejected): provider.respond([])

    def test_invalid_pin_is_rejected_before_transport(self):
        for value in (True, "latest", "a" * 63):
            with self.assertRaises(ValueError): Ollama("local:1b", expected_digest=value)
        self.assertEqual(FakeConnection.requests, [])

    def test_failed_parse_and_timeout_are_receipted_by_agent(self):
        from moa.engine import Agent
        from moa.evidence import EvidenceStore
        from moa.fixtures import fixture
        for reply in ((200, {"done": True, "message": {"content": "malformed JSON"}}), (503, {"error": "unavailable"})):
            self.prepare_responses()
            FakeConnection.replies.append(reply)
            store = EvidenceStore(":memory:")
            try:
                result = Agent(store, Ollama("local:1b")).assess(fixture("normal"))
                self.assertEqual(result["status"], "abstain")
                calls = [e["payload"]["data"] for e in store.export() if e["payload"]["kind"] == "provider_call"]
                self.assertEqual(len(calls), 1)
                if reply[0] == 200: self.assertEqual(calls[0]["content"], "malformed JSON")
                else: self.assertEqual(calls[0]["error"], "provider_error")
            finally: store.close()

    def test_unexpected_returned_model_withheld(self):
        self.prepare_responses()
        provider = Ollama("local:1b"); provider.prepare()
        FakeConnection.replies.append((200, {"model": "different:1b", "done": True, "message": {"content": '{}'}}))
        with self.assertRaises(Rejected) as caught: provider.respond([])
        self.assertEqual(caught.exception.code, "model_changed")

    def test_missing_model_is_not_pulled(self):
        FakeConnection.replies = [(200, {"models": []})]
        with self.assertRaises(Rejected): Ollama("missing:1b").prepare()
        self.assertEqual([r["path"] for r in FakeConnection.requests], ["/api/tags"])

    def test_remote_model_metadata_blocks_chat(self):
        self.prepare_responses(remote_host="https://ollama.com", remote_model="remote")
        with self.assertRaises(Rejected): Ollama("local:1b").prepare()
        self.assertNotIn("/api/chat", [r["path"] for r in FakeConnection.requests])

    def test_cloud_model_name_and_arbitrary_endpoint_disallowed(self):
        for model in ("qwen:cloud", "https://remote/model", "x\nAuthorization: token"):
            with self.assertRaises(ValueError): Ollama(model)

    def test_redirect_is_error_and_never_retried(self):
        FakeConnection.replies = [(302, {"location": "https://example.com"})]
        with self.assertRaises(Rejected): Ollama("local:1b").prepare()
        self.assertEqual(len(FakeConnection.requests), 1)

    def test_incomplete_or_invalid_output_fails_closed(self):
        for response in ([], {"done": False}, {"done": True, "done_reason": "length"}, {"done": True, "message": {"content": 'not json'}}):
            self.prepare_responses(); provider = Ollama("local:1b"); provider.prepare()
            FakeConnection.replies.append((200, response))
            with self.assertRaises(Rejected): provider.respond([])


if __name__ == "__main__": unittest.main()
