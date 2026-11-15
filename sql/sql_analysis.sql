#SQL Analysis

SELECT * FROM glp1_drug_trials;
SELECT COUNT(*) FROM glp1_drug_trials;
#Trial volume by year and phase
SELECT
    YEAR(start_date) AS trial_year,
    phase,
    COUNT(*) AS trial_count
FROM glp1_drug_trials
WHERE start_date IS NOT NULL
GROUP BY YEAR(start_date), phase
ORDER BY trial_year, phase;

#Total trials per year (summing across phases)
SELECT
    YEAR(start_date) AS trial_year,
    COUNT(*) AS trial_count
FROM glp1_drug_trials
WHERE start_date IS NOT NULL
GROUP BY YEAR(start_date)
ORDER BY trial_year;

#What percentage of trials are Recruiting vs. Completed vs. Terminated?
SELECT overall_status, COUNT(*) as number_of_trials, ROUND((COUNT(*)/SUM(COUNT(*)) OVER()) * 100,2) as percentage 
FROM glp1_drug_trials
WHERE overall_status IN ('RECRUITING', 'COMPLETED', 'TERMINATED')
GROUP BY overall_status;

#Find the why_stopped for 'Terminated' trials
SELECT nct_id, brief_title,lead_sponsor_name, why_stopped
FROM glp1_drug_trials
WHERE overall_status='TERMINATED'
ORDER BY nct_id;

