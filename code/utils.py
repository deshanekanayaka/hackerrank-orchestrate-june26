"""Shared CSV loaders used by both main.py and evaluation/main.py.

No side effects at import time: no file reads, no load_dotenv, no global state.
"""

from __future__ import annotations

import csv
from pathlib import Path

_ALL_OBJECTS = "all"


def load_user_history(path: Path) -> dict[str, dict[str, str]]:
    """Load ``user_history.csv`` into a dict keyed by ``user_id``."""
    history: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            history[row["user_id"]] = row
    return history


def load_requirements(path: Path) -> dict[str, list[dict[str, str]]]:
    """Load ``evidence_requirements.csv`` keyed by ``claim_object``.

    Rows scoped to ``all`` are folded into every object's requirement list so
    that the evidence gate sees both the general and object-specific rules.
    """
    by_object: dict[str, list[dict[str, str]]] = {}
    general: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            obj = row["claim_object"]
            if obj == _ALL_OBJECTS:
                general.append(row)
            else:
                by_object.setdefault(obj, []).append(row)
    for obj in by_object:
        by_object[obj] = general + by_object[obj]
    by_object[_ALL_OBJECTS] = general
    return by_object


def resolve_image_paths(raw: str, dataset_dir: Path) -> list[str]:
    """Split the ``;``-separated image paths and prepend ``dataset/``.

    Blank entries are dropped; an empty/blank field yields an empty list so the
    evidence gate can fail the claim deterministically instead of erroring.
    """
    paths: list[str] = []
    for part in (raw or "").split(";"):
        rel = part.strip()
        if rel:
            paths.append(str(dataset_dir / rel))
    return paths
