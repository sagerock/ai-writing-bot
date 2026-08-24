import unittest

from cost_tracker import (
    calculate_cost,
    calculate_cost_cents,
    get_model_pricing,
    get_models_catalog,
)


class CostTrackerTests(unittest.TestCase):
    def test_catalog_model_ids_are_unique(self):
        ids = [model["id"] for model in get_models_catalog()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_catalog_prices_match_cost_tracker(self):
        for model in get_models_catalog():
            pricing = get_model_pricing(model["id"])
            self.assertEqual(model["input_price"], pricing["input"])
            self.assertEqual(model["output_price"], pricing["output"])

    def test_catalog_contains_only_current_curated_models(self):
        ids = {model["id"] for model in get_models_catalog()}
        self.assertEqual(
            ids,
            {
                "gpt-5.6-sol",
                "gpt-5.6-terra",
                "gpt-5.6-luna",
                "claude-fable-5",
                "claude-opus-5",
                "claude-sonnet-5",
                "claude-haiku-4-5-20251001",
                "gemini-3.7-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-pro-preview",
                "sonar-pro",
            },
        )

    def test_dated_model_uses_prefix_pricing(self):
        self.assertEqual(
            get_model_pricing("gpt-5-mini-2025-08-07"),
            {"input": 0.25, "output": 2.00},
        )

    def test_cost_calculation(self):
        self.assertAlmostEqual(calculate_cost("gpt-5-mini", 1_000_000, 1_000_000), 2.25)
        self.assertEqual(calculate_cost_cents("gpt-5-mini", 1, 1), 1)

    def test_sonar_cost_includes_default_request_fee(self):
        self.assertAlmostEqual(calculate_cost("sonar-pro", 0, 0), 0.006)


if __name__ == "__main__":
    unittest.main()
