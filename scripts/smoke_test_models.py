"""Stream one short prompt through every catalog model via main.get_llm.

Usage (needs provider API keys in the environment, e.g. via `railway run`):
    python scripts/smoke_test_models.py [model_id ...]
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cost_tracker import get_models_catalog  # noqa: E402
from llm_content import stream_chunk_text  # noqa: E402
from main import get_llm  # noqa: E402

PROMPT = [{"role": "user", "content": "Reply with exactly the word OK."}]


async def check(model_id: str):
    start = time.time()
    try:
        llm = get_llm(model_id)
        text = ""
        async for chunk in _iter(llm):
            text += stream_chunk_text(chunk.content)
        return model_id, True, f"{time.time()-start:.1f}s  {text.strip()[:60]!r}"
    except Exception as e:  # noqa: BLE001
        return model_id, False, f"{type(e).__name__}: {str(e)[:200]}"


async def _iter(llm):
    async for chunk in llm.astream(PROMPT):
        yield chunk


async def main():
    ids = sys.argv[1:] or [m["id"] for m in get_models_catalog()]
    results = await asyncio.gather(*(asyncio.wait_for(check(m), 120) for m in ids), return_exceptions=True)
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
