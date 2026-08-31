"""
Upsert evals/datasets/check_report_coverage.json into the Langfuse dataset
"check_report_coverage" via the langfuse-cli. Items are upserted by id, so
re-running after editing datasets/check_report_coverage.json is safe.

Requires LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL in the
environment (e.g. `set -a && source .env && set +a` first) and npx on PATH.

Usage:
    python evals/scripts/upload_check_report_coverage.py

The dataset itself ("check_report_coverage") must already exist in Langfuse --
create it once via:
    npx langfuse-cli api datasets create --body-json '{"name": "check_report_coverage"}'
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_check_report_coverage_items import build_items  # noqa: E402

DATASET_NAME = "check_report_coverage"

# Real traces two items were drawn from -- links the dataset item back to its
# source trace/observation in the Langfuse UI.
SOURCE_TRACES = {
    "neg-trace-techno-events": {
        "traceId": "df7be503bede21004798c07d47cb5ec5",
        "observationId": "cd19f6a7e4d4d8ee",
    },
    "pos-trace-hotel-price": {
        "traceId": "f9c2587862b6e44ec9b7122d7b12702a",
        "observationId": "2f671ad434f05532",
    },
}


def main() -> None:
    items = build_items()
    failures = []

    for item in items:
        payload = {
            "datasetName": DATASET_NAME,
            "id": item["id"],
            "input": item["input"],
            "expectedOutput": item["expectedOutput"],
            "metadata": item["metadata"],
        }
        if item["id"] in SOURCE_TRACES:
            payload["sourceTraceId"] = SOURCE_TRACES[item["id"]]["traceId"]
            payload["sourceObservationId"] = SOURCE_TRACES[item["id"]]["observationId"]

        result = subprocess.run(
            ["npx", "langfuse-cli", "api", "dataset-items", "create", "--body-file", "-"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or "error" in result.stdout:
            failures.append(item["id"])
            print(f"FAIL: {item['id']}\n{result.stdout}\n{result.stderr}")
        else:
            print(f"OK: {item['id']}")

    print(f"\n{len(items) - len(failures)}/{len(items)} items upserted")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
