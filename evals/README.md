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
| tricky_negative | 7 |
| straightforward_positive | 5 |
| straightforward_negative | 4 |
| tricky_positive | 2 |
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
