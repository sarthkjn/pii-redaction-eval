"""Custom Presidio recognizers that close gaps found by the evaluator.

Each recognizer exists because the baseline evaluation showed a specific miss:

1. Mastercard2SeriesRecognizer
   Presidio's built-in card pattern does not cover Mastercard's newer
   2221-2720 BIN range, so valid cards starting with "2" were missed.

2. SpokenNumberRecognizer
   Voice transcripts render digits as words: "four one one one ...". A run of
   digit words is converted to digits and labelled by length:
   16 -> CREDIT_CARD, 10 -> PHONE_NUMBER, 9 -> US_SSN.
   Filler words ("um", "uh") and commas inside the run are allowed.

3. SpokenEmailRecognizer / SpokenUrlRecognizer
   "priya dot shah at gmail dot com" and "examplebank dot com slash reset".
"""

from __future__ import annotations

import re

from presidio_analyzer import EntityRecognizer, Pattern, PatternRecognizer, RecognizerResult

DIGIT_WORDS = {
    "zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}
FILLERS = {"um", "uh", "er", "ah", "like"}


def luhn_valid(number: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if len(digits) < 12:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


class Mastercard2SeriesRecognizer(PatternRecognizer):
    PATTERN = (
        r"\b2(?:22[1-9]|2[3-9]\d|[3-6]\d{2}|7[01]\d|720)"
        r"[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"
    )

    def __init__(self):
        super().__init__(
            supported_entity="CREDIT_CARD",
            name="Mastercard2SeriesRecognizer",
            patterns=[Pattern("mastercard_2_series", self.PATTERN, 0.5)],
            context=["card", "mastercard", "credit", "debit"],
        )

    def validate_result(self, pattern_text: str) -> bool:
        return luhn_valid(pattern_text)


class SpokenNumberRecognizer(EntityRecognizer):
    LENGTH_TO_ENTITY = {16: "CREDIT_CARD", 15: "CREDIT_CARD", 10: "PHONE_NUMBER", 9: "US_SSN"}
    TOKEN = re.compile(r"[A-Za-z]+|\d+|,")

    def __init__(self):
        super().__init__(
            supported_entities=sorted(set(self.LENGTH_TO_ENTITY.values())),
            name="SpokenNumberRecognizer",
            supported_language="en",
        )

    def load(self) -> None:  # nothing to load
        pass

    def analyze(self, text, entities, nlp_artifacts=None):
        results: list[RecognizerResult] = []
        run_start = run_end = None
        digits = ""

        def close_run():
            entity = self.LENGTH_TO_ENTITY.get(len(digits))
            if entity and entity in entities:
                results.append(RecognizerResult(entity, run_start, run_end, 0.6))

        for m in self.TOKEN.finditer(text):
            tok = m.group(0).lower()
            if tok in DIGIT_WORDS or tok.isdigit():
                if run_start is None:
                    run_start = m.start()
                    digits = ""
                digits += DIGIT_WORDS.get(tok, tok)
                run_end = m.end()
            elif run_start is not None and (tok in FILLERS or tok == ","):
                continue  # fillers don't break a run
            else:
                if run_start is not None:
                    close_run()
                run_start = None
        if run_start is not None:
            close_run()
        return results


class SpokenEmailRecognizer(PatternRecognizer):
    PATTERN = r"\b[A-Za-z0-9_]+(?: dot [A-Za-z0-9_]+)* at [A-Za-z0-9-]+(?: dot [A-Za-z]{2,})+\b"

    def __init__(self):
        super().__init__(
            supported_entity="EMAIL_ADDRESS",
            name="SpokenEmailRecognizer",
            patterns=[Pattern("spoken_email", self.PATTERN, 0.6)],
        )


class SpokenUrlRecognizer(PatternRecognizer):
    PATTERN = r"\b[A-Za-z0-9-]+ dot (?:com|org|net|io|co)(?: slash [A-Za-z0-9-]+)+\b"

    def __init__(self):
        super().__init__(
            supported_entity="URL",
            name="SpokenUrlRecognizer",
            patterns=[Pattern("spoken_url", self.PATTERN, 0.5)],
        )


def custom_recognizers() -> list[EntityRecognizer]:
    return [
        Mastercard2SeriesRecognizer(),
        SpokenNumberRecognizer(),
        SpokenEmailRecognizer(),
        SpokenUrlRecognizer(),
    ]
