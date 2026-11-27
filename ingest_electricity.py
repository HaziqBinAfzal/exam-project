import json
import sys

from scope2_evidence import build_scope2_evidence


def main():
    try:
        reading = json.load(sys.stdin)
        if not isinstance(reading, dict):
            raise ValueError("Meter reading must be a JSON object")

        for field in ("id", "meter_id", "period_start_utc", "period_end_utc", "kwh", "source"):
            if not isinstance(reading.get(field), str) or not reading[field].strip():
                raise ValueError(f"{field} must be a non-empty string")

        factor = {
            "id": "DEMO-ELECTRICITY-001",
            "kg_co2e_per_kwh": "0.40",
            "source": "illustrative test fixture",
        }
        evidence = build_scope2_evidence(reading, factor)
    except ValueError as error:
        print(f"Reading rejected: {error}", file=sys.stderr)
        return 1

    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
