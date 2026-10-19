"""Load the datasets the evaluator can run on.

Two datasets:
* "synthetic": generated on the fly from templates (app/generator.py).
* "edge_cases": hard, hand-picked or LLM-generated cases stored in
  data/edge_cases.json. These are the formats real callers use that
  pattern-based redactors tend to miss ("four one one one...", "john at
  gmail dot com").

Edge cases are stored in a human-friendly format: the text plus a list of
{type, value} pairs. Character positions are worked out here when loading, so
nobody has to count characters by hand (and an LLM doesn't have to either).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import EDGE_CASES_PATH
from app.generator import generate_samples
from app.models import Sample, Span

DATASETS = ("synthetic", "edge_cases")


def locate_spans(text: str, pii: list[dict]) -> list[Span]:
    """Find where each {type, value} appears in text.

    Repeated values are matched left to right, so the same value listed twice
    maps to two different positions. Values that can't be found are skipped.
    """
    spans: list[Span] = []
    search_from: dict[str, int] = {}
    for item in pii:
        value = item["value"]
        start = text.find(value, search_from.get(value, 0))
        if start == -1:
            continue
        search_from[value] = start + len(value)
        spans.append(Span(start, start + len(value), item["type"]))
    return spans


def load_edge_cases(path: Path = EDGE_CASES_PATH) -> list[Sample]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    samples = []
    for case in raw.get("cases", []):
        spans = locate_spans(case["text"], case.get("pii", []))
        samples.append(Sample(text=case["text"], spans=spans, source="edge_case", note=case.get("note", "")))
    return samples


def load_dataset(name: str, n: int = 200, seed: int = 42) -> list[Sample]:
    if name == "synthetic":
        return generate_samples(n=n, seed=seed)
    if name == "edge_cases":
        return load_edge_cases()
    raise ValueError(f"Unknown dataset {name!r}. Choose one of {DATASETS}.")
