"""
Phase 3 — LLM-based structured extraction from free-text eligibility criteria.

ClinicalTrials.gov stores who-can-join rules as one big block of free text
(eligibilityCriteria), not as separate columns. This script pulls that text
out of raw_json for every trial in glp1_drug_trials, asks Claude to read it
and pull out a handful of structured fields, and writes the results into
the `eligibility_extracted` table.

Same pattern as categorize_terminations.py (one row in, one LLM call, one
structured row out) but at a bigger scale — 579 trials instead of 17 — so
this version adds:
  - a progress line per trial
  - skip-if-already-done, so an interrupted run can just be re-run instead
    of starting over
  - a small delay between calls to stay well under API rate limits

Run:
    python3 src/extract_eligibility.py

Requires ANTHROPIC_API_KEY in your .env file, in addition to the DB_* vars
already used by ingest.py.
"""

import json
import os
import time

import mysql.connector
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

SEX_VALUES = ["ALL", "FEMALE", "MALE"]

SYSTEM_PROMPT = """You are extracting structured facts from a clinical trial's
eligibility criteria text (who can and cannot join the trial).

Read the eligibility criteria text and return ONLY a JSON object in this
exact shape, nothing else:

{
  "min_age": <integer years, or null if not stated/unclear>,
  "max_age": <integer years, or null if no upper bound is stated>,
  "sex_restriction": "<ALL, FEMALE, or MALE>",
  "excludes_prior_bariatric_surgery": <true if prior bariatric/weight-loss
      surgery is listed as an exclusion criterion, else false>,
  "restricted_comorbidity": "<a short lowercase phrase like 'type 2 diabetes',
      'pcos', or 'heart failure' if the trial requires participants to have
      a specific medical condition beyond obesity/overweight itself, else
      null if there's no such extra requirement>",
  "healthy_volunteers_allowed": <true if the text explicitly says healthy
      volunteers are accepted, else false>
}

Rules:
- Ages are usually given like "Minimum Age: 18 Years" / "Maximum Age: 75 Years".
  If a max age is missing or says "N/A", use null.
- If the text doesn't clearly state a field, use null (or false for the
  boolean fields) rather than guessing.
- restricted_comorbidity should stay null for trials that are simply about
  obesity/overweight/weight loss in general — only fill it in when the
  trial requires an ADDITIONAL specific condition (e.g. "participants with
  type 2 diabetes", "women with PCOS", "adults with heart failure").
"""


def fetch_trials_needing_extraction() -> list[dict]:
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "glp1_trials"),
    )
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT t.nct_id,
               JSON_UNQUOTE(JSON_EXTRACT(
                   t.raw_json,
                   '$.protocolSection.eligibilityModule.eligibilityCriteria'
               )) AS eligibility_criteria
        FROM glp1_drug_trials t
        LEFT JOIN eligibility_extracted e ON e.nct_id = t.nct_id
        WHERE e.nct_id IS NULL
          AND JSON_EXTRACT(
                  t.raw_json,
                  '$.protocolSection.eligibilityModule.eligibilityCriteria'
              ) IS NOT NULL
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def extract_fields(client: Anthropic, eligibility_criteria: str) -> dict:
    """Ask Claude to extract structured fields from one trial's eligibility
    text. Returns a dict matching the table's columns, falling back to a
    safe all-null/false default if the model's response can't be parsed."""
    fallback = {
        "min_age": None,
        "max_age": None,
        "sex_restriction": "ALL",
        "excludes_prior_bariatric_surgery": False,
        "restricted_comorbidity": None,
        "healthy_volunteers_allowed": False,
    }

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Eligibility criteria:\n{eligibility_criteria}"}
        ],
    )
    raw_text = message.content[0].text.strip()

    # Claude sometimes wraps its JSON answer in a markdown code fence
    # (```json ... ```) even when told to return JSON only. Strip that
    # off before parsing, so a fenced-but-otherwise-valid response
    # doesn't get treated as unparseable.
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
        if result.get("sex_restriction") not in SEX_VALUES:
            result["sex_restriction"] = "ALL"
        return {
            "min_age": result.get("min_age"),
            "max_age": result.get("max_age"),
            "sex_restriction": result.get("sex_restriction"),
            "excludes_prior_bariatric_surgery": bool(result.get("excludes_prior_bariatric_surgery")),
            "restricted_comorbidity": result.get("restricted_comorbidity"),
            "healthy_volunteers_allowed": bool(result.get("healthy_volunteers_allowed")),
        }
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        print(f"  WARNING: couldn't parse response ({e}). Raw response: {raw_text!r}")
        return fallback


UPSERT_SQL = """
INSERT INTO eligibility_extracted (
    nct_id, min_age, max_age, sex_restriction,
    excludes_prior_bariatric_surgery, restricted_comorbidity,
    healthy_volunteers_allowed
)
VALUES (
    %(nct_id)s, %(min_age)s, %(max_age)s, %(sex_restriction)s,
    %(excludes_prior_bariatric_surgery)s, %(restricted_comorbidity)s,
    %(healthy_volunteers_allowed)s
)
ON DUPLICATE KEY UPDATE
    min_age = VALUES(min_age),
    max_age = VALUES(max_age),
    sex_restriction = VALUES(sex_restriction),
    excludes_prior_bariatric_surgery = VALUES(excludes_prior_bariatric_surgery),
    restricted_comorbidity = VALUES(restricted_comorbidity),
    healthy_volunteers_allowed = VALUES(healthy_volunteers_allowed);
"""


def save_result(row: dict) -> None:
    """Save one trial's result immediately (rather than batching all 579),
    so an interrupted run doesn't lose already-completed work."""
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "glp1_trials"),
    )
    cur = conn.cursor()
    cur.execute(UPSERT_SQL, row)
    conn.commit()
    cur.close()
    conn.close()


def main():
    trials = fetch_trials_needing_extraction()
    print(f"Found {len(trials)} trials still needing eligibility extraction.")

    if not trials:
        print("Nothing to do — all trials already processed. "
              "(Delete rows from eligibility_extracted to re-run any of them.)")
        return

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    done = 0
    for i, trial in enumerate(trials, start=1):
        nct_id = trial["nct_id"]
        criteria = trial["eligibility_criteria"]

        print(f"[{i}/{len(trials)}] Extracting {nct_id}...")

        try:
            fields = extract_fields(client, criteria)
            row = {"nct_id": nct_id, **fields}
            save_result(row)
            done += 1
            print(
                f"    -> age {fields['min_age']}-{fields['max_age']}, "
                f"sex={fields['sex_restriction']}, "
                f"excludes_bariatric={fields['excludes_prior_bariatric_surgery']}, "
                f"comorbidity={fields['restricted_comorbidity']}, "
                f"healthy_ok={fields['healthy_volunteers_allowed']}"
            )
        except Exception as e:
            # Don't let one bad trial kill the whole run — just skip it.
            # Since we skip already-done trials, re-running the script
            # later will retry this one automatically.
            print(f"    ERROR on {nct_id}: {e}. Skipping — will retry on next run.")

        time.sleep(0.5)  # stay comfortably under API rate limits

    print(f"\nDone. Saved {done}/{len(trials)} extractions to eligibility_extracted.")


if __name__ == "__main__":
    main()
