-- Phase 3 — LLM-extracted structured fields from free-text eligibility criteria
-- Run this after schema.sql has already been applied.

USE glp1_trials;

CREATE TABLE IF NOT EXISTS eligibility_extracted (
    nct_id                          VARCHAR(20) PRIMARY KEY,
    min_age                         INT,            -- minimum age in years (NULL if not stated/unclear)
    max_age                         INT,            -- maximum age in years (NULL if not stated/no upper bound)
    sex_restriction                 VARCHAR(10),    -- ALL, FEMALE, MALE
    excludes_prior_bariatric_surgery BOOLEAN,        -- TRUE if prior bariatric surgery is an exclusion criterion
    restricted_comorbidity          VARCHAR(100),   -- e.g. "type 2 diabetes", "PCOS", "heart failure", or NULL if not restricted
    healthy_volunteers_allowed      BOOLEAN,        -- TRUE if healthy volunteers are explicitly allowed
    extracted_at                    DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (nct_id) REFERENCES trials(nct_id)
);
