from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Flag(str, Enum):
    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    NORMAL = "normal"
    MILD = "mild"
    MODERATE = "moderate"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class LabResult(BaseModel):
    test_name: str
    value: float
    unit: str = ""
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    raw_reference_range: str = ""
    canonical_name: Optional[str] = None
    flag: Flag = Flag.UNKNOWN
    severity: Severity = Severity.UNKNOWN
    explanation: str = ""


class Report(BaseModel):
    patient_id: str = "default"
    patient_name: str = ""
    report_date: date = Field(default_factory=date.today)
    source_name: str = ""
    raw_text: str = ""
    results: list[LabResult] = Field(default_factory=list)


class TrendPoint(BaseModel):
    report_date: date
    value: float
    flag: Flag
    severity: Severity


class TrendInsight(BaseModel):
    test_name: str
    points: list[TrendPoint]
    direction: str
    message: str


class AnalysisOutput(BaseModel):
    report: Report
    patient_summary: str
    abnormal_results: list[LabResult]
    doctor_questions: list[str]
    trend_insights: list[TrendInsight]
