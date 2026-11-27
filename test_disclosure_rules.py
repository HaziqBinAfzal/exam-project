import unittest

from screen_disclosure_rules import screen_rules


class DisclosureRulesTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "company": "Demo Manufacturing Group",
            "sec_registrant": True,
            "eu_entity_in_screen": True,
            "average_employees": 1200,
            "net_turnover_eur": 480_000_000,
        }

    def test_eu_screen_triggers_above_both_thresholds(self):
        result = screen_rules(self.profile)
        self.assertEqual(result["eu_csrd"]["screen_status"], "size_screen_triggered")

    def test_eu_screen_does_not_trigger_at_either_exact_threshold(self):
        for field, boundary in (("average_employees", 1000), ("net_turnover_eur", 450_000_000)):
            with self.subTest(field=field):
                result = screen_rules(dict(self.profile, **{field: boundary}))
                self.assertEqual(result["eu_csrd"]["screen_status"], "size_screen_not_triggered")

    def test_sec_registrant_is_sent_for_current_rule_review(self):
        result = screen_rules(self.profile)
        self.assertEqual(
            result["sec_climate_disclosure"]["screen_status"],
            "current_rule_status_requires_review",
        )
