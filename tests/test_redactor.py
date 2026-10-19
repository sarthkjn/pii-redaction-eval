"""Integration tests that run the real Presidio engines.

The last two tests are quality gates: if a code change makes the improved
engine worse, CI fails before the change is merged.
"""

from app.datasets import load_dataset
from app.evaluator import evaluate


def test_baseline_finds_common_pii(baseline):
    text = "Email jane.doe@example.com or call 212-555-0147."
    types = {s.entity_type for s in baseline.detect(text)}
    assert {"EMAIL_ADDRESS", "PHONE_NUMBER"} <= types


def test_redact_replaces_values_with_placeholders(baseline):
    out = baseline.redact("My email is jane.doe@example.com")
    assert "jane.doe@example.com" not in out
    assert "<EMAIL_ADDRESS>" in out


def test_improved_catches_what_baseline_misses(baseline, improved):
    text = "Use my Mastercard 2223 0031 2200 3222, email priya dot shah at gmail dot com"
    base_types = {s.entity_type for s in baseline.detect(text)}
    impr_types = {s.entity_type for s in improved.detect(text)}
    assert "CREDIT_CARD" not in base_types
    assert {"CREDIT_CARD", "EMAIL_ADDRESS"} <= impr_types


def test_quality_gate_synthetic(improved):
    report = evaluate(improved, load_dataset("synthetic", n=200)).to_dict()
    assert report["overall"]["recall"] >= 0.95
    assert report["overall"]["precision"] >= 0.90


def test_quality_gate_improved_beats_baseline_on_edge_cases(baseline, improved):
    samples = load_dataset("edge_cases")
    base = evaluate(baseline, samples).to_dict()["overall"]
    impr = evaluate(improved, samples).to_dict()["overall"]
    assert impr["recall"] > base["recall"]
    assert impr["f1"] > base["f1"]
