"""Tiny local HTTP API for agents/tools that can call URLs but not MCP.

    GET http://127.0.0.1:8765/read?url=<mp.weixin.qq.com link>[&format=md|json][&images=0]
    GET http://127.0.0.1:8765/health
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import WeChatReaderError, __version__, read_article


class _Handler(BaseHTTPRequestHandler):
    server_version = f"wechat-article-reader/{__version__}"

    def _send(self, code: int, body: str, ctype: str) -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parts = urlsplit(self.path)
        qs = {k: v[0] for k, v in parse_qs(parts.query).items()}
        if parts.path == "/health":
            return self._send(200, json.dumps({"ok": True, "version": __version__}), "application/json")
        if parts.path != "/read":
            return self._send(404, json.dumps({"error": "not_found", "usage": "/read?url=..."}), "application/json")
        as_json = qs.get("format", "md") == "json"
        try:
            art = read_article(qs.get("url", ""), browser=qs.get("browser", "never"))
        except ValueError as e:
            return self._send(400, json.dumps({"error": "invalid_url", "message": str(e)}), "application/json")
        except WeChatReaderError as e:
            return self._send(
                502, json.dumps({"error": e.status.value, "message": str(e)}, ensure_ascii=False), "application/json"
            )
        except Exception as e:
            return self._send(502, json.dumps({"error": "fetch_failed", "message": str(e)}), "application/json")
        if qs.get("images") == "0":
            art.strip_images()
        if as_json:
            return self._send(200, json.dumps(art.to_dict(), ensure_ascii=False), "application/json")
        return self._send(200, art.to_markdown(), "text/markdown")

    def log_message(self, fmt, *args) -> None:
        pass


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    print(f"wechat-article-reader HTTP API on http://{host}:{port}/read?url=...", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
