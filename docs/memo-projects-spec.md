# Memo Projects — design spec (draft 2, 2026-08-24)

Status: **implementation in progress.** Steps 1–4 are complete as of
2026-08-24. Draft 2 — revised for handoff to an implementer (human or AI) who has
not seen the discussion behind it.

## 0. Read this first (orientation for the implementer)

- **RomaLume** is a multi-model AI writing assistant: React (Vite) frontend on Firebase
  Hosting, FastAPI backend on Railway, Firestore for user data, GCS for files, Qdrant
  for embeddings. Models are called through LangChain (`get_llm()` in `main.py`) except
  GPT-5.x, which use the OpenAI Responses API directly (`generate_gpt5_response`,
  `main.py:956`). Both paths build the system prompt separately — **every prompt change
  in this spec must be made in both places** (`main.py:993-1001` and `main.py:1434-1441`
  as of commit `b4b2b18`).
- Project rules and commands: `CLAUDE.md` in the repo root. Backend tests are
  `python -m unittest discover -s tests`; tests must import only lightweight modules
  (system Python has no fastapi) — put new logic in its own module, as `llm_content.py`
  and `message_storage.py` do. `railway run -- python scripts/smoke_test_models.py`
  streams a prompt through every model with production keys; extend it for project
  fixtures.
- **Pushing `main` deploys the backend to Railway.** Frontend deploys are manual
  (`firebase deploy`, see `CLAUDE.md`). Commit per build step; don't push half-steps.
- Firestore rules make the browser read-only on its own data; every write is a
  backend endpoint using the Admin SDK. Don't add browser-side Firestore writes.
- `main.py` is ~4,000 lines and growing. New backend code for this feature goes in new
  modules (`projects.py` for the router + Firestore access, `source_extract.py`,
  `project_prompt.py`) and is mounted from `main.py`, not appended to it.
- Line numbers in this doc are from commit `b4b2b18` and will drift; grep for the
  function names.

### Decisions made (assume these unless Sage says otherwise)

| Question | Decision |
|---|---|
| Charge: form or free text? | **Small form** (question presented, jurisdiction, audience, format notes) **+ free-text field**. All optional except question presented. |
| Default project model | **`claude-sonnet-5`**; user can change per project. Opus/Fable available on demand. |
| Project kinds in v1 | **`memo` only.** Keep the `kind` field so generalizing later is additive. |
| Existing "General" archives/documents | **Leave them alone** in the Quick chats list. No migration in v1. |
| Word export | **Not in v1.** Copy-as-markdown is enough at first; `.docx` export is step 7. |
| Editor | **Plain `<textarea>` + preview toggle** using the existing `renderMarkdown`. No new dependency in v1. |
| Autosave | Project chats save to `projects/{id}/chats/{cid}` after every reply and **do not** also autosave to `archives`. Quick chats keep today's behaviour. |
| Credits | Project turns go through the **same credit gate** as today (`main.py:1104-1165`). Full-context turns are more expensive; the per-turn token estimate in the UI is informational, not a separate billing path. |

### Non-goals for v1

Sharing/collaboration, per-project memory, PDF.js rendering, citation verification,
diff/accept UI for draft edits, migration of legacy data, mobile-first layout polish
(it must work on mobile via tabs, not be great).

## 1. The idea in one paragraph

A **Project** is a workspace built around producing one document — the reference
case is a legal memo. It has a **charge** (what the memo must determine), a set of
**sources** (uploaded documents the model has read in full), a living **draft**,
and any number of **chats** that all see the charge, the sources, and the current
draft. The user moves freely between *brainstorming* (talk about the sources) and
*writing* (produce or revise sections of the draft). Everything the model asserts
from a source carries a **citation** that points to the file and page.

RomaLume's current model — one live chat, files as one-off context blobs, a flat
list of archives tagged `"General"` — is what this replaces for project work.
Plain chats outside a project keep working as they do today.

## 2. What exists today (constraints the design has to respect)

