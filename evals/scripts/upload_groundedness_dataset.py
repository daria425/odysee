"""
Upsert the groundedness calibration set (evals/calibration/*.md + planted_claims.json)
into the Langfuse dataset "groundedness_calibration" via the langfuse-cli. Items are
upserted by id, so re-running after editing the calibration set is safe.

Requires LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL in the
environment (e.g. `set -a && source .env && set +a` first) and npx on PATH.

Usage:
    python evals/scripts/upload_groundedness_dataset.py

The dataset itself ("groundedness_calibration") must already exist in Langfuse --
create it once via:
    npx langfuse-cli api datasets create --body-json '{"name": "groundedness_calibration"}'
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_groundedness_items import build_items  # noqa: E402

DATASET_NAME = "groundedness_calibration"


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
