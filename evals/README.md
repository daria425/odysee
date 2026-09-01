# Evals

Eval datasets and tooling for the orchestrator-worker travel agent, backed by Langfuse Datasets/Experiments.

## Structure

```
evals/
  reports/     -- trip report fixtures shared across dataset items
  datasets/    -- hand/AI-authored dataset items (source of truth, git-tracked, human-reviewable)
  scripts/     -- build scripts that merge datasets/ + reports/ into Langfuse item payloads
```

`datasets/*.json` stays free of the full report text so items are small and diffable; `scripts/build_*.py`
merges in the report fixture to produce the actual `{input, expectedOutput, metadata}` payload Langfuse expects.

## check_report_coverage

`datasets/check_report_coverage.json` -- eval set for the `check_report_coverage` node
(`app/agent/chat/nodes.py`), which decides whether a precomputed trip report already contains the specific
fact a follow-up question needs. False positives (`covered=true` when the report only mentions the topic,
not the specific data point) are the priority failure mode -- they silently skip the live-search fallback
and give the user a shallow, unflagged answer.

20 items, all built on one real report (`reports/rostock_2026-10.md`), weighted toward tricky negatives
(topic mentioned, specific fact missing):

| category | count |
|---|---|
| tricky_negative | 6 |
| straightforward_positive | 5 |
| straightforward_negative | 4 |
| tricky_positive | 3 |
| edge_off_topic | 2 |

2 of the 20 items (`neg-trace-techno-events`, `pos-trace-hotel-price`) are taken verbatim from real
`check_report_coverage` Langfuse traces; the rest are synthetic, written against the same report so
ground truth can be checked directly against its text.

Status: reviewed and **live in Langfuse** as dataset `check_report_coverage` (20/20 items).

To preview the merged payload without uploading:

```bash
python evals/scripts/build_check_report_coverage_items.py
```

To (re-)upload after editing `datasets/check_report_coverage.json` (items upsert by id, safe to re-run):

```bash
set -a && source .env && set +a
python evals/scripts/upload_check_report_coverage.py
```

Running it as a Langfuse Experiment against the actual `check_report_coverage` node is the next step,
not yet implemented here.

## groundedness (in progress)

Judge for the research graph's synthesis steps (`web_research`, `finalize_answer`) -- checks whether report
claims are actually supported by the raw Tavily content they were synthesized from, not just plausible-sounding.
Prioritized over a completeness eval per the "does it lie?" > "is it comprehensive?" ordering.

`reports/khiva_2026-10.md` + `reports/khiva_2026-10_web_research_result.json` -- golden fixture pulled from a
real research graph run (Langfuse trace `7e29c73b8eeba1efdaed408bd2495262`, 2026-09-01), the first run captured
since `web_research` started attaching `sources: [{url, title, content}]` per question (see
`app/agent/research/nodes.py`). The JSON preserves every `web_research_result` entry across all reflection
rounds (10 unique key questions, 19 entries total -- 3 questions got 4 attempts each via reflection, the rest 1)
in the order `finalize_answer` actually consumed them -- duplicates across rounds are real, not a fixture bug,
since `web_research_result` accumulates via an `operator.add` reducer and `finalize_answer` joins over the full
list. (Pulling this required `--all` pagination on `langfuse-cli api observations list` -- the trace has 68
observations and a bare `--limit 50` silently truncates to 3 questions worth of nodes.)

`calibration/` -- hand-crafted calibration set built from the Khiva fixture, to prove the judge actually
catches lies before it's trusted on live reports:

