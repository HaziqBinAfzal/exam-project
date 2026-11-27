import argparse
import hashlib
import hmac
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

from auditor_portal import BUNDLE_FILES


def serve(grants_file, audit_log):
    config = json.loads(grants_file.read_text(encoding="utf-8"))
    bundles = {key: Path(value) for key, value in config["bundles"].items()}
    grants = [
        (grant["auditor"], grant["token_sha256"],
         datetime.fromisoformat(grant["expires_at"]), frozenset(grant["bundle_ids"]))
        for grant in config["grants"]
    ]
    if any(expiry.tzinfo is None for _, _, expiry, _ in grants):
        raise ValueError("Grant expiries must include a timezone")
    if len({digest for _, digest, _, _ in grants}) != len(grants):
        raise ValueError("Each auditor grant must have its own token")

    log_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parts = self.path.split("/")
            if (
                len(parts) != 4 or parts[1] != "bundles"
                or parts[3] not in BUNDLE_FILES
            ):
                self.send_error(404)
                return
            _, _, bundle_id, filename = parts
            now = datetime.now(timezone.utc)
            scheme, _, token = self.headers.get("Authorization", "").partition(" ")
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            grant = next(
                (entry for entry in grants if hmac.compare_digest(entry[1], digest)), None
            ) if scheme.lower() == "bearer" and token else None

            auditor = grant[0] if grant else None
            content = b""
            if grant is None:
                status, decision = 401, "invalid_token"
            elif now >= grant[2]:
                status, decision = 403, "expired_grant"
            elif bundle_id not in grant[3]:
                status, decision = 403, "bundle_not_granted"
            elif bundle_id not in bundles:
                status, decision = 404, "bundle_unavailable"
            else:
                try:
                    content = (bundles[bundle_id] / filename).read_bytes()
                    status, decision = 200, "download_authorized"
                except OSError:
                    status, decision = 503, "file_unavailable"

            event = {
                "time": now.isoformat(), "auditor": auditor,
                "bundle_id": bundle_id, "file": filename,
                "decision": decision, "status": status,
            }
            try:
                with log_lock, audit_log.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(event) + "\n")
            except OSError:
                self.send_error(503, "Audit log unavailable")
                return

            self.send_response(status)
            self.send_header("Cache-Control", "no-store")
            if status == 401:
                self.send_header("WWW-Authenticate", "Bearer")
            if status == 200:
                self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            if content:
                self.wfile.write(content)

    with ThreadingHTTPServer(("127.0.0.1", 18089), Handler) as server:
        print("Auditor access service listening on http://127.0.0.1:18089", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve signed bundles with scoped auditor grants")
    parser.add_argument("grants", type=Path)
    parser.add_argument("audit_log", type=Path)
    args = parser.parse_args()
    serve(args.grants, args.audit_log)
