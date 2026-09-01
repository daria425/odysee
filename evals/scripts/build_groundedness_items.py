"""
Merge evals/calibration/*.md + evals/reports/khiva_2026-10_web_research_result.json +
evals/calibration/planted_claims.json into Langfuse dataset item payloads
({input, expectedOutput, metadata}) for the groundedness judge calibration set.

Usage:
    python evals/scripts/build_groundedness_items.py             # print merged items
    python evals/scripts/build_groundedness_items.py --out FILE  # write JSON to FILE

Uploading to Langfuse is a separate, explicit step -- this script only produces the
payload for review.
"""

import argparse
import json
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent.parent
CALIBRATION_DIR = EVALS_DIR / "calibration"
SOURCES_FIXTURE = EVALS_DIR / "reports" / "khiva_2026-10_web_research_result.json"
PLANTED_CLAIMS_FILE = CALIBRATION_DIR / "planted_claims.json"


def build_items() -> list[dict]:
    sources_data = json.loads(SOURCES_FIXTURE.read_text(encoding="utf-8"))
    web_research_result = sources_data["web_research_result"]
    planted = json.loads(PLANTED_CLAIMS_FILE.read_text(encoding="utf-8"))

    items = []

    genuine_file = planted["genuine_baseline"]
    items.append({
        "id": "genuine",
        "input": {
            "report": (CALIBRATION_DIR / genuine_file).read_text(encoding="utf-8"),
            "web_research_result": web_research_result,
        },
        "expectedOutput": {"planted_claims": []},
        "metadata": {"type": "genuine_baseline", "file": genuine_file},
    })

    for variant in planted["variants"]:
        items.append({
            "id": variant["type"],
            "input": {
                "report": (CALIBRATION_DIR / variant["file"]).read_text(encoding="utf-8"),
                "web_research_result": web_research_result,
            },
            "expectedOutput": {
                "planted_claims": [
                    {"claim": c["claim"], "match_keyword": c["match_keyword"]}
                    for c in variant["planted_claims"]
                ]
            },
            "metadata": {"type": variant["type"], "file": variant["file"], "description": variant["description"]},
        })

    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    items = build_items()

    if args.out:
        Path(args.out).write_text(json.dumps(items, indent=2), encoding="utf-8")
        print(f"Wrote {len(items)} items to {args.out}")
    else:
        print(json.dumps(items, indent=2))


if __name__ == "__main__":
    main()
