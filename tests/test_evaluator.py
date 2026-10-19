"""Unit tests for the scoring logic, using fake redactors so they run instantly."""

import pytest

from app.evaluator import evaluate, match_spans
from app.models import Sample, Span

TEXT = "Call Jane at 212-555-0147 or jane@example.com"
GOLD = [Span(5, 9, "PERSON"), Span(13, 25, "PHONE_NUMBER"), Span(29, 45, "EMAIL_ADDRESS")]
SAMPLES = [Sample(TEXT, GOLD)]


class FakeRedactor:
    name = "fake"

    def __init__(self, spans):
        self.spans = spans

    def detect(self, text):
        return self.spans


def test_perfect_detector_scores_100_percent():
    report = evaluate(FakeRedactor(GOLD), SAMPLES).to_dict()
    assert report["overall"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 3, "fp": 0, "fn": 0}


def test_detector_that_finds_nothing_has_zero_recall():
    report = evaluate(FakeRedactor([]), SAMPLES).to_dict()
    assert report["overall"]["recall"] == 0.0
    assert report["overall"]["fn"] == 3
    assert {m["value"] for m in report["misses"]} == {"Jane", "212-555-0147", "jane@example.com"}


def test_partial_overlap_with_right_type_counts_as_found():
    tps, fns, fps = match_spans(GOLD, [Span(14, 25, "PHONE_NUMBER")])
    assert len(tps) == 1 and not fps


def test_wrong_type_is_a_miss_and_a_false_alarm():
    tps, fns, fps = match_spans([Span(13, 25, "PHONE_NUMBER")], [Span(13, 25, "DATE_TIME")])
    assert not tps and len(fns) == 1 and len(fps) == 1


def test_duplicate_detection_is_not_a_false_alarm():
    preds = [Span(13, 25, "PHONE_NUMBER"), Span(14, 25, "PHONE_NUMBER")]
    tps, fns, fps = match_spans([Span(13, 25, "PHONE_NUMBER")], preds)
    assert len(tps) == 1 and not fps


def test_precision_and_recall_math():
    preds = [Span(5, 9, "PERSON"), Span(0, 4, "PERSON")]  # 1 right, 1 wrong; phone/email missed
    report = evaluate(FakeRedactor(preds), SAMPLES).to_dict()
    person = next(t for t in report["per_type"] if t["entity_type"] == "PERSON")
    assert person["precision"] == 0.5
    assert person["recall"] == 1.0
    assert person["f1"] == pytest.approx(0.6667, abs=1e-4)
    assert report["overall"]["recall"] == pytest.approx(1 / 3, abs=1e-4)


def test_unscored_types_are_ignored():
    preds = GOLD + [Span(0, 4, "US_PASSPORT")]
    report = evaluate(FakeRedactor(preds), SAMPLES).to_dict()
    assert report["overall"]["fp"] == 0
