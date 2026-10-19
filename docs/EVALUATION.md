# Evaluation method

## What is measured

For each PII type, the evaluator counts:

| Outcome | Meaning | Why it matters |
|---|---|---|
| **TP** (true positive) | Planted PII was found with the right type | Data protected |
| **FN** (false negative) | Planted PII was missed | **Data leaked.** The costly error in a compliance setting |
| **FP** (false positive) | Something was flagged as that type but nothing was planted there | Text is over-redacted and harder to use for analytics |

From these:

* **Recall** = TP / (TP + FN): the share of real PII that was caught. The main safety number.
* **Precision** = TP / (TP + FP): the share of flags that were real PII. The usability number.
* **F1** = the harmonic mean of the two.

Overall scores are **micro-averaged**: TP, FP and FN are summed across types first. This weights common types more heavily, which matches how often they appear in real text.

## Matching rules

* A prediction matches a ground-truth span when the **types are equal and the character ranges overlap**. Exact boundaries are not required, because catching "John Carter" as "John Carter," still protects the name.
* Each ground-truth span can be matched once, and each prediction can match once.
* A second detection of an item that was already found (same type, overlapping) is a **duplicate**, not a false alarm. Presidio sometimes returns `(973) 396-0520` and `973) 396-0520` for the same number.
* Only the types being evaluated are scored. If an engine labels something as a type we did not plant anywhere in the dataset, it is ignored rather than counted against it.

## Datasets

### `synthetic`
Fifteen customer-service templates filled with Faker values (seeded, so runs are reproducible). Positions are recorded as values are inserted, so the ground truth is exact by construction.

Two deliberate choices:
* **Phone numbers use real US area codes**, so they pass phone-number validation. Random digits would make the detector look worse than it is.
* **Cities come from a fixed list of real places.** Faker's `city()` invents names like "Port Darrellville", which no language model could recognize. An early run showed these as misses; they were a flaw in the test data, not the engine.

### `edge_cases`
Hard, realistic inputs: numbers spoken as words, emails written as "name at domain dot com", speech-to-text filler words, unusual formats, names that are also common words, and text that looks like PII but isn't (order numbers, version numbers).

The committed seed set is hand-written. `scripts/generate_edge_cases.py` generates more with Claude Haiku across eight categories. Labels are stored as `{type, value}` and positions are found by substring search when loading, so the LLM never has to count characters. Any label not found verbatim in its text is dropped by the script, and `tests/test_datasets.py` checks the committed file the same way.

## Reading the results honestly

* **Synthetic results** measure the engine on clean, well-formatted input. The templates were written before any engine was tested.
* **Edge-case results with the seed set** are optimistic for the improved engine, because the custom recognizers were designed after seeing those failures. To get an unbiased number, generate a fresh set with the script and evaluate on it without changing the code. That is the held-out test.
* With 30 edge cases, a single example moves a per-type score by 10–50 points. Treat per-type edge-case numbers as directional.

## Reproducing

```bash
python scripts/run_eval.py --n 300 --seed 42
```

This regenerates `reports/results.md` and `reports/results.json`. The same seed gives the same synthetic data on any machine.
