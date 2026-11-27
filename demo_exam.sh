#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

output_dir=$(mktemp -d)
public_key="$HOME/.config/exam-project/signing/issuer-public.pem"
fabric_dir="$HOME/exam-tools/fabric/fabric-samples/test-network"

publish_reading() {
  mosquitto_pub -h 127.0.0.1 -p 18883 \
    -t "exam-project/meters/$1" -q 1 -r -m "$2"
}

printf '\n1. Capture signed fuel and electricity evidence\n'
publish_reading fuel \
  '{"id":"EXAM-FUEL","meter_id":"GENERATOR-001","period_start_utc":"2026-11-05T00:00:00Z","period_end_utc":"2026-11-06T00:00:00Z","fuel":"diesel","litres":"20","source":"simulated generator meter"}'
fuel_bundle=$(bash capture_meter_evidence.sh fuel)

publish_reading electricity \
  '{"id":"EXAM-SPIKE","meter_id":"METER-001","period_start_utc":"2026-11-05T00:00:00Z","period_end_utc":"2026-11-06T00:00:00Z","kwh":"300","source":"simulated meter"}'
electricity_bundle=$(bash capture_meter_evidence.sh electricity)

printf '\n2. Check an ESG claim against two signed periods\n'
python3 -B scope2_evidence.py > "$output_dir/claim-baseline.json"
printf '%s\n' \
  '{"id":"CLAIM-CURRENT","meter_id":"METER-001","period_start_utc":"2026-11-02T00:00:00Z","period_end_utc":"2026-11-03T00:00:00Z","kwh":"125","source":"simulated meter"}' |
  python3 -B ingest_electricity.py > "$output_dir/claim-current.json"

baseline_bundle=$(bash issue_audit_bundle.sh "$output_dir/claim-baseline.json")
current_bundle=$(bash issue_audit_bundle.sh "$output_dir/claim-current.json")

python3 -B check_signed_claim.py 'We reduced Scope 2 emissions by 20%.' \
  "$baseline_bundle" "$current_bundle" "$public_key" > "$output_dir/claim-check.json"
jq -e 'select(.review_required == true and .difference_percentage_points == "45.00")
       | {claim, calculated_reduction_pct, difference_percentage_points, peer_benchmark}' \
  "$output_dir/claim-check.json"

printf '\n3. Read the retired credit from Fabric\n'
(
  cd "$fabric_dir"
  export PATH="$PWD/../bin:$PATH"
  export FABRIC_CFG_PATH="$PWD/../config"
  export CORE_PEER_TLS_ENABLED=true
  VERBOSE=false
  set +u
  source scripts/envVar.sh
  setGlobals 2 >&2
  peer chaincode query -C carboncredits -n carboncredits \
    -c '{"Args":["ReadCredit","CC-001"]}'
) > "$output_dir/retired-credit.json"

jq -e 'select(.status == "RETIRED") | {creditId, ownerMsp, status, retirementTxId}' \
  "$output_dir/retired-credit.json"

printf '\n4. Generate, screen, sign, and verify the disclosure\n'
python3 -B generate_disclosure_draft.py \
  "$fuel_bundle" "$electricity_bundle" "$public_key" \
  --freight-csv fixtures/supplier_freight_demo.csv \
  --retired-credit "$output_dir/retired-credit.json" > "$output_dir/draft.json"

python3 -B screen_disclosure_rules.py "$output_dir/draft.json" \
  fixtures/disclosure_company_demo.json > "$output_dir/disclosure.json"

jq -e 'select(.status == "provisional"
       and .combined_scope_1_and_2_kg_co2e == "170.00"
       and any(.open_reviews[]; .reading_id == "EXAM-SPIKE"))
       | {status, combined_scope_1_and_2_kg_co2e, open_reviews}' \
  "$output_dir/disclosure.json"

python3 -B render_disclosure.py "$output_dir/disclosure.json" > "$output_dir/disclosure.md"
report_bundle=$(bash issue_audit_bundle.sh "$output_dir/disclosure.md")
bash audit_evidence.sh "$output_dir/disclosure.md" "$report_bundle/evidence.sha256" \
  "$report_bundle/evidence.sig" "$public_key"

printf '\nPASS: exam demo completed\nOutput: %s\nSigned report bundle: %s\n' \
  "$output_dir" "$report_bundle"
