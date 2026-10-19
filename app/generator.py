"""Synthetic test data with known answers.

Each template is a short customer-service style utterance with placeholders
such as {PERSON}. The generator fills every placeholder with fake data from
Faker and records exactly where each value landed. That record is the ground
truth the evaluator scores against.

All data here is fake. Nothing comes from a real person or a real system.
"""

from __future__ import annotations

import random
import re

from faker import Faker

from app.models import Sample, Span

TEMPLATES = [
    "Hi, this is {PERSON} calling about my card ending, the full number is {CREDIT_CARD}.",
    "Sure, my email is {EMAIL_ADDRESS} and you can reach me at {PHONE_NUMBER}.",
    "Agent: Can I get your Social Security number? Customer: Yes, it's {US_SSN}.",
    "My name is {PERSON}, I moved to {LOCATION} last year and need to update my address.",
    "I was charged twice on {DATE_TIME}. The card was {CREDIT_CARD}.",
    "Please send the statement to {EMAIL_ADDRESS}, attention {PERSON}.",
    "The login came from IP {IP_ADDRESS}, which isn't mine. I live in {LOCATION}.",
    "Transfer the funds to IBAN {IBAN_CODE} by {DATE_TIME}, please.",
    "I tried resetting my password on {URL} but it kept failing.",
    "Callback number is {PHONE_NUMBER}. Ask for {PERSON}.",
    "For verification: SSN {US_SSN}, date of birth {DATE_TIME}.",
    "Hello {PERSON}, we noticed a sign-in from {IP_ADDRESS} on {DATE_TIME}.",
    "You can find the dispute form at {URL} or email {EMAIL_ADDRESS}.",
    "My wife {PERSON} and I both use the card {CREDIT_CARD}.",
    "I'm travelling to {LOCATION} next week, please don't block my card.",
]

PLACEHOLDER = re.compile(r"\{([A-Z_]+)\}")

# Real US area codes so phone numbers pass libphonenumber validation.
AREA_CODES = ["201", "212", "305", "312", "415", "512", "617", "646", "702", "917", "973"]

REAL_CITIES = [
    "Jersey City", "Newark", "Hoboken", "New York", "Boston", "Chicago", "Austin",
    "Seattle", "Denver", "Atlanta", "Miami", "Phoenix", "San Diego", "Philadelphia",
    "Pittsburgh", "Toronto", "London", "Berlin", "Prague", "Singapore",
]


class SyntheticGenerator:
    def __init__(self, seed: int = 42):
        self.fake = Faker("en_US")
        self.fake.seed_instance(seed)
        self.rng = random.Random(seed)

    def _value(self, entity_type: str) -> str:
        f, r = self.fake, self.rng
        if entity_type == "PERSON":
            return f.name()
        if entity_type == "EMAIL_ADDRESS":
            return f.email()
        if entity_type == "PHONE_NUMBER":
            area = r.choice(AREA_CODES)
            exchange = f"{r.randint(2, 9)}{r.randint(0, 9)}{r.randint(0, 9)}"
            line = f"{r.randint(0, 9999):04d}"
            style = r.choice(["({a}) {e}-{l}", "{a}-{e}-{l}", "{a}.{e}.{l}"])
            return style.format(a=area, e=exchange, l=line)
        if entity_type == "CREDIT_CARD":
            return f.credit_card_number(card_type=r.choice(["visa16", "mastercard", "amex"]))
        if entity_type == "US_SSN":
            return f.ssn()
        if entity_type == "IP_ADDRESS":
            return f.ipv4_public()
        if entity_type == "IBAN_CODE":
            return f.iban()
        if entity_type == "URL":
            return f"https://{f.domain_name()}/{f.uri_path()}"
        if entity_type == "DATE_TIME":
            return f.date_between(start_date="-80y", end_date="today").strftime("%B %d, %Y")
        if entity_type == "LOCATION":
            # Faker's f.city() invents names like "Port Darrellville", which no
            # NER model could know. Real places make the test fair.
            return r.choice(REAL_CITIES)
        raise ValueError(f"No generator for entity type {entity_type!r}")

    def fill(self, template: str) -> Sample:
        """Fill one template and record the position of every planted value."""
        parts: list[str] = []
        spans: list[Span] = []
        cursor = 0
        length = 0
        for match in PLACEHOLDER.finditer(template):
            literal = template[cursor:match.start()]
            parts.append(literal)
            length += len(literal)

            entity_type = match.group(1)
            value = self._value(entity_type)
            spans.append(Span(length, length + len(value), entity_type))
            parts.append(value)
            length += len(value)
            cursor = match.end()
        parts.append(template[cursor:])
        return Sample(text="".join(parts), spans=spans, source="synthetic")

    def generate(self, n: int) -> list[Sample]:
        return [self.fill(self.rng.choice(TEMPLATES)) for _ in range(n)]


def generate_samples(n: int = 200, seed: int = 42) -> list[Sample]:
    return SyntheticGenerator(seed).generate(n)
