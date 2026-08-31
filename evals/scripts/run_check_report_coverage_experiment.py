"""
Run the check_report_coverage eval dataset (Langfuse dataset "check_report_coverage")
as a Langfuse Experiment against the real check_report_coverage node
(app/agent/chat/nodes.py) -- no reimplementation of the node's logic.

The node reads the trip's report from MemoryStore via config["configurable"]["thread_id"],
not from graph state directly. So per dataset item, this script spins up a throwaway
trip (in a temp sqlite db, one per run) with research_report set to the item's report,
then calls the real node with a minimal state/config -- just enough plumbing for the node
to run unmodified.

Usage (from repo root, via poetry so the langfuse 4.x SDK is available):
    poetry run python evals/scripts/run_check_report_coverage_experiment.py
"""

import tempfile
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

load_dotenv()

from langfuse import Evaluation  # noqa: E402
from app.lib.langfuse_client import lf  # noqa: E402
from app.lib.db.store import MemoryStore  # noqa: E402
from app.lib.db.models import Trip  # noqa: E402
from app.agent.chat.nodes import make_check_report_coverage  # noqa: E402

DATASET_NAME = "check_report_coverage"


def make_task(store: MemoryStore):
    check_report_coverage = make_check_report_coverage(store)

    def task(*, item, **kwargs):
        report = item.input["report"]
        question = item.input["question"]

        store.create_trip(Trip(
            trip_id=item.id,
            name="eval",
            destinations=["eval"],
            research_status="done",
            research_report=report,
        ))

        state = {"messages": [HumanMessage(content=question)]}
        config = {"configurable": {"thread_id": item.id}}
        result = check_report_coverage(state, config)
        return {"covered": result["report_covered"]}

    return task


def correct_evaluator(*, output, expected_output, **kwargs):
    is_correct = output["covered"] == expected_output["covered"]
    return Evaluation(name="correct", value=1.0 if is_correct else 0.0)


def false_positive_evaluator(*, output, expected_output, **kwargs):
    is_false_positive = expected_output["covered"] is False and output["covered"] is True
    return Evaluation(name="false_positive", value=1.0 if is_false_positive else 0.0)


def accuracy_run_evaluator(*, item_results, **kwargs):
    scores = [e.value for r in item_results for e in r.evaluations if e.name == "correct"]
    accuracy = sum(scores) / len(scores) if scores else None
    return Evaluation(name="accuracy", value=accuracy, comment=f"{sum(scores):.0f}/{len(scores)} correct")


def false_positive_rate_run_evaluator(*, item_results, **kwargs):
    scores = [e.value for r in item_results for e in r.evaluations if e.name == "false_positive"]
    rate = sum(scores) / len(scores) if scores else None
    return Evaluation(name="false_positive_rate", value=rate, comment=f"{sum(scores):.0f}/{len(scores)} false positives")


def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = MemoryStore(db_path=Path(tmp_dir) / "eval.db")

        dataset = lf.get_dataset(DATASET_NAME)
        run_name = f"{DATASET_NAME}_{date.today():%Y_%m_%d}"

        result = dataset.run_experiment(
            name=run_name,
            description="Accuracy + false-positive rate of check_report_coverage against evals/datasets/check_report_coverage.json",
            task=make_task(store),
            evaluators=[correct_evaluator, false_positive_evaluator],
            run_evaluators=[accuracy_run_evaluator, false_positive_rate_run_evaluator],
        )

        print(result.format())


if __name__ == "__main__":
    main()
