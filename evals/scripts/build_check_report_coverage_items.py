"""
Merge evals/datasets/check_report_coverage.json + its report fixture into
Langfuse dataset item payloads ({input, expectedOutput, metadata}).

Usage:
    python evals/scripts/build_check_report_coverage_items.py            # print merged items
    python evals/scripts/build_check_report_coverage_items.py --out FILE  # write JSON to FILE

Uploading to Langfuse is a separate, explicit step (see evals/README.md) --
this script only produces the payload for review.
"""

import argparse
import json
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent.parent
DATASET_FILE = EVALS_DIR / "datasets" / "check_report_coverage.json"


def build_items() -> list[dict]:
    dataset = json.loads(DATASET_FILE.read_text())
    report = (EVALS_DIR / "reports" / f"{dataset['report_ref']}.md").read_text()

    items = []
    for item in dataset["items"]:
        items.append(
            {
                "id": item["id"],
                "input": {"report": report, "question": item["question"]},
                "expectedOutput": {"covered": item["expected_covered"]},
                "metadata": {
                    "category": item["category"],
                    "source": item["source"],
                    "notes": item["notes"],
                },
            }
        )
    return items


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    merged = build_items()
    output = json.dumps(merged, indent=2)

    if args.out:
        args.out.write_text(output)
        print(f"Wrote {len(merged)} items to {args.out}")
    else:
        print(output)
