# Architecture

This page explains how the code fits together and how to extend it.

## Core idea: one interface for every engine

Every redaction engine exposes two methods:

```python
detect(text: str) -> list[Span]   # find PII
redact(text: str) -> str          # replace it with placeholders like <EMAIL_ADDRESS>
```

The evaluator, API, CLI and dashboard only call these two methods. That is what makes it possible to compare engines side by side, and to add a new engine without touching anything else.

A `Span` (in `app/models.py`) is `(start, end, entity_type, score)`. Ground truth and predictions use the same type, so comparing them is simple.

## Modules

| Module | Responsibility | Depends on |
|---|---|---|
| `config.py` | Entity types, file paths, spaCy model, score threshold | — |
| `models.py` | `Span` and `Sample` data classes | — |
| `generator.py` | Fill templates with Faker values; record each value's position | models |
| `datasets.py` | Load `synthetic` (generated) or `edge_cases` (JSON) as `Sample`s | generator, models |
| `recognizers.py` | Custom Presidio recognizers | presidio |
| `redactor.py` | Baseline and improved engines; conflict resolution; `get_redactor(name)` | recognizers, presidio |
| `evaluator.py` | Match predictions to ground truth; compute metrics; collect misses | models |
| `storage.py` | Save and list runs in SQLite | config |
| `main.py` | FastAPI endpoints | all of the above |

`evaluator.py` does not import Presidio at all. It works with any object that has a `detect` method, which is why its unit tests can use a tiny fake engine and run in milliseconds.

## Request flow: `POST /evaluate`

1. `load_dataset("edge_cases")` reads `data/edge_cases.json`, converts each `{type, value}` label into a `Span` by locating the value in the text.
2. `get_redactor("improved")` returns a cached engine. The spaCy model loads once per process (a few seconds), then every call is fast.
3. `evaluate(engine, samples)` calls `engine.detect` on each sample, matches predictions to ground truth, and tallies TP/FP/FN per type.
4. The report is saved to SQLite (if `save` is true) and returned as JSON.

## The improved engine

`ImprovedRedactor` is the baseline with two additions:

1. **Extra recognizers** registered in Presidio's registry (`app/recognizers.py`).
2. **A post-processing step**, `resolve_conflicts`, that removes detections matching known false-alarm patterns.

Both are small and individually tested. Each one exists because the baseline evaluation showed a specific failure, which is noted in its docstring.

## How to extend

**Add a PII type**
1. Add its Presidio label to `ENTITY_TYPES` in `app/config.py`.
2. Add a fake-value branch in `SyntheticGenerator._value` and at least one template that uses it.
3. Run `pytest`. `test_every_entity_type_is_generated` will fail until both steps are done.

**Add a recognizer**
1. Write a `PatternRecognizer` (regex) or `EntityRecognizer` (custom logic) in `app/recognizers.py`.
2. Add it to `custom_recognizers()`.
3. Add a unit test in `tests/test_recognizers.py`, then run `python scripts/run_eval.py` to see the effect.

**Add an engine** (for example a cloud redaction API or an LLM)
1. Write a class with `name`, `detect` and `redact`.
2. Register it in `ENGINES` in `app/redactor.py`.
3. It now appears in the CLI (`--engine`), the API (`engine` field, after adding it to the `Engine` literal in `main.py`) and the dashboard.

## Why these tools

| Choice | Reason |
|---|---|
| Presidio | Open source, widely used, pluggable recognizers, runs offline |
| spaCy `en_core_web_sm` | ~15 MB, runs on any laptop; swappable via one config line |
| Faker | Realistic, reproducible fake data with a seed |
| FastAPI | Typed request validation and automatic Swagger docs |
| SQLite | Built into Python; no server to install |
| Streamlit | A working dashboard in one Python file |
| Playwright | Reliable browser automation with auto-waiting assertions |
