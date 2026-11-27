#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ] || [[ ! "$2" =~ ^[A-Za-z0-9_-]{1,64}$ ]]; then
  printf 'Usage: bash fabric_evidence.sh issue BUNDLE_ID EVIDENCE_FILE\n' >&2
  printf '       bash fabric_evidence.sh verify BUNDLE_ID BUNDLE_DIR\n' >&2
  exit 2
fi

action=$1
bundle_id=$2
root=$(cd -- "$(dirname -- "$0")" && pwd)
fabric_dir="$HOME/exam-tools/fabric/fabric-samples/test-network"
public_key="$HOME/.config/exam-project/signing/issuer-public.pem"

case "$action" in
  issue) bundle=$(bash "$root/issue_audit_bundle.sh" "$3") ;;
  verify) bundle=$3 ;;
  *) printf 'Unknown action: %s\n' "$action" >&2; exit 2 ;;
esac

bash "$root/audit_evidence.sh" "$bundle/evidence.json" "$bundle/evidence.sha256" \
  "$bundle/evidence.sig" "$public_key" >&2
fingerprint=$(python3 -B "$root/verify_evidence.py" "$bundle/evidence.json")

anchor=$(
  cd "$fabric_dir"
  export PATH="$PWD/../bin:$PATH"
  export FABRIC_CFG_PATH="$PWD/../config"
  export CORE_PEER_TLS_ENABLED=true
  VERBOSE=false
  set +u
  source scripts/envVar.sh

  if [ "$action" = issue ]; then
    setGlobals 1 >&2
    request=$(jq -cn --arg id "$bundle_id" --arg hash "$fingerprint" \
      '{Args: ["AnchorEvidence", $id, $hash]}')
    timeout 25s peer chaincode invoke \
      -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
      --tls --cafile "$ORDERER_CA" \
      -C carboncredits -n carboncredits \
      --peerAddresses localhost:7051 --tlsRootCertFiles "$PEER0_ORG1_CA" \
      --peerAddresses localhost:9051 --tlsRootCertFiles "$PEER0_ORG2_CA" \
      --waitForEvent -c "$request" >&2 || exit 1
  fi

  setGlobals 2 >&2
  request=$(jq -cn --arg id "$bundle_id" '{Args: ["ReadEvidenceAnchor", $id]}')
  timeout 12s peer chaincode query -C carboncredits -n carboncredits -c "$request"
)

jq -e --arg id "$bundle_id" --arg hash "$fingerprint" '
  select(.bundleId == $id and .evidenceSha256 == $hash
    and .issuerMsp == "Org1MSP" and (.anchorTxId | length > 0))
' <<< "$anchor" >&2

printf 'PASS: signed evidence matches its Fabric anchor\n' >&2
if [ "$action" = issue ]; then
  printf '%s\n' "$bundle"
fi
