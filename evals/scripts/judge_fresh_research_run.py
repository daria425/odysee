"""
Run the actual research graph (app/agent/research/graph.py) for a destination, then
immediately run the groundedness judge on its output -- so you can make a change to
the research/synthesis prompts or nodes and directly see whether the resulting report
has more or fewer unsupported claims than before.

This exists because a live /start run only persists the final report text to the trips
table (see run_research() in app/main.py) -- the web_research_result (with per-question
sources) that the judge needs is otherwise discarded once the graph call returns. This
script captures it directly from the graph's return value instead.

Usage (from repo root, via poetry):
    poetry run python -m evals.scripts.judge_fresh_research_run --destination Khiva --travel-date "October 2026"

    # save the report + sources next to the run for later reference/diffing:
    poetry run python -m evals.scripts.judge_fresh_research_run --destination Khiva --travel-date "October 2026" --save-to /tmp/khiva_rerun
"""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

from langfuse.langchain import CallbackHandler  # noqa: E402
from app.agent.research.graph import workflow as research_workflow  # noqa: E402
from evals.lib.groundedness_judge import format_sources, run_judge  # noqa: E402


async def run_research(destination: str, travel_date: str) -> dict:
    langfuse_handler = CallbackHandler()
    thread_id = f"judge-fresh-run-{uuid4()}"
    state = {
        "destination": destination,
        "travel_date": travel_date,
        "search_queries": [],
        "web_research_result": [],
        "sources_gathered": [],
        "report": "",
    }
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [langfuse_handler],
        "metadata": {"langfuse_session_id": thread_id},
    }
    return await research_workflow.ainvoke(state, config)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True)
    parser.add_argument("--travel-date", required=True)
    parser.add_argument("--save-to", type=str, default=None, help="Directory to write report.md + web_research_result.json into")
    args = parser.parse_args()

    print(f"Running research graph for {args.destination} / {args.travel_date}...")
    result = asyncio.run(run_research(args.destination, args.travel_date))
    report = result["report"]
    web_research_result = result["web_research_result"]
    print(f"Done. Report: {len(report)} chars, {len(web_research_result)} web_research_result entries.")

    if args.save_to:
        out_dir = Path(args.save_to)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.md").write_text(report, encoding="utf-8")
        (out_dir / "web_research_result.json").write_text(
            json.dumps({"destination": args.destination, "travel_date": args.travel_date, "web_research_result": web_research_result}, indent=2),
            encoding="utf-8",
        )
        print(f"Saved to {out_dir}/")

    print("\nRunning groundedness judge...")
    sources_text = format_sources(web_research_result)
    judge_result = run_judge(report, sources_text)

    counts = {"supported": 0, "unsupported": 0, "uncertain": 0}
    for c in judge_result.claims:
        counts[c.verdict] += 1

    print("=" * 100)
    print(f"Total claims: {len(judge_result.claims)} | {counts}")
    print("=" * 100)
    for c in judge_result.claims:
        if c.verdict != "supported":
            print(f"[{c.verdict.upper()}] ({c.section}) {c.claim}")
            print(f"    evidence: {c.evidence}")
            print()


if __name__ == "__main__":
    main()
