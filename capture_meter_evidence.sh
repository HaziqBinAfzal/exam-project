#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

case "${1:-}" in
  electricity) ingest_script=ingest_electricity.py ;;
  fuel) ingest_script=ingest_fuel.py ;;
  *)
    printf 'Usage: bash capture_meter_evidence.sh electricity|fuel\n' >&2
    exit 2
    ;;
esac

evidence=$(mktemp)
trap 'rm -f -- "$evidence"' EXIT

mosquitto_sub -h 127.0.0.1 -p 18883 \
  -t "exam-project/meters/$1" -q 1 -C 1 -W 5 |
  python3 -B "$ingest_script" |
  python3 -B flag_meter_anomaly.py fixtures/meter_history_demo.json |
  python3 -B store_electricity.py > "$evidence"

bash issue_audit_bundle.sh "$evidence"
