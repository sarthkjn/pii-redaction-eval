"""Redaction engines behind one small interface.

Every engine has the same two methods:
    detect(text) -> list[Span]   find PII
    redact(text) -> str          replace PII with placeholders like <EMAIL_ADDRESS>

The evaluator, API and dashboard only use those two methods, so engines can be
swapped or compared freely.

Engines
-------
* PresidioRedactor ("baseline"): Microsoft Presidio with default recognizers.
* ImprovedRedactor ("improved"): the baseline plus custom recognizers
  (app/recognizers.py) and a conflict-resolution step that removes known
  false-alarm patterns. Every change targets a failure the evaluator found.
"""

from __future__ import annotations

import re
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

from app.config import DEFAULT_SCORE_THRESHOLD, ENTITY_TYPES, SPACY_MODEL
from app.models import Span
from app.recognizers import custom_recognizers


@lru_cache(maxsize=2)
def _analyzer(improved: bool) -> AnalyzerEngine:
    """Build a Presidio analyzer once per engine. Loading spaCy takes a few seconds."""
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    if improved:
        for recognizer in custom_recognizers():
            analyzer.registry.add_recognizer(recognizer)
    return analyzer


@lru_cache(maxsize=1)
def _anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


class PresidioRedactor:
    name = "baseline"
    improved = False

    def __init__(self, entities: list[str] | None = None,
                 score_threshold: float = DEFAULT_SCORE_THRESHOLD):
        self.entities = entities or ENTITY_TYPES
        self.score_threshold = score_threshold

    def _analyze(self, text: str) -> list[RecognizerResult]:
        return _analyzer(self.improved).analyze(
            text=text, language="en", entities=self.entities,
            score_threshold=self.score_threshold,
        )

    def detect(self, text: str) -> list[Span]:
        """Return every PII span found, sorted by position."""
        return sorted(
            (Span(r.start, r.end, r.entity_type, round(r.score, 3)) for r in self._analyze(text)),
            key=lambda s: (s.start, s.end),
        )

    def redact(self, text: str) -> str:
        return _anonymizer().anonymize(text=text, analyzer_results=self._analyze(text)).text


# Entities found by strict patterns + checksums. When one of these overlaps a
# DATE_TIME guess from the NLP model, the pattern match is far more reliable.
NUMERIC_ENTITIES = {"PHONE_NUMBER", "US_SSN", "CREDIT_CARD", "IBAN_CODE", "IP_ADDRESS"}
MONTHS = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b", re.IGNORECASE)


# Tie-breaker when two numeric types claim the same text with equal confidence.
# Formats with strict structure (dotted quads, checksums) win over looser ones.
NUMERIC_PRIORITY = {"IP_ADDRESS": 5, "IBAN_CODE": 4, "CREDIT_CARD": 3, "US_SSN": 2, "PHONE_NUMBER": 1}


def _strength(r: RecognizerResult) -> tuple[float, int]:
    return (r.score, NUMERIC_PRIORITY.get(r.entity_type, 0))


def _contains(outer: RecognizerResult, inner: RecognizerResult) -> bool:
    return outer.start <= inner.start and inner.end <= outer.end


def _overlaps(a: RecognizerResult, b: RecognizerResult) -> bool:
    return a.start < b.end and b.start < a.end


def resolve_conflicts(text: str, results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Remove detections that the baseline evaluation showed are false alarms.

    1. A URL inside an email address ("example.com" in "a@example.com").
    2. A DATE_TIME overlapping a phone, SSN, card, IBAN or IP number
       ("396-0520" inside a phone number).
    3. A DATE_TIME with no digit and no month name ("last year", "next week").
       Relative dates are not personal data.
    4. Two different numeric types on the same characters (an IP address also
       flagged as a phone number): keep only the higher-confidence one.
    """
    emails = [r for r in results if r.entity_type == "EMAIL_ADDRESS"]
    numerics = [r for r in results if r.entity_type in NUMERIC_ENTITIES]
    kept = []
    for r in results:
        if r.entity_type == "URL" and any(_contains(e, r) for e in emails):
            continue
        if r.entity_type in NUMERIC_ENTITIES and any(
            n.entity_type != r.entity_type and _overlaps(n, r) and _strength(n) > _strength(r)
            for n in numerics
        ):
            continue
        if r.entity_type == "DATE_TIME":
            value = text[r.start:r.end]
            if any(_overlaps(n, r) for n in numerics):
                continue
            if not re.search(r"\d", value) and not MONTHS.search(value):
                continue
        kept.append(r)
    return kept


class ImprovedRedactor(PresidioRedactor):
    name = "improved"
    improved = True

    def _analyze(self, text: str) -> list[RecognizerResult]:
        return resolve_conflicts(text, super()._analyze(text))


ENGINES = {"baseline": PresidioRedactor, "improved": ImprovedRedactor}


def get_redactor(name: str = "improved") -> PresidioRedactor:
    if name not in ENGINES:
        raise ValueError(f"Unknown engine {name!r}. Choose one of {list(ENGINES)}.")
    return ENGINES[name]()
