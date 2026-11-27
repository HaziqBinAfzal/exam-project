#!/usr/bin/env bash
set -euo pipefail
umask 077

if [ "$#" -ne 1 ]; then
  printf 'Usage: bash issue_audit_bundle.sh EVIDENCE_JSON\n' >&2
  exit 2
fi

script_dir=$(dirname -- "$0")
private_key="$HOME/.config/exam-project/signing/issuer-private.pem"
bundle_dir=$(mktemp -d "${TMPDIR:-/tmp}/exam-audit.XXXXXXXX")

cp -- "$1" "$bundle_dir/evidence.json"
python3 -B "$script_dir/verify_evidence.py" "$bundle_dir/evidence.json" \
  > "$bundle_dir/evidence.sha256"
openssl dgst -sha256 -sign "$private_key" \
  -out "$bundle_dir/evidence.sig" "$bundle_dir/evidence.sha256"

printf '%s\n' "$bundle_dir"
