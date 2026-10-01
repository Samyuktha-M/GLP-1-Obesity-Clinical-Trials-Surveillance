# GLP-1 / Obesity Clinical Trials Surveillance

An end-to-end data pipeline and analytics project tracking clinical trial
activity in the obesity / GLP-1 drug space, built on the public
ClinicalTrials.gov API. The project pulls live trial data, cleans and
analyzes it in SQL, uses Claude to classify and extract insights from unstructured trial text,
and presents the findings in an interactive dashboard.

**Dashboard:** [Looker Studio](https://datastudio.google.com/s/lXxactoIq78)
**Data source:** [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api)

## What this project does

1. **Ingests** clinical trial data for GLP-1 / obesity drug trials directly
   from the ClinicalTrials.gov public API (900+ trials pulled, ~579 scoped 
   to interventional trials with a tracked phase for analysis).
2. **Analyzes** the data in SQL — trial phase trends, enrollment patterns,
   sponsor activity, drug comparisons, and time-to-completion.
3. **Applies AI (Claude API)** to two unstructured-text problems:
   - Classifying why terminated trials were stopped (safety, recruitment,
     funding, or administrative reasons).
   - Extracting structured eligibility fields (age range, sex restriction,
     comorbidity requirements, surgery exclusions, healthy-volunteer
     eligibility) from free-text eligibility criteria.
4. **Visualizes** all of the above in a multi-page Looker Studio dashboard.

## Repository structure

```
sql/
  schema.sql                    — core trials + pull_log tables
  data_sanity_checks.sql        — validation queries (duplicates, NULL rates,
                                   date/enrollment ranges) and creation of the
                                   glp1_drug_trials scoping view
  termination_categories.sql    — table for LLM-categorized termination reasons
  eligibility_extraction.sql    — table for LLM-extracted eligibility fields
src/
  ingest.py                     — pulls & loads trial data from the API
  categorize_terminations.py    — LLM classification of termination reasons
  extract_eligibility.py        — LLM extraction of eligibility criteria fields
requirements.txt
.env.example
```

## Pipeline architecture

**1. Ingestion (`src/ingest.py`)**
Pulls trials matching a GLP-1/obesity query from the ClinicalTrials.gov v2
API (paginated), flattens the nested JSON response into a clean relational
schema, and loads it into MySQL using upsert logic — so the script can be
safely re-run to pick up new or updated trials without creating duplicates.
The full raw API response is also archived per trial (`raw_json` column) for
later reference.

**2. Validation and scoping (`sql/data_sanity_checks.sql`)**
Before building analysis on top of the ingested data, a set of validation
queries check for duplicate `nct_id`s, unexpectedly high NULL rates on key
fields, reasonable date/enrollment ranges, and expected status/phase
category values — plus manual spot-checks of individual trials against
ClinicalTrials.gov. This file also defines the `glp1_drug_trials` view, which
filters the full dataset down to interventional trials with a tracked phase
(excluding 143 observational and 194 non-phase-tracked interventional
trials) — the relevant population for phase/enrollment/sponsor analysis
(579 trials).

**3. SQL analysis**
Direct SQL queries against `glp1_drug_trials` covering:
- Trial phase distribution and enrollment trends over time
- Drug comparison (semaglutide, liraglutide, tirzepatide, retatrutide —
  matched on both generic and brand names)
- Sponsor leaderboard and sponsor class breakdown
- Time-to-completion analysis
- Termination status and reasons

**4. LLM-based structured extraction (Claude API)**
Two features apply Claude to unstructured trial text and save the results
back into new tables:
- `categorize_terminations.py` — reads each terminated trial's stated reason
  and classifies it into one of four categories (SAFETY, RECRUITMENT,
  FUNDING_STRATEGIC, ADMINISTRATIVE_OTHER), with a one-sentence justification.
- `extract_eligibility.py` — reads each trial's full eligibility criteria
  text (pulled from the archived raw JSON via MySQL's `JSON_EXTRACT`) and
  extracts six structured fields: minimum/maximum age, sex restriction,
  whether prior bariatric surgery is excluded, whether the trial requires a
  specific comorbidity beyond obesity, and whether healthy volunteers are
  accepted. Built with resumable, save-as-you-go processing so an
  interrupted run (network issue, rate limit) can pick up where it left off
  rather than restarting — important at this dataset's scale (578 trials,
  each a separate API call).

**5. Dashboard (Looker Studio)**
A multi-page dashboard built from CSV exports of the above:
- Trial volume & phase mix over time
- Sponsor and Trial Status
- Drugs and Trial Outcomes
- Enrollment and Trial Scale
- Termination reason breakdown
- Eligibility criteria (comorbidity restrictions, bariatric surgery
  exclusion, healthy-volunteer eligibility)

## Key findings

- **Drug landscape:** Semaglutide and liraglutide together account for the majority of trials, once brand names (Ozempic, Wegovy, Saxenda, Victoza, etc.) are matched alongside generic/code names.
- **Trial volume growth:** Trial starts stayed in the single digits through the early 2010s, then accelerated sharply — from 33 trials starting in 2021 to a peak of 107 in 2025 — reflecting GLP-1 drugs' rapidly growing prominence in both diabetes and obesity research.
- **Sponsor concentration:** Novo Nordisk (93 trials) and Eli Lilly (58 trials) together account for roughly a quarter of all 579 trials in the dataset, far outpacing any other sponsor (the next-highest, University Medical Centre Ljubljana, has 13) — consistent with their position as the two leading GLP-1 drug manufacturers (Novo Nordisk: semaglutide/Ozempic/Wegovy; Eli Lilly: tirzepatide/Mounjaro/Zepbound).
- **Termination reasons:** Of trials terminated with a stated reason, roughly even splits across administrative/other (5) and funding/strategic (5) reasons, with recruitment (4) and safety (3) issues somewhat less common.
- **Comorbidity restrictions:** Type 2 diabetes is by far the most common comorbidity a trial requires alongside obesity (77 trials) — nearly 3x the next-most-common condition (PCOS, 24 trials) — reflecting GLP-1 drugs' origins in diabetes treatment before their obesity indication. Beyond the top handful of conditions, there's a long tail of 100+ distinct, mostly one-off conditions (cancers, rare diseases, mental health and substance-use disorders) — exploratory research testing GLP-1 drugs' effects beyond their established uses.
- **Bariatric surgery exclusion:** 43% of trials specifically exclude people with a history of bariatric surgery, to isolate the drug's effect without surgical weight loss as a confounder; the majority (57%) place no such restriction.
- **Healthy volunteers:** 93% of trials require participants to already have obesity/overweight (or a related condition) — only 7% accept healthy volunteers, consistent with those being early-phase (predominantly Phase 1) pharmacokinetic/safety studies rather than efficacy trials.

## Setup

```bash
cd GLP-1-Obesity-Clinical-Trials-Surveillance   # or wherever you placed the project
pip install -r requirements.txt
cp .env.example .env   # fill in DB credentials + ANTHROPIC_API_KEY
mysql -u root -p < sql/schema.sql
python3 src/ingest.py
mysql -u root -p < sql/data_sanity_checks.sql   # validates data + creates glp1_drug_trials view
mysql -u root -p < sql/termination_categories.sql
mysql -u root -p < sql/eligibility_extraction.sql
python3 src/categorize_terminations.py
python3 src/extract_eligibility.py
```

## Notes on data quality

- API date fields aren't consistently formatted (some are full dates, some
  only `YYYY-MM`); `ingest.py` normalizes these to MySQL-safe `DATE` values.
- `phase IS NULL` marks observational studies (no drug being tested);
  `phase = 'NA'` marks interventional studies that aren't phase-tracked
  (e.g., surgical, behavioral, or mechanistic studies using already-approved
  drugs). The `glp1_drug_trials` view excludes both, scoping analysis to
  drug trials with a tracked phase.
- Drug categorization matches both generic and brand names (e.g.,
  liraglutide, Saxenda, and Victoza are all counted as liraglutide trials)
  to avoid undercounting.
- LLM-extracted fields (termination category, eligibility fields) reflect
  the model's best reading of free text and were spot-checked against
  source records on ClinicalTrials.gov, but were not manually reviewed for
  every trial.

## Tech stack

MySQL · Python (requests, mysql-connector-python) · Claude API (Anthropic) ·
Looker Studio
