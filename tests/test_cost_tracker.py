import unittest

from cost_tracker import (
    MODEL_ID_ALIASES,
    calculate_cost,
    calculate_cost_cents,
    get_model_pricing,
    get_models_catalog,
    normalize_model_id,
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
            {"claude-sonnet-5", "claude-opus-5-5", "gpt-6-luna"},
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

    def test_retired_model_ids_map_to_current_replacements(self):
        self.assertEqual(normalize_model_id("gemini-3-pro-preview"), "claude-opus-5-5")
        self.assertEqual(normalize_model_id("gemini-3.5-flash-lite"), "gpt-6-luna")
        self.assertEqual(normalize_model_id("gpt-5.5"), "claude-sonnet-5")
        self.assertEqual(normalize_model_id("gpt-6-sol"), "claude-sonnet-5")
        self.assertEqual(normalize_model_id("gpt-5.6-luna"), "gpt-6-luna")
        self.assertEqual(normalize_model_id("claude-opus-5"), "claude-opus-5-5")
        self.assertEqual(normalize_model_id("claude-fable-5-1"), "claude-opus-5-5")
        self.assertEqual(normalize_model_id("claude-haiku-4-5-20251001"), "gpt-6-luna")
        self.assertEqual(normalize_model_id("sonar-pro"), "claude-sonnet-5")
        self.assertEqual(normalize_model_id("claude-sonnet-5"), "claude-sonnet-5")

    def test_every_alias_targets_a_catalog_model(self):
        ids = {model["id"] for model in get_models_catalog()}
        for alias, target in MODEL_ID_ALIASES.items():
            with self.subTest(alias=alias):
                self.assertIn(target, ids)


if __name__ == "__main__":
    unittest.main()