#Sponsor leaderboard — which companies/institutions are most active in this space.
SELECT lead_sponsor_name, lead_sponsor_class, COUNT(*) as number_of_trials,
SUM(CASE WHEN overall_status = 'RECRUITING' THEN 1 ELSE 0 END) as currently_recuiting,
SUM(CASE WHEN overall_status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
SUM(CASE WHEN overall_status = 'TERMINATED' THEN 1 ELSE 0 END) as terminatd
FROM glp1_drug_trials
GROUP BY lead_sponsor_name, lead_sponsor_class
ORDER BY number_of_trials desc
LIMIT 20;

#Average enrollment size by phase
SELECT 
    phase, 
    COUNT(*) AS trial_count,
    ROUND(AVG(enrollment_count), 0) AS avg_enrollment
FROM glp1_drug_trials
WHERE enrollment_count IS NOT NULL
GROUP BY phase
ORDER BY trial_count DESC;

#How has average enrollment count changed over time?
SELECT
    YEAR(start_date) AS trial_year,
    phase,
    COUNT(*) AS trial_count,
    ROUND(AVG(enrollment_count), 0) AS avg_enrollment
FROM glp1_drug_trials
WHERE start_date IS NOT NULL 
  AND enrollment_count IS NOT NULL
  AND phase IN ('PHASE1', 'PHASE2', 'PHASE3', 'PHASE4')  -- exclude low-n combined phases
GROUP BY YEAR(start_date), phase
ORDER BY trial_year, phase;

#Why is the average enrollment high in 2018 for Phase 3?
SELECT nct_id, brief_title, enrollment_count, lead_sponsor_name
FROM glp1_drug_trials
WHERE YEAR(start_date) = 2018 AND phase = 'PHASE3'
ORDER BY enrollment_count DESC;

#Why there is zero enrollment in 2016 Phase 2?
SELECT nct_id, brief_title, overall_status, enrollment_count
FROM glp1_drug_trials
WHERE YEAR(start_date) = 2016 AND phase = 'PHASE2';

#Time to Completion - How long does a GLP 1 trial actually take from start to finish?

SELECT 
    nct_id, 
    brief_title, 
    phase, 
    start_date, 
    completion_date,
    DATEDIFF(completion_date, start_date) AS days_to_complete,
    ROUND(DATEDIFF(completion_date, start_date) / 30.44, 1) AS months_to_complete
FROM glp1_drug_trials
WHERE overall_status = 'COMPLETED'
  AND start_date IS NOT NULL
  AND completion_date IS NOT NULL
ORDER BY days_to_complete DESC;

#Head-to-head drug comparison — Semaglutide vs. Tirzepatide vs. Liraglutide

SELECT 
    COUNT(*) as trial_count, 
    ROUND(AVG(enrollment_count),0) as avg_enrollment,
    CASE
        WHEN interventions LIKE '%Semaglutide%' OR interventions LIKE '%Ozempic%' OR interventions LIKE '%Wegovy%' OR interventions LIKE '%Rybelsus%' THEN 'Semaglutide'
        WHEN interventions LIKE '%Tirzepatide%' OR interventions LIKE '%Mounjaro%' OR interventions LIKE '%Zepbound%' THEN 'Tirzepatide'
        WHEN interventions LIKE '%Liraglutide%' OR interventions LIKE '%Saxenda%' OR interventions LIKE '%Victoza%' THEN 'Liraglutide'
        WHEN interventions LIKE '%Retatrutide%' OR interventions LIKE '%LY3437943%' THEN 'Retatrutide'
        ELSE 'Other'
    END AS primary_drug
FROM glp1_drug_trials
GROUP BY primary_drug
ORDER BY trial_count desc;

#Retatrutide's average enrollment of 1,673
SELECT nct_id, brief_title, enrollment_count, phase, overall_status
FROM glp1_drug_trials
WHERE interventions LIKE '%Retatrutide%' OR interventions LIKE '%LY3437943%' 
ORDER BY enrollment_count DESC;

#Other 150 trials
SELECT interventions, COUNT(*)
FROM glp1_drug_trials
WHERE interventions NOT LIKE '%Semaglutide%'
  AND interventions NOT LIKE '%Ozempic%'
  AND interventions NOT LIKE '%Wegovy%'
  AND interventions NOT LIKE '%Rybelsus%'
  AND interventions NOT LIKE '%Tirzepatide%'
  AND interventions NOT LIKE '%Mounjaro%'
  AND interventions NOT LIKE '%Zepbound%'
  AND interventions NOT LIKE '%Liraglutide%'
  AND interventions NOT LIKE '%Saxenda%'
  AND interventions NOT LIKE '%Victoza%'
  AND interventions NOT LIKE '%Retatrutide%'
  AND interventions NOT LIKE '%LY3437943%'
GROUP BY interventions
ORDER BY COUNT(*) DESC
LIMIT 20;

SELECT * FROM glp1_drug_trials where overall_status = 'COMPLETED';

SELECT nct_id, brief_title, phase, start_date
FROM glp1_drug_trials
WHERE interventions LIKE '%Semaglutide%'
  AND phase IN ('PHASE1', 'PHASE2', 'PHASE3', 'PHASE4')
ORDER BY 
    CASE phase
        WHEN 'PHASE1' THEN 1
        WHEN 'PHASE2' THEN 2
        WHEN 'PHASE3' THEN 3
        WHEN 'PHASE4' THEN 4
    END,
    start_date;
    
    SELECT nct_id, brief_title, phase, start_date
FROM glp1_drug_trials
WHERE brief_title LIKE '%Extension%'
   OR brief_title LIKE '%extension%'
   OR brief_title LIKE '%Long-term%'
   OR brief_title LIKE '%Long term%'
   OR brief_title LIKE '%Continuation%'
   OR brief_title LIKE '%Follow-up%'
   OR brief_title LIKE '%Follow up%'
ORDER BY start_date;


#Termination Categories

SELECT * from termination_categories;

SELECT nct_id, category, reasoning FROM termination_categories ORDER BY category;

#Eligibility Criteria

SELECT * FROM eligibility_extracted;

#Age ranges over time
SELECT YEAR(g.start_date) as start_year, ROUND(AVG(e.age_diff),1) as avg_age_diff, COUNT(*) as no_of_trials FROM (SELECT nct_id, min_age, max_age, max_age-min_age as age_diff
FROM eligibility_extracted 
WHERE min_age IS NOT NULL AND max_age IS NOT NULL) e JOIN glp1_drug_trials g
ON g.nct_id = e.nct_id
GROUP BY YEAR(g.start_date)
ORDER BY start_year;

#% of trials excluding prior bariatric surgery
SELECT excludes_prior_bariatric_surgery, ROUND(COUNT(*)/(SUM(COUNT(*)) OVER())*100) as percentage_of_trials
FROM eligibility_extracted 
GROUP BY excludes_prior_bariatric_surgery;

#Which comorbidities show up most?
SELECT restricted_comorbidity, COUNT(*) as no_of_trials
FROM eligibility_extracted 
WHERE restricted_comorbidity IS NOT NULL
GROUP BY restricted_comorbidity
ORDER BY no_of_trials desc;

#% allowing healthy volunteers
SELECT healthy_volunteers_allowed, ROUND(COUNT(*)/(SUM(COUNT(*)) OVER())*100) as percentage_of_trials
FROM eligibility_extracted 
GROUP BY healthy_volunteers_allowed;

#Export the data
SELECT 
    e.nct_id,
    g.start_date,
    g.phase,
    e.min_age,
    e.max_age,
    (e.max_age - e.min_age) AS age_diff,
    e.sex_restriction,
    e.excludes_prior_bariatric_surgery,
    e.restricted_comorbidity,
    e.healthy_volunteers_allowed
FROM eligibility_extracted e
JOIN glp1_drug_trials g ON g.nct_id = e.nct_id;
