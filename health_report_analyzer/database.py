from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


PACKAGE_ROOT = Path(__file__).parent
PROJECT_ROOT = PACKAGE_ROOT.parent
REFERENCE_DB_PATH = PACKAGE_ROOT / "data" / "medical_reference.db"
DEFAULT_SEED_CSV = PROJECT_ROOT / "medical_reference_seed.csv"


def normalize_marker_name(name: str) -> str:
    return " ".join(
        name.lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("/", " ")
        .split()
    )


def get_reference_connection(db_path: Path = REFERENCE_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_reference_schema(conn)
    return conn


def create_reference_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS biomarker_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_name TEXT NOT NULL UNIQUE,
            normalized_name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            unit TEXT NOT NULL,
            ref_low REAL,
            ref_high REAL,
            normal_condition TEXT NOT NULL,
            low_interpretation TEXT NOT NULL,
            high_interpretation TEXT NOT NULL,
            severity_notes TEXT NOT NULL,
            related_tests TEXT NOT NULL,
            source_note TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS biomarker_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            biomarker_id INTEGER NOT NULL,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL UNIQUE,
            FOREIGN KEY (biomarker_id) REFERENCES biomarker_tests(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_biomarker_aliases_name ON biomarker_aliases(normalized_alias)")


def seed_reference_database(
    seed_csv: Path = DEFAULT_SEED_CSV,
    db_path: Path = REFERENCE_DB_PATH,
    replace: bool = False,
) -> int:
    if not seed_csv.exists():
        raise FileNotFoundError(f"Reference seed CSV not found: {seed_csv}")

    conn = get_reference_connection(db_path)
    inserted = 0
    with conn:
        if replace:
            conn.execute("DELETE FROM biomarker_aliases")
            conn.execute("DELETE FROM biomarker_tests")

        with seed_csv.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                test_name = row["test_name"].strip()
                normalized = normalize_marker_name(test_name)
                cursor = conn.execute(
                    """
                    INSERT INTO biomarker_tests (
                        test_name, normalized_name, category, unit, ref_low, ref_high,
                        normal_condition, low_interpretation, high_interpretation,
                        severity_notes, related_tests, source_note
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(normalized_name) DO UPDATE SET
                        test_name = excluded.test_name,
                        category = excluded.category,
                        unit = excluded.unit,
                        ref_low = excluded.ref_low,
                        ref_high = excluded.ref_high,
                        normal_condition = excluded.normal_condition,
                        low_interpretation = excluded.low_interpretation,
                        high_interpretation = excluded.high_interpretation,
                        severity_notes = excluded.severity_notes,
                        related_tests = excluded.related_tests,
                        source_note = excluded.source_note,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        test_name,
                        normalized,
                        row["category"].strip(),
                        row["unit"].strip(),
                        _to_float(row["ref_low"]),
                        _to_float(row["ref_high"]),
                        row["normal_condition"].strip(),
                        row["low_interpretation"].strip(),
                        row["high_interpretation"].strip(),
                        row["severity_notes"].strip(),
                        row["related_tests"].strip(),
                        row["source_note"].strip(),
                    ),
                )
                biomarker_id = _get_biomarker_id(conn, normalized)
                inserted += 1 if cursor.rowcount else 0

                aliases = [test_name, *(alias.strip() for alias in row["aliases"].split("|") if alias.strip())]
                for alias in aliases:
                    conn.execute(
                        """
                        INSERT INTO biomarker_aliases (biomarker_id, alias, normalized_alias)
                        VALUES (?, ?, ?)
                        ON CONFLICT(normalized_alias) DO UPDATE SET
                            biomarker_id = excluded.biomarker_id,
                            alias = excluded.alias
                        """,
                        (biomarker_id, alias, normalize_marker_name(alias)),
                    )
    conn.close()
    return inserted


def lookup_biomarker(name: str, db_path: Path = REFERENCE_DB_PATH) -> sqlite3.Row | None:
    normalized = normalize_marker_name(name)
    conn = get_reference_connection(db_path)
    row = conn.execute(
        """
        SELECT bt.*
        FROM biomarker_tests bt
        LEFT JOIN biomarker_aliases ba ON ba.biomarker_id = bt.id
        WHERE bt.normalized_name = ? OR ba.normalized_alias = ?
        LIMIT 1
        """,
        (normalized, normalized),
    ).fetchone()

    if row is None:
        row = conn.execute(
            """
            SELECT bt.*
            FROM biomarker_tests bt
            LEFT JOIN biomarker_aliases ba ON ba.biomarker_id = bt.id
            WHERE bt.normalized_name LIKE ? OR ba.normalized_alias LIKE ?
            LIMIT 1
            """,
            (f"%{normalized}%", f"%{normalized}%"),
        ).fetchone()

    conn.close()
    return row


def _get_biomarker_id(conn: sqlite3.Connection, normalized_name: str) -> int:
    row = conn.execute(
        "SELECT id FROM biomarker_tests WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Could not find inserted biomarker: {normalized_name}")
    return int(row["id"])


def _to_float(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    return float(value)
