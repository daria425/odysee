# Vacation Software Factory — Task Backlog

Worked top to bottom, one (occasionally two, if the first is blocked) unchecked task per daily
run, by the cloud routine on this branch (`automation/vacation-sprint`). See
`.claude/factory-changelog.md` for the run-by-run log.

Rules for the daily agent (see routine prompt for the full version):

- Never touch `master` directly, never force-push.
- A task is only `[x]` if its "Done means" criterion is actually true.
- If genuinely blocked after reasonable effort, leave it unchecked and add a `BLOCKED: <reason>`
  line under it instead of forcing a checkmark.

---

- [ ] **1. Housekeeping + pipeline validation**
      Clean up `CLAUDE.md`'s "Next Steps → Still open" section — Docker (`Dockerfile`,
      `frontend/Dockerfile`, `docker-compose.yml`) and CI (`.github/workflows/build.yml`) already
      shipped in `67a97ab` ("build setup") but the doc still lists them as open gaps. Also confirm
      `docker-compose.yml`'s `./data:/app/data` volume actually persists `data/travel_agent.db`
      across a container recreation (`docker compose down && up`), and that `poetry run pytest` /
      `cd frontend && npm run lint && npm run build` are green as a baseline.
      Done means: `CLAUDE.md` no longer describes shipped work as open, volume persistence confirmed
      (or a real gap documented), pytest + frontend lint/build green.

- [ ] **2. Evals refresh**
      Per `CLAUDE.md`'s "Evals depend on frozen fixtures" section: `evals/reports/*` and
      `evals/calibration/*` were captured 2026-09-01, before `75ddcb0` (2026-09-02) changed the
      `web_research` prompt and made `finalize_answer` deterministic (no more LLM synthesis step).
      Check whether the fixtures are actually stale/unrepresentative of current graph output; if so,
      regenerate from a fresh graph run and re-run the relevant `evals/scripts/*` experiments.
      Document what changed and why (or why the old fixtures were still valid, if they turn out to be).
      Done means: fixtures confirmed current (regenerated if not), eval scripts run clean against them,
      findings recorded in the changelog.

- [ ] **3. Frontend design polish pass**
      Visual-only pass over `frontend/src/components/{Sidebar,ChatWindow,ReportPanel}.tsx` and
      `frontend/src/index.css` — use the `ui-ux-pro-max` skill. Explicitly scoped to styling/layout
      only — no changes to component logic, data flow, or props.
      Key Tasks:
  - Use Three.js/React-Three to create a 3D background in the report panel. Reference is located in /home/daria/projects/orchestrator-worker-travel-agent/.claude/references/three-js-ref.jpeg. This has a translucent white overlay (~70%) + blur for a glass effect and readability of report cards.
  - Use react framer for smooth progressive rendering of report cards. Once data is available each card should float upwards rather than jump at the user.

  Done means: `npm run lint` + `npm run build` still green, before/after noted in the changelog. Screenshots as evidence once complete.

- [ ] **4. Trip comparison mode**
      New endpoint (e.g. `GET /trips/compare?ids=<id1>,<id2>,...`) making a request to claude sonnet with user profile to compare trips side by side: destinations, dates, and comparable facts pulled out of each
      trip's `research_report` / `research_report_ui` (e.g. budget range, safety notes — whatever's
      reliably extractable without a new LLM call, or a small structured-output call if needed,
      following the existing `check_report_coverage`/`log_memory` pattern in `app/agent/chat/nodes.py`
      for cheap-model structured calls).
      This is then sent through alongside the user profile and past trip reviews (trimmed to location + date, rating and text review limmited to 2 most recent for simplicity, full support to be added in task 5) if available as a request to Claude using existing patterns to help the user decide which trip would be best. Initial comparison is returned to the frontend after which user is able to ask follow up questions and ponder their decision, mirroring the agent/chat/ pattern.
      Link in sidebar to enter compare mode directly
      User is also able to enter compare mode using "/compare | <destination 1>, <destination 2>, ... <destination n> | some date" e.g "/compare | Berlin, Amsterdam | October 2026"

      Note: task 5 (below) is what adds review/rating columns to the db, and this task comes
      before it in the backlog — so when this task is implemented, no trip has review data yet.
      Handle that gracefully (empty/no reviews is a normal case, not an error) rather than
      assuming the columns exist.

      Done means:
      - `GET /trips/compare?ids=...` tested (pytest), returns comparable facts for 2+ real trips
        in `data/travel_agent.db`, and doesn't error when a trip has no review data yet.
      - The Sonnet call includes user profile + extracted comparable facts + trimmed past reviews
        (when present) and returns an initial comparison grounded in that data (no fabricated
        specifics — spot-check against the source reports).
      - Frontend: sidebar entry point into compare mode; side-by-side comparison view renders the
        initial response; follow-up chat works against the same comparison context (mirrors
        `app/agent/chat/` request/response pattern, not a new one-off).
      - `/compare | <dest1>, <dest2>, ... | <date>` is parsed and routes into compare mode the
        same way `/start` is parsed today.
      - `poetry run pytest` and `cd frontend && npm run lint && npm run build` green.

- [ ] **5. Trip review and memory**
      New endpoint (e.g. `POST /trips/review?ids=<id1>,<id2>,...`) makes a post request and adds 2 fields to an existing trip in the db: Review (TEXT) and Rating (INT out of 10)
      Link in sidebar to enter review mode directly which opens a form with the folloing inputs: 1. Dropdown of existing trips (select 1 to review so that we can match) 2. Text area for writing a review 3. Numerical slider for review rating
      Everything necessary to support adding reviews on the data storage side completed

      Note: the form picks exactly one trip to review, so the endpoint likely wants a single
      `trip_id` rather than plural `ids=` — flagging in case that param name/shape was intentional
      for a different use case; otherwise treat this as a single-trip review endpoint.

      Done means:
      - `trips` gains `review TEXT` and `rating INTEGER` columns via a non-destructive
        `ALTER TABLE` (matching the precedent set for `research_report_ui` in
        `app/lib/db/store.py`'s `_init_db()`/migration history) — existing trip rows/data
        untouched, `Trip` model + `_row_to_trip()` updated to match.
      - `POST /trips/review` (or whatever the finalized single-trip shape is) tested (pytest),
        writes review + rating (0–10) against a real trip, rejects an unknown trip id.
      - Sidebar entry point opens a form: trip dropdown (populated from real trips), textarea,
        0–10 slider; submitting it round-trips to the db and is reflected back in the UI.
      - A trip reviewed this way is correctly picked up by task 4's comparison endpoint (trimmed
        to location/date/rating/text, most recent 2) — verify by reviewing a trip and re-running
        a compare call against it.
      - `poetry run pytest` and `cd frontend && npm run lint && npm run build` green.
