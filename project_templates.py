"""Project-type catalog, intake validation, and deterministic draft scaffolds."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PROJECT_TEMPLATES: dict[str, dict[str, Any]] = {
    "memo": {
        "id": "memo",
        "label": "Memo",
        "description": "Analyze a legal question against a source record.",
        "brief_label": "Project charge",
        "primary_field": "question",
        "fields": [
            {"key": "question", "label": "Question presented", "required": True, "multiline": True, "max_length": 5000, "placeholder": "What must the memorandum determine?"},
            {"key": "jurisdiction", "label": "Jurisdiction", "max_length": 500, "placeholder": "Federal, Ohio, Ninth Circuit…"},
            {"key": "audience", "label": "Audience", "max_length": 500, "placeholder": "Supervising attorney, client…"},
            {"key": "format_notes", "label": "Format notes", "max_length": 2000, "placeholder": "Short answer first, 2,000 words, formal tone…"},
            {"key": "free_text", "label": "Additional instructions", "multiline": True, "max_length": 10_000},
        ],
        "scaffold": "# {title}\n\n## Question Presented\n\n## Brief Answer\n\n## Facts\n\n## Discussion\n\n## Conclusion\n",
        "brainstorm_actions": [
            {"label": "Identify issues", "prompt": "Identify the key legal and factual issues raised by the question presented and sources."},
            {"label": "Summarize sources", "prompt": "Summarize each source separately, then explain how the sources relate to one another."},
            {"label": "Outline memo", "prompt": "Create a well-structured outline for the memorandum, including the likely rule and application sections."},
            {"label": "Test the analysis", "prompt": "Give me the strongest counterargument and identify the weakest assumptions in the likely analysis."},
        ],
        "write_actions": [
            {"label": "Draft Facts", "prompt": "Draft the Facts section as polished memorandum prose, using the source record and precise citations."},
            {"label": "Draft Analysis", "prompt": "Draft the Analysis section as polished memorandum prose, addressing both the best argument and counterargument."},
            {"label": "Draft whole memo", "prompt": "Draft the complete memorandum in the requested format, with a clear answer and source-grounded citations."},
            {"label": "Strengthen target", "prompt": "Rewrite the selected target to make it more precise, concise, and persuasive without overstating the sources."},
        ],
        "project_instruction": "You are helping analyze and write a legal memorandum.",
        "brainstorm_instruction": "Act as a legal analyst. Issue-spot, weigh competing arguments, argue both sides, ask useful clarifying questions, and cite every source-grounded factual or legal claim. Do not produce polished memorandum prose unless the user asks for it.",
        "write_instruction": "Act as the memorandum drafter. Produce polished memorandum prose in the requested format, cite every source-grounded factual or legal proposition, and follow the current draft's structure and voice. Frame the response as an edit that can replace the requested target or be applied to the draft.",
    },
    "research_paper": {
        "id": "research_paper",
        "label": "Research paper",
        "description": "Develop a thesis-driven paper grounded in a research record.",
        "brief_label": "Research brief",
        "primary_field": "research_question",
        "fields": [
            {"key": "research_question", "label": "Research question", "required": True, "multiline": True, "max_length": 5000, "placeholder": "What question will the paper investigate?"},
            {"key": "thesis", "label": "Working thesis", "multiline": True, "max_length": 5000, "placeholder": "Optional—the thesis can evolve during research."},
            {"key": "discipline", "label": "Field or discipline", "max_length": 500, "placeholder": "History, sociology, computer science…"},
            {"key": "citation_style", "label": "Citation style", "max_length": 100, "placeholder": "APA, Chicago, MLA…"},
            {"key": "audience", "label": "Audience", "max_length": 500, "placeholder": "Instructor, journal readers, specialists…"},
            {"key": "format_notes", "label": "Length and format", "max_length": 2000, "placeholder": "5,000 words, include an abstract…"},
            {"key": "free_text", "label": "Additional instructions", "multiline": True, "max_length": 10_000},
        ],
        "scaffold": "# {title}\n\n## Abstract\n\n## Introduction\n\n## Research Question\n\n## Background and Literature Review\n\n## Method or Approach\n\n## Analysis\n\n## Conclusion\n\n## References\n",
        "brainstorm_actions": [
            {"label": "Refine question", "prompt": "Refine the research question into a focused, answerable question and identify any necessary subquestions."},
            {"label": "Map the literature", "prompt": "Group the sources into themes, schools of thought, or areas of agreement and disagreement."},
            {"label": "Test the thesis", "prompt": "Stress-test the working thesis against the strongest contrary evidence and alternative explanations."},
            {"label": "Build an outline", "prompt": "Create a thesis-driven paper outline that integrates the source record."},
        ],
        "write_actions": [
            {"label": "Draft introduction", "prompt": "Draft an introduction that establishes the problem, research question, thesis, and roadmap."},
            {"label": "Draft literature review", "prompt": "Draft a synthesized literature review organized by ideas rather than one source at a time."},
            {"label": "Draft analysis", "prompt": "Draft the analysis section, connecting the evidence to the thesis and addressing counterarguments."},
            {"label": "Strengthen target", "prompt": "Revise the selected target for scholarly clarity, structure, and evidentiary support."},
        ],
        "project_instruction": "You are helping research and write a thesis-driven research paper.",
        "brainstorm_instruction": "Act as a rigorous research partner. Clarify the research question, synthesize rather than merely summarize sources, distinguish evidence from inference, test the thesis against alternatives, identify research gaps, and cite every source-grounded claim.",
        "write_instruction": "Act as an academic drafter. Produce clear thesis-driven prose appropriate to the stated discipline, audience, citation style, and format. Synthesize sources, distinguish evidence from interpretation, preserve scholarly caution, and frame the response as an edit that can be applied to the requested draft target.",
    },
    "article": {
        "id": "article",
        "label": "Article",
        "description": "Create a substantial publication-ready article for a defined audience.",
        "brief_label": "Editorial brief",
        "primary_field": "topic",
        "fields": [
            {"key": "topic", "label": "Topic", "required": True, "multiline": True, "max_length": 5000, "placeholder": "What is the article about?"},
            {"key": "angle", "label": "Angle or central argument", "multiline": True, "max_length": 5000, "placeholder": "What should make this treatment distinctive?"},
            {"key": "audience", "label": "Audience", "max_length": 500},
            {"key": "publication", "label": "Publication or venue", "max_length": 500},
            {"key": "target_length", "label": "Target length", "max_length": 200, "placeholder": "1,500 words"},
            {"key": "tone", "label": "Tone", "max_length": 500, "placeholder": "Authoritative, accessible, narrative…"},
            {"key": "free_text", "label": "Additional instructions", "multiline": True, "max_length": 10_000},
        ],
        "scaffold": "# {title}\n\n## Standfirst\n\n## Introduction\n\n## Main Argument\n\n## Implications\n\n## Conclusion\n",
        "brainstorm_actions": [
            {"label": "Find the angle", "prompt": "Propose several distinctive article angles grounded in the sources and explain which is strongest."},
            {"label": "Map the argument", "prompt": "Map the article's central argument, supporting points, counterpoints, and implications."},
            {"label": "Find the lead", "prompt": "Suggest several compelling openings appropriate to the audience and publication."},
            {"label": "Build an outline", "prompt": "Create a publication-ready article outline with a strong narrative and argumentative progression."},
        ],
        "write_actions": [
            {"label": "Draft the lead", "prompt": "Draft a compelling opening that establishes the article's stakes and angle."},
            {"label": "Draft main argument", "prompt": "Draft the main argument with clear transitions and source-grounded support."},
            {"label": "Draft whole article", "prompt": "Draft the complete article for the specified audience, venue, length, and tone."},
            {"label": "Edit for publication", "prompt": "Revise the selected target for clarity, pacing, voice, and publication readiness."},
        ],
        "project_instruction": "You are helping develop and write a substantial publication-ready article.",
        "brainstorm_instruction": "Act as an editorial thought partner. Find a distinctive angle, clarify the central argument and stakes, test it against counterpoints, organize the source record, and cite every source-grounded factual claim. Do not invent reporting or quotations.",
        "write_instruction": "Act as an article writer and editor. Produce engaging, publication-ready prose for the stated audience, venue, length, and tone. Maintain a coherent argument and voice, attribute source-grounded claims precisely, and frame the response as an edit for the requested draft target.",
    },
    "blog_post": {
        "id": "blog_post",
        "label": "Blog post",
        "description": "Write a focused web post with a clear reader takeaway.",
        "brief_label": "Post brief",
        "primary_field": "topic",
        "fields": [
            {"key": "topic", "label": "Topic", "required": True, "multiline": True, "max_length": 5000, "placeholder": "What should the post explain or argue?"},
            {"key": "audience", "label": "Audience", "max_length": 500},
            {"key": "tone", "label": "Tone and voice", "max_length": 500, "placeholder": "Conversational, expert, playful…"},
            {"key": "keywords", "label": "Keywords", "max_length": 1000, "placeholder": "Optional search terms, comma-separated"},
            {"key": "call_to_action", "label": "Call to action", "max_length": 1000},
            {"key": "target_length", "label": "Target length", "max_length": 200, "placeholder": "800 words"},
            {"key": "free_text", "label": "Additional instructions", "multiline": True, "max_length": 10_000},
        ],
        "scaffold": "# {title}\n\n## Introduction\n\n## Key Takeaway\n\n## Main Points\n\n## Conclusion and Next Step\n",
        "brainstorm_actions": [
            {"label": "Clarify takeaway", "prompt": "Define the single most useful takeaway this post should give its reader."},
            {"label": "Generate hooks", "prompt": "Generate several honest, compelling hooks suited to the audience and topic."},
            {"label": "Plan the post", "prompt": "Create a concise blog-post outline with scannable sections and a clear progression."},
            {"label": "Anticipate questions", "prompt": "Identify the reader's likely questions or objections and how the post should address them."},
        ],
        "write_actions": [
            {"label": "Draft opening", "prompt": "Draft a concise opening that earns attention without clickbait."},
            {"label": "Draft main points", "prompt": "Draft the main body in clear, scannable sections with source-grounded support."},
            {"label": "Draft whole post", "prompt": "Draft the complete blog post in the specified voice, length, and structure."},
            {"label": "Tighten for web", "prompt": "Revise the selected target for clarity, brevity, scanability, and a natural voice."},
        ],
        "project_instruction": "You are helping plan and write a focused, useful blog post.",
        "brainstorm_instruction": "Act as a content strategist and thoughtful editor. Clarify the reader, takeaway, honest hook, structure, and necessary evidence. Challenge vague or unsupported claims and cite every factual claim derived from project sources.",
        "write_instruction": "Act as a skilled blog writer. Produce clear, engaging, scannable prose in the requested voice and length, without clickbait or unsupported claims. Use keywords naturally, support factual claims from the project record, and frame the response as an edit for the requested draft target.",
    },
    "general_document": {
        "id": "general_document",
        "label": "General document",
        "description": "Start with a flexible objective and an editable blank structure.",
        "brief_label": "Project brief",
        "primary_field": "objective",
        "fields": [
            {"key": "objective", "label": "Objective", "required": True, "multiline": True, "max_length": 5000, "placeholder": "What should this document accomplish?"},
            {"key": "audience", "label": "Audience", "max_length": 500},
            {"key": "format_notes", "label": "Format and length", "max_length": 2000},
            {"key": "tone", "label": "Tone and voice", "max_length": 500},
            {"key": "free_text", "label": "Additional instructions", "multiline": True, "max_length": 10_000},
        ],
        "scaffold": "# {title}\n\n## Purpose\n\n## Main Content\n\n## Conclusion\n",
        "brainstorm_actions": [
            {"label": "Clarify objective", "prompt": "Clarify the document's objective, audience, constraints, and definition of success."},
            {"label": "Organize sources", "prompt": "Summarize and organize the source record around the document's objective."},
            {"label": "Build an outline", "prompt": "Create a practical document outline based on the objective and available sources."},
            {"label": "Find gaps", "prompt": "Identify missing information, weak assumptions, and questions that should be resolved before drafting."},
        ],
        "write_actions": [
            {"label": "Draft opening", "prompt": "Draft an opening appropriate to the document's objective and audience."},
            {"label": "Draft target", "prompt": "Draft the selected target using the project brief, sources, and existing document voice."},
            {"label": "Draft whole document", "prompt": "Draft the complete document in the requested format, length, and tone."},
            {"label": "Revise target", "prompt": "Revise the selected target for clarity, structure, accuracy, and audience fit."},
        ],
        "project_instruction": "You are helping plan and write a source-grounded document.",
        "brainstorm_instruction": "Act as a rigorous thought partner. Clarify the objective, audience, constraints, structure, evidence, and open questions. Challenge unsupported assumptions and cite every factual claim derived from project sources.",
        "write_instruction": "Act as a careful writer and editor. Produce clear prose suited to the stated objective, audience, format, and voice. Ground factual claims in the project record and frame the response as an edit for the requested draft target.",
    },
}

PROJECT_KINDS = tuple(PROJECT_TEMPLATES)


def get_project_template(kind: str) -> dict[str, Any]:
    """Return a template, treating unknown legacy kinds as general documents."""
    return PROJECT_TEMPLATES.get(kind) or PROJECT_TEMPLATES["general_document"]


def public_project_templates() -> list[dict[str, Any]]:
    private_keys = {"project_instruction", "brainstorm_instruction", "write_instruction"}
    return [
        {key: deepcopy(value) for key, value in template.items() if key not in private_keys}
        for template in PROJECT_TEMPLATES.values()
    ]


def validate_project_charge(kind: str, charge: dict[str, Any]) -> dict[str, str]:
    if kind not in PROJECT_TEMPLATES:
        raise ValueError(f"Unsupported project kind: {kind}")
    template = PROJECT_TEMPLATES[kind]
    fields = {field["key"]: field for field in template["fields"]}
    unknown = set(charge) - set(fields)
    if unknown:
        raise ValueError(f"Unsupported {template['label']} field: {sorted(unknown)[0]}")
    cleaned: dict[str, str] = {}
    for key, field in fields.items():
        value = str(charge.get(key) or "").strip()
        if field.get("required") and not value:
            raise ValueError(f"{field['label']} is required.")
        if len(value) > int(field.get("max_length", 10_000)):
            raise ValueError(f"{field['label']} is too long.")
        cleaned[key] = value
    return cleaned


def initial_project_draft(kind: str, title: str) -> str:
    safe_title = " ".join(str(title).split()) or get_project_template(kind)["label"]
    return str(get_project_template(kind)["scaffold"]).format(title=safe_title)
