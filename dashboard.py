import argparse
import io
import json
import zipfile
import re
import subprocess
from threading import Lock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def serve_dashboard(report_path):
    root = Path(__file__).resolve().parent
    page = root / "web" / "index.html"
    latest_report_path = report_path
    latest_bundle_path = None
    generation_lock = Lock()

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/api/credits/"):
                self.lookup_credit(self.path.removeprefix("/api/credits/"))
            elif self.path == "/api/disclosure/download":
                self.download_disclosure()
            elif self.path == "/":
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

        def lookup_credit(self, credit_id):
            content_type = "application/json"
            if self.headers.get("Host") != "127.0.0.1:18088":
                self.respond(403, content_type, b'{"error":"Request not allowed"}')
                return
            if not re.fullmatch(r"CC-[A-Z0-9-]{1,40}", credit_id):
                self.respond(400, content_type, b'{"error":"Enter a valid credit ID such as CC-001"}')
                return

            network = Path.home() / "exam-tools/fabric/fabric-samples/test-network"
            request = json.dumps({"Args": ["ReadCredit", credit_id]})
            command = r"""
export PATH="$PWD/../bin:$PATH"
export FABRIC_CFG_PATH="$PWD/../config"
export CORE_PEER_TLS_ENABLED=true
VERBOSE=false
source scripts/envVar.sh || exit 1
setGlobals 2 >&2 || exit 1
exec peer chaincode query -C carboncredits -n carboncredits -c "$1"
"""
            try:
                result = subprocess.run(
                    ["bash", "-c", command, "fabric-credit-query", request],
                    cwd=network, capture_output=True, text=True, timeout=12, check=True,
                )
                credit = json.loads(result.stdout)
                if not isinstance(credit, dict) or credit.get("creditId") != credit_id:
                    raise ValueError("Fabric returned an unexpected credit")
            except subprocess.CalledProcessError as error:
                if f"Credit {credit_id} was not found" in error.stderr:
                    self.respond(404, content_type, b'{"error":"Credit not found"}')
                    return
                self.log_error("Fabric query failed: %s", error.stderr.strip())
                self.respond(503, content_type, b'{"error":"Fabric credit lookup is unavailable"}')
                return
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                self.log_error("Fabric query failed: %s", error)
                self.respond(503, content_type, b'{"error":"Fabric credit lookup is unavailable"}')
                return

            self.respond(200, content_type, json.dumps(credit).encode("utf-8"))

        def download_disclosure(self):
            if self.headers.get("Host") != "127.0.0.1:18088":
                self.send_error(403)
                return

            bundle = latest_bundle_path
            if bundle is None:
                self.send_error(404, "Generate a demo disclosure first")
                return

            archive = io.BytesIO()
            try:
                with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
                    for name, source in (
                        ("disclosure.md", "evidence.json"),
                        ("disclosure.sha256", "evidence.sha256"),
                        ("disclosure.sig", "evidence.sig"),
                    ):
                        package.writestr(name, (bundle / source).read_bytes())
            except OSError as error:
                self.log_error("Signed disclosure download failed: %s", error)
                self.send_error(503, "Signed disclosure is unavailable")
                return

            self.respond(
                200, "application/zip", archive.getvalue(),
                download_name="signed-disclosure.zip",
            )

        def do_POST(self):
            nonlocal latest_report_path, latest_bundle_path
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
                bundles = [
                    line.removeprefix("Signed report bundle: ")
                    for line in completed.stdout.splitlines()
                    if line.startswith("Signed report bundle: ")
                ]
                if len(bundles) != 1:
                    raise ValueError("Demo did not report a signed bundle")
                latest_report_path = candidate
                latest_bundle_path = Path(bundles[0])
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

        def respond(self, status, content_type, body, download_name=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if download_name:
                self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
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
