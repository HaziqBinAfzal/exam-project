from decimal import Decimal, InvalidOperation


def calculate_scope2(electricity_kwh, factor_kg_co2e_per_kwh):
    try:
        electricity = Decimal(electricity_kwh)
        factor = Decimal(factor_kg_co2e_per_kwh)
    except InvalidOperation as error:
        raise ValueError("Electricity and emissions factor must be numbers") from error

    if not electricity.is_finite() or electricity < 0:
        raise ValueError("Electricity use must be finite and non-negative")

    if not factor.is_finite() or factor < 0:
        raise ValueError("Emissions factor must be finite and non-negative")

    return electricity + factor
