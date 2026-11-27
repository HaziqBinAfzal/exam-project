import json
from decimal import Decimal, InvalidOperation


def nonnegative_number(value):
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError) as error:
        raise ValueError("Expected a numeric value") from error
    if not number.is_finite() or number < 0:
        raise ValueError("Expected a finite, non-negative value")
    return number


def train_freight_model(records):
    activity_squared = Decimal("0")
    activity_times_emissions = Decimal("0")
    for tonne_km, kg_co2e in records:
        activity = nonnegative_number(tonne_km)
        emissions = nonnegative_number(kg_co2e)
        activity_squared += activity * activity
        activity_times_emissions += activity * emissions

    if activity_squared == 0:
        raise ValueError("Training requires at least one positive activity value")

    return activity_times_emissions / activity_squared


def assess_declaration(rate, tonne_km, declared_kg_co2e):
    estimate = nonnegative_number(rate) * nonnegative_number(tonne_km)
    declared = nonnegative_number(declared_kg_co2e)
    difference = abs(declared - estimate)
    review_threshold = max(Decimal("5"), estimate * Decimal("0.20"))

    return {
        "scope": 3,
        "activity": "third-party freight",
        "data_source": "synthetic supplier demo",
        "estimated_kg_co2e": str(estimate.quantize(Decimal("0.01"))),
        "declared_kg_co2e": str(declared),
        "absolute_difference_kg_co2e": str(difference.quantize(Decimal("0.01"))),
        "review_required": difference > review_threshold,
    }


if __name__ == "__main__":
    training = [("100", "11"), ("200", "24"), ("300", "36")]
    rate = train_freight_model(training)

    held_out = assess_declaration(rate, "250", "30")
    unusual = assess_declaration(rate, "500", "25")

    assert held_out["absolute_difference_kg_co2e"] == "0.18"
    assert held_out["review_required"] is False
    assert unusual["review_required"] is True

    print(json.dumps({"held_out_check": held_out, "supplier_review": unusual}, indent=2))
