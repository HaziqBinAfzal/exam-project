import argparse
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from statistics import median

from check_esg_claim import check_claim


def load_verified_evidence(bundle, trusted_key):
    evidence = bundle / "evidence.json"
    verifier = Path(__file__).resolve().with_name("audit_evidence.sh")
    subprocess.run(
        ["bash", verifier, evidence, bundle / "evidence.sha256",
         bundle / "evidence.sig", trusted_key],
        check=True,
        stdout=sys.stderr,
    )
    return json.loads(evidence.read_text(encoding="utf-8"))


def demo_peer_benchmark(baseline, current, calculated_reduction):
    # Fixed synthetic comparison cohort for the two demo periods.
    expected_periods = (
        ("2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z"),
        ("2026-11-02T00:00:00Z", "2026-11-03T00:00:00Z"),
    )
    periods = tuple(
        (record["reading"]["period_start_utc"], record["reading"]["period_end_utc"])
        for record in (baseline, current)
    )
    if periods != expected_periods:
        return {"status": "unavailable", "reason": "No demo cohort for these periods"}

    reductions = [Decimal("4"), Decimal("8"), Decimal("12")]
    peer_median = median(reductions)
    return {
        "source": "synthetic peer cohort",
        "peer_count": len(reductions),
        "median_reduction_pct": f"{peer_median:.2f}",
        "company_minus_peer_median_pp": f"{Decimal(calculated_reduction) - peer_median:.2f}",
    }


def main():
    parser = argparse.ArgumentParser(description="Compare an ESG claim with signed evidence")
    parser.add_argument("claim")
    parser.add_argument("baseline_bundle", type=Path)
    parser.add_argument("current_bundle", type=Path)
    parser.add_argument("trusted_public_key", type=Path)
    args = parser.parse_args()

    try:
        baseline = load_verified_evidence(args.baseline_bundle, args.trusted_public_key)
        current = load_verified_evidence(args.current_bundle, args.trusted_public_key)
        result = check_claim(args.claim, baseline, current)
        result["peer_benchmark"] = demo_peer_benchmark(
            baseline, current, result["calculated_reduction_pct"]
        )
    except (OSError, subprocess.CalledProcessError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Signed claim check rejected: {error}\n")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
