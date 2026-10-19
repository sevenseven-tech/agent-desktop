#!/usr/bin/env python3
"""Auth gate + reverse proxy for MCP endpoints (stdlib only).

HTTP-aware on purpose: MCP clients use keep-alive with multiple POSTs per
connection, so authentication and Host normalization must happen PER REQUEST,
not per connection (upstream playwright-mcp enforces Host == localhost:<port>
as DNS-rebinding protection and would reject later requests otherwise).

Per request:
  - Authorization: Bearer <MCP_TOKEN>   (constant-time compare)
  - Origin header, when present, must be in MCP_ALLOWED_ORIGINS.
    Native (non-browser) MCP clients send no Origin and are allowed;
    browser-context clients without a matching Origin are rejected
    (MCP spec 2026-07-28: Origin validation is MUST on Streamable HTTP).
  - one JSON audit line to stdout (kubectl logs = audit trail)

Refuses to start without MCP_TOKEN - no silent open-access.
"""
import http.client
import hmac
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN_PORT = int(os.environ.get("MCP_PORT", "8931"))
UPSTREAM_PORT = int(os.environ.get("MCP_UPSTREAM_PORT", "8930"))
DESKTOP_UPSTREAM_PORT = int(os.environ.get("MCP_DESKTOP_UPSTREAM_PORT", "8932"))
TOKEN = os.environ.get("MCP_TOKEN", "")
ORIGINS = [o.strip() for o in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()]
HOP_BY_HOP = {"host", "authorization", "content-length", "connection",
              "transfer-encoding", "accept-encoding", "keep-alive", "upgrade"}

if not TOKEN:
    sys.stderr.write("mcp_forward: MCP_TOKEN is not set - refusing to start open-access\n")
    sys.exit(1)


def audit(code, method, path, origin, peer):
    print(json.dumps({
        "ts": round(time.time(), 3), "ev": "mcp_http", "code": code,
        "method": method, "path": path.split("?")[0],
        "origin": origin or "-", "peer": peer[0] if peer else "-",
    }), flush=True)


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _check(self):
        auth = self.headers.get("Authorization", "")
        # compare on UTF-8 BYTES: str-compare_digest raises TypeError on any
        # non-ASCII character, which would kill the handler thread before a
        # response is sent (silent 000 for every request).
        if not hmac.compare_digest(auth.encode("utf-8"), ("Bearer " + TOKEN).encode("utf-8")):
            return 401
        origin = self.headers.get("Origin", "")
        if origin and origin not in ORIGINS:
            return 403
        return 0

    def _proxy(self):
        code = self._check()
        origin = self.headers.get("Origin", "")
        if code:
            audit(code, self.command, self.path, origin, self.client_address)
            self.send_error(code)
            return
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            audit(400, self.command, self.path, origin, self.client_address)
            self.send_error(400)
            return
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        # Path routing: /desktop* -> desktop_actions (rewritten to its /mcp
        # mount point); everything else -> playwright-mcp. Host is normalized
        # PER UPSTREAM (each enforces Host == localhost:<its own port>).
        if self.path.split("?")[0].rstrip("/").startswith("/desktop"):
            upstream, upath = DESKTOP_UPSTREAM_PORT, "/mcp"
        else:
            upstream, upath = UPSTREAM_PORT, self.path
        headers["Host"] = "localhost:%d" % upstream
        try:
            conn = http.client.HTTPConnection("127.0.0.1", upstream)
            conn.request(self.command, upath, body=body, headers=headers)
            resp = conn.getresponse()
        except OSError:
            audit(502, self.command, self.path, origin, self.client_address)
            self.send_error(502)
            return
        audit(resp.status, self.command, self.path, origin, self.client_address)
        self.send_response(resp.status, resp.reason)
        for k, v in resp.getheaders():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        # Always chunk toward the client: works for plain JSON bodies AND
        # long-lived SSE streams without needing upstream framing knowledge.
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        try:
            while True:
                # read1, NOT read: read(4096) blocks until 4096 bytes or EOF,
                # which deadlocks SSE streams (MCP tools/call responses stream
                # as small events on a POST stream that stays open). read1
                # returns whatever is available now.
                chunk = resp.read1(65536)
                if not chunk:
                    break
                self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except OSError:
            pass  # client went away (SSE disconnect) - normal
        finally:
            conn.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _proxy

    def log_message(self, format, *args):  # audit() covers it; silence stderr spam
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Proxy).serve_forever()
