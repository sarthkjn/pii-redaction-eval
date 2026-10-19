"""Score a redactor against samples with known PII.

How a match is counted
----------------------
A predicted span is a true positive (TP) when it has the same entity type as a
ground-truth span and the two overlap. Overlap, not exact boundaries, is used
because a redactor that catches "John Carter" as "John Carter," still protects
the data.

* TP: planted PII that was found with the right type.
* FN: planted PII that was missed. In a compliance setting this is the costly
  error, because missed PII is leaked PII.
* FP: something flagged as PII of that type that we never planted. This costs
  readability, not privacy.

Per type:  precision = TP / (TP + FP),  recall = TP / (TP + FN),
           F1 = harmonic mean of precision and recall.
Overall numbers are micro-averaged (counts summed across types first).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from app.models import Sample, Span


def _ratio(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _f1(p: float, r: float) -> float:
    return round(2 * p * r / (p + r), 4) if (p + r) else 0.0


@dataclass
class TypeScore:
    entity_type: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return _ratio(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> float:
        return _ratio(self.tp, self.tp + self.fn)

    @property
    def f1(self) -> float:
        return _f1(self.precision, self.recall)

    @property
    def support(self) -> int:
        """How many planted examples of this type existed."""
        return self.tp + self.fn

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "tp": self.tp, "fp": self.fp, "fn": self.fn,
            "support": self.support,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass
class EvalReport:
    engine: str
    dataset: str
    n_samples: int
    per_type: dict[str, TypeScore]
    misses: list[dict] = field(default_factory=list)            # FN examples
    false_alarms: list[dict] = field(default_factory=list)      # FP examples
    seconds: float = 0.0

    @property
    def totals(self) -> TypeScore:
        t = TypeScore("ALL")
        for s in self.per_type.values():
            t.tp += s.tp
            t.fp += s.fp
            t.fn += s.fn
        return t

    def to_dict(self) -> dict:
        totals = self.totals
        return {
            "engine": self.engine,
            "dataset": self.dataset,
            "n_samples": self.n_samples,
            "seconds": round(self.seconds, 2),
            "overall": {
                "precision": totals.precision,
                "recall": totals.recall,
                "f1": totals.f1,
                "tp": totals.tp, "fp": totals.fp, "fn": totals.fn,
            },
            "per_type": [s.to_dict() for s in sorted(self.per_type.values(), key=lambda s: s.entity_type)],
            "misses": self.misses,
            "false_alarms": self.false_alarms,
        }


def match_spans(gold: list[Span], predicted: list[Span]) -> tuple[list[Span], list[Span], list[Span]]:
    """Return (true positives, false negatives, false positives).

    Each gold span can be matched at most once, and each prediction can match
    at most one gold span, so duplicates are not double counted.
    """
    used_pred: set[int] = set()
    tps: list[Span] = []
    fns: list[Span] = []
    for g in gold:
        hit = None
        for i, p in enumerate(predicted):
            if i not in used_pred and p.entity_type == g.entity_type and p.overlaps(g):
                hit = i
                break
        if hit is None:
            fns.append(g)
        else:
            used_pred.add(hit)
            tps.append(g)
    # A second detection of an already-found item (same type, overlapping, e.g.
    # "(973) 396-0520" and "973) 396-0520") is a duplicate, not a false alarm.
    fps = [
        p for i, p in enumerate(predicted)
        if i not in used_pred
        and not any(p.entity_type == g.entity_type and p.overlaps(g) for g in tps)
    ]
    return tps, fns, fps


def evaluate(
    redactor,
    samples: list[Sample],
    dataset: str = "synthetic",
    entity_types: list[str] | None = None,
    max_examples: int = 25,
) -> EvalReport:
    """Run the redactor over every sample and tally results per entity type.

    Only types in `entity_types` are scored. If not given, the types that
    actually appear in the samples are used, so a detector is not punished for
    labelling something we never asked about.
    """
    if entity_types is None:
        entity_types = sorted({s.entity_type for sample in samples for s in sample.spans})
    scored = set(entity_types)

    per_type: dict[str, TypeScore] = defaultdict(lambda: TypeScore(""))
    for t in entity_types:
        per_type[t] = TypeScore(t)

    misses: list[dict] = []
    false_alarms: list[dict] = []
    start = time.perf_counter()

    for sample in samples:
        gold = [s for s in sample.spans if s.entity_type in scored]
        predicted = [p for p in redactor.detect(sample.text) if p.entity_type in scored]
        tps, fns, fps = match_spans(gold, predicted)

        for s in tps:
            per_type[s.entity_type].tp += 1
        for s in fns:
            per_type[s.entity_type].fn += 1
            if len(misses) < max_examples:
                misses.append({
                    "entity_type": s.entity_type,
                    "value": sample.text[s.start:s.end],
                    "text": sample.text,
                    "note": sample.note,
                })
        for s in fps:
            per_type[s.entity_type].fp += 1
            if len(false_alarms) < max_examples:
                false_alarms.append({
                    "entity_type": s.entity_type,
                    "value": sample.text[s.start:s.end],
                    "text": sample.text,
                })

    return EvalReport(
        engine=getattr(redactor, "name", type(redactor).__name__),
        dataset=dataset,
        n_samples=len(samples),
        per_type=dict(per_type),
        misses=misses,
        false_alarms=false_alarms,
        seconds=time.perf_counter() - start,
    )
