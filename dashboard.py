import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve_dashboard(report_path):
    page = Path(__file__).resolve().parent / "web" / "index.html"

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self.respond(200, "text/html; charset=utf-8", page.read_bytes())
            elif self.path == "/api/disclosure":
                try:
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    self.respond(503, "application/json", b'{"error":"Disclosure unavailable"}')
                    return
                self.respond(200, "application/json", json.dumps(report).encode("utf-8"))
            else:
                self.send_error(404)

        def respond(self, status, content_type, body):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    with ThreadingHTTPServer(("127.0.0.1", 18088), DashboardHandler) as server:
        print("Dashboard: http://127.0.0.1:18088", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="View a generated Topic 175 disclosure")
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    serve_dashboard(args.report.resolve())