| file | type | planted claims |
|---|---|---|
| `khiva_2026-10_genuine.md` | baseline (unmodified) | 0 -- judge should flag nothing as unsupported |
| `khiva_2026-10_variant_numeric_swap.md` | numeric swap | 4 -- real sourced numbers (distance, transfer price, venue hours, SIM cost) replaced with different plausible numbers |
| `khiva_2026-10_variant_fabricated.md` | fabrication | 4 -- confident, specific claims added that appear in no source (night bus, safety survey stat, a whole invented venue, an invented eSIM plan) |
| `khiva_2026-10_variant_inverted.md` | inversion | 4 -- real sourced claims flipped to their opposite (Uber/Bolt availability, Khiva's club scene, CMI Bar's days, card acceptance) |

`calibration/planted_claims.json` is the ground-truth manifest -- each entry names the section, the planted
claim text, and (for swaps/inversions) the original text plus which `web_research` source answer it
contradicts. Judge calibration = run the judge against all 4 files, confirm it flags every entry in
`planted_claims.json` and flags nothing extra on the genuine baseline.

`evals/lib/groundedness_judge.py` -- the judge itself. v1 architecture: **one combined call per report**
(not one call to extract + N calls to verify) -- report and all `web_research` source content go into a single
structured-output Sonnet call that both extracts claims and verifies each against the sources in one pass.
Chosen for calibration-iteration speed over the two-pass design; revisit if a report grows large enough that
one call starts skipping claims. Prompt: `evals/prompts/groundedness_judge_prompt.txt`.

**This judge is not wired into the app** -- it only runs via the scripts below, against the frozen
`evals/calibration/` fixture. It does not re-run the research graph and does not automatically catch
regressions from changes to `app/agent/research/nodes.py` -- see the CLAUDE.md section on eval fixture
staleness.

Status: **calibrated, recall 1.000** (12/12 planted claims caught across the 3 variants) as of the
`groundedness_calibration_2026_09_01` run. One soft miss during calibration -- the card-acceptance inversion
was scored `uncertain` instead of `unsupported` -- was fixed by tightening the prompt's unsupported-vs-uncertain
rule to also cover absolute/confident qualifiers ("excellent," "everywhere") asserted with no source backing,
not just invented numbers/names. Bonus finding: the judge also flagged a real, unplanted hallucination in the
genuine baseline (`"mid-range travel runs approximately $260-290/day"` -- no source supports that figure) --
consistent across every run, a good sign of stability at `temperature=0`.

Live in Langfuse as dataset `groundedness_calibration` (4 items: genuine + 3 variants).

To preview the merged payload without uploading:

```bash
python evals/scripts/build_groundedness_items.py
```

To (re-)upload after editing `calibration/planted_claims.json` or the calibration `.md` files:

```bash
set -a && source .env && set +a
python evals/scripts/upload_groundedness_dataset.py
```

To run the judge standalone (prints every non-supported claim, no Langfuse dataset needed):

```bash
poetry run python -m evals.scripts.run_groundedness_judge
```

To run it as a Langfuse Experiment (recall against `planted_claims.json`, keyword-matched since the judge
paraphrases claims):

```bash
set -a && source .env && set +a
poetry run python -m evals.scripts.run_groundedness_experiment
```

To run the judge against a **fresh** research graph run -- for checking whether a change to
`app/agent/research/nodes.py` made groundedness better or worse, since a live `/start` run only persists the
final report text and discards `web_research_result`/sources once `run_research()` returns:

```bash
set -a && source .env && set +a
poetry run python -m evals.scripts.judge_fresh_research_run --destination "Khiva" --travel-date "October 2026"
# optionally: --save-to <dir>  to keep the report + sources from that specific run
```

This re-runs the real graph (not the calibration fixture) and judges its actual output -- no fixed expected
output here, so there's nothing to score; read the printed unsupported/uncertain counts and compare against a
prior run's output to judge better/worse. Confirmed working end to end: a fresh Khiva run produced a
different report than the calibration fixture (34 claims, 2 unsupported, 2 uncertain) and the judge caught two
more real, previously-unseen hallucinations (a wrong airport distance, a wrong ticket price range).

Parked: completeness eval, after groundedness is trustworthy on live reports.
