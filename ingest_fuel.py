import json
import sys

from scope1_evidence import build_scope1_evidence


def main():
    try:
        reading = json.load(sys.stdin)
        if not isinstance(reading, dict):
            raise ValueError("Fuel reading must be a JSON object")

        fields = ("id", "meter_id", "period_start_utc", "period_end_utc", "fuel", "litres", "source")
        for field in fields:
            if not isinstance(reading.get(field), str) or not reading[field].strip():
                raise ValueError(f"{field} must be a non-empty string")

        factor = {
            "id": "DEMO-DIESEL-001",
            "fuel": "diesel",
            "kg_co2e_per_litre": "2.50",
            "source": "illustrative test fixture",
        }
        evidence = build_scope1_evidence(reading, factor)
    except ValueError as error:
        print(f"Fuel reading rejected: {error}", file=sys.stderr)
        return 1

    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
