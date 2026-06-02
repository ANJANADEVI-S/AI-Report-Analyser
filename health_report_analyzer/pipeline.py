from __future__ import annotations

from health_report_analyzer.agents.detector import detect_abnormalities
from health_report_analyzer.agents.explainer import explain_result, generate_summary
from health_report_analyzer.agents.parser import parse_report_text
from health_report_analyzer.agents.trend import analyze_trends
from health_report_analyzer.models import AnalysisOutput, Flag, Report


def run_pipeline(raw_text: str, source_name: str, patient_id: str, historical_reports: list[Report]) -> AnalysisOutput:
    parsed = parse_report_text(raw_text, source_name=source_name, patient_id=patient_id)
    detected = detect_abnormalities(parsed)
    for result in detected.results:
        result.explanation = explain_result(result)

    abnormal = [result for result in detected.results if result.flag in {Flag.LOW, Flag.HIGH}]
    summary, questions = generate_summary(detected)
    trends = analyze_trends(detected, historical_reports)
    return AnalysisOutput(
        report=detected,
        patient_summary=summary,
        abnormal_results=abnormal,
        doctor_questions=questions,
        trend_insights=trends,
    )
