"""REST API for the redaction engines and the evaluator.

Run locally:
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000/docs for interactive Swagger docs.
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import __version__
from app.datasets import load_dataset
from app.evaluator import evaluate
from app.redactor import get_redactor
from app.storage import get_run, list_runs, save_run

app = FastAPI(
    title="PII Redaction Evaluator",
    version=__version__,
    description="Redact PII from text and measure how well each engine performs on known test data.",
)

Engine = Literal["baseline", "improved"]


class RedactRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000,
                      examples=["Hi, I'm Jane Doe, email jane@example.com"])
    engine: Engine = "improved"


class SpanOut(BaseModel):
    start: int
    end: int
    entity_type: str
    score: float
    value: str


class RedactResponse(BaseModel):
    engine: str
    redacted_text: str
    entities: list[SpanOut]


class EvaluateRequest(BaseModel):
    dataset: Literal["synthetic", "edge_cases"] = "synthetic"
    engine: Engine = "improved"
    n_samples: int = Field(100, ge=1, le=2000, description="Only used by the synthetic dataset.")
    seed: int = 42
    save: bool = True


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post("/redact", response_model=RedactResponse)
def redact(req: RedactRequest) -> RedactResponse:
    redactor = get_redactor(req.engine)
    spans = redactor.detect(req.text)
    return RedactResponse(
        engine=req.engine,
        redacted_text=redactor.redact(req.text),
        entities=[SpanOut(**s.to_dict(), value=req.text[s.start:s.end]) for s in spans],
    )


@app.post("/evaluate")
def run_evaluation(req: EvaluateRequest) -> dict:
    samples = load_dataset(req.dataset, n=req.n_samples, seed=req.seed)
    if not samples:
        raise HTTPException(status_code=404, detail=f"Dataset {req.dataset!r} is empty.")
    report = evaluate(get_redactor(req.engine), samples, dataset=req.dataset).to_dict()
    if req.save:
        report["run_id"] = save_run(report)
    return report


@app.get("/runs")
def runs(limit: int = 20) -> list[dict]:
    return list_runs(limit=limit)


@app.get("/runs/{run_id}")
def run_detail(run_id: int) -> dict:
    report = get_run(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return report
