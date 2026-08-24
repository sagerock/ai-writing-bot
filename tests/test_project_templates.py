import unittest

from project_templates import (
    PROJECT_KINDS,
    get_project_template,
    initial_project_draft,
    public_project_templates,
    validate_project_charge,
)


class ProjectTemplateTests(unittest.TestCase):
    def test_catalog_has_five_complete_types(self):
        self.assertEqual(
            PROJECT_KINDS,
            ("memo", "research_paper", "article", "blog_post", "general_document"),
        )
        for template in public_project_templates():
            self.assertTrue(template["fields"])
            self.assertTrue(template["brainstorm_actions"])
            self.assertTrue(template["write_actions"])
            self.assertNotIn("write_instruction", template)

    def test_charge_validation_is_type_specific(self):
        charge = validate_project_charge(
            "research_paper",
            {"research_question": "  Why do institutions change?  ", "citation_style": "Chicago"},
        )
        self.assertEqual(charge["research_question"], "Why do institutions change?")
        self.assertEqual(charge["citation_style"], "Chicago")
        self.assertEqual(charge["thesis"], "")
        with self.assertRaisesRegex(ValueError, "Research question is required"):
            validate_project_charge("research_paper", {})
        with self.assertRaisesRegex(ValueError, "Unsupported Research paper field"):
            validate_project_charge("research_paper", {"research_question": "Why?", "jurisdiction": "Ohio"})

    def test_scaffolds_use_the_project_title(self):
        for kind in PROJECT_KINDS:
            draft = initial_project_draft(kind, "  My   Project  ")
            self.assertTrue(draft.startswith("# My Project\n"))
            self.assertGreaterEqual(draft.count("## "), 2)

    def test_unknown_legacy_kind_has_safe_prompt_fallback(self):
        self.assertEqual(get_project_template("future_kind")["id"], "general_document")


if __name__ == "__main__":
    unittest.main()
