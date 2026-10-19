"""Central settings. Change things here rather than hunting through the code."""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = ROOT_DIR / "reports"

EDGE_CASES_PATH = DATA_DIR / "edge_cases.json"
# Override with the PII_EVAL_DB environment variable if you want the DB elsewhere.
DB_PATH = Path(os.getenv("PII_EVAL_DB", DATA_DIR / "runs.db"))

# Small spaCy model: ~15 MB, runs on any laptop. Swap for "en_core_web_lg"
# for better PERSON/LOCATION detection at the cost of ~500 MB.
SPACY_MODEL = "en_core_web_sm"

# The PII types this project evaluates. Each one is planted by the generator
# and scored by the evaluator. Names match Presidio's entity labels.
ENTITY_TYPES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "IP_ADDRESS",
    "IBAN_CODE",
    "URL",
    "DATE_TIME",
    "LOCATION",
]

# Presidio's minimum confidence for a detection to count.
DEFAULT_SCORE_THRESHOLD = 0.35
