#!/usr/bin/env python3
"""Check and serve a Godot Web export locally with the headers threads need (stdlib only).

Usage:
  python serve_web.py DIR --check
      Inspect an export folder: thread support, file sizes, PWA/service worker, hosting warnings.
  python serve_web.py DIR [--port 8060] [--host 127.0.0.1] [--no-isolation] [--seconds N]
      Serve DIR with Cross-Origin-Opener-Policy/Embedder-Policy (needed by thread builds),
      correct .wasm/.pck MIME types and precompressed .br/.gz files when present.
      Prints one JSON line with the URL, then serves until stopped (or for N seconds).
      Run it in the background; open the URL in a browser (headless Godot can't render).
Output (--check): {"ok", "html", "threads", "files": {name: MB}, "total_mb", "warnings"}
"""
import functools
import http.server
import json
import os
import pathlib
import re
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _godotx import emit  # noqa: E402

MIME = {".wasm": "application/wasm", ".pck": "application/octet-stream", ".js": "text/javascript",
        ".html": "text/html", ".json": "application/json", ".webmanifest": "application/manifest+json"}


def check(d):
    d = pathlib.Path(d)
    if not d.is_dir():
        return {"ok": False, "error": f"not a folder: {d}"}
    htmls = sorted(p.name for p in d.glob("*.html") if not p.name.endswith(".offline.html"))
    sizes = {p.name: p.stat().st_size for p in sorted(d.iterdir()) if p.is_file()}
    files = {k: round(v / 1048576, 2) for k, v in sizes.items()}
    warns, threads = [], None
    for h in htmls:
        m = re.search(r"GODOT_THREADS_ENABLED\s*=\s*(true|false)", (d / h).read_text("utf-8", "replace"))
        if m:
            threads = m.group(1) == "true"
    if not htmls:
        warns.append("no .html file: is this a Web export folder?")
    if not any(n.endswith(".wasm") for n in files):
        warns.append("no .wasm file")
    if threads:
        warns.append("thread build: the host must send COOP: same-origin and COEP: require-corp "
                     "(itch.io: enable 'SharedArrayBuffer support'; GitHub Pages: enable the PWA "
                     "option progressive_web_app/ensure_cross_origin_isolation_headers or export without threads)")
    wasm = sum(v for k, v in files.items() if k.endswith(".wasm"))
    if wasm and not any(k.endswith((".wasm.br", ".wasm.gz")) for k in files):
        warns.append(f".wasm is {wasm} MB uncompressed: make sure the host serves it with gzip/brotli (~4x smaller)")
    pck = sum(v for k, v in files.items() if k.endswith(".pck"))
    if pck > 100:
        warns.append(f".pck is {pck} MB: the browser downloads it all before start; compress textures, stream or split content")
    pwa = any(re.search(r'"serviceWorker"\s*:\s*"[^"]+"', (d / h).read_text("utf-8", "replace")) for h in htmls)
    if pwa:
        warns.append("PWA service worker present: it caches aggressively, so bump the version or hard-reload when testing")
    return {"ok": bool(htmls) and any(k.endswith(".wasm") and v > 0 for k, v in sizes.items()), "html": htmls, "threads": threads, "files": files,
            "total_mb": round(sum(files.values()), 2), "warnings": warns}


class Handler(http.server.SimpleHTTPRequestHandler):
    isolation = True

    def end_headers(self):
        if self.isolation:
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def guess_type(self, path):
        return MIME.get(pathlib.Path(str(path)).suffix, None) or super().guess_type(path)

    def send_head(self):
        path = pathlib.Path(self.translate_path(self.path))
        enc = self.headers.get("Accept-Encoding", "")
        for suffix, name in ((".br", "br"), (".gz", "gzip")):
            alt = path.with_name(path.name + suffix)
            if name in enc and path.suffix in (".wasm", ".pck", ".js") and alt.is_file():
                f = open(alt, "rb")
                self.send_response(200)
                self.send_header("Content-Type", self.guess_type(str(path)))
                self.send_header("Content-Encoding", name)
                self.send_header("Content-Length", str(alt.stat().st_size))
                self.end_headers()
                return f
        return super().send_head()

    def log_message(self, fmt, *args):
        pass


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    d = argv[0]
    if "--check" in argv:
        res = check(d)
        emit(res)
        return 0 if res["ok"] else 1
    opt = lambda k, v: argv[argv.index(k) + 1] if k in argv else v  # noqa: E731
    port, host = int(opt("--port", 8060)), opt("--host", "127.0.0.1")
    Handler.isolation = "--no-isolation" not in argv
    srv = http.server.ThreadingHTTPServer((host, port), functools.partial(Handler, directory=os.path.abspath(d)))
    html = next((p.name for p in pathlib.Path(d).glob("*.html") if not p.name.endswith(".offline.html")), "")
    print(json.dumps({"ok": True, "url": f"http://{host}:{port}/{html}", "isolation": Handler.isolation}), flush=True)
    secs = opt("--seconds", None)
    if secs:
        threading.Timer(float(secs), srv.shutdown).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
