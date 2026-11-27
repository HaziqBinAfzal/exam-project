import argparse
import json
import subprocess
from threading import Lock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve_dashboard(report_path):
    root = Path(__file__).resolve().parent
    page = root / "web" / "index.html"
    latest_report_path = report_path
    generation_lock = Lock()

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self.respond(200, "text/html; charset=utf-8", page.read_bytes())
            elif self.path == "/api/disclosure":
                try:
                    report = json.loads(latest_report_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    self.respond(503, "application/json", b'{"error":"Disclosure unavailable"}')
                    return
                self.respond(200, "application/json", json.dumps(report).encode("utf-8"))
            else:
                self.send_error(404)

        def do_POST(self):
            nonlocal latest_report_path
            if self.path != "/api/disclosure/generate-demo":
                self.send_error(404)
                return

            if (
                self.headers.get("Host") != "127.0.0.1:18088"
                or self.headers.get("Origin") != "http://127.0.0.1:18088"
                or self.headers.get("X-Exam-Action") != "generate-demo"
            ):
                self.respond(403, "application/json", b'{"error":"Request not allowed"}')
                return

            if not generation_lock.acquire(blocking=False):
                self.respond(409, "application/json", b'{"error":"A demo run is already in progress"}')
                return

            try:
                completed = subprocess.run(
                    ["bash", "demo_exam.sh"], cwd=root, stdout=subprocess.PIPE,
                    stderr=None, text=True, timeout=90, check=True,
                )
                outputs = [
                    line.removeprefix("Output: ")
                    for line in completed.stdout.splitlines() if line.startswith("Output: ")
                ]
                if len(outputs) != 1 or "PASS: exam demo completed" not in completed.stdout:
                    raise ValueError("Demo did not report a completed output")
                candidate = Path(outputs[0]) / "disclosure.json"
                report = json.loads(candidate.read_text(encoding="utf-8"))
                latest_report_path = candidate
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                self.log_error("Demo generation failed: %s", error)
                self.respond(
                    503, "application/json",
                    b'{"error":"Demo failed. Check Mosquitto, InfluxDB, Fabric, and the dashboard terminal."}',
                )
                return
            finally:
                generation_lock.release()

            self.respond(200, "application/json", json.dumps(report).encode("utf-8"))

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
