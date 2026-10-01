-- Phase 2 stretch — LLM-categorized termination reasons
-- Run this after schema.sql has already been applied.

USE glp1_trials;

CREATE TABLE IF NOT EXISTS termination_categories (
    nct_id          VARCHAR(20) PRIMARY KEY,
    category         VARCHAR(50),     -- SAFETY, RECRUITMENT, FUNDING_STRATEGIC, ADMINISTRATIVE_OTHER
    reasoning         VARCHAR(500),    -- Claude's brief justification for the category
    categorized_at     DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (nct_id) REFERENCES trials(nct_id)
);
