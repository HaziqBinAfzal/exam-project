#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 4 ]; then
  printf 'Usage: bash audit_evidence.sh EVIDENCE HASH SIGNATURE TRUSTED_PUBLIC_KEY\n' >&2
  exit 2
fi

evidence=$1
fingerprint=$2
signature=$3
public_key=$4
script_dir=$(dirname -- "$0")

if ! openssl dgst -sha256 -verify "$public_key" \
  -signature "$signature" "$fingerprint"; then
  printf 'AUDIT REJECTED: fingerprint signature did not verify\n' >&2
  exit 1
fi

if ! python3 -B "$script_dir/verify_evidence.py" "$evidence" \
  --expected "$(cat -- "$fingerprint")"; then
  printf 'AUDIT REJECTED: evidence integrity check failed\n' >&2
  exit 1
fi

printf 'AUDIT CHECK PASSED: signed fingerprint matches the evidence\n'
