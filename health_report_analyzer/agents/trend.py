from __future__ import annotations

from collections import defaultdict

from health_report_analyzer.models import LabResult, Report, TrendInsight, TrendPoint


def analyze_trends(current_report: Report, historical_reports: list[Report]) -> list[TrendInsight]:
    reports = sorted([*historical_reports, current_report], key=lambda report: report.report_date)
    by_test: dict[str, list[tuple[Report, LabResult]]] = defaultdict(list)
    for report in reports:
        for result in report.results:
            key = result.canonical_name or result.test_name
            by_test[key].append((report, result))

    insights: list[TrendInsight] = []
    for test_name, rows in by_test.items():
        if len(rows) < 2:
            continue
        points = [
            TrendPoint(
                report_date=report.report_date,
                value=result.value,
                flag=result.flag,
                severity=result.severity,
            )
            for report, result in rows
        ]
        direction = _direction([point.value for point in points])
        insights.append(
            TrendInsight(
                test_name=test_name,
                points=points,
                direction=direction,
                message=_message(test_name, direction, points),
            )
        )
    return insights


def _direction(values: list[float]) -> str:
    delta = values[-1] - values[0]
    baseline = max(abs(values[0]), 1)
    if abs(delta) / baseline < 0.05:
        return "stable"
    return "increasing" if delta > 0 else "decreasing"


def _message(test_name: str, direction: str, points: list[TrendPoint]) -> str:
    first = points[0]
    last = points[-1]
    return (
        f"{test_name} is {direction}: {first.value:g} on {first.report_date.isoformat()} "
        f"to {last.value:g} on {last.report_date.isoformat()}."
    )
