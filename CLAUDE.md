# CLAUDE.md

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
  = Act as a partner and discuss things with me, do not blindly agree but do not push back on everything, be rational

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## Project Specific Guidelines

## Trip Research Orchestrator.

Core idea:

1. a chatbot that is able to direct queries to specialized subagents for research
2. deep research graph for travel report generation that answers all of my key questions
   These will later be combined in some way which is TBC

Report graph is inspired by https://towardsdatascience.com/langgraph-101-lets-build-a-deep-research-agent/ article and https://github.com/google-gemini/gemini-fullstack-langgraph-quickstart github repo (which I have a local clone of at "\\wsl.localhost\Ubuntu\home\daria\projects\gemini-fullstack-langgraph-quickstart")

Check/review .claude/handoff.md for latest project state and next steps

## DB Schema (`data/travel_agent.db`, sqlite)

App-owned tables (created by `MemoryStore._init_db()` in `app/lib/db/store.py`):

```
-- trips --
  trip_id (TEXT)        -- also doubles as the LangGraph thread_id
  name (TEXT)
  destinations (TEXT)   -- stored as JSON list
  start_date (TEXT)
  end_date (TEXT)
  notes (TEXT)
  created_at (TEXT)
  research_status (TEXT)       -- not_started | running | done | failed
  research_report (TEXT)
  research_report_ui (TEXT)    -- A2UI JSON compiled from research_report, or NULL (see A2UI section below)
  research_error (TEXT)
  research_started_at (TEXT)   -- set when research_status becomes "running"
  research_updated_at (TEXT)   -- set on every research_status update

-- memory_log --
  entry_id (INTEGER, autoincrement)
  trip_id (TEXT)
  content (TEXT)
  created_at (TEXT)
```

LangGraph-owned tables (created by `SqliteSaver` in `app/main.py`, same db file):

```
-- checkpoints --
  thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
  type, checkpoint (BLOB), metadata (BLOB)

-- writes --
  thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel,
  type, value (BLOB)
```

Inspect/manage via `poetry run python -m app.lib.db.utils {schema|threads|view <thread_id>|delete <trip_id>}` (see `app/lib/db/utils.py`). No bulk-clear command — delete `data/travel_agent.db` to wipe everything; it's recreated on next run.

## Manual Integration Test: trip creation → report → follow-up chat

Deterministic end-to-end check for the `/start` → research → chat-with-report flow. Run the server first (`uvicorn app.main:app --reload`).

1. Kick off a trip (research runs as a background task, so this returns immediately):

```
POST /chat
{
  "user_message": "/start <name> | <destination(s)> | <date>",
  "thread_id": "<trip_id>",
  "langfuse_session_id": "<trip_id>"
}
```

2. Wait for research to finish, then check the report landed in the db:

```
sqlite3 data/travel_agent.db "SELECT trip_id, research_status, research_started_at, research_updated_at, research_report FROM trips WHERE trip_id='<trip_id>';"
```

(status should be `done`, with `research_report` populated — poll until then, or watch `ws://localhost:8000/ws/trip/<trip_id>` for the `"done"` broadcast instead of polling)

