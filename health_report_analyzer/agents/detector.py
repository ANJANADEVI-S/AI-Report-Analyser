from __future__ import annotations

from health_report_analyzer.models import Flag, LabResult, Report, Severity
from health_report_analyzer.reference import find_reference


def detect_abnormalities(report: Report) -> Report:
    updated = report.model_copy(deep=True)
    updated.results = [classify_result(result) for result in updated.results]
    return updated


def classify_result(result: LabResult) -> LabResult:
    ref = find_reference(result.test_name)
    classified = result.model_copy()

    low = result.reference_low
    high = result.reference_high
    if ref:
        classified.canonical_name = ref.canonical_name
        if not classified.unit:
            classified.unit = ref.unit
        low = low if low is not None else ref.low
        high = high if high is not None else ref.high
        classified.reference_low = low
        classified.reference_high = high

    classified.flag = _flag_value(result.value, low, high)
    classified.severity = _severity(result.value, classified.flag, low, high, ref)
    return classified


def _flag_value(value: float, low: float | None, high: float | None) -> Flag:
    if low is not None and value < low:
        return Flag.LOW
    if high is not None and value > high:
        return Flag.HIGH
    if low is None and high is None:
        return Flag.UNKNOWN
    return Flag.NORMAL


def _severity(value: float, flag: Flag, low: float | None, high: float | None, ref) -> Severity:
    if flag == Flag.NORMAL:
        return Severity.NORMAL
    if flag == Flag.UNKNOWN:
        return Severity.UNKNOWN

    if ref and (value <= ref.critical_low or value >= ref.critical_high):
        return Severity.CRITICAL

    if flag == Flag.LOW and low:
        distance = (low - value) / max(abs(low), 1)
    elif flag == Flag.HIGH and high:
        distance = (value - high) / max(abs(high), 1)
    else:
        return Severity.MILD

    if distance >= 0.5:
        return Severity.MODERATE
    return Severity.MILD
