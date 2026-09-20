import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from moa.contracts import Rejected
from moa.deepseek import DeepSeek, read_api_key
from moa.cloud_comparison import compare_deepseek, cloud_metrics

KEY = "sk-" + "test" * 8


class HTTPS:
    replies = []
    calls = []

    def __init__(self, host, timeout):
        self.host = host

    def request(self, method, path, body=None, headers=None):
        self.calls.append({"host": self.host, "method": method, "path": path, "body": json.loads(body) if body else None, "headers": headers})

    def getresponse(self):
        status, data = self.replies.pop(0)
        class Response:
            def read(self, size): return json.dumps(data).encode()[:size]
        response = Response(); response.status = status
        return response

    def close(self): pass


def completion(content='{"kind":"abstain","reason":"insufficient_evidence"}', **changes):
    return {"model": "deepseek-flash", "id": "test-response", "system_fingerprint": "test-fingerprint",
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}, **changes}


class DeepSeekTests(unittest.TestCase):
    def setUp(self):
        HTTPS.calls = []; HTTPS.replies = []
        self.patch = patch("moa.deepseek.http.client.HTTPSConnection", HTTPS)
        self.patch.start(); self.addCleanup(self.patch.stop)

    def provider(self):
        HTTPS.replies.append((200, {"data": [{"id": "deepseek-flash"}]}))
        provider = DeepSeek(KEY, allow_cloud_synthetic=True); provider.prepare()
        return provider

    def test_explicit_consent_before_credentials_or_network(self):
        with self.assertRaises(ValueError): DeepSeek(KEY)
        with patch("moa.cloud_comparison.read_api_key") as reader:
            with self.assertRaises(ValueError): compare_deepseek("unused", "unused", "unused")
            reader.assert_not_called()
        self.assertEqual(HTTPS.calls, [])

    def test_fixed_endpoint_json_protocol_and_no_secret_in_receipts(self):
        provider = self.provider(); HTTPS.replies.append((200, completion()))
        self.assertEqual(provider.respond([])["kind"], "abstain")
        self.assertEqual([c["host"] for c in HTTPS.calls], ["api.deepseek.com"] * 2)
        call = HTTPS.calls[-1]
        self.assertEqual(call["path"], "/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], "Bearer " + KEY)
        self.assertEqual(call["body"]["thinking"], {"type": "disabled"})
        self.assertEqual(call["body"]["response_format"], {"type": "json_object"})
        self.assertNotIn(KEY, json.dumps(provider.prepare()))
        receipts = provider.drain_receipts()
        self.assertNotIn(KEY, json.dumps(receipts))
        self.assertEqual(receipts[0]["reported"]["usage"]["total_tokens"], 70)

    def test_redirect_and_authentication_errors_never_follow_or_echo(self):
        for status in (301, 401, 429, 500):
            HTTPS.calls = []; HTTPS.replies = [(status, {"error": KEY})]
            with self.assertRaises(Rejected) as caught: DeepSeek(KEY, allow_cloud_synthetic=True).prepare()
            self.assertNotIn(KEY, str(caught.exception))
            self.assertEqual(len(HTTPS.calls), 1)

    def test_no_alias_substitution_or_unrelated_routes(self):
        HTTPS.replies = [(200, {"data": [{"id": "deepseek-v4-pro"}]} )]
        provider = DeepSeek(KEY, allow_cloud_synthetic=True)
        with self.assertRaises(Rejected): provider.prepare()
        with self.assertRaises(Rejected): provider._request("GET", "/user/balance")
        self.assertEqual(len(HTTPS.calls), 1)

    def test_truncation_wrong_model_and_invalid_json_are_withheld(self):
        for response in (completion(choices=[{"finish_reason":"length", "message":{"content":"{}"}}]),
                         completion(model="deepseek-v4-pro"), completion(content="not-json"), completion(choices=[])):
            provider = self.provider(); HTTPS.replies.append((200, response))
            with self.assertRaises(Rejected): provider.respond([])
            self.assertIn("error", provider.drain_receipts()[0])

    def test_echoed_key_is_discarded_before_receipting(self):
        provider = self.provider(); HTTPS.replies.append((200, completion(content=KEY)))
        with self.assertRaises(Rejected): provider.respond([])
        self.assertNotIn(KEY, json.dumps(provider.drain_receipts()))

    def test_key_in_request_and_exhausted_budget_block_network(self):
        provider = self.provider()
        with self.assertRaises(Rejected): provider.respond([{"role":"user","content":KEY}])
        provider.calls = provider.max_calls
        with self.assertRaises(Rejected) as caught: provider.respond([])
        self.assertEqual(caught.exception.code, "provider_budget")
        self.assertEqual(len(HTTPS.calls), 1)

    def test_literal_dotenv_only_without_execution_or_interpolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"; marker = Path(directory) / "never-created"
            path.write_text(f"OTHER=$(touch {marker})\nexport DEEPSEEK_API_KEY='{KEY}' # comment\n")
            self.assertEqual(read_api_key(path), KEY)
            self.assertFalse(marker.exists())
            for text in (f"DEEPSEEK_API_KEY={KEY}\nDEEPSEEK_API_KEY={KEY}", "DEEPSEEK_API_KEY=$(touch nowhere)", "DEEPSEEK_API_KEY=${OTHER}"):
                path.write_text(text)
                with self.assertRaises(ValueError) as caught: read_api_key(path)
                self.assertNotIn(KEY, str(caught.exception))

    def test_failed_preflight_is_preserved_without_scoring(self):
        with tempfile.TemporaryDirectory() as directory, patch("moa.cloud_comparison.evaluate_drills") as evaluate:
            path=Path(directory)/".env"; path.write_text("DEEPSEEK_API_KEY="+KEY)
            output=Path(directory)/"run"; HTTPS.replies=[(401,{"error":KEY})]
            with self.assertRaises(Rejected): compare_deepseek("unused",path,output,allow_cloud_synthetic=True)
            evaluate.assert_not_called()
            record=(output/"run.json").read_text()
            self.assertNotIn(KEY,record)
            self.assertEqual(json.loads(record)["status"],"interrupted")
            self.assertFalse((output/"comparison.json").exists())

    def test_missing_usage_is_unknown_not_zero(self):
        report={"evidence":{"events":[{"payload":{"kind":"provider_call","data":{"wall_ms":10}}}]}}
        self.assertIsNone(cloud_metrics(report)["reported_usage"]["total_tokens"])

    def test_malformed_usage_does_not_fabricate_counters(self):
        for usage in (None, "unknown", {"total_tokens": True}):
            report={"evidence":{"events":[{"payload":{"kind":"provider_call","data":{"wall_ms":10,"reported":{"usage":usage}}}}]}}
            self.assertIsNone(cloud_metrics(report)["reported_usage"]["total_tokens"])

    @unittest.skipUnless(os.environ.get("MOA_SIM_REPO"), "Set MOA_SIM_REPO for synthetic cloud-runner integration")
    def test_cloud_runner_with_simulator_and_mocked_model(self):
        from moa.providers import Baseline
        class MockCloud(DeepSeek):
            def _request(self, method, path, body=None):
                if path == "/models": return {"data":[{"id":"deepseek-flash"}]}
                self_test.assertNotIn(KEY,json.dumps(body))
                self_test.assertNotIn('"expected"',json.dumps(body))
                reply=Baseline().respond(body["messages"])
                return completion(content=json.dumps(reply))
        self_test=self
        with tempfile.TemporaryDirectory() as directory, patch("moa.cloud_comparison.DeepSeek",MockCloud):
            path=Path(directory)/".env"; path.write_text("DEEPSEEK_API_KEY="+KEY)
            output=Path(directory)/"run"
            report=compare_deepseek(os.environ["MOA_SIM_REPO"],path,output,allow_cloud_synthetic=True)
            self.assertTrue(report["comparison_valid"])
            self.assertTrue(report["cloud_passed_development"])
            self.assertEqual(report["inference"]["calls"],40)
            self.assertEqual(report["reports"]["always-refuse"]["metrics"]["useful_assessment"]["passed"],0)
            for artifact in output.glob('*.json'):
                self.assertNotIn(KEY,artifact.read_text())


if __name__ == "__main__": unittest.main()
