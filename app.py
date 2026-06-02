from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import plotly.express as px
import streamlit as st

from health_report_analyzer.agents.parser import extract_text_from_image, extract_text_from_pdf
from health_report_analyzer.models import Flag, Severity
from health_report_analyzer.pipeline import run_pipeline
from health_report_analyzer.storage import list_patients, load_reports, save_report, seed_demo_history


st.set_page_config(page_title="AI Health Report Analyzer", layout="wide")


def main() -> None:
    st.title("AI Health Report Analyzer")
    st.caption("Patient-friendly lab report summaries with trend tracking and safety guardrails.")

    with st.sidebar:
        st.header("Patient")
        existing = list_patients()
        patient_id = st.text_input("Patient ID", value=existing[0] if existing else "demo")
        if st.button("Load demo history"):
            seed_demo_history(patient_id)
            st.success("Demo history loaded.")
        st.divider()
        st.warning("This tool does not diagnose or recommend treatment. Discuss results with your doctor.")

    historical_reports = load_reports(patient_id)

    upload_tab, history_tab = st.tabs(["Analyze Report", "Trends & History"])
    with upload_tab:
        render_upload(patient_id, historical_reports)
    with history_tab:
        render_history(historical_reports)


def render_upload(patient_id: str, historical_reports) -> None:
    left, right = st.columns([0.42, 0.58], gap="large")
    with left:
        uploaded = st.file_uploader("Upload PDF, image, or text report", type=["pdf", "png", "jpg", "jpeg", "webp", "txt"])
        sample_text = Path("sample_reports/sample_report_1.txt").read_text(encoding="utf-8")
        raw_text = st.text_area("Or paste report text", value=sample_text, height=330)
        analyze = st.button("Analyze report", type="primary", use_container_width=True)

    if uploaded:
        raw_text = _read_upload(uploaded)
        source_name = uploaded.name
    else:
        source_name = "pasted_report.txt"

    if not analyze:
        with right:
            st.info("Upload a report or use the sample text, then run the analyzer.")
        return

    output = run_pipeline(raw_text, source_name, patient_id, historical_reports)
    save_report(output.report)

    with right:
        st.subheader("Patient Summary")
        st.write(output.patient_summary)

        metrics = st.columns(4)
        metrics[0].metric("Extracted tests", len(output.report.results))
        metrics[1].metric("Abnormal", len(output.abnormal_results))
        metrics[2].metric("Critical", len([r for r in output.abnormal_results if r.severity == Severity.CRITICAL]))
        metrics[3].metric("Trend insights", len(output.trend_insights))

    st.subheader("Color-Coded Results")
    df = _results_dataframe(output.report.results)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={"Explanation": st.column_config.TextColumn(width="large")},
    )

    st.subheader("Questions for Your Doctor")
    for question in output.doctor_questions:
        st.markdown(f"- {question}")

    if output.trend_insights:
        st.subheader("Trend Highlights")
        for insight in output.trend_insights:
            st.info(insight.message)


def render_history(reports) -> None:
    if not reports:
        st.info("No saved reports yet. Analyze a report to start trend tracking.")
        return

    st.subheader("Saved Reports")
    report_rows = [
        {
            "Date": report.report_date.isoformat(),
            "Source": report.source_name,
            "Patient": report.patient_name or report.patient_id,
            "Tests": len(report.results),
            "Abnormal": len([result for result in report.results if result.flag in {Flag.LOW, Flag.HIGH}]),
        }
        for report in reports
    ]
    st.dataframe(pd.DataFrame(report_rows), use_container_width=True, hide_index=True)

    trend_rows = []
    for report in reports:
        for result in report.results:
            trend_rows.append(
                {
                    "Date": report.report_date,
                    "Test": result.canonical_name or result.test_name,
                    "Value": result.value,
                    "Unit": result.unit,
                    "Flag": result.flag.value,
                }
            )

    trend_df = pd.DataFrame(trend_rows)
    tests = sorted(trend_df["Test"].unique())
    selected_tests = st.multiselect("Choose tests to chart", tests, default=tests[: min(4, len(tests))])
    if selected_tests:
        chart_df = trend_df[trend_df["Test"].isin(selected_tests)]
        fig = px.line(chart_df, x="Date", y="Value", color="Test", markers=True, hover_data=["Unit", "Flag"])
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Side-by-Side Comparison")
    if len(reports) < 2:
        st.info("Analyze at least two reports to compare them.")
        return

    first, second = st.columns(2)
    labels = [f"{report.report_date.isoformat()} - {report.source_name}" for report in reports]
    left_label = first.selectbox("Earlier report", labels, index=max(0, len(labels) - 2))
    right_label = second.selectbox("Later report", labels, index=len(labels) - 1)
    left_report = reports[labels.index(left_label)]
    right_report = reports[labels.index(right_label)]
    st.dataframe(_comparison_dataframe(left_report, right_report), use_container_width=True, hide_index=True)


def _read_upload(uploaded) -> str:
    suffix = Path(uploaded.name).suffix.lower()
    if suffix == ".txt":
        return uploaded.getvalue().decode("utf-8", errors="ignore")

    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        tmp_path = Path(tmp.name)
    try:
        if suffix == ".pdf":
            return extract_text_from_pdf(tmp_path)
        return extract_text_from_image(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _results_dataframe(results) -> pd.DataFrame:
    rows = []
    for result in results:
        rows.append(
            {
                "Test": result.canonical_name or result.test_name,
                "Value": result.value,
                "Unit": result.unit,
                "Range": _range_label(result),
                "Flag": result.flag.value,
                "Severity": result.severity.value,
                "Explanation": result.explanation,
            }
        )
    return pd.DataFrame(rows)


def _comparison_dataframe(left_report, right_report) -> pd.DataFrame:
    left = {result.canonical_name or result.test_name: result for result in left_report.results}
    right = {result.canonical_name or result.test_name: result for result in right_report.results}
    rows = []
    for test in sorted(set(left) | set(right)):
        left_result = left.get(test)
        right_result = right.get(test)
        rows.append(
            {
                "Test": test,
                "Earlier": _value_label(left_result),
                "Later": _value_label(right_result),
                "Change": _change_label(left_result, right_result),
            }
        )
    return pd.DataFrame(rows)


def _range_label(result) -> str:
    if result.reference_low is not None and result.reference_high is not None:
        return f"{result.reference_low:g} - {result.reference_high:g}"
    if result.reference_high is not None:
        return f"< {result.reference_high:g}"
    if result.reference_low is not None:
        return f"> {result.reference_low:g}"
    return "Unknown"


def _value_label(result) -> str:
    if result is None:
        return "-"
    return f"{result.value:g} {result.unit} ({result.flag.value})"


def _change_label(left_result, right_result) -> str:
    if left_result is None or right_result is None:
        return "-"
    delta = right_result.value - left_result.value
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:g}"


if __name__ == "__main__":
    main()
