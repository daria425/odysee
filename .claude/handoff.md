# Handoff — 2026-08-30T21:30(session)

## Project Summary

Trip Research Orchestrator — a travel companion app with two LangGraph graphs sharing one SQLite DB (`data/travel_agent.db`):

1. **Chat graph** (`app/agent/chat/`) — conversational assistant behind `POST /chat`. `/start <name> | <destinations> | <date>` creates a trip; otherwise routes through the chat workflow.
2. **Research graph** (`app/agent/research/`) — deep-research pipeline producing a single upfront report against a fixed set of key questions (`data/key_qs.json`), inspired by the LangGraph/Gemini deep-research quickstart. Runs as a background asyncio task kicked off by `/start`.

FastAPI app in `app/main.py`. `/ws/trip/{trip_id}` websocket streams research status/report to clients, pushing on connect and again on completion.

This session's design thread: rather than re-executing live searches for every chat question (common AI-travel-app pattern, adds latency), precompute the report once and inject it as context; only fall back to live per-domain search tools (`search_nightlife`, `search_budget`, `search_side_quests` in `app/agent/chat/tools.py`) when the report doesn't cover the specific fact needed. A router node makes that call explicitly (not just a prompt hint) by hard-restricting tool binding.

Working style note: user prefers to write/apply code themselves in many cases, but explicitly asked me to apply this feature directly this session ("go ahead ill review") — confirm scope before assuming write-vs-explain mode next session.

---

## Key Decisions Made

| Decision | Detail |
|---|---|
| Report → chat context | `inject_context` now appends `trip.research_report` into `trip_context` when `research_status == "done"` (previously never wired in) |
| Coverage check | New `check_report_coverage` node — cheap Haiku + structured output (`ReportCoverageResult.covered: bool`), same pattern as existing `log_memory` node |
| Coverage granularity | Must check the *specific data point* the question needs is in the report, not just topic overlap (e.g. general "budget" mention ≠ covers "is €70/night a scam") — encoded via examples in the prompt |
| Enforcement | Hard tool-binding restriction, not a prompt instruction: `call_model` binds `[respond_tool]` only when `report_covered` is true, else the full `chatbot_tools` set |
| Full report rebuild vs. single search | Full rebuild triggered by trip fundamentals changing or staleness (via new timestamp columns); single search stays for anything outside the fixed 10 questions — not yet implemented (no rebuild trigger exists yet, `/start` is still the only thing that runs research) |
| DB migration approach | No migration system — agreed to just delete `data/travel_agent.db` and let `_init_db()` recreate it, rather than building `ALTER TABLE` handling |
| Timestamp columns type | `TEXT` (ISO8601 strings via `datetime.now(timezone.utc).isoformat()`), matching existing `created_at` convention — SQLite has no real timestamp type so `TIMESTAMP` would buy nothing |
| Langfuse tracing in nodes | Any node that calls `llm.invoke()` directly must forward `config` explicitly (`llm.invoke(messages, config)`) — LangGraph does NOT auto-propagate callbacks to nested calls. Fixed in `check_report_coverage` and `log_memory`; **`call_model` itself still doesn't forward config — flagged, not yet fixed, user was going to check if it's actually a problem there** |
| Anthropic API gotcha | Anthropic rejects a message list containing only a `SystemMessage` (`messages: at least one message is required`). Any user-facing templated content (e.g. the question a structured-output judge call evaluates) must go in a separate `HumanMessage`, never interpolated into the system prompt string. Documented in `CLAUDE.md` under "Known Issues / Gotchas" |

---

## Current State of Key Files

### `app/lib/db/store.py` / `app/lib/db/models.py` ✅ done, committed
- `trips` table gained `research_started_at`, `research_updated_at` (both `TEXT`)
- `update_research_status()`: stamps `research_updated_at` on every call; `research_started_at` only when status transitions to `"running"`
- `Trip` model and `_row_to_trip()` updated to match

### `app/main.py` ✅ done, committed
- `_research_status_message()` includes the two new timestamps in the websocket payload

