"""
Phase 1 — Ingestion script
Pulls obesity / GLP-1 clinical trials from the ClinicalTrials.gov v2 API,
parses the nested JSON into flat records, and upserts them into MySQL.

Run:
    python src/ingest.py

Requires a .env file (see .env.example) with your DB credentials.
"""

import json
import os
from datetime import datetime, date
from pathlib import Path

import requests
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://clinicaltrials.gov/api/v2/studies"

# Essie search expression: obesity/weight-loss trials involving GLP-1
# class drugs. Adjust freely — this is the single knob that controls
# your whole dataset.
QUERY_TERM = (
    'AREA[ConditionSearch](obesity OR "weight loss" OR overweight) '
    'AND AREA[InterventionSearch](semaglutide OR tirzepatide OR liraglutide '
    'OR "GLP-1" OR "GLP1" OR retatrutide OR "glucagon-like peptide")'
)

PAGE_SIZE = 100
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch_all_studies(query_term: str) -> list[dict]:
    """Page through the ClinicalTrials.gov v2 API and return all raw study records."""
    studies = []
    params = {
        "query.term": query_term,
        "pageSize": PAGE_SIZE,
        "format": "json",
    }
    page = 1

    while True:
        resp = requests.get(API_BASE, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        batch = payload.get("studies", [])
        studies.extend(batch)
        print(f"  page {page}: fetched {len(batch)} studies (running total: {len(studies)})")

        next_token = payload.get("nextPageToken")
        if not next_token:
            break
        params["pageToken"] = next_token
        page += 1

    return studies


def _get(d: dict, *path, default=None):
    """Safely walk a nested dict; returns `default` if any key is missing."""
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _parse_date(date_struct: dict | None) -> tuple[str | None, str | None]:
    """
    ClinicalTrials.gov dates come as {'date': '2024-01-15', 'type': 'ACTUAL'}
    or sometimes just a month/year like '2024-01'. Normalize to a MySQL-safe
    DATE string (day defaults to 01 when missing) and keep the type separately.
    """
    if not date_struct:
        return None, None
    raw = date_struct.get("date")
    date_type = date_struct.get("type")
    if not raw:
        return None, date_type

    parts = raw.split("-")
    if len(parts) == 3:
        normalized = raw
    elif len(parts) == 2:
        normalized = f"{raw}-01"
    elif len(parts) == 1:
        normalized = f"{raw}-01-01"
    else:
        normalized = None
    return normalized, date_type


def parse_study(study: dict) -> dict:
    """Flatten one ClinicalTrials.gov v2 study record into a row for the `trials` table."""
    protocol = study.get("protocolSection", {})

    nct_id = _get(protocol, "identificationModule", "nctId")
    brief_title = _get(protocol, "identificationModule", "briefTitle")

    overall_status = _get(protocol, "statusModule", "overallStatus")
    why_stopped = _get(protocol, "statusModule", "whyStopped")

    start_raw = _get(protocol, "statusModule", "startDateStruct")
    start_date, start_date_type = _parse_date(start_raw)

    completion_raw = _get(protocol, "statusModule", "completionDateStruct")
    completion_date, completion_date_type = _parse_date(completion_raw)

    submit_raw = {"date": _get(protocol, "statusModule", "studyFirstSubmitDate")}
    study_first_submit_date, _ = _parse_date(submit_raw)

    update_raw = _get(protocol, "statusModule", "lastUpdatePostDateStruct")
    last_update_post_date, _ = _parse_date(update_raw)

    phases = _get(protocol, "designModule", "phases", default=[])
    phase = "|".join(phases) if phases else None

    study_type = _get(protocol, "designModule", "studyType")

    enrollment_count = _get(protocol, "designModule", "enrollmentInfo", "count")
    enrollment_type = _get(protocol, "designModule", "enrollmentInfo", "type")

    lead_sponsor_name = _get(protocol, "sponsorCollaboratorsModule", "leadSponsor", "name")
    lead_sponsor_class = _get(protocol, "sponsorCollaboratorsModule", "leadSponsor", "class")

    conditions = _get(protocol, "conditionsModule", "conditions", default=[])
    conditions_str = "|".join(conditions) if conditions else None

    interventions_list = _get(protocol, "armsInterventionsModule", "interventions", default=[])
    interventions_str = "|".join(
        i.get("name", "") for i in interventions_list if i.get("name")
    ) or None

    locations = _get(protocol, "contactsLocationsModule", "locations", default=[])
    countries = sorted({loc.get("country") for loc in locations if loc.get("country")})
    countries_str = "|".join(countries) if countries else None

    return {
        "nct_id": nct_id,
        "brief_title": brief_title,
        "overall_status": overall_status,
        "phase": phase,
        "study_type": study_type,
        "lead_sponsor_name": lead_sponsor_name,
        "lead_sponsor_class": lead_sponsor_class,
        "enrollment_count": enrollment_count,
        "enrollment_type": enrollment_type,
        "conditions": conditions_str,
        "interventions": interventions_str,
        "start_date": start_date,
        "start_date_type": start_date_type,
        "completion_date": completion_date,
        "completion_date_type": completion_date_type,
        "study_first_submit_date": study_first_submit_date,
        "last_update_post_date": last_update_post_date,
        "locations_countries": countries_str,
        "why_stopped": why_stopped,
        "raw_json": json.dumps(study),
    }


UPSERT_SQL = """
INSERT INTO trials (
    nct_id, brief_title, overall_status, phase, study_type,
    lead_sponsor_name, lead_sponsor_class, enrollment_count, enrollment_type,
    conditions, interventions, start_date, start_date_type,
    completion_date, completion_date_type, study_first_submit_date,
    last_update_post_date, locations_countries, why_stopped, raw_json
) VALUES (
    %(nct_id)s, %(brief_title)s, %(overall_status)s, %(phase)s, %(study_type)s,
    %(lead_sponsor_name)s, %(lead_sponsor_class)s, %(enrollment_count)s, %(enrollment_type)s,
    %(conditions)s, %(interventions)s, %(start_date)s, %(start_date_type)s,
    %(completion_date)s, %(completion_date_type)s, %(study_first_submit_date)s,
    %(last_update_post_date)s, %(locations_countries)s, %(why_stopped)s, %(raw_json)s
)
ON DUPLICATE KEY UPDATE
    brief_title = VALUES(brief_title),
    overall_status = VALUES(overall_status),
    phase = VALUES(phase),
    study_type = VALUES(study_type),
    lead_sponsor_name = VALUES(lead_sponsor_name),
    lead_sponsor_class = VALUES(lead_sponsor_class),
    enrollment_count = VALUES(enrollment_count),
    enrollment_type = VALUES(enrollment_type),
    conditions = VALUES(conditions),
    interventions = VALUES(interventions),
    start_date = VALUES(start_date),
    start_date_type = VALUES(start_date_type),
    completion_date = VALUES(completion_date),
    completion_date_type = VALUES(completion_date_type),
    study_first_submit_date = VALUES(study_first_submit_date),
    last_update_post_date = VALUES(last_update_post_date),
    locations_countries = VALUES(locations_countries),
    why_stopped = VALUES(why_stopped),
    raw_json = VALUES(raw_json);
"""


def load_to_db(rows: list[dict]) -> tuple[int, int]:
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "glp1_trials"),
    )
    cur = conn.cursor()

    # Count existing rows before, so we can report inserted vs updated.
    cur.execute("SELECT COUNT(*) FROM trials")
    before_count = cur.fetchone()[0]

    for row in rows:
        cur.execute(UPSERT_SQL, row)

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM trials")
    after_count = cur.fetchone()[0]
    inserted = after_count - before_count
    updated = len(rows) - inserted

    cur.execute(
        """INSERT INTO pull_log (query_term, records_fetched, records_inserted, records_updated)
           VALUES (%s, %s, %s, %s)""",
        (QUERY_TERM, len(rows), inserted, updated),
    )
    conn.commit()
    cur.close()
    conn.close()
    return inserted, updated


def save_raw_snapshot(studies: list[dict]) -> Path:
    """Archive the raw pull to disk as JSONL — this becomes the input for
    the Phase 5 diff/surveillance logic later (compare today's file to
    the previous one)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_path = RAW_DIR / f"pull_{stamp}.jsonl"
    with open(out_path, "w") as f:
        for s in studies:
            f.write(json.dumps(s) + "\n")
    return out_path


def main():
    print("Fetching GLP-1 / obesity trials from ClinicalTrials.gov API v2...")
    studies = fetch_all_studies(QUERY_TERM)
    print(f"Total studies fetched: {len(studies)}")

    raw_path = save_raw_snapshot(studies)
    print(f"Raw snapshot saved to: {raw_path}")

    rows = [parse_study(s) for s in studies]
    rows = [r for r in rows if r["nct_id"]]  # drop anything malformed

    print("Loading into MySQL...")
    inserted, updated = load_to_db(rows)
    print(f"Done. Inserted: {inserted}, Updated: {updated}, Total in this pull: {len(rows)}")


if __name__ == "__main__":
    main()
