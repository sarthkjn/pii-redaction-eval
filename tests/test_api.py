"""API tests using FastAPI's in-process TestClient (no server needed)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_redact_returns_redacted_text_and_entities(client):
    r = client.post("/redact", json={"text": "Email jane.doe@example.com now"})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "improved"
    assert "<EMAIL_ADDRESS>" in body["redacted_text"]
    assert any(e["entity_type"] == "EMAIL_ADDRESS" and e["value"] == "jane.doe@example.com"
               for e in body["entities"])


def test_redact_can_use_baseline_engine(client):
    r = client.post("/redact", json={"text": "card 2223 0031 2200 3222", "engine": "baseline"})
    assert r.status_code == 200
    assert r.json()["engine"] == "baseline"


@pytest.mark.parametrize("payload", [{"text": ""}, {}, {"text": "hi", "engine": "magic"}])
def test_redact_rejects_bad_input(client, payload):
    assert client.post("/redact", json=payload).status_code == 422


def test_evaluate_saves_a_run_that_can_be_fetched(client):
    r = client.post("/evaluate", json={"dataset": "synthetic", "n_samples": 20})
    assert r.status_code == 200
    report = r.json()
    assert 0 <= report["overall"]["f1"] <= 1
    run_id = report["run_id"]

    runs = client.get("/runs").json()
    assert runs[0]["id"] == run_id

    detail = client.get(f"/runs/{run_id}").json()
    assert detail["overall"] == report["overall"]


def test_evaluate_without_saving(client):
    r = client.post("/evaluate", json={"dataset": "edge_cases", "save": False})
    assert r.status_code == 200
    assert "run_id" not in r.json()
    assert client.get("/runs").json() == []


def test_missing_run_returns_404(client):
    assert client.get("/runs/99999").status_code == 404
