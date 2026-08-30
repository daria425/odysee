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

## Known Issues / Gotchas

- **Anthropic API rejects system-only message lists.** `anthropic.BadRequestError: messages: at least one message is required` — the Anthropic API requires at least one non-system message in the request; a `[SystemMessage(...)]`-only call fails even though the system prompt has content. Any templated user-facing content (e.g. the question a small structured-output LLM call is judging) must go in a separate `HumanMessage`, never interpolated into the system prompt string. If there's genuinely no user-relevant content, still send a minimal `HumanMessage` rather than omitting it.
