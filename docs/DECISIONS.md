# Design decisions and trade-offs

Each decision gave something up. This page records what was chosen, why, and what would change it.

| Decision | Why | Cost | When I'd change it |
|---|---|---|---|
| Recall is the headline metric | A miss is leaked personal data; a false alarm only over-masks text | More over-redaction is tolerated | If readable output matters more, report both and raise the precision gate (currently 90%) |
| Overlap matching, not exact boundaries | "John Carter" caught as "John Carter," still protects the name | Partial coverage counts as found even if part leaks | Add a character-level "share of PII masked" metric |
| Synthetic data only | No privacy risk; exact ground truth | Templates are cleaner than real calls | The edge-case set covers messy input; real data only under a proper data agreement |
| Edge-case labels stored as values | People and LLMs are bad at counting characters | Repeated values need left-to-right matching | — |
| Presidio as the base engine | Open source, offline, pluggable | Default patterns had gaps (the subject of this project) | Benchmark a cloud API or LLM as another engine via the same interface |
| spaCy `en_core_web_sm` | 15 MB, fast, runs anywhere | Weak on lowercase and common-word names | Switch `SPACY_MODEL` in `app/config.py` if names matter most |
| Rule-based recognizers and conflict rules | Small, explainable, unit-tested | Cover known patterns only | Unknown patterns need a stronger NER model or an LLM pass |
| LLM-generated edge cases, generated once | Deterministic tests; CI never needs a key or spends credits | Set doesn't refresh on its own | Re-run the script and review the diff |
| SQLite for run history | Built into Python | Single writer | Postgres behind the same `save_run` / `list_runs` functions |
| Streamlit dashboard | Working UI in one file | Limited layout control | A React frontend on the existing API |
| Quality gates in tests | Regressions fail CI before merge | Thresholds can be too loose | Raise thresholds as the engine improves |

## Known weakness

The improved engine's edge-case score was measured on the same cases that guided the fixes, so it is optimistic. The fair measure is a held-out set generated after the fixes were written. See [EVALUATION.md](EVALUATION.md).
