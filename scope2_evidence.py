import json

from scope2 import calculate_scope2


def build_scope2_evidence(reading, factor):
    emissions = calculate_scope2(reading["kwh"], factor["kg_co2e_per_kwh"])
    return {
        "schema_version": 1,
        "scope": 2,
        "reading": dict(reading),
        "emissions_factor": dict(factor),
        "result": {"kg_co2e": str(emissions)},
    }


if __name__ == "__main__":
    reading = {
        "id": "READING-001",
        "meter_id": "METER-001",
        "period_start_utc": "2026-11-01T00:00:00Z",
        "period_end_utc": "2026-11-02T00:00:00Z",
        "kwh": "100",
        "source": "simulated meter",
    }
    factor = {
        "id": "DEMO-ELECTRICITY-001",
        "kg_co2e_per_kwh": "0.40",
        "source": "illustrative test fixture",
    }
    print(json.dumps(build_scope2_evidence(reading, factor), indent=2))
