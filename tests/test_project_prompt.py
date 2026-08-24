import unittest
from datetime import date

from project_prompt import (
    build_project_prompt_sections,
    build_project_system_prompt,
    parse_citations,
    segments_from_offsets,
)


PROJECT = {
    "name": "Smith memo",
    "context_mode": "full",
    "charge": {
        "question": "Is Smith's claim timely?",
        "jurisdiction": "Ohio",
        "audience": "Partner",
        "format_notes": "Short answer first",
        "free_text": "Address equitable tolling.",
    },
}
SOURCES = [
    {
        "id": "source-one",
        "source_num": 1,
        "label": "Smith Deposition",
        "filename": "smith.pdf",
        "pages": 20,
        "segments": [
            {"page": 14, "text": "Smith learned of the injury in 2022."},
        ],
    },
    {
        "id": "source-three",
        "source_num": 3,
        "label": "Timeline",
        "filename": "timeline.txt",
        "paragraphs": 9,
        "segments": [{"paragraph": 7, "text": "The complaint was filed in 2025."}],
    },
]


class ProjectPromptTests(unittest.TestCase):
    def test_prompt_order_and_source_markers(self):
        prompt = build_project_system_prompt(
            PROJECT,
            SOURCES,
            "# Existing analysis",
            "write",
            base_system_prompt="BASE",
            profile_context="Prefers concise answers.",
            today=date(2026, 8, 24),
            write_target="Analysis",
        )

        expected_order = [
            "BASE",
            "Today's date is August 24, 2026.",
            "=== PROJECT CHARGE ===",
            "=== CITATION CONTRACT ===",
            "=== PROJECT SOURCES ===",
            "=== [1] Smith Deposition — page 14 ===",
            "=== CURRENT DRAFT ===",
            "=== MODE: WRITE ===",
            "=== USER PROFILE ===",
        ]
        offsets = [prompt.index(value) for value in expected_order]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("[3] Timeline (timeline.txt, 9 paragraphs)", prompt)
        self.assertIn("requested draft target is: Analysis", prompt)

    def test_anthropic_cache_breakpoint_ends_at_stable_sources(self):
        sections = build_project_prompt_sections(
            PROJECT,
            SOURCES,
            "Draft changes frequently",
            "brainstorm",
            base_system_prompt="BASE",
            today=date(2026, 8, 24),
        )

        blocks = sections.anthropic_content()
        self.assertEqual(blocks[1]["cache_control"], {"type": "ephemeral"})
        self.assertIn("PROJECT SOURCES", blocks[1]["text"])
        self.assertIn("CURRENT DRAFT", blocks[2]["text"])

    def test_retrieval_mode_is_disclosed(self):
        project = {**PROJECT, "context_mode": "retrieval"}
        prompt = build_project_system_prompt(
            project,
            SOURCES,
            "",
            "brainstorm",
            base_system_prompt="BASE",
        )
        self.assertIn("most relevant excerpts", prompt)
        sections = build_project_prompt_sections(
            project,
            SOURCES,
            "",
            "brainstorm",
            base_system_prompt="BASE",
        )
        self.assertNotIn("cache_control", sections.anthropic_content()[1])

    def test_research_project_uses_research_brief_and_mode_instructions(self):
        project = {
            "name": "Institutional change",
            "kind": "research_paper",
            "context_mode": "full",
            "charge": {
                "research_question": "Why do institutions change?",
                "thesis": "Change follows legitimacy crises.",
                "citation_style": "Chicago",
            },
        }
        prompt = build_project_system_prompt(
            project,
            SOURCES,
            "# Draft",
            "write",
            base_system_prompt="BASE",
            write_target="Literature Review",
        )
        self.assertIn("=== PROJECT BRIEF ===", prompt)
        self.assertIn("Research question: Why do institutions change?", prompt)
        self.assertIn("Citation style: Chicago", prompt)
        self.assertIn("Act as an academic drafter", prompt)
        self.assertNotIn("legal memorandum", prompt)

    def test_offset_maps_become_prompt_segments(self):
        segments = segments_from_offsets(
            "First page\nSecond paragraph",
            [
                {"page": 1, "start": 0, "end": 10},
                {"paragraph": 2, "start": 11, "end": 27},
            ],
        )
        self.assertEqual(segments[0], {"page": 1, "text": "First page"})
        self.assertEqual(
            segments[1],
            {"paragraph": 2, "text": "Second paragraph"},
        )

    def test_citations_are_parsed_and_unknown_sources_are_ignored(self):
        text = (
            "The injury was known in 2022 [1, p. 14]. Filing followed later "
            "[1, pp. 14–15; 3, ¶ 7]. Unknown [2, p. 4]. Whole source [1]."
        )
        citations = parse_citations(text, SOURCES)

        self.assertEqual([item["source_num"] for item in citations], [1, 1, 3, 1])
        self.assertEqual(citations[0]["page"], 14)
        self.assertEqual(citations[1]["page_end"], 15)
        self.assertEqual(citations[2]["paragraph"], 7)
        self.assertIsNone(citations[3]["page"])
        self.assertEqual(citations[0]["source_id"], "source-one")
        self.assertEqual(citations[1]["span"]["text"], "[1, pp. 14–15; 3, ¶ 7]")


if __name__ == "__main__":
    unittest.main()
