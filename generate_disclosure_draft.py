import argparse
import json
import subprocess
from pathlib import Path

from check_esg_claim import reporting_period
from check_signed_claim import load_verified_evidence
from scope3_freight import nonnegative_number


def build_draft(fuel, electricity):
    if fuel["scope"] != 1 or electricity["scope"] != 2:
        raise ValueError("Expected Scope 1 fuel and Scope 2 electricity evidence")

    start, end = reporting_period(fuel)
    if (start, end) != reporting_period(electricity):
        raise ValueError("Both records must cover the same reporting period")

    totals = {}
    references = []
    open_reviews = []
    for record in (fuel, electricity):
        scope = record["scope"]
        reading_id = record["reading"]["id"]
        totals[scope] = nonnegative_number(record["result"]["kg_co2e"])
        anomaly = record.get("anomaly_check", {})
        references.append({
            "scope": scope,
            "reading_id": reading_id,
            "factor_id": record["emissions_factor"]["id"],
        })
        if anomaly.get("review_required") is not False:
            open_reviews.append({
                "scope": scope,
                "reading_id": reading_id,
                "reason": anomaly.get("status", "anomaly_check_missing"),
            })

    return {
        "report_type": "simulated emissions disclosure draft",
        "status": "provisional" if open_reviews else "ready_for_review",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "scope_1_kg_co2e": str(totals[1]),
        "scope_2_kg_co2e": str(totals[2]),
        "combined_scope_1_and_2_kg_co2e": str(totals[1] + totals[2]),
        "evidence_references": references,
        "open_reviews": open_reviews,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a draft from signed meter evidence")
    parser.add_argument("fuel_bundle", type=Path)
    parser.add_argument("electricity_bundle", type=Path)
    parser.add_argument("trusted_public_key", type=Path)
    args = parser.parse_args()

    try:
        fuel = load_verified_evidence(args.fuel_bundle, args.trusted_public_key)
        electricity = load_verified_evidence(args.electricity_bundle, args.trusted_public_key)
        print(json.dumps(build_draft(fuel, electricity), indent=2))
    except (OSError, subprocess.CalledProcessError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Disclosure draft rejected: {error}\n")
