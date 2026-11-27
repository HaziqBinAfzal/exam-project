import json
from decimal import Decimal, InvalidOperation


def build_scope1_evidence(reading, factor):
    if reading["fuel"] != factor["fuel"]:
        raise ValueError("Emissions factor must match the recorded fuel")

    try:
        litres = Decimal(reading["litres"])
        rate = Decimal(factor["kg_co2e_per_litre"])
    except (InvalidOperation, TypeError) as error:
        raise ValueError("Fuel volume and emissions factor must be numbers") from error

    if not litres.is_finite() or litres < 0:
        raise ValueError("Fuel volume must be finite and non-negative")

    if not rate.is_finite() or rate <= 0:
        raise ValueError("Fuel emissions factor must be finite and positive")

    return {
        "schema_version": 1,
        "scope": 1,
        "reading": dict(reading),
        "emissions_factor": dict(factor),
        "result": {"kg_co2e": str(litres * rate)},
    }


if __name__ == "__main__":
    reading = {
        "id": "FUEL-001",
        "meter_id": "GENERATOR-001",
        "fuel": "diesel",
        "period_start_utc": "2026-11-04T00:00:00Z",
        "period_end_utc": "2026-11-05T00:00:00Z",
        "litres": "20",
        "source": "simulated on-site generator fuel log",
    }
    factor = {
        "id": "DEMO-DIESEL-001",
        "fuel": "diesel",
        "kg_co2e_per_litre": "2.50",
        "source": "illustrative test fixture",
    }
    print(json.dumps(build_scope1_evidence(reading, factor), indent=2))