| Area | Today | Consequence |
|---|---|---|
| Conversations | One doc per user: `users/{uid}/conversations/current_chat`, overwritten every turn (`main.py:3046`). Archives are copies, autosaved after every reply under `"General"` (`Chat.jsx:337`). | Projects need real multi-conversation persistence. This is the biggest structural change. |
| Files | `/upload_quick` (what the UI uses) hardcodes `project_name="General"` in its background indexer (`main.py:2645`). `/upload` accepts a project but is unreachable from the live UI. | Upload path must take a `project_id`. |
| PDF text | Pages flattened with `"\n"`, page numbers discarded (`main.py:2820`). | Page-level citations are impossible until extraction keeps page boundaries. |
| RAG | Qdrant payload has `project_name`, but `rag.search()` is never called with it (`main.py:1310`). Chunks 4000 chars, top-5, threshold 0.5. | Retrieval is user-wide and lossy. Wrong tool for "read the whole record." |
| Citations | `[Source n: filename]` blocks; model asked to cite `[n]`; frontend gets a bare `rag_sources` filename list and `console.log`s it (`Chat.jsx:248`). | No structured citations reach the UI. |
| System prompt | `BASE_SYSTEM_PROMPT` + user profile. Date only injected when web search is on (`main.py:1478`). | Need a project-instructions slot; should always inject the date. |
| Frontend | Only `RecentChats` is mounted. `ProjectsPanel`, `DocumentsPanel`, `ArchivesPanel` are orphaned. No editor library; markdown via `marked` + DOMPurify. | Replace the orphans; v1 draft editor is a textarea + existing preview (no new dependency). |
| Firestore rules | Browser is read-only on its own data; all writes via backend. | Every new write is a FastAPI endpoint. Fine. |

## 3. Data model (Firestore, all writes via backend)

```
users/{uid}/projects/{project_id}
  name              "Smith v. Jones — statute of limitations"
  kind              "memo"            # future: "brief", "article", "general"
  charge            { question, jurisdiction, audience, format_notes, free_text }
  draft             { markdown, updated_at, version }
  draft_versions/   subcollection: {markdown, saved_at, reason}  (cap ~50)
  context_mode      "full" | "retrieval"   # computed, see §5
  default_model     optional model id
  created_at, updated_at, archived: bool

users/{uid}/projects/{project_id}/sources/{source_id}
  filename, content_type, size, storage_path
  label             short display name, user-editable ("Smith Depo")
  pages             int | null
  text_chars        int
  status            "processing" | "ready" | "error"
  indexed, chunk_count, indexing_error
  uploaded_at

users/{uid}/projects/{project_id}/chats/{chat_id}
  title             derived from first user message, editable
  mode              "brainstorm" | "write"     # last-used, see §6
  model
  messages          [ {role, content, citations?: [...]}, ... ]  (compact_messages_for_storage)
  created_at, updated_at
```

Extracted text lives in GCS next to the original: `{uid}/projects/{project_id}/sources/{source_id}.txt`
plus a `.pages.json` (`[{page: 1, start: 0, end: 4123}, ...]`) so page citations can be
resolved without re-parsing the PDF.

Qdrant payload gains `project_id` (keep `project_name` for display) and `page` per chunk.

**Migration:** none needed for existing users. Existing archives/documents stay in the
"General" world and keep rendering in RecentChats. A one-time "move this file into a
project" action can come later.

## 4. Citations

This is the feature the legal audience will judge the tool by, so it gets a real
contract rather than "please write [1]".

**Source numbering** — each source in a project has a stable number in upload order:
`[1] Smith Deposition (Smith_depo.pdf, 84 pp.)`. Numbers never change when a
source is deleted (the slot stays retired). The model is given this table in every
request.

**Inline form** — the model is instructed to cite as `[1, p. 14]`, `[2, pp. 3–5]`, or
`[1]` for whole-document claims. Multiple: `[1, p. 14; 3, p. 2]`. This is a plain
text convention, so it survives copy-paste into Word, which is where memos end up.

**Grounding** — sources are injected with explicit page markers
(`=== [1] Smith Deposition — page 14 ===`) so the model has the page number in front of
it rather than guessing. For txt/md/docx (no pages) we use paragraph-block numbers
`[2, ¶ 7]`; those are computed at extraction and injected the same way.

**Parsing** — backend regex-parses citations from the completed assistant message and
stores `citations: [{source_num, source_id, page, span}]` on the message. Frontend
renders them as clickable chips; clicking opens the source viewer scrolled to that
page (PDF.js is a later step — v1 opens the extracted text at the page marker).

**Verification (v1.5, not v1)** — a "check citations" action that re-asks a model,
per citation, whether the cited page supports the sentence. Cheap on Haiku, very
valuable for legal work. Designed in, not built.

