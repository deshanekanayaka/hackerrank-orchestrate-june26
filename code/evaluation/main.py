"""Evaluation entry point.

Runs the full pipeline on ``dataset/sample_claims.csv`` (the 20 labelled rows),
compares predictions against the ground-truth labels for the six fields below,
and prints a per-field and overall accuracy report.

Results are written to ``code/evaluation/sample_predictions.csv``. Each row
carries all 14 prediction columns plus one ``expected_<field>`` column per
compared field so mismatches are visible at a glance.

Usage (from repo root):
    python3 code/evaluation/main.py
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

# Allow imports from the sibling code/ directory.
CODE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_DIR))

from dotenv import load_dotenv

load_dotenv()

import agent
import output as output_mod
from utils import load_user_history, load_requirements, resolve_image_paths

# --- Paths (resolved from repo root, two levels up from this file) -----------
REPO_ROOT = CODE_DIR.parent
DATASET_DIR = REPO_ROOT / "dataset"
SAMPLE_CSV = DATASET_DIR / "sample_claims.csv"
USER_HISTORY_CSV = DATASET_DIR / "user_history.csv"
EVIDENCE_REQUIREMENTS_CSV = DATASET_DIR / "evidence_requirements.csv"
OUTPUT_CSV = CODE_DIR / "evaluation" / "sample_predictions.csv"

# Fields the evaluator compares. Order affects the printed report.
COMPARE_FIELDS = [
    "claim_status",
    "severity",
    "issue_type",
    "object_part",
    "evidence_standard_met",
    "valid_image",
]


# --- Evaluation logic ---------------------------------------------------------

def evaluate(
    predictions: list[dict],
    ground_truth: list[dict],
) -> dict[str, dict]:
    """Return per-field match counts keyed by field name, plus an 'overall' key."""
    assert len(predictions) == len(ground_truth)
    n = len(predictions)
    counts: dict[str, int] = {f: 0 for f in COMPARE_FIELDS}
    counts["overall"] = 0

    for pred, gt in zip(predictions, ground_truth):
        all_correct = True
        for field in COMPARE_FIELDS:
            if pred.get(field, "").strip().lower() == gt[field].strip().lower():
                counts[field] += 1
            else:
                all_correct = False
        if all_correct:
            counts["overall"] += 1

    return {
        field: {"correct": counts[field], "total": n, "pct": counts[field] / n * 100}
        for field in [*COMPARE_FIELDS, "overall"]
    }


def print_report(results: dict[str, dict], elapsed: float) -> None:
    print()
    print("=" * 52)
    print("  Evaluation — sample_claims.csv (20 rows)")
    print("=" * 52)
    print(f"  Runtime: {elapsed:.1f}s")
    print()
    print("  Accuracy per field:")
    for field in COMPARE_FIELDS:
        r = results[field]
        print(f"    {field:<25} {r['correct']:>2}/{r['total']}  ({r['pct']:5.1f}%)")
    print()
    r = results["overall"]
    print(f"  Overall (all 6 fields correct): {r['correct']:>2}/{r['total']}  ({r['pct']:5.1f}%)")
    print("=" * 52)
    print()


def build_eval_rows(
    predictions: list[dict], ground_truth: list[dict]
) -> list[dict]:
    """Merge predictions with expected values; mismatches are visible in the CSV."""
    rows = []
    for pred, gt in zip(predictions, ground_truth):
        row = dict(pred)
        for field in COMPARE_FIELDS:
            row[f"expected_{field}"] = gt[field]
            row[f"match_{field}"] = str(
                pred.get(field, "").strip().lower() == gt[field].strip().lower()
            ).lower()
        rows.append(row)
    return rows


def write_eval_csv(eval_rows: list[dict], path: Path) -> None:
    """Write evaluation CSV: all 14 prediction columns + expected_* + match_* columns."""
    base_cols = output_mod.COLUMNS
    extra_cols = [
        col
        for field in COMPARE_FIELDS
        for col in (f"expected_{field}", f"match_{field}")
    ]
    all_cols = base_cols + extra_cols
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=all_cols, extrasaction="ignore")
        writer.writeheader()
        for row in eval_rows:
            writer.writerow({col: row.get(col, "") for col in all_cols})


# --- Entry point --------------------------------------------------------------

def main() -> None:
    history = load_user_history(USER_HISTORY_CSV)
    requirements = load_requirements(EVIDENCE_REQUIREMENTS_CSV)

    ground_truth: list[dict] = []
    input_rows: list[dict] = []
    with SAMPLE_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ground_truth.append(row)
            row = dict(row)
            row["resolved_image_paths"] = resolve_image_paths(
                row.get("image_paths", ""), DATASET_DIR
            )
            input_rows.append(row)

    print(f"Running pipeline on {len(input_rows)} labelled claims ...")
    t0 = time.monotonic()
    predictions: list[dict] = []
    for i, row in enumerate(input_rows, 1):
        print(f"  [{i:>2}/{len(input_rows)}] {row['user_id']} ...", end=" ", flush=True)
        pred = agent.process_claim(row, history, requirements)
        predictions.append(pred)
        print(pred["claim_status"])
    elapsed = time.monotonic() - t0

    results = evaluate(predictions, ground_truth)
    print_report(results, elapsed)

    eval_rows = build_eval_rows(predictions, ground_truth)
    write_eval_csv(eval_rows, OUTPUT_CSV)
    print(f"  Predictions written to {OUTPUT_CSV.relative_to(REPO_ROOT)}")
    print()


if __name__ == "__main__":
    main()
