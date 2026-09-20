"""Index a school's seed library into its Qdrant collection.

    railway run -- .venv/bin/python scripts/index_school_library.py --school cfa \\
        --manifest docs/cfa-seed-manifest.json [--dry-run] [--limit N] [--include-retired]

Reads the manifest the client session produced (docs/cfa-pilot-brief.md §8),
extracts text per file, chunks and embeds it with the same splitter Quick Chat
uses, and tags every point with client_id and audience. Registry rows go to
romalume.library_documents. Re-runs skip files whose content hash is
unchanged.

Rules from the manifest notes:
  - retired pages are skipped unless --include-retired
  - posts that exist both as a WordPress export and in the cfa-website repo
    are indexed once, preferring the cfa-website copy
  - folders, spreadsheets, and Drive URLs are skipped (recorded as errors)
  - board audience is never indexed from here
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import library_store  # noqa: E402
from rag_service import get_rag_service  # noqa: E402
from source_extract import extract  # noqa: E402

TEXT_EXT = {".md", ".txt", ".markdown"}
SKIP_EXT = {".xlsx", ".xls", ".csv", ""}


def slug_of(path: str) -> str:
    name = Path(path).stem.lower()
    name = re.sub(r"^\d+-", "", name)            # WordPress export ids: 10044-title
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)  # dated post files
    return name


def read_text(path: str) -> str:
    ext = Path(path).suffix.lower()
    data = Path(path).read_bytes()
    if ext in TEXT_EXT:
        text = data.decode("utf-8", errors="replace")
        # Drop YAML front matter but keep its title/date lines as plain text.
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                front = text[3:end].strip()
                body = text[end + 4:]
                keep = "\n".join(l for l in front.splitlines() if re.match(r"^(title|date|description|author)\s*:", l, re.I))
                text = (keep + "\n\n" + body).strip()
        return text
    if ext == ".json":
        payload = json.loads(data.decode("utf-8", errors="replace"))
        return json.dumps(payload, indent=1, ensure_ascii=False)
    if ext == ".pdf":
        return extract(data, "application/pdf")["text"]
    if ext == ".docx":
        return extract(data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")["text"]
    raise ValueError(f"unsupported file type {ext or '(none)'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--school", required=True, help="school slug, e.g. cfa")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--include-retired", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-embed even if the content hash is unchanged")
    args = ap.parse_args()

    school = library_store.get_school_by_slug(args.school)
    if not school:
        print(f"no school with slug {args.school}"); return 2
    client_id = school["client_id"]
    collection = school.get("qdrant_collection") or f"{args.school}_library"
    manifest = json.loads(Path(args.manifest).read_text())
    items = manifest["items"] if isinstance(manifest, dict) else manifest

    # Dedupe posts across the two sources, preferring the cfa-website copy.
    site_slugs = {slug_of(i["path"]) for i in items if i.get("source_system") == "cfa_website_git"}
    plan, skipped = [], []
    for it in items:
        path = it.get("path") or ""
        reason = None
        if it.get("audience") == "board":
            reason = "board audience is never indexed from here"
        elif it.get("retired") and not args.include_retired:
            reason = "retired page"
        elif path.startswith("http"):
            reason = "remote folder, not a file"
        elif Path(path).suffix.lower() in SKIP_EXT or it.get("kind") == "folder":
            reason = f"unsupported: {it.get('kind')}/{Path(path).suffix or 'no extension'}"
        elif not os.path.exists(path):
            reason = "file not found"
        elif it.get("source_system") == "wordpress_export" and it.get("kind") == "post" and slug_of(path) in site_slugs:
            reason = "duplicate of cfa-website post"
        (skipped if reason else plan).append((it, reason))
    if args.limit:
        plan = plan[: args.limit]

    print(f"school {school['name']} ({client_id}) -> collection {collection}")
    print(f"plan: {len(plan)} to index, {len(skipped)} skipped")
    from collections import Counter
    print(" skip reasons:", dict(Counter(r for _, r in skipped)))
    print(" audiences:", dict(Counter(i.get('audience') for i, _ in plan)))
    if args.dry_run:
        return 0

    rag = get_rag_service()
    if rag is None:
        print("Qdrant/OpenAI not configured"); return 2
    rag.ensure_library_collection(collection)
    known = {} if args.force else library_store.existing_hashes(client_id)

    done = unchanged = failed = chunks_total = 0
    started = time.time()
    for n, (it, _) in enumerate(plan, 1):
        path = it["path"]
        try:
            text = read_text(path).strip()
            digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
            if known.get(path) == digest:
                unchanged += 1
                continue
            if len(text) < 40:
                raise ValueError("no usable text")
            document_id = f"library:{client_id}:{hashlib.sha1(path.encode()).hexdigest()}"
            count = rag.index_library_document(
                collection,
                client_id=client_id,
                document_id=document_id,
                text=text,
                audience=it.get("audience") or "staff",
                title=it.get("title") or Path(path).stem,
                metadata={
                    "url": it.get("url"), "source_system": it.get("source_system"),
                    "kind": it.get("kind"), "last_modified": it.get("last_modified"),
                },
            )
            library_store.upsert_document(
                client_id, source_path=path, title=it.get("title") or Path(path).stem,
                audience=it.get("audience") or "staff", qdrant_collection=collection,
                chunk_count=count, source_system=it.get("source_system"), kind=it.get("kind"),
                url=it.get("url"), last_modified=it.get("last_modified"), content_hash=digest,
                text_chars=len(text),
            )
            done += 1; chunks_total += count
        except Exception as e:  # noqa: BLE001
            failed += 1
            library_store.upsert_document(
                client_id, source_path=path, title=it.get("title") or Path(path).stem,
                audience=it.get("audience") or "staff", qdrant_collection=collection,
                chunk_count=0, source_system=it.get("source_system"), kind=it.get("kind"),
                url=it.get("url"), last_modified=it.get("last_modified"), content_hash="",
                text_chars=0, error=str(e)[:500],
            )
            print(f"  ! {path}: {e}")
        if n % 50 == 0:
            print(f"  {n}/{len(plan)} ({time.time()-started:.0f}s) indexed={done} unchanged={unchanged} failed={failed} chunks={chunks_total}")

    print(f"done: indexed={done} unchanged={unchanged} failed={failed} chunks={chunks_total} in {time.time()-started:.0f}s")
    print("summary:", library_store.summary(client_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
