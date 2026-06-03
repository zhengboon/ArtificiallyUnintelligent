"""log_sink.py — receives log lines over HTTP and appends to per-tag files.

Run on the DESKTOP. Listens on port 9999. Any POST to /<tag> is appended,
one line per request, to D:/hackerverse/laptop_logs/<tag>.log with a server
timestamp prefix.

Usage:
    python3 log_sink.py                  # default port 9999, default dir
    python3 log_sink.py --port 8888 --dir D:/some/other/dir

The laptop then POSTs lines via wrap.sh (see this dir).
"""

import argparse
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Sink(BaseHTTPRequestHandler):
    log_dir: Path = Path("D:/hackerverse/laptop_logs")

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n).decode("utf-8", "replace")
            tag = self.path.lstrip("/").replace("/", "_") or "default"
            # Sanity: don't write to absolute paths or escape the dir
            tag = "".join(c for c in tag if c.isalnum() or c in ("-", "_", "."))
            tag = tag[:64] or "default"
            ts = datetime.now().isoformat(timespec="seconds")
            out = self.log_dir / f"{tag}.log"
            with out.open("a", encoding="utf-8") as f:
                for line in body.splitlines():
                    f.write(f"{ts}  {line}\n")
            self.send_response(204)
            self.end_headers()
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"{e}".encode())

    def do_GET(self):
        # Health check
        if self.path == "/_health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass  # silence per-request prints; logs go to files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9999)
    ap.add_argument("--dir", type=Path, default=Path("D:/hackerverse/laptop_logs"))
    ap.add_argument("--bind", default="0.0.0.0",
                    help="Interface to bind. 0.0.0.0 = all (incl Tailscale).")
    args = ap.parse_args()

    args.dir.mkdir(parents=True, exist_ok=True)
    Sink.log_dir = args.dir
    srv = ThreadingHTTPServer((args.bind, args.port), Sink)
    print(f"log_sink listening on {args.bind}:{args.port}, writing to {args.dir}/")
    print(f"  health check:  curl http://localhost:{args.port}/_health")
    print(f"  test post:     curl -X POST -d 'hello' http://localhost:{args.port}/test")
    print(f"  -> appends to: {args.dir / 'test.log'}")
    print("Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")


if __name__ == "__main__":
    sys.exit(main())