### `app/agent/chat/nodes.py` ✅ done, committed
- `inject_context`: appends `## Trip Report\n{report}` when done + present
- `make_check_report_coverage(store)`: new node, Haiku structured-output classifier, forwards `config` for tracing, sends question as `HumanMessage` (not interpolated into system prompt — this was the bug we just fixed)
- `make_call_model(llm, profile, chatbot_tools, respond_tool)`: signature changed (now takes `respond_tool` separately); binds `chat_llm_report_only` (respond-only) vs `chat_llm_full` based on `state.get("report_covered")`
- `log_memory`: now forwards `config` to its `llm.invoke()` call too (same tracing fix)

### `app/agent/chat/graph.py` / `app/agent/chat/state.py` ✅ done, committed
- Graph edge order: `trim_messages` → `inject_context` → `check_report_coverage` → `call_model` → …
- `State` gained `report_covered: bool`

### `app/lib/prompts/check_report_coverage_prompt.txt` ✅ done, committed
- Instructs content-level grounding check (specific data point present, not just topic), with worked examples (hotel price, solo-female-safety)
- Report is interpolated into the system prompt; the question is **not** — it's passed as a separate `HumanMessage` at call time

### `app/lib/models.py` ✅ done, committed
- Added `ReportCoverageResult(covered: bool)`

### `CLAUDE.md` ✅ done, committed
- `trips` schema block updated with the new research columns
- New "Manual Integration Test" section documenting the `/start` → poll DB via sqlite3 → follow-up `/chat` workflow, including picking a deliberately-uncovered question to exercise the full tool path
- New "Known Issues / Gotchas" section with the Anthropic system-only-message gotcha

---

## Verified This Session

Manual end-to-end test was run by the user against a real trip (Rostock, Oct 2026):
- Nightlife question (deliberately uncovered — specific October techno lineup) → `covered=False` → routed through `call_nightlife_agent`, produced a grounded answer citing what was/wasn't confirmed
- Hotel price question (covered — report states `Accommodation: €60–80`) → `covered=True` → answered directly from report context, no tool calls

Both outputs looked correct and well-grounded. Router is working as designed.

---

## Current Position & Next Steps

We were mid-conversation about **evals** when this handoff was triggered. Plan going into next session:

