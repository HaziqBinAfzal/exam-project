import argparse
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from scope3_freight import nonnegative_number


def reporting_period(evidence):
    reading = evidence["reading"]
    start = datetime.fromisoformat(reading["period_start_utc"])
    end = datetime.fromisoformat(reading["period_end_utc"])
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise ValueError("Evidence needs a valid reporting period with timezones")
    return start, end


def check_claim(claim, baseline, current):
    match = re.fullmatch(
        r"We reduced Scope 2 emissions by ([0-9]+(?:\.[0-9]+)?)%\.",
        claim.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError('Supported claim format: "We reduced Scope 2 emissions by 20%."')
    claimed = Decimal(match.group(1))
    if claimed > 100:
        raise ValueError("A reduction claim cannot exceed 100%")

    if baseline["scope"] != 2 or current["scope"] != 2:
        raise ValueError("Both records must contain Scope 2 evidence")
    if baseline["reading"]["meter_id"] != current["reading"]["meter_id"]:
        raise ValueError("Both demo records must cover the same meter")

    baseline_start, baseline_end = reporting_period(baseline)
    current_start, current_end = reporting_period(current)
    if baseline_end > current_start or baseline_end - baseline_start != current_end - current_start:
        raise ValueError("Compare non-overlapping periods of equal length")

    previous = nonnegative_number(baseline["result"]["kg_co2e"])
    latest = nonnegative_number(current["result"]["kg_co2e"])
    if previous == 0:
        raise ValueError("A percentage reduction needs a positive baseline")

    calculated = (previous - latest) / previous * 100
    difference = abs(claimed - calculated)
    return {
        "claim": claim,
        "scope": 2,
        "baseline_reading_id": baseline["reading"]["id"],
        "current_reading_id": current["reading"]["id"],
        "baseline_kg_co2e": str(previous),
        "current_kg_co2e": str(latest),
        "claimed_reduction_pct": str(claimed),
        "calculated_reduction_pct": f"{calculated:.2f}",
        "difference_percentage_points": f"{difference:.2f}",
        "review_required": difference > Decimal("0.5"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check a Scope 2 reduction claim")
    parser.add_argument("claim")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    args = parser.parse_args()

    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        current = json.loads(args.current.read_text(encoding="utf-8"))
        print(json.dumps(check_claim(args.claim, baseline, current), indent=2))
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Claim check rejected: {error}\n")
