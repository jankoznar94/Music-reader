#!/usr/bin/env python3
"""Servíruje `dist/` s SPA fallbackem na 5173 — pro sondy bez vite.

Router je `createWebHistory`, takže bez fallbacku spadne `/prohlizec/:id`;
proto každou neexistující cestu vracíme jako index.html.

Použití:  python3 scripts/serve-dist.py [port]
"""
import http.server
import os
import socketserver
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5173


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass

    def send_head(self):
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path):
            if os.path.isdir(path) and os.path.exists(os.path.join(path, "index.html")):
                return super().send_head()
            self.path = "/index.html"
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


with Server(("127.0.0.1", PORT), Handler) as httpd:
    print(f"dist na http://127.0.0.1:{PORT}/", flush=True)
    httpd.serve_forever()
