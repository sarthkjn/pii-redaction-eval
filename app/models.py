"""Shared data types used across the project.

A `Span` marks one piece of PII inside a text: where it starts, where it ends,
and what type it is. Both the ground truth (what we planted) and the
predictions (what the redactor found) are expressed as spans, which makes them
easy to compare.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Span:
    start: int          # index of the first character
    end: int            # index one past the last character (Python slice style)
    entity_type: str    # e.g. "EMAIL_ADDRESS"
    score: float = 1.0  # confidence; ground-truth spans are always 1.0

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Sample:
    """One test case: a piece of text plus the PII we know is inside it."""

    text: str
    spans: list[Span] = field(default_factory=list)
    source: str = "synthetic"   # "synthetic" or "edge_case"
    note: str = ""              # optional description of why the case is tricky

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "spans": [s.to_dict() for s in self.spans],
            "source": self.source,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Sample":
        return cls(
            text=data["text"],
            spans=[Span(**s) for s in data.get("spans", [])],
            source=data.get("source", "synthetic"),
            note=data.get("note", ""),
        )
