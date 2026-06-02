# AI Health Report Analyzer & Patient Summary Agent

An MVP for parsing lab reports, flagging abnormal values, explaining findings in patient-friendly language, tracking trends over time, and generating doctor-visit questions.

## Features

- Upload PDF/image lab reports or paste extracted report text.
- Extract structured lab values using regex-based parsing, with optional OCR for image reports.
- Detect low, high, and critical values using a local medical reference database.
- Generate plain-language summaries with strict safety boundaries.
- Store patient reports in SQLite.
- Visualize trends across multiple reports.
- Suggest questions to ask a doctor.

## Safety Note

This app is educational and does not diagnose, treat, or replace medical advice. It always recommends discussing abnormal or concerning results with a qualified clinician.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Optional: set `OPENAI_API_KEY` in a `.env` file to enable LLM-assisted summaries. Without a key, the app uses deterministic local summaries.

## Project Structure

```text
health_report_analyzer/
  agents/
    parser.py
    detector.py
    explainer.py
    trend.py
  data/reference_ranges.csv
  models.py
  storage.py
  pipeline.py
app.py
sample_reports/sample_report_1.txt
```

## Agent Pipeline

1. Report Parser extracts test name, value, unit, and reference range.
2. Abnormality Detector normalizes tests and classifies severity.
3. Medical Explainer produces patient-friendly summaries and doctor questions.
4. Trend Analyzer compares the current report with previous reports.
