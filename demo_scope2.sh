#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

demo_dir=$(mktemp -d)
topic='exam-project/meters/electricity'
evidence="$demo_dir/evidence.json"
edited="$demo_dir/evidence-edited.json"

mosquitto_pub -h 127.0.0.1 -p 18883 -t "$topic" -q 1 -r \
  -m '{"id":"READING-DEMO","meter_id":"METER-001","period_start_utc":"2026-11-04T00:00:00Z","period_end_utc":"2026-11-05T00:00:00Z","kwh":"125","source":"simulated meter"}'

mosquitto_sub -h 127.0.0.1 -p 18883 -t "$topic" -q 1 -C 1 -W 5 |
  python3 -B ingest_electricity.py |
  python3 -B store_electricity.py > "$evidence"

cat "$evidence"
expected_hash=$(python3 -B verify_evidence.py "$evidence")
printf '%s\n' "$expected_hash" > "$demo_dir/evidence.sha256"
python3 -B verify_evidence.py "$evidence" --expected "$expected_hash"

sed 's/"kwh": "125"/"kwh": "150"/' "$evidence" > "$edited"
status=0
python3 -B verify_evidence.py "$edited" --expected "$expected_hash" || status=$?

if [ "$status" -ne 1 ]; then
  printf 'FAIL: expected the edited evidence to return exit code 1, got %s\n' "$status" >&2
  exit 1
fi

printf 'PASS: edited evidence was rejected\nFiles: %s\n' "$demo_dir"
