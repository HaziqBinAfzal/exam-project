import unittest
from decimal import Decimal

from scope2 import calculate_scope2


class Scope2Tests(unittest.TestCase):
    def test_calculates_emissions(self):
        self.assertEqual(calculate_scope2("100", "0.40"), Decimal("40.00"))

    def test_accepts_zero_usage(self):
        self.assertEqual(calculate_scope2("0", "0.40"), Decimal("0.00"))

    def test_rejects_invalid_inputs(self):
        for invalid in ("-1", "unknown", "NaN", "Infinity"):
            with self.subTest(value=invalid, field="electricity"):
                with self.assertRaises(ValueError):
                    calculate_scope2(invalid, "0.40")
            with self.subTest(value=invalid, field="factor"):
                with self.assertRaises(ValueError):
                    calculate_scope2("100", invalid)
