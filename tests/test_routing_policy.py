import asyncio
import unittest
from unittest.mock import patch

import main
from routing_policy import is_internal_client_data_query


class InternalClientDataPolicyTests(unittest.TestCase):
    def test_center_finance_question_is_internal(self):
        self.assertTrue(is_internal_client_data_query(
            "Can you tell me how much money we've made in the last 30 days?",
            has_client_context=True,
        ))

    def test_internal_system_and_enrollment_questions_are_internal(self):
        for message in (
            "What does QuickBooks show for this month?",
            "How many of our students are enrolled this term?",
            "Summarize the Center's current registrations.",
        ):
            with self.subTest(message=message):
                self.assertTrue(is_internal_client_data_query(
                    message, has_client_context=True,
                ))

    def test_public_or_context_free_questions_are_not_internal(self):
        self.assertFalse(is_internal_client_data_query(
            "What is Apple's current revenue?", has_client_context=True,
        ))
        self.assertFalse(is_internal_client_data_query(
            "How much money have we made?", has_client_context=False,
        ))

    def test_internal_route_bypasses_llm_classifier_and_web_model(self):
        with patch.object(main, "AsyncOpenAI") as router:
            model, category = asyncio.run(main.route_to_best_model(
                "How much money have we made in the last 30 days?",
                has_client_context=True,
            ))
        router.assert_not_called()
        self.assertEqual(category, "internal_data")
        self.assertEqual(model, main.ROUTING_MODELS["internal_data"])

    def test_generic_how_much_no_longer_forces_web_search(self):
        self.assertFalse(main._needs_web_search(
            "How much money have we made in the last 30 days?"
        ))
        self.assertTrue(main._needs_web_search("What is the stock price today?"))


if __name__ == "__main__":
    unittest.main()
