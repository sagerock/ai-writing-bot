"""Stream one short prompt through every catalog model.

Usage (needs provider API keys in the environment, e.g. via `railway run`):
    python scripts/smoke_test_models.py [model_id ...]
    python scripts/smoke_test_models.py --project PROJECT_ID [model_id ...]
"""
import argparse
import asyncio
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cost_tracker import get_models_catalog  # noqa: E402
from llm_content import stream_chunk_text  # noqa: E402
from main import (  # noqa: E402
    AsyncOpenAI,
    BASE_SYSTEM_PROMPT,
    ProjectStore,
    bucket,
    db,
    get_llm,
    get_rag_service,
    is_gpt5_model,
)
from project_context import ProjectContext, load_project_context  # noqa: E402
from project_prompt import build_project_prompt_sections, parse_citations  # noqa: E402

PROMPT = [{"role": "user", "content": "Reply with exactly the word OK."}]


async def check(model_id: str, project_fixture=None):
    start = time.time()
    try:
        if project_fixture:
            text = await _check_project(model_id, project_fixture)
            citations = parse_citations(text, project_fixture["context"].sources)
            if not citations:
                raise ValueError(f"No valid project citation in response: {text[:200]!r}")
            detail = (
                f"{time.time()-start:.1f}s  {len(citations)} citation(s)  "
                f"{text.strip()[:60]!r}"
            )
        else:
            llm = get_llm(model_id)
            text = ""
            async for chunk in _iter(llm):
                text += stream_chunk_text(chunk.content)
            detail = f"{time.time()-start:.1f}s  {text.strip()[:60]!r}"
        return model_id, True, detail
    except Exception as e:  # noqa: BLE001
        return model_id, False, f"{type(e).__name__}: {str(e)[:200]}"


async def _iter(llm):
    async for chunk in llm.astream(PROMPT):
        yield chunk


def _find_project_owner(project_id: str) -> str:
    configured_user = os.getenv("SMOKE_TEST_USER_ID")
    if configured_user:
        snapshot = (
            db.collection("users")
            .document(configured_user)
            .collection("projects")
            .document(project_id)
            .get()
        )
        if snapshot.exists:
            return configured_user
        raise ValueError("Project was not found for SMOKE_TEST_USER_ID.")

    matches = []
    for user in db.collection("users").stream():
        project = user.reference.collection("projects").document(project_id).get()
        if project.exists:
            matches.append(user.id)
    if len(matches) != 1:
        raise ValueError(
            "Project ID must match exactly one user, or set SMOKE_TEST_USER_ID."
        )
    return matches[0]


def _load_project_fixture(project_id: str):
    question = (
        "Answer the project's question presented in one sentence using the supplied "
        "sources, and cite the exact page or paragraph using the required citation format."
    )
    if project_id == "fixture":
        context = ProjectContext(
            project={
                "id": "fixture",
                "name": "Model smoke-test memo",
                "kind": "memo",
                "context_mode": "full",
                "charge": {
                    "question": "Was the complaint filed after the demand letter?",
                    "jurisdiction": "Ohio",
                    "audience": "Testing",
                    "format_notes": "One sentence",
                    "free_text": "",
                },
                "draft": {"markdown": ""},
            },
            sources=[
                {
                    "id": "fixture-pdf",
                    "source_num": 1,
                    "label": "Demand Letter",
                    "filename": "demand_letter.pdf",
                    "pages": 2,
                    "segments": [
                        {"page": 2, "text": "The demand letter was sent on March 1, 2025."}
                    ],
                },
                {
                    "id": "fixture-timeline",
                    "source_num": 2,
                    "label": "Case Timeline",
                    "filename": "timeline.txt",
                    "paragraphs": 3,
                    "segments": [
                        {"paragraph": 3, "text": "The complaint was filed on April 15, 2025."}
                    ],
                },
                {
                    "id": "fixture-notes",
                    "source_num": 3,
                    "label": "Intake Notes",
                    "filename": "intake.md",
                    "paragraphs": 2,
                    "segments": [
                        {"paragraph": 2, "text": "The client confirmed both dates."}
                    ],
                },
            ],
            draft="",
        )
        user_id = "model-smoke-fixture"
    else:
        user_id = _find_project_owner(project_id)
        store = ProjectStore(db)
        project = store.get_project_record(user_id, project_id)
        rag = get_rag_service() if project.get("context_mode") == "retrieval" else None
        context = load_project_context(
            store=store,
            bucket=bucket,
            rag=rag,
            user_id=user_id,
            project_id=project_id,
            history=[{"role": "user", "content": question}],
        )
    if len(context.sources) < 3 or not any(
        source.get("filename", "").lower().endswith(".pdf")
        for source in context.sources
    ):
        raise ValueError("Fixture project must have at least three ready sources and one PDF.")
    sections = build_project_prompt_sections(
        context.project,
        context.sources,
        context.draft,
        "brainstorm",
        base_system_prompt=BASE_SYSTEM_PROMPT,
    )
    return {
        "user_id": user_id,
        "question": question,
        "context": context,
        "sections": sections,
    }


async def _check_project(model_id: str, fixture) -> str:
    sections = fixture["sections"]
    question = fixture["question"]
    if is_gpt5_model(model_id):
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.responses.create(
            model=model_id,
            input=[
                {"role": "system", "content": sections.text},
                {"role": "user", "content": question},
            ],
            max_output_tokens=500,
            safety_identifier=hashlib.sha256(
                f"romalume-smoke:{fixture['user_id']}".encode()
            ).hexdigest(),
            store=False,
            stream=True,
        )
        text = ""
        async for event in response:
            if event.type == "response.output_text.delta" and event.delta:
                text += event.delta
        return text

    llm = get_llm(model_id)
    system_content = (
        sections.anthropic_content()
        if model_id.startswith("claude-")
        else sections.text
    )
    text = ""
    last_metadata = {}
    async for chunk in llm.astream(
        [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question},
        ]
    ):
        text += stream_chunk_text(chunk.content)
        last_metadata = getattr(chunk, "response_metadata", {}) or last_metadata
    if not text:
        raise ValueError(f"Empty model response; final metadata: {last_metadata}")
    return text


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model_ids", nargs="*")
    parser.add_argument("--project", help="Fixture project ID for citation smoke tests")
    args = parser.parse_args()
    ids = args.model_ids or [m["id"] for m in get_models_catalog()]
    project_fixture = _load_project_fixture(args.project) if args.project else None
    results = await asyncio.gather(
        *(
            asyncio.wait_for(check(model_id, project_fixture), 180)
            for model_id in ids
        ),
        return_exceptions=True,
    )
    failed = 0
    for model_id, res in zip(ids, results):
        if isinstance(res, Exception):
            ok, detail = False, f"{type(res).__name__}: {res}"
        else:
            _, ok, detail = res
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {model_id:32} {detail}")
    print(f"\n{len(ids)-failed}/{len(ids)} models OK")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
