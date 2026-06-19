"""Terminal entry point.

Reads ``dataset/claims.csv``, runs each row through the agent pipeline, and
writes structured predictions to ``output.csv``. See AGENTS.md §6 for the
evaluable-submission contract.

``load_dotenv()`` is called before importing :mod:`agent` / :mod:`output` so
that ``ANTHROPIC_API_KEY`` is present in the environment before any module that
may construct an Anthropic client at import time.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()  # must run before importing modules that read ANTHROPIC_API_KEY

import csv
from pathlib import Path
from typing import Any

import agent
import output
from utils import load_user_history, load_requirements, resolve_image_paths

# --- Paths (resolved from this file, not the current working directory) ------
ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "dataset"
CLAIMS_CSV = DATASET_DIR / "claims.csv"
USER_HISTORY_CSV = DATASET_DIR / "user_history.csv"
EVIDENCE_REQUIREMENTS_CSV = DATASET_DIR / "evidence_requirements.csv"
OUTPUT_CSV = ROOT / "output.csv"

def main() -> None:
    history = load_user_history(USER_HISTORY_CSV)
    requirements = load_requirements(EVIDENCE_REQUIREMENTS_CSV)

    rows: list[dict[str, Any]] = []
    with CLAIMS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row["resolved_image_paths"] = resolve_image_paths(
                row.get("image_paths", ""), DATASET_DIR
            )
            rows.append(row)

    total = len(rows)
    print(f"Loaded {total} claims. Starting pipeline...", flush=True)

    predictions: list[dict[str, Any]] = []
    for i, row in enumerate(rows, 1):
        bar = "█" * i + "░" * (total - i)
        print(f"\r[{bar}] {i}/{total} {row['user_id']} ({row['claim_object']})", end="", flush=True)
        predictions.append(agent.process_claim(row, history, requirements))

    print()
    output.write(predictions, OUTPUT_CSV)
    print(f"✓ Done — {total} predictions written to output.csv")


if __name__ == "__main__":
    main()
