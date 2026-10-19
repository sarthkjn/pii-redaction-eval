"""Generate hard PII test cases with Claude and save them to data/edge_cases.json.

This is the ONLY file in the project that calls an LLM. It is meant to be run
once (or occasionally), and the output is committed to the repo. Tests and CI
read the saved JSON, so they stay deterministic and never spend API credits.

Usage:
    # put ANTHROPIC_API_KEY=sk-ant-... in a .env file (it is git-ignored)
    python scripts/generate_edge_cases.py               # ~8 categories x 6 cases
    python scripts/generate_edge_cases.py --per-category 4 --dry-run

Cost: a handful of short requests to the smallest model. A full run should
cost a few cents; check current pricing on the Anthropic site.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import EDGE_CASES_PATH, ENTITY_TYPES  # noqa: E402

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")

CATEGORIES = [
    "numbers spoken as words, the way a voice transcript renders them (e.g. 'four one one one ...')",
    "emails and URLs written out to dodge filters ('john at gmail dot com', 'example dot com slash login')",
    "PII split across a sentence with filler words, like a speech-to-text transcript with 'um' and pauses",
    "unusual but valid formats: card numbers with dashes or spaces, phone numbers with +1 or extensions",
    "names that are also common words or places (e.g. 'Will Hunter', 'Paris Jackson', 'Grace Mills')",
    "non-US formats: UK phone numbers, IBANs from different countries, international addresses",
    "messages with typos and lowercase everything, like a quick chat message",
    "text that LOOKS like PII but is not (order numbers, tracking IDs, version numbers) "
    "mixed with one real PII item",
]

SYSTEM = """You write test data for evaluating PII redaction systems.
All data must be fictional. Never use real people's details.
Return ONLY valid JSON, no prose, no markdown fences."""

PROMPT = """Write {n} short customer-service messages (1-2 sentences each) for this category:
{category}

Each message must contain at least one PII item of these types: {types}.
For every PII item, give its type and its value copied EXACTLY as it appears in the text
(same characters, spacing and case), so it can be found with a plain substring search.
Do not label anything that is not PII.

Return JSON in this exact shape:
{{"cases": [{{"text": "...",
             "pii": [{{"type": "PHONE_NUMBER", "value": "..."}}],
             "note": "why this is hard, in under 12 words"}}]}}"""


def _parse_json(raw: str) -> dict:
    """Pull the JSON object out of the reply even if the model added fences."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("No JSON object in model reply")
    return json.loads(match.group(0))


def _validate(case: dict) -> dict | None:
    """Keep only PII items whose value really appears in the text."""
    text = case.get("text", "")
    pii = [
        p for p in case.get("pii", [])
        if p.get("type") in ENTITY_TYPES and p.get("value") and p["value"] in text
    ]
    if not text or not pii:
        return None
    return {"text": text, "pii": pii, "note": case.get("note", "")}


def generate(per_category: int, model: str) -> list[dict]:
    from anthropic import Anthropic  # imported here so tests don't need the SDK

    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    cases: list[dict] = []
    for i, category in enumerate(CATEGORIES, 1):
        print(f"[{i}/{len(CATEGORIES)}] {category[:60]}...")
        message = client.messages.create(
            model=model,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": PROMPT.format(
                n=per_category, category=category, types=", ".join(ENTITY_TYPES))}],
        )
                # The reply can contain several blocks (e.g. reasoning, then the answer); keep only text.
        reply = "".join(block.text for block in message.content if block.type == "text")
        try:
            batch = _parse_json(reply).get("cases", [])
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"   skipped: could not parse reply ({exc})")
            continue
        kept = [c for c in (_validate(c) for c in batch) if c]
        print(f"   kept {len(kept)}/{len(batch)} cases")
        cases.extend(kept)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-category", type=int, default=6)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, default=EDGE_CASES_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Print the prompts without calling the API.")
    args = parser.parse_args()

    if args.dry_run:
        for c in CATEGORIES:
            print(PROMPT.format(n=args.per_category, category=c, types=", ".join(ENTITY_TYPES)), "\n---")
        return

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Add it to a .env file (see .env.example).")

    cases = generate(args.per_category, args.model)
    payload = {
        "generated_by": args.model,
        "generated_on": date.today().isoformat(),
        "description": "LLM-generated hard cases for PII redaction. Fictional data only.",
        "cases": cases,
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(cases)} cases to {args.out}")


if __name__ == "__main__":
    main()