1. **Langfuse access for me**: user wants to set up the Langfuse Agent Skill + Langfuse CLI (recommended path per Langfuse docs for agents that can run shell commands, vs. MCP which is the fallback for agents that can't) so I can pull traces/sessions directly instead of copy-paste. API keys likely already in `.env` (used by `app/lib/langfuse_client.py`). **Not yet installed — do this first if picking eval work back up.**

2. **Evals — agreed direction, not yet built**:
   - **Priority: labeled eval set for `check_report_coverage`** (the newest, least-tested piece). ~15-20 `(report snippet, question, expected covered)` pairs, including deliberately tricky ones (topic mentioned but not the specific fact — like the hotel example). Score accuracy, but weight **false positives** (`covered=True` when it shouldn't be) as the worse failure mode — that's the silent one where the user gets a shallow answer with no search and no warning. Langfuse Datasets + Experiments is the natural fit for this, would let us diff scores across prompt edits.
   - LLM-as-judge for open-ended output (report completeness against the 10 `key_qs.json` questions; chat response groundedness) — lower priority, less tractable than the router eval.
   - Regression harness (fixed set of 2-3 trips, re-run when prompts/graph change) — later.
   - Track tool-call count / latency per turn as a non-correctness metric, to confirm the router is actually cutting unnecessary searches (the original motivation for this whole feature).

3. **Not yet addressed, mentioned in passing**:
   - Whether `call_model`'s own `llm.invoke()` needs `config` forwarding too for tracing (user was going to check first)
   - No trigger yet for full report *rebuild* (staleness detection exists as data now via the timestamp columns, but nothing consumes it)
   - No `GET /trip/{trip_id}` REST fetch endpoint — deliberately deferred until an actual client is wired in and its needs are known

---

# Handoff — 2026-09-01T14:17(session)

## Project Summary

Odysee (formerly untitled Trip Research Orchestrator) — same two-graph architecture as before (chat graph +
research graph, one SQLite DB). This session had two parts:

1. **Frontend shell** (already committed in `7ccf178 "basic ui"`, before this session's own work): a
   lightweight Vite/React shell (`frontend/`) — header, sidebar (New Chat + Trips list), chat window — wired
   to new `GET /trips`, `GET /trip/{id}`, `GET /trip/{id}/messages` endpoints and `CORSMiddleware` on the
   FastAPI backend, plus a gradient design pass (`#ff5a57` → `#fccbf0`) via the `ui-ux-pro-max` skill. **Note:
   `CLAUDE.md`'s "Next Steps → Frontend Integration" section still lists `GET /trips`/CORS as open gaps —
   that's now stale, those shipped in `7ccf178`. Worth cleaning up that section next time it's touched.**
2. **A2UI integration** (this session's main focus, uncommitted) — compiling a finalized trip report
   (Markdown) into A2UI protocol JSON so the frontend can eventually render it as native components instead
   of raw markdown, independent of the chat flow. Working end-to-end against both real trips in the db
   (Rostock, Khiva) as of this handoff, but not yet wired into `run_research()`/`main.py`, and not yet
   exposed to the frontend.

User's explicit intent throughout: report/research UI generation must stay decoupled from chat — "don't want
their shit in my shit." Chat (`/chat` POST) stays plain-text, untouched, no A2UI involvement.

---

## Key Decisions Made (A2UI)

| Decision | Detail |
|---|---|
| Package choice | `a2ui-core` (PyPI, lightweight: pydantic/jsonschema/referencing only) — **not** `a2ui-agent-sdk`, which hard-depends on `google-adk` + `google-genai` + `a2a-sdk` just to get schema/prompt utilities we don't need. Confirmed by downloading and unpacking both wheels; only `a2ui/adk/*` in the agent-sdk actually touches ADK, but pip would still force-install it as a package dependency regardless of what's imported. |
| Model | `claude-haiku-4-5-20251001`, same cheap-model tier as `check_report_coverage`/`log_memory` |
| **Generation method — reversed mid-session** | Originally planned: bind `with_structured_output()` directly to `a2ui-core`'s real component Pydantic classes (`TextComponent`, `CardComponent`, etc.). **This does not work** — tested against the real Rostock report: `method="function_calling"` silently returned the component array as a JSON *string* inside one field (malformed, no error raised); `method="json_schema"` was flat-out rejected by Anthropic's API: `400 "The compiled grammar is too large"`. Root cause: those classes carry generality we don't use (`DataBinding`/`FunctionCall` dynamic-value unions, `TemplateChildList`, `accessibility`, `weight`), which blows up the schema Anthropic has to compile. |
| Resolution | Checked how Google ADK's own reference implementation (`DirectJsonFormat` in `a2ui-agent-sdk`) does it — it **never** uses provider-side structured output/tool-calling at all. It embeds the schema as prompt text, generates plain text, parses with a tolerant JSON parser (`payload_fixer.py`: strips code fences, normalizes smart quotes, retries), then validates client-side against the real catalog JSON schema. We now follow that same pattern — see `app/lib/report_ui.py`. This is a genuine advantage the user flagged: provider-agnostic, would work identically with Llama/other models since nothing depends on Anthropic-specific structured-output support. |
| Retry behavior | Up to `MAX_ATTEMPTS = 3`. On validation failure, the raw model output + the validator's error message are appended to the message list and the model is asked to correct it. Confirmed working live: attempt 1 on both real reports failed with a dangling-reference error (`Component 'X' references non-existent component 'Y'`), attempt 2 succeeded both times. |
| Validation | `a2ui_core.validating.A2uiValidator` + `CatalogSchemaValidator` against a real `BasicCatalog()` instance — catches JSON-schema violations, dangling references, orphan components, and (the one gap the prompt didn't originally cover) **missing root**: A2UI requires exactly one component with the literal `id: "root"` as the surface's unreferenced entry point. This wasn't in any doc we read; found by hitting `Missing root component: No component has id='root'` in testing and fixing the prompt to require it explicitly. |
| Catalog subset (v1) | `Text`, `Column`, `Row`, `Card`, `Divider`, `List` — read-only content only, no form/interactive components (`Button`, `TextField`, `CheckBox`, etc. deliberately excluded) |
| Structure mapping | Report `#` title → standalone `h1` `Text` under `root`. Each `##` section → one `Card` (wrapping a `Column` of `h2` heading + paragraph `Text`s + `List`s for bullets). `root` is a `Column` listing title + all section-card ids in order. |
| DB storage | New `trips.research_report_ui TEXT` column, added via **non-destructive `ALTER TABLE`** (not the old "delete the db and let `_init_db()` recreate it" precedent — that precedent no longer applies now that there's real trip data worth keeping; explicitly flagged and user agreed) |
| Where the generation call lives | Agreed: **not** a LangGraph node — a plain post-processing function called from `run_research()` in `main.py`, after `research_workflow.ainvoke()` returns. Reasoning: keeps the research graph's job purely "produce a grounded report" (same separation principle as chat), and means eval scripts that invoke `research_workflow` directly never trigger UI generation regardless of default, no extra plumbing needed. **Not yet implemented** — `report_ui.py` exists and works standalone, but nothing in `main.py` calls it yet. |
| Trigger gating | Agreed: `should_generate_ui` param, default `False`, so it can be called explicitly for now without accidentally firing during eval/test runs of the graph. **Not yet implemented.** |
| Observability | Even though it's outside the graph, still forward `config` (with the existing `langfuse_handler` callback) into the `llm.invoke()` call the same way `check_report_coverage`/`log_memory` already do — confirmed this gives a real Langfuse generation in the same session, just not nested under the graph's span tree. `generate_report_ui()` already accepts and forwards `config: RunnableConfig | None`, ready to receive it once wired into `main.py`. |
| Staleness | Explicitly decided **not** to track UI staleness separately — it's derived data, coupled 1:1 to report generation at the same call site, so it inherits whatever staleness/rebuild logic eventually governs the report itself (which still doesn't exist yet — no rebuild trigger, per prior handoff). |

---

## Current State of Key Files

### `app/lib/report_ui.py` ✅ done, uncommitted, tested working
- `generate_report_ui(report: str, surface_id: str, config: RunnableConfig | None = None) -> str` — returns
  a JSON string of `[createSurfaceMessage, updateComponentsMessage]`
- `_extract_json()`: strips markdown code fences + normalizes smart quotes before `json.loads`
- `_build_payload()`: assembles the two-message envelope with `SPEC_VERSION`/`BASIC_CATALOG_ID` from
  `a2ui.core.basic_catalog`
- Module-level `_catalog = BasicCatalog()`, `_schema_validator`, `_validator` (built once, reused)
- Raises `ReportUiGenerationError` if all `MAX_ATTEMPTS` (3) fail
- **Verified live** against both real trips in `data/travel_agent.db`: `my-test-trip-1` (Rostock) → 79 valid
  components after 1 retry; `my-test-trip-2` (Khiva) → 68 valid components after 1 retry

### `app/lib/prompts/generate_report_ui_prompt.txt` ✅ done, uncommitted
- Describes the flat/adjacency-list component model, the 6-component catalog subset with usage guidance,
  the `##`→`Card` / `#`→standalone-`h1` structure mapping, and the mandatory `root`-id requirement
- One worked example (Markdown section → component list) — matches the density of
  `check_report_coverage_prompt.txt`'s worked-example convention

### `app/lib/db/models.py` ✅ done, uncommitted
- `Trip.research_report_ui: Optional[str] = None` added

### `app/lib/db/store.py` ✅ done, uncommitted
- `_init_db()`'s `CREATE TABLE` now includes `research_report_ui TEXT` (for anyone cloning fresh)
- New `update_research_report_ui(trip_id, report_ui) -> Trip | None` setter
- `_row_to_trip()` reads the new column

### `data/travel_agent.db` — live migration already applied
- `ALTER TABLE trips ADD COLUMN research_report_ui TEXT` run directly against the real db (via Python's
  `sqlite3` module — no `sqlite3` CLI binary available in this environment). Both existing trips
  (`my-test-trip-1` Rostock, `my-test-trip-2` Khiva) preserved, `NULL` in the new column since generation
  hasn't been wired into the actual research flow yet.

### `pyproject.toml` / `poetry.lock` — uncommitted
- Only new dependency: `a2ui-core = "^0.1.1"`. Pulled in 4 sub-deps (`jsonschema`, `jsonschema-specifications`,
  `referencing`, `rpds-py`) — nothing else, confirmed via `poetry add` output.

### `app/main.py` — **not yet touched this session**
- Still just has the endpoints from `7ccf178`: `/health`, `/trips`, `/trip/{id}`, `/trip/{id}/messages`,
  `/chat`, `/ws/trip/{trip_id}`. No call to `generate_report_ui` anywhere yet, no `should_generate_ui` param,
  no `GET /trip/{id}/report-ui` endpoint for the frontend to fetch the compiled UI.

### `frontend/` — from `7ccf178`, not touched this session
- No A2UI rendering yet — nothing fetches or renders `research_report_ui`. The chat window / trip selection
  flow is unrelated to this work by design.

---

## Current Position & Next Steps

Immediately next (agreed in conversation, not yet built):
1. Wire `generate_report_ui()` into `run_research()` in `main.py`: after `research_workflow.ainvoke()`
   returns and the report is finalized, call it behind `should_generate_ui: bool = False` (default off),
   forward the real `langfuse_handler` callback via `config`, and persist the result via
   `store.update_research_report_ui(trip.trip_id, result)`.
2. Add a `GET /trip/{id}/report-ui` endpoint so the frontend can fetch the compiled JSON separately from
   `GET /trip/{id}` (which still returns the raw markdown `research_report` for chat-context injection —
   both fields stay, this doesn't replace the markdown column).
3. Frontend: an A2UI JSON renderer component — genuinely not started, no research done yet this session on
   the client-side rendering piece (only the server-side generation). Client capabilities/renderer choice
   (`@a2ui/web_core` or similar, or reading raw component JSON manually) is open.
4. Housekeeping: `CLAUDE.md`'s "Next Steps → Frontend Integration" section is stale (lists shipped gaps as
   open) — worth a cleanup pass whenever that file is next touched.

Not discussed yet: whether `report-ui` generation failures (after all 3 retries exhaust) should surface to
the user somehow, or just log and leave `research_report_ui` as `NULL` (falling back to markdown rendering
client-side). Worth deciding before wiring into `main.py`, since that's the actual failure-handling contract
for the endpoint.

---

# Handoff — 2026-09-02T12:36(session)

## Project Summary

Odysee — same two-graph architecture (chat graph + research graph, one SQLite DB). This session closed out
everything the previous handoff (2026-09-01) left open — A2UI wired into `run_research()`, exposed to the
frontend, rendered live — and then went a step further: **progressive, per-question report rendering**
(cards stream in as each question's research is confirmed by reflection, not one big dump at the end), plus
a real-time UX fix so starting a trip opens the live report panel immediately. Everything in this entry is
**committed** (`ce8e764 "a2ui setup"` = prior session's backend work committed as-is; `75ddcb0 "add
progressively generated ui"` = this session's work). `git status` is clean.

---

## Key Decisions Made

| Decision | Detail |
|---|---|
| Kill `finalize_answer`'s LLM synthesis entirely | Each `web_research` answer is already a complete, sourced, synthesized writeup (confirmed by inspecting real output) — the old final-synthesis call's only unique value was (a) regrouping 10 raw Q&As into themed sections and (b) profile-tailoring. (b) got folded straight into `web_research`'s own prompt (one paragraph, no extra LLM call); (a) was judged not worth an LLM round-trip. `finalize_answer` is now a **deterministic, no-LLM** node that just concatenates `## {question}\n\n{answer}` sections ordered by id. |
| Report UI granularity = one card per question, not one big surface | Each question gets its own independent A2UI surface (`generate_report_ui()` reused unchanged, called once per question with a scoped `surface_id`). `research_report_ui` in the DB changed shape: from one surface's JSON to **a JSON array of `{question_id, surface_id, messages}` section entries**. Clean break, no migration — DB gets wiped between sessions anyway right now. |
| Streaming trigger = reflection-confirmed, never raw `web_research` completion | Explicit user call: showing a card that reflection might still flag for regeneration is bad UX, not an acceptable interim state — never show something that might get silently replaced. This forced a real state-model fix (see below), not just a plumbing change. |
| `web_research_result` reducer fixed: `operator.add` → `merge_by_id` | Pre-existing latent bug: plain list-append meant a regenerated answer sat *next to* its own stale first-round version rather than replacing it, and `should_regenerate` re-judged the whole polluted list every round. New `merge_by_id` reducer (in `state.py`) upserts by `id`. Required for "confirmed" to be well-defined at all. |
| New `confirmed_ids` state field, self-narrowing per round | `should_regenerate` now only judges ids not already in `confirmed_ids`; returns each round's *newly* confirmed ids (not flagged for regen, or reflection cap reached). `regenerate_queries` now preserves the original `id` (was reassigning a fresh local index each round, breaking identity across rounds). |
| DB writes batched per round, not per section | A round confirming several questions at once must not fire concurrent read-modify-write cycles against the same `research_report_ui` row (real lost-update race). `store.append_report_ui_sections()` takes the whole round's sections in one call. Generation itself still runs concurrently (independent Haiku calls); only the persist+broadcast step is what's batched/sequenced. |
| Streaming mechanism | `run_research()` switched from `research_workflow.ainvoke()` to `research_workflow.astream(..., stream_mode="updates")`, consumed as an async generator. Confirmed via direct inspection of LangGraph's `pregel/main.py` that `astream` is a true consumer-paced generator (`yield` sits directly inside the execution loop) — the graph does not run ahead of the consumer in the background. |
| `/start` opens the report panel immediately, not after clicking the trip in the sidebar | User caught this: waiting for the chat response (or worse, requiring a manual sidebar click) before connecting the websocket makes zero sense for "start a trip, watch it build." Fix: `/start`'s `trip_id` is always exactly the current `threadId` — known client-side before the request even completes — so `ChatWindow` fires `onTripStarted(threadId)` immediately on detecting `/start`, opening `ReportPanel`/its websocket right away. |

---

## Current State of Key Files

### `app/agent/research/nodes.py` ✅ done, committed
- `web_research`: now loads `user-profile.json` and tailors emphasis via the prompt; includes `"id"` in its returned result dict (needed for stable identity across regen rounds)
- `should_regenerate`: filters to unconfirmed ids only before judging; returns `confirmed_ids` (this round's newly-cleared ids) alongside `queries_to_regenerate`; hardened against the judge returning an out-of-range `item_index` (drops invalid entries with a warning instead of crashing — this happened for real during testing)
- `regenerate_queries`: preserves original `id` from the flagged entry
- `finalize_answer`: now pure Python, no LLM call — deterministic markdown assembly only
- `Configuration.synthesis_model` removed (orphaned by killing `finalize_answer`'s LLM call)

### `app/agent/research/state.py` ✅ done, committed
- `web_research_result`: `Annotated[list[dict], merge_by_id]` (new reducer, defined in this file)
- New `confirmed_ids: Annotated[list[int], operator.add]`
- `QueryToRegenerate` gained `id: int`

### `app/lib/prompts/web_researcher_prompt.txt` ✅ done, committed
- One added paragraph: tailor emphasis/framing to `{{user_profile}}`

### `app/lib/db/store.py` ✅ done, committed
- `update_research_report_ui()` (single-surface setter) replaced with `append_report_ui_sections(trip_id, sections: list[dict])` — reads current array, upserts each given section by `question_id`, writes back once

### `app/main.py` ✅ done, committed
- `run_research()`: consumes `astream(..., stream_mode="updates")`; caches each `web_research` answer locally by id; on each `should_regenerate` update, generates+broadcasts+persists only that round's newly-`confirmed_ids` (never anything still pending reflection)
- `_generate_and_broadcast_sections()`: generates a round's confirmed cards concurrently (`asyncio.as_completed`), but persists+broadcasts each one the instant *it* finishes rather than waiting for the slowest card in the round
- `_research_status_message()` / the websocket's "trip not found yet" fallback both now carry `"type": "status"`, consistent with the new `"type": "section_ui"` messages
- **Real bug found and fixed this session**: an earlier `Edit` call meant to replace the old batch-then-broadcast implementation with the new per-completion one only replaced the first half — the old implementation was still present below it, so every confirmed section ran through `generate_report_ui` twice. Cost a long, wrong-direction detour through asyncio/LangGraph internals before a full re-read of the function caught it. **Logged in `CLAUDE.md` under a new "Debugging Practice" section and in the auto-memory system (`feedback_debug_check_own_edits_first.md`) — check for self-inflicted leftover/duplicate code before theorizing about deep systemic causes.**

### `frontend/src/lib/useTripWebSocket.ts` ✅ done, committed (new file)
- Opens `ws://localhost:8000/ws/trip/{tripId}`, accumulates `section_ui` messages into a `sections` array (upserted by `question_id`), also parses `report_ui` off any `status` message (covers reconnect-mid-research and already-done trips)

### `frontend/src/components/ReportPanel.tsx` ✅ done, committed
- Reworked to render a *list* of independent surfaces (one `MessageProcessor`/`<A2uiSurface>` per section, sorted by `question_id`), not one shared growing surface. Markdown-fallback path (`markdownToA2ui.ts`) unchanged, still single-surface, still only used when `sections` is empty and a fallback `report` markdown exists.

### `frontend/src/components/ChatWindow.tsx` / `App.tsx` ✅ done, committed
- `ChatWindow` takes `onTripStarted?: (tripId: string) => void`, fires it immediately on detecting `/start` (and again after the response resolves, to trigger a sidebar refresh)
- `App.tsx`: `handleTripStarted` sets `activeTripId` + refreshes `listTrips()`; no more `getTrip()` one-shot fetch — `ReportPanel` is now driven entirely by the websocket hook

### `CLAUDE.md` ✅ done, committed
- New "Debugging Practice" section (see above)
- DB schema / architecture sections updated for the new `research_report_ui` array shape and the progressive-streaming design (worth a final read-through next session to confirm nothing from the pre-progressive-UI description is still lingering as stale)

---

## Verified vs. Not Yet Re-Verified

**Verified this session** (before the two fixes below were applied):
- Full graph logic (`merge_by_id`, `confirmed_ids` threading, reflection cap, deterministic `finalize_answer`) via a direct `astream` smoke test — 10 questions, parallel research, correct confirm/regen/cap behavior, clean final report, zero LLM calls in `finalize_answer`.
- End-to-end through the real FastAPI app + websocket: sections streamed progressively, persisted correctly, all validated against the real A2UI schema validator.
- Frontend rendering in a real headless browser: progressive cards appearing live, zero console errors, StrictMode-safe.

**NOT yet re-verified** (fixed after the above, user was about to test at the point this handoff was triggered):
1. The duplicate-generation bug fix (dead leftover code removed from `_generate_and_broadcast_sections`) — user was restarting the backend to re-test when this handoff fired.
2. The `/start` → immediate-panel-open fix (`onTripStarted`) — implemented but not yet exercised live.

**First thing next session should do**: confirm both fixes actually work end-to-end — start a trip from the chat box, confirm the report panel opens immediately (no sidebar click needed), and confirm each card is generated exactly once (watch for `generate_report_ui` log lines — should be one `attempt=1` per surface per round, not two).

---

## Current Position & Next Steps

Immediate: re-verify the two fixes above with a live run.

Beyond that, nothing is currently blocking — the feature as scoped (progressive report UI + live websocket UX)
is functionally complete pending that re-verification. Known follow-ups, not yet started:

1. **Evals are now stale against the new `web_research` prompt and missing `finalize_answer` output shape**
   (flagged per `CLAUDE.md`'s "Evals depend on frozen fixtures" section, not yet acted on) — `evals/reports/*`
   and `evals/calibration/*` fixtures were captured against the old synthesis-based report shape and the old
   (non-profile-tailored) `web_research` prompt. Check whether they need regenerating before trusting eval
   results against current code.
2. Still nothing for Docker/CI (unrelated to this session, carried over from earlier handoffs, never actually
   started).
3. Not discussed: whether the reflection-cap-reached path (`should_regenerate` giving up and confirming
   everything unconditionally) should surface any indication to the user that a section wasn't fully vetted
   — currently it's silent, renders identically to a normally-confirmed section.
