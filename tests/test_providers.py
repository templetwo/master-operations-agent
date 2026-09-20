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
