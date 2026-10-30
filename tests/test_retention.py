import unittest
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retention import retention_percentage, schedule_review


class RetentionTests(unittest.TestCase):
    def test_first_successful_review_returns_tomorrow(self):
        result = schedule_review(4, 0, 0, 2.5, date(2026, 8, 5))
        self.assertTrue(result.remembered)
        self.assertEqual(result.repetitions, 1)
        self.assertEqual(result.interval_days, 1)
        self.assertEqual(result.next_review, "2026-08-06")

    def test_second_successful_review_uses_six_days(self):
        result = schedule_review(5, 1, 1, 2.5, date(2026, 8, 5))
        self.assertEqual(result.repetitions, 2)
        self.assertEqual(result.interval_days, 6)
        self.assertEqual(result.next_review, "2026-08-11")

    def test_forgotten_card_resets_repetitions(self):
        result = schedule_review(1, 4, 30, 2.3, date(2026, 8, 5))
        self.assertFalse(result.remembered)
        self.assertEqual(result.repetitions, 0)
        self.assertEqual(result.interval_days, 1)

    def test_ease_factor_never_drops_below_minimum(self):
        result = schedule_review(0, 0, 0, 1.3, date(2026, 8, 5))
        self.assertEqual(result.ease_factor, 1.3)

    def test_retention_percentage(self):
        self.assertEqual(retention_percentage(8, 2), 80)
        self.assertEqual(retention_percentage(0, 0), 0)

    def test_invalid_quality_is_rejected(self):
        with self.assertRaises(ValueError):
            schedule_review(6, 0, 0, 2.5)


if __name__ == "__main__":
    unittest.main()
