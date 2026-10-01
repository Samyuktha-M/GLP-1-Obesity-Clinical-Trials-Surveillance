USE glp1_trials;
SELECT * FROM trials;
#Sanity Checks on Data

#1
SELECT COUNT(*) FROM trials;

#2 Check for duplicate nct_ids
SELECT nct_id, COUNT(nct_id) from trials 
GROUP BY nct_id
HAVING count(nct_id)>1;

#3 Check for unexpectedly high NULL rates on key fields
SELECT
    SUM(CASE WHEN brief_title IS NULL THEN 1 ELSE 0 END) AS null_title,
    SUM(CASE WHEN overall_status IS NULL THEN 1 ELSE 0 END) AS null_status,
    SUM(CASE WHEN phase IS NULL THEN 1 ELSE 0 END) AS null_phase,
    SUM(CASE WHEN phase = "NA" THEN 1 ELSE 0 END) AS na_phase,
    SUM(CASE WHEN start_date IS NULL THEN 1 ELSE 0 END) AS null_start_date,
    SUM(CASE WHEN lead_sponsor_name IS NULL THEN 1 ELSE 0 END) AS null_sponsor,
    SUM(CASE WHEN enrollment_count IS NULL THEN 1 ELSE 0 END) AS null_enrollment
FROM trials;

#Checking the study_type for NULL and 'NA' phases
SELECT phase, study_type, count(*) from trials WHERE phase is null OR phase = 'NA'
group by phase, study_type;

#If most of these NULL-phase rows have study_type = 'OBSERVATIONAL', that confirms it's expected 
#— observational studies genuinely don't have phases, and your data isn't broken.

#Checking interventions for 'NA' phases
SELECT interventions, COUNT(*)
FROM trials
WHERE phase = 'NA' AND study_type = 'INTERVENTIONAL'
GROUP BY interventions
ORDER BY COUNT(*) DESC;

#Create the scoped view, excluding the 337 non-phase-tracked trials (143 observational + 194 NA-phase):
CREATE VIEW glp1_drug_trials AS
SELECT *
FROM trials
WHERE study_type = 'INTERVENTIONAL'
  AND phase IS NOT NULL
  AND phase != 'NA';
  
SELECT COUNT(*) FROM glp1_drug_trials;
SELECT COUNT(*) FROM trials 
WHERE study_type = 'INTERVENTIONAL' AND phase IS NOT NULL AND phase != 'NA';
  

#4. Sanity-check the value ranges you'd expect
-- Status values — should all be recognizable categories
SELECT overall_status, COUNT(*) 
FROM glp1_drug_trials  
GROUP BY overall_status 
ORDER BY COUNT(*) DESC;

-- Phase values — should mostly be PHASE1/2/3/4 or combinations, plus NULL for non-drug studies
SELECT phase, COUNT(*) 
FROM glp1_drug_trials 
GROUP BY phase 
ORDER BY COUNT(*) DESC;

#Date sanity
SELECT MIN(start_date), MAX(start_date) FROM glp1_drug_trials;
SELECT MIN(completion_date), MAX(completion_date) FROM glp1_drug_trials;

#Check that dates fall in a reasonable range (e.g., not 1900 or 2099 from a parsing error) and that MAX(completion_date) isn't wildly in the past for trials still marked "RECRUITING."

SELECT nct_id, brief_title, phase, overall_status, completion_date, completion_date_type
FROM glp1_drug_trials
ORDER BY completion_date DESC
LIMIT 3;

#Enrollment sanity — no negative or absurd numbers
SELECT MIN(enrollment_count), MAX(enrollment_count), AVG(enrollment_count)FROM glp1_drug_trials;

SELECT nct_id, brief_title, overall_status, enrollment_count, enrollment_type
FROM glp1_drug_trials
WHERE enrollment_count = 0
ORDER BY nct_id;
#A trial with enrollment_count = -5 or enrollment_count = 5000000 would flag a parsing issue immediately.

#Spot-check a few real records against the website
#Pick 2-3 nct_ids from your table, and manually look them up on clinicaltrials.gov:
SELECT * FROM glp1_drug_trials LIMIT 3 OFFSET 100;

#Confirm pull_log is tracking correctly

SELECT * FROM pull_log;
