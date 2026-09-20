"""Loopback-only research dashboard. No configurable upstream or file endpoint."""

import json
import secrets
import socketserver
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from .contracts import Rejected, MAX_BYTES, canonical, keys, strict_json
from .engine import Agent
from .evidence import EvidenceError
from .fixtures import SCENARIOS, fixture

WEB = Path(__file__).with_name("web")


class LocalServer(ThreadingHTTPServer):
    daemon_threads = False

    def server_bind(self):
        # Avoid HTTPServer's reverse-DNS lookup. This service is numeric loopback.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address


def make_server(store, port=8765, provider=None):
    token = secrets.token_urlsafe(32)
    busy = threading.Lock()
    agent = Agent(store, provider)

    class Handler(BaseHTTPRequestHandler):
        server_version = "MOA-Lab/0.2"

        def log_message(self, *_):
            pass

        def allowed_origin(self):
            expected = f"127.0.0.1:{self.server.server_port}"
            origin = self.headers.get("Origin")
            return self.headers.get("Host") == expected and (origin is None or origin == f"http://{expected}")

        def send(self, code, body, content_type="application/json"):
            data = canonical(body).encode() if content_type == "application/json" else body
            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.allowed_origin():
                return self.send(403, {"error": "Origin or Host rejected."})
            url = urlparse(self.path)
            assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
            if url.path in assets:
                name, type_ = assets[url.path]
                return self.send(200, (WEB / name).read_bytes(), type_)
            if url.path == "/api/config":
                return self.send(200, {"token": token, "scenarios": SCENARIOS, "provider": agent.provider.name})
            if url.path == "/api/scenario":
                name = parse_qs(url.query).get("name", ["cooling"])[0]
                if name not in SCENARIOS:
                    return self.send(400, {"error": "Unknown scenario."})
                return self.send(200, fixture(name))
            if url.path == "/api/evidence":
                try:
                    return self.send(200, store.bundle())
                except (EvidenceError, ValueError, sqlite3.Error):
                    return self.send(503, {"error": "Evidence verification failed."})
            if url.path == "/api/health":
                return self.send(200, {"status": "lab", "provider": agent.provider.name, "plant_connection": False})
            return self.send(404, {"error": "Not found."})

        def do_POST(self):
            supplied = self.headers.get("X-MOA-Token", "")
            if not self.allowed_origin() or self.headers.get("Origin") != f"http://127.0.0.1:{self.server.server_port}" or not supplied.isascii() or not secrets.compare_digest(supplied, token):
                return self.send(403, {"error": "Same-origin session token required."})
            if self.path != "/api/assess":
                return self.send(404, {"error": "Not found. No control endpoint exists."})
            if self.headers.get("Content-Type") != "application/json" or self.headers.get("Transfer-Encoding"):
                return self.send(415, {"error": "A bounded JSON body is required."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BYTES:
                    return self.send(413, {"error": "Body exceeds the input limit."})
                self.connection.settimeout(5)
                request = strict_json(self.rfile.read(length))
                keys(request, {"observation"}, "assessment request")
            except (ValueError, OSError):
                return self.send(400, {"error": "Invalid assessment request."})
            if not busy.acquire(blocking=False):
                return self.send(429, {"error": "An assessment is already running."})
            try:
                result = agent.assess(request["observation"])
            except (EvidenceError, OSError, sqlite3.Error):
                return self.send(503, {"error": "Evidence unavailable. No advice released."})
            finally:
                busy.release()
            return self.send(200, result)

    return LocalServer(("127.0.0.1", port), Handler)
