from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import csv
import math

from health_report_analyzer.database import REFERENCE_DB_PATH, lookup_biomarker, seed_reference_database


DATA_PATH = Path(__file__).parent / "data" / "reference_ranges.csv"


@dataclass(frozen=True)
class ReferenceRange:
    canonical_name: str
    aliases: tuple[str, ...]
    unit: str
    low: float | None
    high: float | None
    critical_low: float
    critical_high: float
    plain_name: str
    description: str
    category: str = ""
    normal_condition: str = "between"
    low_interpretation: str = ""
    high_interpretation: str = ""
    severity_notes: str = ""
    related_tests: tuple[str, ...] = ()

    @property
    def all_names(self) -> tuple[str, ...]:
        return (self.canonical_name, *self.aliases)


@lru_cache(maxsize=1)
def load_reference_ranges() -> list[ReferenceRange]:
    ranges: list[ReferenceRange] = []
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ranges.append(
                ReferenceRange(
                    canonical_name=row["canonical_name"],
                    aliases=tuple(alias.strip() for alias in row["aliases"].split("|") if alias.strip()),
                    unit=row["unit"],
                    low=float(row["low"]),
                    high=float(row["high"]),
                    critical_low=float(row["critical_low"]),
                    critical_high=float(row["critical_high"]),
                    plain_name=row["plain_name"],
                    description=row["description"],
                )
            )
    return ranges


def normalize_name(name: str) -> str:
    return " ".join(name.lower().replace("-", " ").replace("_", " ").split())


def find_reference(test_name: str) -> ReferenceRange | None:
    db_reference = _find_reference_from_db(test_name)
    if db_reference:
        return db_reference

    normalized = normalize_name(test_name)
    for ref in load_reference_ranges():
        if any(normalize_name(candidate) == normalized for candidate in ref.all_names):
            return ref
    for ref in load_reference_ranges():
        if any(normalize_name(candidate) in normalized or normalized in normalize_name(candidate) for candidate in ref.all_names):
            return ref
    return None


def _find_reference_from_db(test_name: str) -> ReferenceRange | None:
    if not REFERENCE_DB_PATH.exists():
        try:
            seed_reference_database()
        except FileNotFoundError:
            return None

    row = lookup_biomarker(test_name)
    if row is None:
        return None

    low = row["ref_low"]
    high = row["ref_high"]
    return ReferenceRange(
        canonical_name=row["test_name"],
        aliases=(),
        unit=row["unit"],
        low=low,
        high=high,
        critical_low=_critical_low(low),
        critical_high=_critical_high(high),
        plain_name=row["test_name"],
        description=_description_for(row),
        category=row["category"],
        normal_condition=row["normal_condition"],
        low_interpretation=row["low_interpretation"],
        high_interpretation=row["high_interpretation"],
        severity_notes=row["severity_notes"],
        related_tests=tuple(test.strip() for test in row["related_tests"].split("|") if test.strip()),
    )


def _description_for(row) -> str:
    parts = [row["severity_notes"]]
    if row["low_interpretation"]:
        parts.append(f"If low: {row['low_interpretation']}")
    if row["high_interpretation"]:
        parts.append(f"If high: {row['high_interpretation']}")
    return " ".join(part for part in parts if part)


def _critical_low(low: float | None) -> float:
    if low is None:
        return -math.inf
    return low * 0.5 if low > 0 else low - 1


def _critical_high(high: float | None) -> float:
    if high is None:
        return math.inf
    return high * 1.5 if high > 0 else high + 1
