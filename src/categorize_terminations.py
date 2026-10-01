"""
Phase 2 stretch — LLM-based categorization of trial termination reasons.

Pulls every TERMINATED trial's `why_stopped` text from MySQL, asks Claude to
classify each one into a category (SAFETY / RECRUITMENT / FUNDING_STRATEGIC /
ADMINISTRATIVE_OTHER) with a brief justification, and writes the results into
the `termination_categories` table.

This is a small, self-contained preview of the same pattern Phase 4/5 will use
at larger scale (an LLM reading structured data and returning a structured
judgment) — good to build and test now, on a small, human-checkable dataset.

Run:
    python src/categorize_terminations.py

Requires ANTHROPIC_API_KEY in your .env file, in addition to the DB_* vars
already used by ingest.py.
"""

import json
import os

import mysql.connector
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

CATEGORIES = ["SAFETY", "RECRUITMENT", "FUNDING_STRATEGIC", "ADMINISTRATIVE_OTHER"]

SYSTEM_PROMPT = f"""You are classifying why a clinical trial was terminated early.

Read the trial's title and its stated termination reason, then classify it into
exactly one of these categories:

- SAFETY: stopped due to a safety signal, adverse events, or a risk to participants
  (e.g., liver enzyme elevation, unexpected side effects)
- RECRUITMENT: stopped due to inability to enroll enough participants
- FUNDING_STRATEGIC: stopped due to funding loss, sponsor business decision,
  portfolio prioritization, or a "strategic" reason not tied to safety or recruitment
- ADMINISTRATIVE_OTHER: any other reason — PI departure, participant withdrawal,
  protocol/logistics issues, or reasons that don't clearly fit the above

Respond with ONLY a JSON object in this exact shape, nothing else:
{{"category": "<one of {CATEGORIES}>", "reasoning": "<one short sentence>"}}
"""


def fetch_terminated_trials() -> list[dict]:
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "glp1_trials"),
    )
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT nct_id, brief_title, why_stopped
        FROM glp1_drug_trials
        WHERE overall_status = 'TERMINATED' AND why_stopped IS NOT NULL
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def classify_termination(client: Anthropic, brief_title: str, why_stopped: str) -> dict:
    """Ask Claude to classify one trial's termination reason. Returns
    {"category": ..., "reasoning": ...}, falling back to a safe default
    if the model's response can't be parsed."""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Trial title: {brief_title}\nTermination reason: {why_stopped}",
            }
        ],
    )
    raw_text = message.content[0].text.strip()

    try:
        result = json.loads(raw_text)
        if result.get("category") not in CATEGORIES:
            raise ValueError(f"Unexpected category: {result.get('category')}")
        return result
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  WARNING: couldn't parse response ({e}). Raw response: {raw_text!r}")
        return {"category": "ADMINISTRATIVE_OTHER", "reasoning": "Unparsed model response — needs manual review."}


UPSERT_SQL = """
INSERT INTO termination_categories (nct_id, category, reasoning)
VALUES (%(nct_id)s, %(category)s, %(reasoning)s)
ON DUPLICATE KEY UPDATE
    category = VALUES(category),
    reasoning = VALUES(reasoning);
"""


def save_categories(results: list[dict]) -> None:
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "glp1_trials"),
    )
    cur = conn.cursor()
    for row in results:
        cur.execute(UPSERT_SQL, row)
    conn.commit()
    cur.close()
    conn.close()


def main():
    trials = fetch_terminated_trials()
    print(f"Found {len(trials)} terminated trials with a stated reason.")

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    results = []
    for i, trial in enumerate(trials, start=1):
        print(f"[{i}/{len(trials)}] Classifying {trial['nct_id']}...")
        classification = classify_termination(
            client, trial["brief_title"], trial["why_stopped"]
        )
        results.append(
            {
                "nct_id": trial["nct_id"],
                "category": classification["category"],
                "reasoning": classification["reasoning"],
            }
        )
        print(f"    -> {classification['category']}: {classification['reasoning']}")

    save_categories(results)
    print(f"\nDone. Saved {len(results)} categorizations to termination_categories.")

    # Quick summary
    from collections import Counter
    counts = Counter(r["category"] for r in results)
    print("\nSummary:")
    for cat, count in counts.most_common():
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
