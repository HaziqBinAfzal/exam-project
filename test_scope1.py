import unittest
from decimal import Decimal

from scope1_evidence import build_scope1_evidence


class Scope1Tests(unittest.TestCase):
    def setUp(self):
        self.reading = {"fuel": "diesel", "litres": "20"}
        self.factor = {"fuel": "diesel", "kg_co2e_per_litre": "2.50"}

    def test_calculates_direct_emissions(self):
        evidence = build_scope1_evidence(self.reading, self.factor)
        self.assertEqual(evidence["scope"], 1)
        self.assertEqual(Decimal(evidence["result"]["kg_co2e"]), Decimal("50.00"))

    def test_rejects_negative_fuel_volume(self):
        with self.assertRaises(ValueError):
            build_scope1_evidence(dict(self.reading, litres="-1"), self.factor)

    def test_rejects_factor_for_other_fuel(self):
        with self.assertRaises(ValueError):
            build_scope1_evidence(self.reading, dict(self.factor, fuel="petrol"))
