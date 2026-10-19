"""End-to-end UI tests: start the Streamlit dashboard and drive it with a real browser.

Run with:
    pytest -m e2e
Requires Playwright's Chromium:  playwright install chromium
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[2]
PORT = 8599


def _wait_for_port(port: int, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise RuntimeError(f"Dashboard did not start on port {port}")


@pytest.fixture(scope="module")
def dashboard_url(tmp_path_factory):
    env = {**os.environ, "PII_EVAL_DB": str(tmp_path_factory.mktemp("db") / "e2e.db")}
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard/streamlit_app.py",
         "--server.headless", "true", "--server.port", str(PORT)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port(PORT)
        yield f"http://127.0.0.1:{PORT}"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_redact_tab_hides_pii(page, dashboard_url):
    page.goto(dashboard_url)
    page.get_by_role("heading", name="PII Redaction Evaluator").wait_for(timeout=60_000)
    page.get_by_role("button", name="Redact").click()

    expect(page.get_by_text("Engine: improved")).to_be_visible(timeout=60_000)
    # The improved engine catches the 2-series Mastercard in the sample text.
    expect(page.get_by_text("<CREDIT_CARD>").first).to_be_visible(timeout=30_000)


def test_evaluate_tab_shows_scores(page, dashboard_url):
    page.goto(dashboard_url)
    page.get_by_role("tab", name="Evaluate").click()
    page.get_by_role("button", name="Run evaluation").click()
    expect(page.get_by_text("improved F1")).to_be_visible(timeout=120_000)
    expect(page.get_by_text("Recall by PII type")).to_be_visible()
