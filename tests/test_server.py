import http.client
import json
import threading
import unittest
from moa.evidence import EvidenceStore
from moa.fixtures import fixture
from moa.server import make_server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = EvidenceStore(":memory:")
        cls.server = make_server(cls.store, port=0)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.store.close()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body, headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally: conn.close()

    def headers(self):
        _, _, raw = self.request("GET", "/api/config")
        return {"Content-Type": "application/json", "X-MOA-Token": json.loads(raw)["token"], "Origin": f"http://127.0.0.1:{self.port}"}

    def test_advisory_and_export_end_to_end(self):
        status, _, body = self.request("POST", "/api/assess", json.dumps({"observation": fixture()}), self.headers())
        self.assertEqual(status, 200); self.assertEqual(json.loads(body)["status"], "advisory")
        status, _, body = self.request("GET", "/api/evidence")
        self.assertEqual(status, 200); self.assertTrue(json.loads(body)["events"])

    def test_cross_origin_and_dns_rebinding_rejected(self):
        for headers in ({"Origin": "https://evil.example"}, {"Host": "evil.example"}):
            self.assertEqual(self.request("GET", "/api/config", headers=headers)[0], 403)
        headers = self.headers(); headers["Origin"] = "https://evil.example"
        self.assertEqual(self.request("POST", "/api/assess", "{}", headers)[0], 403)

    def test_missing_session_token_rejected(self):
        headers = self.headers(); del headers["X-MOA-Token"]
        self.assertEqual(self.request("POST", "/api/assess", "{}", headers)[0], 403)

    def test_imported_json_retains_duplicate_key_rejection(self):
        raw = json.dumps(fixture()).replace('"schema_version": "1.0"', '"schema_version": "0.9", "schema_version": "1.0"')
        status, _, body = self.request("POST", "/api/assess", json.dumps({"observation": raw}), self.headers())
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["reason"], "duplicate_key")

    def test_non_ascii_session_token_is_rejected(self):
        headers = self.headers(); headers["X-MOA-Token"] = "invalid-\u00e9"
        self.assertEqual(self.request("POST", "/api/assess", "{}", headers)[0], 403)

    def test_control_routes_and_path_traversal_absent(self):
        for route in ("/api/write_tag", "/api/execute_script", "/../pyproject.toml"):
            self.assertEqual(self.request("POST", route, "{}", self.headers())[0], 404)
            self.assertEqual(self.request("GET", route)[0], 404)

    def test_oversized_body_and_duplicate_key_rejected(self):
        self.assertEqual(self.request("POST", "/api/assess", "x" * 262145, self.headers())[0], 413)
        self.assertEqual(self.request("POST", "/api/assess", '{"observation":{},"observation":{}}', self.headers())[0], 400)

    def test_dashboard_has_local_only_assets_and_csp(self):
        from moa import __version__
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Server"].startswith("MOA-Lab/" + __version__ + " "))
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertIn(b"SYNTHETIC ENVIRONMENT", body)
        self.assertNotIn(b"https://", body)


if __name__ == "__main__": unittest.main()
