-- ============================================================
-- GLP-1 / Obesity Clinical Trials Surveillance — Phase 1 Schema
-- ============================================================
-- Works on MySQL 8+ / MariaDB. For Postgres, swap AUTO_INCREMENT
-- for SERIAL and TEXT[] handling if you later normalize arrays.

CREATE DATABASE IF NOT EXISTS glp1_trials;
USE glp1_trials;

-- Core trials table. One row per NCT ID (trial). Re-running the
-- ingestion script upserts this table, so it always reflects the
-- latest known state of each trial.
CREATE TABLE IF NOT EXISTS trials (
    nct_id                  VARCHAR(20)   PRIMARY KEY,
    brief_title              VARCHAR(500),
    overall_status            VARCHAR(50),
    phase                     VARCHAR(50),        -- e.g. 'PHASE3', 'PHASE1|PHASE2'
    study_type                VARCHAR(50),
    lead_sponsor_name          VARCHAR(255),
    lead_sponsor_class         VARCHAR(50),        -- INDUSTRY, NIH, OTHER, etc.
    enrollment_count            INT,
    enrollment_type             VARCHAR(20),        -- ACTUAL or ESTIMATED
    conditions                 TEXT,                -- pipe-delimited list
    interventions               TEXT,                -- pipe-delimited list
    start_date                 DATE,
    start_date_type             VARCHAR(20),
    completion_date             DATE,
    completion_date_type        VARCHAR(20),
    study_first_submit_date      DATE,
    last_update_post_date        DATE,
    locations_countries          TEXT,               -- pipe-delimited list
    why_stopped                VARCHAR(1000),       -- populated for terminated/withdrawn/suspended trials
    raw_json                   JSON,                -- full record, kept for future re-parsing / diffing
    first_seen_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_pulled_at               DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_status (overall_status),
    INDEX idx_phase (phase),
    INDEX idx_sponsor (lead_sponsor_name),
    INDEX idx_start_date (start_date)
);

-- Logs every ingestion run — useful immediately for sanity-checking
-- pulls, and becomes the backbone of the Phase 5 surveillance/diff
-- logic later (compare record counts and status mixes run over run).
CREATE TABLE IF NOT EXISTS pull_log (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    pulled_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    query_term      VARCHAR(500),
    records_fetched  INT,
    records_inserted INT,
    records_updated  INT,
    notes          VARCHAR(500)
);

SELECT * from trials;
SELECT nct_id, brief_title, phase, overall_status FROM trials LIMIT 5;
SELECT * FROM pull_log;
SELECT raw_json from trials;
