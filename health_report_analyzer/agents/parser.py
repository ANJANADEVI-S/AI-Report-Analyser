from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re

from health_report_analyzer.models import LabResult, Report


DATE_PATTERNS = [
    re.compile(r"(?:report\s*date|date)\s*[:\-]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})", re.I),
    re.compile(r"(?:report\s*date|date)\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})", re.I),
]

RESULT_PATTERNS = [
    re.compile(
        r"^(?P<name>[A-Za-z][A-Za-z0-9 /().,%+-]{2,}?)\s+"
        r"(?P<value>-?\d+(?:\.\d+)?)\s*"
        r"(?P<unit>[A-Za-z0-9/%^µμ.\-]+(?:/[A-Za-z0-9]+)?)?\s+"
        r"(?P<low>-?\d+(?:\.\d+)?)\s*[-–]\s*(?P<high>-?\d+(?:\.\d+)?)$"
    ),
    re.compile(
        r"^(?P<name>[A-Za-z][A-Za-z0-9 /().,%+-]{2,}?)\s+"
        r"(?P<value>-?\d+(?:\.\d+)?)\s*"
        r"(?P<unit>[A-Za-z0-9/%^µμ.\-]+(?:/[A-Za-z0-9]+)?)?\s+"
        r"(?P<operator>[<>])\s*(?P<bound>-?\d+(?:\.\d+)?)$"
    ),
]


def extract_text_from_pdf(path: Path) -> str:
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_image(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(path))
    except Exception as exc:
        return (
            "OCR could not read this image automatically. "
            f"Please paste the report text manually. Error: {exc}"
        )


def parse_report_text(raw_text: str, source_name: str = "", patient_id: str = "default") -> Report:
    patient_name = _extract_patient_name(raw_text)
    report_date = _extract_report_date(raw_text)
    results = [_parse_line(line) for line in raw_text.splitlines()]
    return Report(
        patient_id=patient_id,
        patient_name=patient_name,
        report_date=report_date,
        source_name=source_name,
        raw_text=raw_text,
        results=[result for result in results if result is not None],
    )


def parse_report_file(path: Path, patient_id: str = "default") -> Report:
    if path.suffix.lower() == ".pdf":
        text = extract_text_from_pdf(path)
    elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
        text = extract_text_from_image(path)
    else:
        text = path.read_text(encoding="utf-8")
    return parse_report_text(text, source_name=path.name, patient_id=patient_id)


def _parse_line(line: str) -> LabResult | None:
    clean_line = " ".join(line.strip().split())
    if not clean_line:
        return None

    for pattern in RESULT_PATTERNS:
        match = pattern.match(clean_line)
        if not match:
            continue

        data = match.groupdict()
        low = data.get("low")
        high = data.get("high")
        raw_range = ""
        if low is not None and high is not None:
            reference_low = float(low)
            reference_high = float(high)
            raw_range = f"{low} - {high}"
        else:
            bound = float(data["bound"])
            if data["operator"] == "<":
                reference_low = 0.0
                reference_high = bound
                raw_range = f"< {data['bound']}"
            else:
                reference_low = bound
                reference_high = None
                raw_range = f"> {data['bound']}"

        return LabResult(
            test_name=data["name"].strip(" :-"),
            value=float(data["value"]),
            unit=(data.get("unit") or "").strip(),
            reference_low=reference_low,
            reference_high=reference_high,
            raw_reference_range=raw_range,
        )
    return None


def _extract_patient_name(raw_text: str) -> str:
    match = re.search(r"(?:patient|name)\s*[:\-]\s*([A-Za-z .]+)", raw_text, re.I)
    return match.group(1).strip() if match else ""


def _extract_report_date(raw_text: str) -> date:
    for pattern in DATE_PATTERNS:
        match = pattern.search(raw_text)
        if not match:
            continue
        value = match.group(1).replace("/", "-")
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass
    return date.today()
