from contextlib import closing
import csv
import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "matrikontho.db"

TABLE_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("created_at", "TEXT NOT NULL"),
    ("patient_name", "TEXT"),
    ("pregnancy_status", "TEXT"),
    ("gestational_weeks", "INTEGER"),
    ("transcript", "TEXT"),
    ("extraction_method", "TEXT"),
    ("extraction_json", "TEXT"),
    ("risk_level", "TEXT"),
    ("reasons", "TEXT"),
    ("recommendation", "TEXT"),
    ("advice", "TEXT"),
    ("referral_sms", "TEXT"),
    ("speaker", "TEXT"),
    ("village", "TEXT"),
    ("bp_systolic", "INTEGER"),
    ("bp_diastolic", "INTEGER"),
    ("referral_facility", "TEXT"),
    ("sms_sent", "INTEGER"),
]

LIST_COLUMNS = [name for name, _ in TABLE_COLUMNS if name != "extraction_json"]

EXPORT_HEADERS = [name for name, _ in TABLE_COLUMNS]


def _get_connection():
    target_path = Path(DB_PATH)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(target_path)
    connection.row_factory = sqlite3.Row
    return connection


def _clean_positive_int(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if value > 0 else None


def init_db():
    """Create the assessment table and apply lightweight column migrations if needed."""
    with closing(_get_connection()) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    patient_name TEXT,
                    pregnancy_status TEXT,
                    gestational_weeks INTEGER,
                    transcript TEXT,
                    extraction_method TEXT,
                    extraction_json TEXT,
                    risk_level TEXT,
                    reasons TEXT,
                    recommendation TEXT,
                    advice TEXT,
                    referral_sms TEXT
                )
                """
            )

            existing_cols = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(assessments)").fetchall()
            }
            for col_name, col_def in TABLE_COLUMNS:
                if col_name not in existing_cols and "PRIMARY KEY" not in col_def:
                    connection.execute(
                        f"ALTER TABLE assessments ADD COLUMN {col_name} {col_def}"
                    )


def save_assessment(
    transcript,
    extraction,
    result,
    advice=None,
    sms=None,
    gestational_weeks=None,
    pregnancy_status=None,
    patient_name=None,
    speaker=None,
    village=None,
    bp_systolic=None,
    bp_diastolic=None,
    referral_facility=None,
    sms_sent=False,
):
    """Save one assessment and return its database ID."""
    init_db()

    extraction = extraction if isinstance(extraction, dict) else {}
    result = result if isinstance(result, dict) else {}

    advice_text = (
        "\n".join(str(item) for item in advice if item is not None)
        if isinstance(advice, list)
        else str(advice or "")
    )

    reasons = result.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [str(reasons)] if reasons else []

    clean_weeks = (
        int(gestational_weeks)
        if isinstance(gestational_weeks, (int, float))
        and not isinstance(gestational_weeks, bool)
        and gestational_weeks > 0
        else None
    )

    with closing(_get_connection()) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO assessments (
                    created_at,
                    patient_name,
                    pregnancy_status,
                    gestational_weeks,
                    transcript,
                    extraction_method,
                    extraction_json,
                    risk_level,
                    reasons,
                    recommendation,
                    advice,
                    referral_sms,
                    speaker,
                    village,
                    bp_systolic,
                    bp_diastolic,
                    referral_facility,
                    sms_sent
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    patient_name,
                    pregnancy_status,
                    clean_weeks,
                    transcript or "",
                    extraction.get("extraction_method", "unknown"),
                    json.dumps(extraction, ensure_ascii=False),
                    str(result.get("risk_level", "UNKNOWN")).upper(),
                    json.dumps(reasons, ensure_ascii=False),
                    str(result.get("recommendation", "")),
                    advice_text,
                    str(sms or ""),
                    speaker,
                    (village or "").strip() or None,
                    _clean_positive_int(bp_systolic),
                    _clean_positive_int(bp_diastolic),
                    referral_facility,
                    1 if sms_sent else 0,
                ),
            )

            return cursor.lastrowid


def list_assessments(limit=200):
    """Return recent assessments as dictionaries for the dashboard."""
    init_db()
    safe_limit = max(1, int(limit))

    with closing(_get_connection()) as connection:
        rows = connection.execute(
            f"""
            SELECT {", ".join(LIST_COLUMNS)}
            FROM assessments
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    records = []

    for row in rows:
        record = dict(row)

        try:
            parsed_reasons = json.loads(record["reasons"] or "[]")
            record["reasons"] = (
                parsed_reasons if isinstance(parsed_reasons, list) else []
            )
        except json.JSONDecodeError:
            record["reasons"] = []

        records.append(record)

    return records


def export_csv():
    """Return all assessment records as CSV text."""
    init_db()

    with closing(_get_connection()) as connection:
        rows = connection.execute(
            f"""
            SELECT {", ".join(EXPORT_HEADERS)}
            FROM assessments
            ORDER BY id DESC
            """
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    if rows:
        headers = list(rows[0].keys())
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row[key] for key in headers])
    else:
        writer.writerow(EXPORT_HEADERS)

    return output.getvalue()
