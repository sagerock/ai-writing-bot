import unittest
from unittest import mock

import web_search


class UserQueryFromPromptTests(unittest.TestCase):
    def test_returns_plain_text_unchanged(self):
        self.assertEqual(web_search.user_query_from_prompt("  latest Lexis update "), "latest Lexis update")

    def test_strips_url_context_wrapper(self):
        prompt = "The user's message contains links...\n--- BEGIN PAGE ---\nlots\n--- END PAGE ---\n\nUser message: what changed at https://x.test"
        self.assertEqual(web_search.user_query_from_prompt(prompt), "what changed at https://x.test")

    def test_strips_rag_wrapper(self):
        prompt = "Context:\n[1] doc text\n\nUser question: who signed the lease?"
        self.assertEqual(web_search.user_query_from_prompt(prompt), "who signed the lease?")

    def test_non_string_is_empty(self):
        self.assertEqual(web_search.user_query_from_prompt([{"type": "text"}]), "")


class CleanSearchQueryTests(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(web_search.clean_search_query("a   b\n\nc"), "a b c")

    def test_caps_words_and_chars(self):
        query = " ".join(["word"] * 80)
        cleaned = web_search.clean_search_query(query)
        self.assertEqual(len(cleaned.split(" ")), 50)
        long_word = "x" * 500
        self.assertEqual(len(web_search.clean_search_query(long_word)), 400)


class BraveSearchTests(unittest.TestCase):
    def test_parse_brave_results_normalizes_and_caps(self):
        payload = {"web": {"results": [
            {"title": "A", "url": "https://a", "description": "alpha"},
            {"title": "", "url": "https://blank", "description": ""},
            {"title": "B", "url": "https://b", "description": "beta"},
            {"title": "C", "url": "https://c", "description": "gamma"},
        ]}}
        results = web_search.parse_brave_results(payload, 2)
        self.assertEqual(results, [
            {"title": "A", "href": "https://a", "body": "alpha"},
            {"title": "B", "href": "https://b", "body": "beta"},
        ])

    def test_parse_handles_missing_web_block(self):
        self.assertEqual(web_search.parse_brave_results({}, 5), [])

    def test_web_search_uses_brave_when_key_present(self):
        fake = mock.Mock()
        fake.raise_for_status.return_value = None
        fake.json.return_value = {"web": {"results": [{"title": "T", "url": "u", "description": "d"}]}}
        with mock.patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "k"}), \
             mock.patch.object(web_search.requests, "get", return_value=fake) as get, \
             mock.patch.object(web_search, "ddgs_search") as ddgs:
            results = web_search.web_search("User message: lexis update", 3)
        self.assertEqual(results, [{"title": "T", "href": "u", "body": "d"}])
        ddgs.assert_not_called()
        kwargs = get.call_args.kwargs
        self.assertEqual(kwargs["params"], {"q": "lexis update", "count": 3})
        self.assertEqual(kwargs["headers"]["X-Subscription-Token"], "k")

    def test_web_search_falls_back_to_ddgs_when_brave_fails(self):
        with mock.patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "k"}), \
             mock.patch.object(web_search.requests, "get", side_effect=RuntimeError("boom")), \
             mock.patch.object(web_search, "ddgs_search", return_value=[{"title": "x", "href": "", "body": ""}]) as ddgs:
            results = web_search.web_search("query", 5)
        self.assertEqual(len(results), 1)
        ddgs.assert_called_once_with("query", 5)

    def test_web_search_without_key_uses_ddgs(self):
        with mock.patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": ""}), \
             mock.patch.object(web_search, "ddgs_search", return_value=[]) as ddgs:
            self.assertEqual(web_search.web_search("query", 5), [])
        ddgs.assert_called_once()

    def test_empty_query_short_circuits(self):
        with mock.patch.object(web_search, "ddgs_search") as ddgs:
            self.assertEqual(web_search.web_search("   ", 5), [])
        ddgs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
