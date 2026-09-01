"""
Run the groundedness_calibration Langfuse dataset as an Experiment against the real
groundedness judge (evals/lib/groundedness_judge.py) -- no reimplementation of the
judge's logic.

Per item, the judge does a single combined extract+verify call over the item's report
+ raw web_research sources. Item evaluator checks recall against the item's planted
claims (matched by keyword substring, not exact text, since the judge paraphrases).
There's no precision/false-positive check against a fixed expected set here -- unlike
check_report_coverage, a report can contain real, unplanted hallucinations (see the
genuine baseline's $260-290/day figure) that are correct catches, not noise. Extra
unsupported/uncertain claims are printed for manual review, not scored.

Usage (from repo root, via poetry so the langfuse 4.x SDK is available):
    poetry run python -m evals.scripts.run_groundedness_experiment
"""

from datetime import date

from dotenv import load_dotenv

load_dotenv()

from langfuse import Evaluation  # noqa: E402
from app.lib.langfuse_client import lf  # noqa: E402
from evals.lib.groundedness_judge import format_sources, run_judge  # noqa: E402

DATASET_NAME = "groundedness_calibration"


def task(*, item, **kwargs):
    report = item.input["report"]
    sources_text = format_sources(item.input["web_research_result"])
    result = run_judge(report, sources_text)
    return {
        "claims": [
            {"claim": c.claim, "section": c.section, "verdict": c.verdict, "evidence": c.evidence}
            for c in result.claims
        ]
    }


def recall_evaluator(*, output, expected_output, **kwargs):
    planted_claims = expected_output["planted_claims"]
    if not planted_claims:
        return None  # genuine baseline has nothing planted to recall

    flagged = [c for c in output["claims"] if c["verdict"] != "supported"]
    matched = sum(
        1 for pc in planted_claims
        if any(pc["match_keyword"].lower() in c["claim"].lower() for c in flagged)
    )
    return Evaluation(
        name="recall",
        value=matched / len(planted_claims),
        comment=f"{matched}/{len(planted_claims)} planted claims caught",
    )


def genuine_unsupported_evaluator(*, output, metadata=None, **kwargs):
    if not metadata or metadata.get("type") != "genuine_baseline":
        return None
    unsupported = [c for c in output["claims"] if c["verdict"] == "unsupported"]
    return Evaluation(
        name="genuine_unsupported_count",
        value=len(unsupported),
        comment="; ".join(c["claim"] for c in unsupported) or "none",
    )


def recall_run_evaluator(*, item_results, **kwargs):
    scores = [e.value for r in item_results for e in r.evaluations if e.name == "recall" and e.value is not None]
    recall = sum(scores) / len(scores) if scores else None
    return Evaluation(name="mean_recall", value=recall, comment=f"across {len(scores)} variants with planted claims")


def main():
    dataset = lf.get_dataset(DATASET_NAME)
    run_name = f"{DATASET_NAME}_{date.today():%Y_%m_%d}"

    result = dataset.run_experiment(
        name=run_name,
        description="Groundedness judge (v1, single combined call) recall against evals/calibration/planted_claims.json",
        task=task,
        evaluators=[recall_evaluator, genuine_unsupported_evaluator],
        run_evaluators=[recall_run_evaluator],
    )

    print(result.format())


if __name__ == "__main__":
    main()