## 5. Context strategy: read everything, retrieve only when forced

Legal memos need the model to have *read the record*, not seen five similar chunks.
All current catalog frontier models have ≥1M-token context, so:

- **`full` mode (default):** if the project's total source text ≤ `PROJECT_FULL_CONTEXT_TOKENS`
  (start at 400k tokens ≈ 1,200 pages), every source is injected in full, with page
  markers, as a cached system-prompt block. Order: charge → source table → sources →
  current draft → conversation.
- **`retrieval` mode:** above the cap, fall back to Qdrant filtered by `project_id`,
  but with a much larger budget (top-40 chunks, 2000-char chunks with `page` in the
  payload) and the source table still in full so numbering stays stable. The UI shows
  a banner: "This project is large; the model sees the most relevant excerpts."
- Mode is computed on every source add/remove and stored on the project.

**Cost control** is the real risk of full mode. A 300-page project is ~100k input
tokens per turn; at Opus 5 pricing that's ~$0.50/turn uncached. Mitigations, all in v1:
1. Prompt caching on the source block (Anthropic: explicit `cache_control`; OpenAI and
   Gemini cache long stable prefixes automatically). The source block only changes when
   sources change, so cache hits should be the norm within a session.
2. Per-project token estimate shown in the UI ("~120k tokens / turn") and counted into
   the existing credit system honestly.
3. Default project model = Sonnet 5 unless the user changes it; Opus/Fable on demand.
4. Haiku 4.5 (200k context) is excluded from full mode above 150k tokens; the UI greys it
   out with the reason.

## 6. Two modes, one chat

Rather than separate "brainstorm" and "write" features, each chat has a **mode toggle**
on the composer. It changes the instructions and the affordances, not the data.

| | Brainstorm | Write |
|---|---|---|
| Instructions | Analyst: issue-spot, weigh, argue both sides, ask clarifying questions, cite every factual claim. Do **not** produce memo prose unless asked. | Drafter: produce memo prose in the charge's format, cite everything, follow the draft's existing structure and voice. |
| Draft awareness | Sees the draft; refers to it ("your Analysis §2 already covers this"). | Sees the draft; every reply is framed as an edit: whole section, or replacement for a selected range. |
| Composer extras | — | "Target: [section dropdown / whole draft / selection]" and an **Apply to draft** button on each reply. |
| Default model | Project default | Project default |

**Apply to draft** is the bridge: it replaces the target section (or appends) and writes a
`draft_versions` entry with `reason: "chat {chat_id}, message {n}"`. Undo = restore a
version. No diff/accept UI in v1 — the version list is the safety net.

Suggested quick actions on a fresh project (buttons above the composer, mode-aware):
*Identify the issues · Summarize each source · Outline the memo · Draft the Facts section ·
Draft the whole memo · What's the strongest counter-argument?*

## 7. Prompt assembly (backend)

Both `generate_chat_response` and `generate_gpt5_response` gain a `project_id` branch;
factor the assembly into `project_prompt.build_project_system_prompt(project, sources, draft, mode)`
so the two paths share it. Order of the system prompt:

1. `BASE_SYSTEM_PROMPT` (existing) + today's date (always, not only with web search).
2. **Charge block**: "You are helping write a legal memorandum. Question presented: …
   Jurisdiction: … Audience: … Format: …" + free text.
3. **Citation contract** (§4) with the source table.
4. **Sources** (full text with page markers) or retrieved excerpts — cached.
5. **Current draft** (if non-empty), under `=== CURRENT DRAFT ===`.
6. **Mode instructions** (§6).
7. User profile (existing) — moved *after* project context, it's the least relevant here.

Then the chat messages. `search_docs` is ignored inside a project (the project *is* the
docs); `search_web` still works and its results go in the last user message as today.

## 8. API

```
POST   /projects                      create {name, kind, charge}
GET    /projects                      list (replaces the current archives-by-name grouping)
GET    /projects/{id}                 project + sources + chats (summaries)
PATCH  /projects/{id}                 name, charge, default_model, archived
DELETE /projects/{id}                 soft-delete (archived=true); hard delete later

POST   /projects/{id}/sources         multipart upload → extract, page-map, index, compute context_mode
PATCH  /projects/{id}/sources/{sid}   label
DELETE /projects/{id}/sources/{sid}
GET    /projects/{id}/sources/{sid}/text?page=14

GET    /projects/{id}/draft
PUT    /projects/{id}/draft           {markdown, reason}  → new version
GET    /projects/{id}/draft/versions
POST   /projects/{id}/draft/restore   {version}

POST   /projects/{id}/chats           → chat_id
GET    /projects/{id}/chats/{cid}
DELETE /projects/{id}/chats/{cid}
POST   /chat_stream                   existing; body gains project_id?, chat_id?, mode?, write_target?
                                      new SSE events: {"citations": [...]} after [DONE]-1
```

