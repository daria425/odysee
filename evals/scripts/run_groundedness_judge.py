"""
Run the groundedness judge (v1: single combined extract+verify call per report) against
the calibration set in evals/calibration/ -- prints every extracted claim with its verdict
so we can eyeball whether the judge catches the planted lies in planted_claims.json and stays
quiet on the genuine baseline.

Usage (from repo root, via poetry):
    poetry run python -m evals.scripts.run_groundedness_judge
"""

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from evals.lib.groundedness_judge import format_sources, run_judge  # noqa: E402

EVALS_DIR = Path(__file__).parents[1]
CALIBRATION_DIR = EVALS_DIR / "calibration"
REPORTS_DIR = EVALS_DIR / "reports"
SOURCES_FIXTURE = REPORTS_DIR / "khiva_2026-10_web_research_result.json"


def main():
    sources_data = json.loads(SOURCES_FIXTURE.read_text(encoding="utf-8"))
    sources_text = format_sources(sources_data["web_research_result"])

    calibration_files = sorted(CALIBRATION_DIR.glob("khiva_2026-10_*.md"))

    for path in calibration_files:
        print("=" * 100)
        print(path.name)
        print("=" * 100)
        report_text = path.read_text(encoding="utf-8")
        result = run_judge(report_text, sources_text)

        counts = {"supported": 0, "unsupported": 0, "uncertain": 0}
        for c in result.claims:
            counts[c.verdict] += 1

        print(f"Total claims: {len(result.claims)} | {counts}")
        print()

        for c in result.claims:
            if c.verdict != "supported":
                print(f"[{c.verdict.upper()}] ({c.section}) {c.claim}")
                print(f"    evidence: {c.evidence}")
                print()


if __name__ == "__main__":
    main()
