from __future__ import annotations

import os

from health_report_analyzer.models import Flag, LabResult, Report, Severity
from health_report_analyzer.reference import find_reference


DISCLAIMER = (
    "This is not a diagnosis. Lab values need clinical context, symptoms, medicines, "
    "and examination findings. Please review abnormal or concerning results with your doctor."
)


def generate_summary(report: Report) -> tuple[str, list[str]]:
    abnormal = [result for result in report.results if result.flag in {Flag.LOW, Flag.HIGH}]
    if os.getenv("OPENAI_API_KEY"):
        llm_summary = _try_openai_summary(report, abnormal)
        if llm_summary:
            return llm_summary, generate_doctor_questions(abnormal)
    return _local_summary(report, abnormal), generate_doctor_questions(abnormal)


def explain_result(result: LabResult) -> str:
    ref = find_reference(result.canonical_name or result.test_name)
    plain_name = ref.plain_name if ref else result.test_name
    description = ref.description if ref else "This test should be interpreted with your clinician."

    if result.flag == Flag.NORMAL:
        return f"{plain_name} is within the reference range. {description}"
    direction = "below" if result.flag == Flag.LOW else "above"
    severity = "markedly" if result.severity in {Severity.MODERATE, Severity.CRITICAL} else "slightly"
    return f"{plain_name} is {severity} {direction} the reference range. {description}"


def generate_doctor_questions(abnormal_results: list[LabResult]) -> list[str]:
    if not abnormal_results:
        return ["Are there any preventive steps I should take based on this report?"]

    questions = [
        "Which of these abnormal results are most important for me to follow up on?",
        "Could any medicines, supplements, recent illness, diet, or fasting status have affected these values?",
        "Do I need to repeat any tests, and if so, when?",
    ]
    for result in abnormal_results[:5]:
        name = result.canonical_name or result.test_name
        questions.append(f"What could explain my {name} being {result.flag.value}, and what should I monitor next?")
    return questions


def _local_summary(report: Report, abnormal: list[LabResult]) -> str:
    normal_count = len([result for result in report.results if result.flag == Flag.NORMAL])
    if not report.results:
        return f"No lab values could be extracted from this report. {DISCLAIMER}"

    lines = [
        f"I found {len(report.results)} lab values in this report dated {report.report_date.isoformat()}.",
        f"{normal_count} values appear within range and {len(abnormal)} need attention or follow-up.",
    ]

    critical = [result for result in abnormal if result.severity == Severity.CRITICAL]
    if critical:
        names = ", ".join((result.canonical_name or result.test_name) for result in critical)
        lines.append(f"Some values are far outside the reference range: {names}. Please contact your doctor promptly.")

    if abnormal:
        top_findings = "; ".join(
            f"{result.canonical_name or result.test_name}: {result.value:g} {result.unit} ({result.flag.value})"
            for result in abnormal[:6]
        )
        lines.append(f"Key findings: {top_findings}.")
    else:
        lines.append("No abnormal values were detected using the available reference ranges.")

    lines.append(DISCLAIMER)
    return "\n\n".join(lines)


def _try_openai_summary(report: Report, abnormal: list[LabResult]) -> str:
    try:
        from openai import OpenAI

        client = OpenAI()
        findings = [
            {
                "test": result.canonical_name or result.test_name,
                "value": result.value,
                "unit": result.unit,
                "flag": result.flag.value,
                "severity": result.severity.value,
            }
            for result in abnormal
        ]
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=[
                {
                    "role": "system",
                    "content": (
                        "You explain lab reports in simple language. Do not diagnose, "
                        "recommend treatment, or replace a doctor. Always advise clinical follow-up."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Report date: {report.report_date}. Abnormal findings: {findings}",
                },
            ],
        )
        return response.output_text.strip()
    except Exception:
        return ""
