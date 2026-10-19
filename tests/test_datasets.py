import json

from app.config import EDGE_CASES_PATH
from app.datasets import load_dataset, load_edge_cases, locate_spans


def test_locate_spans_handles_repeated_values():
    text = "Ana called. Ana again."
    spans = locate_spans(text, [{"type": "PERSON", "value": "Ana"}, {"type": "PERSON", "value": "Ana"}])
    assert [(s.start, s.end) for s in spans] == [(0, 3), (12, 15)]


def test_locate_spans_skips_values_not_in_text():
    assert locate_spans("hello", [{"type": "PERSON", "value": "Bob"}]) == []


def test_every_edge_case_label_is_found_in_its_text():
    """Data integrity: a typo in a label would silently shrink the test set."""
    raw = json.loads(EDGE_CASES_PATH.read_text(encoding="utf-8"))
    for case in raw["cases"]:
        for item in case["pii"]:
            assert item["value"] in case["text"], f"{item['value']!r} not in {case['text']!r}"


def test_edge_cases_load():
    samples = load_edge_cases()
    assert len(samples) >= 20
    assert all(s.source == "edge_case" for s in samples)


def test_unknown_dataset_raises():
    try:
        load_dataset("nope")
    except ValueError as exc:
        assert "Unknown dataset" in str(exc)
    else:
        raise AssertionError("expected ValueError")
