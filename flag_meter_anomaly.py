import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from statistics import median

from scope3_freight import nonnegative_number


def flag_meter_anomaly(evidence, history):
    scope = evidence["scope"]
    field, unit = {1: ("litres", "L"), 2: ("kwh", "kWh")}[scope]
    reading = evidence["reading"]
    observed = nonnegative_number(reading[field])
    baseline = history["meters"].get(reading["meter_id"])

    if baseline is None or baseline["scope"] != scope or baseline["unit"] != unit:
        return {"status": "insufficient_history", "review_required": True}

    values = [nonnegative_number(value) for value in baseline["values"]]
    if len(values) < 3 or median(values) == 0:
        return {"status": "insufficient_history", "review_required": True}

    typical = median(values)
    deviation = (observed - typical) / typical * 100
    flagged = abs(deviation) > Decimal("50")
    return {
        "status": "flagged" if flagged else "within_range",
        "review_required": flagged,
        "observed": str(observed),
        "median": str(typical),
        "unit": unit,
        "deviation_pct": f"{deviation:.2f}",
        "threshold_pct": "50",
        "history_count": len(values),
        "history_source": history["source"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a meter anomaly check to emissions evidence")
    parser.add_argument("history", type=Path)
    args = parser.parse_args()

    try:
        evidence = json.load(sys.stdin)
        history = json.loads(args.history.read_text(encoding="utf-8"))
        evidence["anomaly_check"] = flag_meter_anomaly(evidence, history)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Anomaly check failed: {error}\n")

    print(json.dumps(evidence, indent=2))
