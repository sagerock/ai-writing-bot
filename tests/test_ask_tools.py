import unittest
from datetime import date
from unittest.mock import patch

import ask_tools


class ToolArgumentNormalizationTests(unittest.TestCase):
    def test_last_thirty_days_overrides_stale_model_dates(self):
        args = ask_tools.normalize_tool_args(
            "get_cfa_accounting_summary",
            {"start_date": "2025-05-18", "end_date": "2025-06-17"},
            latest_user_message="How much money have we made in the last 30 days?",
            today=date(2026, 9, 22),
        )
        self.assertEqual(args, {
            "start_date": "2026-08-24",
            "end_date": "2026-09-22",
        })

    def test_past_days_is_also_supported(self):
        args = ask_tools.normalize_tool_args(
            "get_cfa_accounting_summary",
            {},
            latest_user_message="Show our revenue for the past 7 days.",
            today=date(2026, 9, 22),
        )
        self.assertEqual(args["start_date"], "2026-09-16")
        self.assertEqual(args["end_date"], "2026-09-22")

    def test_explicit_dates_and_other_tools_are_unchanged(self):
        original = {"start_date": "2026-01-01", "end_date": "2026-01-31"}
        self.assertEqual(
            ask_tools.normalize_tool_args(
                "get_cfa_accounting_summary",
                original,
                latest_user_message="Show January 2026.",
                today=date(2026, 9, 22),
            ),
            original,
        )
        self.assertEqual(
            ask_tools.normalize_tool_args(
                "another_tool",
                {"days": 30},
                latest_user_message="last 30 days",
                today=date(2026, 9, 22),
            ),
            {"days": 30},
        )

    def test_reporting_date_uses_configured_timezone(self):
        with patch.dict("os.environ", {"ASK_TOOL_TIMEZONE": "America/New_York"}):
            self.assertIsInstance(ask_tools.reporting_date(), date)


if __name__ == "__main__":
    unittest.main()
