"""Streamlit dashboard: try the redactor, run evaluations, browse past runs.

Run locally:
    streamlit run dashboard/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.datasets import load_dataset  # noqa: E402
from app.evaluator import evaluate  # noqa: E402
from app.redactor import ENGINES, get_redactor  # noqa: E402
from app.storage import list_runs, save_run  # noqa: E402

st.set_page_config(page_title="PII Redaction Evaluator", layout="wide")
st.title("PII Redaction Evaluator")
st.caption("Measure how well a redaction engine catches personal data. All test data is synthetic.")

SAMPLE_TEXT = (
    "Hi, this is Maria Lopez. My card is 2223 0031 2200 3222 and my email is "
    "maria dot lopez at gmail dot com. Call me back at nine one seven five five five "
    "zero one two three."
)


@st.cache_resource
def redactor(name: str):
    return get_redactor(name)


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


tab_try, tab_eval, tab_history = st.tabs(["Try it", "Evaluate", "Run history"])

# --- Try it -----------------------------------------------------------------
with tab_try:
    text = st.text_area("Text to redact", SAMPLE_TEXT, height=120, key="input_text")
    if st.button("Redact", type="primary", key="redact_btn"):
        cols = st.columns(len(ENGINES))
        for col, name in zip(cols, ENGINES, strict=True):
            engine = redactor(name)
            spans = engine.detect(text)
            with col:
                st.subheader(f"Engine: {name}")
                st.code(engine.redact(text), language=None, wrap_lines=True)
                st.dataframe(
                    pd.DataFrame(
                        [{"type": s.entity_type, "value": text[s.start:s.end], "score": s.score}
                         for s in spans],
                        columns=["type", "value", "score"],
                    ),
                    hide_index=True, use_container_width=True,
                )

# --- Evaluate -----------------------------------------------------------------
with tab_eval:
    c1, c2, c3 = st.columns(3)
    dataset = c1.selectbox("Dataset", ["edge_cases", "synthetic"], key="dataset")
    n = c2.number_input("Synthetic samples", 10, 2000, 300, step=50, disabled=dataset != "synthetic")
    save = c3.checkbox("Save runs to history", value=True)

    if st.button("Run evaluation", type="primary", key="eval_btn"):
        samples = load_dataset(dataset, n=int(n))
        reports = {}
        with st.spinner("Evaluating both engines..."):
            for name in ENGINES:
                report = evaluate(redactor(name), samples, dataset=dataset).to_dict()
                if save:
                    save_run(report)
                reports[name] = report

        st.subheader("Overall")
        metric_cols = st.columns(len(reports))
        base = reports["baseline"]["overall"]
        for col, (name, rep) in zip(metric_cols, reports.items(), strict=True):
            o = rep["overall"]
            delta = None if name == "baseline" else f"{(o['f1'] - base['f1']) * 100:+.1f} pts F1"
            col.metric(f"{name} F1", pct(o["f1"]), delta)
            col.write(f"Precision {pct(o['precision'])} · Recall {pct(o['recall'])} · "
                      f"Missed {o['fn']} · False alarms {o['fp']}")

        st.subheader("Recall by PII type (higher = less leaked PII)")
        recall = pd.DataFrame({
            name: {t["entity_type"]: t["recall"] for t in rep["per_type"] if t["support"]}
            for name, rep in reports.items()
        })
        st.bar_chart(recall, stack=False)

        st.subheader("Per-type detail")
        for name, rep in reports.items():
            with st.expander(f"{name}", expanded=name == "improved"):
                df = pd.DataFrame(rep["per_type"])
                df = df[df["support"] > 0]
                st.dataframe(df, hide_index=True, use_container_width=True)
                if rep["misses"]:
                    st.write("Missed PII examples")
                    st.dataframe(pd.DataFrame(rep["misses"])[["entity_type", "value", "note"]],
                                 hide_index=True, use_container_width=True)

# --- Run history ---------------------------------------------------------------
with tab_history:
    runs = list_runs(limit=100)
    if runs:
        df = pd.DataFrame(runs)
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.info("No runs saved yet. Run an evaluation first.")
