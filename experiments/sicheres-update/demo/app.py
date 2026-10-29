"""Minimal simulated service. No connection to the real app or OpenStack."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from gate import Gate

gate = Gate(os.getenv("REDIS_HOST", "gate"), 6379)
mode = os.getenv("APP_MODE", "v1")


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.respond(503 if mode == "broken" else 200, {"version": mode})
        else:
            self.respond(404, {})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 256:
                return self.respond(400, {})
            task = json.loads(self.rfile.read(length))["task"]
            if not isinstance(task, str) or not task or len(task) > 64:
                return self.respond(400, {})
            if self.path == "/start":
                result = gate.accept(task)
                self.respond(202 if result == 1 else 503 if result == 0 else 409, {})
            elif self.path == "/finish":
                self.respond(200 if gate.finish(task) else 404, {})
            else:
                self.respond(404, {})
        except (OSError, ValueError, KeyError, RuntimeError):
            self.respond(503, {"error": "gate unavailable"})

    def log_message(self, *_args):
        pass


ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