Extraction gets one new module, `source_extract.py`: per-type text + page/paragraph map,
returning `{text, pages: [...], kind}`; `/upload_quick` keeps using it too so the two
upload paths stop drifting.

## 9. Screens

1. **Projects list** — replaces the "Chats" tab's flat list with: *Projects* (cards: name,
   source count, last activity, draft word count) and *Quick chats* (today's behaviour).
2. **Project page** — three-pane on desktop, tabs on mobile:
   - Left: sources (upload, label, status, token estimate, context-mode banner) and chats list.
   - Center: the active chat with the Brainstorm/Write toggle and quick actions.
   - Right: the draft (markdown editor, word count, version menu, export → .md / .docx).
3. **New project dialog** — name, memo charge form (question presented, jurisdiction,
   audience, format notes), initial file drop.
4. **Source viewer** — modal showing extracted text with page markers; deep-linked
   from citation chips.

Editor: add `@uiw/react-md-editor` (small, React 19-compatible, split preview) — or a
plain `<textarea>` + existing `renderMarkdown` preview toggle for v1 if we want zero new
deps. Recommend the textarea for v1; the draft is markdown headed for Word anyway.

Export to `.docx`: `python-docx` is already a backend dep (used by `/upload_quick`);
one endpoint renders draft markdown → docx with citations left as plain text.

## 10. Build order (each step shippable)

1. **Extraction with page maps** — `source_extract.py`, tests. Also fixes `/upload_quick`'s
   hardcoded project. No UI change.
2. **Project + sources + chats model and endpoints** — backend only, tests against the
   Firestore emulator (already configured in `firebase.json`).
3. **Prompt assembly with full-context mode, citation contract, citation parsing** —
   testable with the smoke-test harness (`railway run`) against a fixture project.
4. **Projects list + project page + chat scoped to project** (Brainstorm mode only).
5. **Draft pane + Write mode + Apply to draft + versions.**
6. **Citation chips + source viewer.**
7. Later: citation verification, PDF.js viewer, docx export polish, per-project sharing.

Steps 1–3 are roughly a day of backend work. 4–6 are the bulk — the frontend is where
the time goes.

**Definition of done per step**

| Step | Done when |
|---|---|
| 1 | `source_extract.extract(bytes, content_type) -> {text, pages, kind}` with unit tests for pdf/txt/md/docx/csv; `/upload_quick` uses it and passes the real project (or `"General"`); no behaviour change visible to users. |
| 2 | All `/projects…` endpoints in §8 exist, are auth-guarded to the owner, and have tests against the Firestore emulator (`firebase emulators:start --only firestore`, port 8082 per `firebase.json`). |
| 3 | A fixture project (3 sources, one PDF) run through `scripts/smoke_test_models.py --project <id>` returns answers with `[n, p. x]` citations from every catalog model; citations are parsed and returned in the `citations` SSE event; `context_mode` flips to `retrieval` when the fixture exceeds the cap. |
| 4 | A user can create a project, upload sources, and hold a Brainstorm chat that cites them, on desktop and mobile; Quick chats unchanged. |
| 5 | Write mode + Apply to draft + version restore work; the draft survives reload. |
| 6 | Citation chips open the source viewer at the cited page/paragraph. |

## 11. Open questions (resolved in §0 — kept for the record)

1. **Charge as a form or free text?** I've specified a small form (question / jurisdiction /
   audience / format) plus free text. A single textarea is simpler and might be enough.
2. **Default model for projects** — Sonnet 5 (cost) vs Opus 5 (quality) for a legal audience?
3. **Is "memo" the only `kind` in v1**, or should the charge form be generic from day one?
   (I'd ship memo-only and generalize once it's used.)
4. **Existing "General" archives/documents** — leave them as-is in Quick chats, or offer
   migration into projects? I'd leave them.
5. **Word export** — needed in v1, or is copy-paste of markdown acceptable at first?