3. Send a follow-up on the same thread — pick a question the report deliberately does NOT cover (a specific number/fact it wouldn't have), to exercise the full tool-calling path through `check_report_coverage`:

```
POST /chat
{
  "user_message": "<question not covered by the report>",
  "thread_id": "<same trip_id>",
  "langfuse_session_id": "<same trip_id>"
}
```

Confirm via the `[check_report_coverage] covered=...` log line and the Langfuse trace which branch (`report_covered` true/false) was taken.

## Evals depend on frozen fixtures — check before changing the nodes they cover

`evals/` datasets are built from fixtures captured at a point in time (a real report + `web_research_result`
with sources, e.g. `evals/reports/khiva_2026-10.md`). Eval scripts do **not** re-run the graph — they test
prompts/judges against the frozen fixture. So:

- Changing `app/lib/prompts/check_report_coverage_prompt.txt` or `check_report_coverage`'s logic → re-run
  `evals/scripts/run_check_report_coverage_experiment.py`; the fixture report itself doesn't need to change.
- Changing `app/agent/research/nodes.py` (`web_research`, `finalize_answer` — anything that changes what a
  report or `sources` looks like) → the existing fixtures are now stale/unrepresentative of current graph
  output. Check whether `evals/reports/*` and `evals/calibration/*` need to be regenerated from a fresh graph
  run before trusting eval results against the new code.
- The groundedness judge (`evals/lib/groundedness_judge.py`, prompt at
  `evals/prompts/groundedness_judge_prompt.txt`) is **not wired into the app itself** (no production node calls
  it) but can be run against a fresh graph output directly via
  `evals/scripts/judge_fresh_research_run.py --destination ... --travel-date ...` — this actually re-runs
  `app/agent/research/graph.py` and judges its real output, so it's the right tool for "did my prompt change
  make groundedness better or worse." `evals/scripts/run_groundedness_experiment.py` is the separate calibration
  check against the frozen `evals/calibration/` set — re-run that only when the judge prompt/architecture itself
  changes, not when the research graph changes.

## Debugging Practice

- **Before theorizing about asyncio/LangGraph/library internals, re-read your own recently-edited
  code for leftover/duplicate blocks.** Burned a large chunk of a session chasing a "duplicate LLM
  call" bug through `asyncio.as_completed` semantics, LangGraph's `astream` streaming model, and
  multiple isolated repro scripts — the actual cause was a botched `Edit` call that left the old
  pre-refactor function body still present below the new one, so every item ran through twice. A
  single re-read of the full function (not just the diff) would have caught it immediately. First
  debugging step: check for exactly this kind of self-inflicted slop before reaching for deeper
  systemic theories.

## Known Issues / Gotchas

- **Anthropic API rejects system-only message lists.** `anthropic.BadRequestError: messages: at least one message is required` — the Anthropic API requires at least one non-system message in the request; a `[SystemMessage(...)]`-only call fails even though the system prompt has content. Any templated user-facing content (e.g. the question a small structured-output LLM call is judging) must go in a separate `HumanMessage`, never interpolated into the system prompt string. If there's genuinely no user-relevant content, still send a minimal `HumanMessage` rather than omitting it.

## Next Steps

### Frontend Integration

React shell (`frontend/`, Vite) — chat window + header "Odysee" + sidebar (New Chat / Trips) — shipped in
`7ccf178`, backed by `GET /trips`, `GET /trip/{id}`, `GET /trip/{id}/messages` and `CORSMiddleware` on the
FastAPI backend. Run locally without Docker: backend via `poetry run uvicorn app.main:app --reload`, frontend
via `npm run dev` (in `frontend/`). Docker and CI are still deferred — see below.

### A2UI report rendering

The research report renders as native components (not raw markdown) via [A2UI](https://a2ui.org/), split
across two independent producers feeding one renderer:

- **Primary path**: `app/lib/report_ui.py`'s `generate_report_ui()` — a cheap-model (`claude-haiku-4-5`)
  call that compiles the report Markdown into A2UI JSON (unconstrained plain-text generation + client-side
  schema validation + retry, not provider-side structured output — see the module docstring for why). Wired
  into `run_research()` in `main.py` behind `should_generate_ui` (only `/start` passes `True`); persisted to
  `trips.research_report_ui`. On failure after all retries, it just logs and leaves the column `NULL` — it
  never fails the research request itself, since `research_report` (the markdown) is already saved by then.
- **Fallback path**: `frontend/src/lib/markdownToA2ui.ts` — a deterministic (no LLM, can't fail) Markdown →
  A2UI JSON converter mirroring the same `##`→Card mapping the LLM prompt uses. `ReportPanel.tsx` uses this
  whenever `research_report_ui` is `null` (generation hasn't run yet for older trips, or failed).
- **Renderer**: `@a2ui/react` + `@a2ui/web_core`, both pinned to the `v0_9` subpath (matches the Python
  `a2ui-core` package's `SPEC_VERSION`) — `MessageProcessor` processes either producer's message array,
  `<A2uiSurface>` renders it. **Gotcha**: don't memoize/reuse a single `MessageProcessor` instance across
  re-renders — React StrictMode's dev-mode double-invoke will call `createSurface` twice on it and throw
  `A2uiStateError: Surface already exists`. Create a fresh one per effect run instead (see `ReportPanel.tsx`).
- Report view is a split layout — `ChatWindow` + `ReportPanel` side by side (`.main-split` in `index.css`) —
  shown whenever a trip is selected, independent of and untouched by the chat flow itself.

### Still open

- **No Dockerfile / docker-compose anywhere in the repo.** Needed later for "run locally via Docker,
  including by someone else who just clones the repo": a backend Dockerfile (poetry-based), a frontend
  Dockerfile, and a `docker-compose.yml` wiring both plus env vars from `.env`.
- **SQLite persistence across container recreation.** `data/travel_agent.db` lives on disk at a path that's
  gitignored (`data/`). A plain `docker restart` (same container) would NOT lose it — but
  `docker compose down` / rebuild recreating the container WOULD, unless `./data:/app/data` (or equivalent)
  is mounted as a volume in compose. Needs a volume mount when Docker is set up, not a code change.
- **No CI config** (no `.github/workflows`) for "build backend + frontend on commit" — a separate GitHub
  Actions setup, not yet started.
