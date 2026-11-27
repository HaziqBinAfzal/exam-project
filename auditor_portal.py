import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BUNDLE_FILES = ("evidence.json", "evidence.sha256", "evidence.sig")


def serve_bundle(bundle, token):
    files = {f"/bundle/{name}": (bundle / name).read_bytes() for name in BUNDLE_FILES}
    expected_header = f"Bearer {token}".encode("utf-8")

    class AuditorHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            supplied_header = self.headers.get("Authorization", "").encode("utf-8")
            if not hmac.compare_digest(supplied_header, expected_header):
                self.send_response(401)
                self.send_header("WWW-Authenticate", "Bearer")
                self.end_headers()
                return

            content = files.get(self.path)
            if content is None:
                self.send_error(404)
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

    with ThreadingHTTPServer(("127.0.0.1", 18087), AuditorHandler) as server:
        print("Auditor service listening on http://127.0.0.1:18087", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve one approved local audit bundle")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    token_path = Path.home() / ".config/exam-project/auditor-token"

    try:
        token = token_path.read_text(encoding="utf-8").strip()
        if not token:
            raise ValueError("Auditor token file is empty")
        serve_bundle(args.bundle, token)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Auditor service failed: {error}\n")
