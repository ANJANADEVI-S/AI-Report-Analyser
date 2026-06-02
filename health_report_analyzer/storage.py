from __future__ import annotations

from datetime import date
import json
import sqlite3
from pathlib import Path

from health_report_analyzer.models import Report


DB_PATH = Path("health_reports.db")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            patient_name TEXT,
            report_date TEXT NOT NULL,
            source_name TEXT,
            raw_text TEXT,
            report_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def save_report(report: Report, db_path: Path = DB_PATH) -> int:
    conn = get_connection(db_path)
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO reports (patient_id, patient_name, report_date, source_name, raw_text, report_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report.patient_id,
                report.patient_name,
                report.report_date.isoformat(),
                report.source_name,
                report.raw_text,
                report.model_dump_json(),
            ),
        )
    conn.close()
    return int(cursor.lastrowid)


def load_reports(patient_id: str, db_path: Path = DB_PATH) -> list[Report]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT report_json FROM reports WHERE patient_id = ? ORDER BY report_date ASC, id ASC",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [Report.model_validate(json.loads(row["report_json"])) for row in rows]


def list_patients(db_path: Path = DB_PATH) -> list[str]:
    conn = get_connection(db_path)
    rows = conn.execute("SELECT DISTINCT patient_id FROM reports ORDER BY patient_id").fetchall()
    conn.close()
    return [row["patient_id"] for row in rows]


def seed_demo_history(patient_id: str = "demo") -> None:
    if load_reports(patient_id):
        return
    from health_report_analyzer.agents.detector import detect_abnormalities
    from health_report_analyzer.agents.explainer import explain_result
    from health_report_analyzer.agents.parser import parse_report_text

    texts = [
        """
        Patient: Demo Patient
        Report Date: 2026-02-10
        Hemoglobin 11.7 g/dL 12.0 - 17.5
        Fasting Glucose 104 mg/dL 70 - 99
        HbA1c 5.8 % 4.0 - 5.6
        LDL Cholesterol 128 mg/dL < 100
        HDL Cholesterol 41 mg/dL > 40
        Triglycerides 158 mg/dL < 150
        Creatinine 1.0 mg/dL 0.6 - 1.3
        """,
        """
        Patient: Demo Patient
        Report Date: 2026-04-15
        Hemoglobin 11.2 g/dL 12.0 - 17.5
        Fasting Glucose 112 mg/dL 70 - 99
        HbA1c 6.0 % 4.0 - 5.6
        LDL Cholesterol 136 mg/dL < 100
        HDL Cholesterol 39 mg/dL > 40
        Triglycerides 169 mg/dL < 150
        Creatinine 1.1 mg/dL 0.6 - 1.3
        """,
    ]
    for index, text in enumerate(texts, start=1):
        report = detect_abnormalities(parse_report_text(text, f"demo_history_{index}.txt", patient_id))
        report.report_date = date.fromisoformat(report.report_date.isoformat())
        for result in report.results:
            result.explanation = explain_result(result)
        save_report(report)
