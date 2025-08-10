-- PharmChecker Database Functions - Comprehensive Results
-- Simplified function that returns ALL search results for client-side aggregation

-- Drop the new function if it exists (for clean reinstallation)
DROP FUNCTION IF EXISTS get_all_results_with_context(TEXT, TEXT, TEXT);

-- Function to get all search results with full context for client-side processing
CREATE OR REPLACE FUNCTION get_all_results_with_context(
  p_states_tag TEXT,
  p_pharmacies_tag TEXT,
  p_validated_tag TEXT
) RETURNS TABLE (
  pharmacy_id INT,
  pharmacy_name TEXT,
  search_state CHAR(2),
  result_id INT,
  search_name TEXT,
  license_number TEXT,
  license_status TEXT,
  license_name TEXT,
  license_type TEXT,
  issue_date DATE,
  expiration_date DATE,
  score_overall NUMERIC,
  score_street NUMERIC,
  score_city_state_zip NUMERIC,
  override_type TEXT,
  validated_license TEXT,
  result_status TEXT,
  search_timestamp TIMESTAMP,
  screenshot_path TEXT,
  screenshot_storage_type TEXT,
  screenshot_file_size BIGINT,
  -- Additional context fields for display and analysis
  pharmacy_address TEXT,
  pharmacy_city TEXT,
  pharmacy_state TEXT,
  pharmacy_zip TEXT,
  result_address TEXT,
  result_city TEXT,
  result_state TEXT,
  result_zip TEXT,
  pharmacy_dataset_id INT,
  states_dataset_id INT,
  validated_dataset_id INT
) AS $$
WITH 
dataset_ids AS (
  SELECT 
    (SELECT id FROM datasets WHERE kind = 'states' AND tag = p_states_tag) as states_id,
    (SELECT id FROM datasets WHERE kind = 'pharmacies' AND tag = p_pharmacies_tag) as pharmacies_id,
    (SELECT id FROM datasets WHERE kind = 'validated' AND tag = p_validated_tag) as validated_id
),
pharmacy_state_pairs AS (
  -- Get all (pharmacy, state) pairs from claimed licenses
  SELECT 
    p.id AS pharmacy_id,
    p.name AS pharmacy_name,
    p.address AS pharmacy_address,
    p.city AS pharmacy_city,
    p.state AS pharmacy_state,
    p.zip AS pharmacy_zip,
    (jsonb_array_elements_text(p.state_licenses))::char(2) AS state_code,
    d.pharmacies_id,
    d.states_id,
    d.validated_id
  FROM pharmacies p, dataset_ids d
  WHERE p.dataset_id = d.pharmacies_id
    AND p.state_licenses IS NOT NULL 
    AND p.state_licenses <> '[]'::jsonb
),
all_results AS (
  -- Get ALL search results for pharmacy-state pairs (no aggregation)
  SELECT 
    psp.pharmacy_id,
    psp.pharmacy_name,
    psp.pharmacy_address,
    psp.pharmacy_city,
    psp.pharmacy_state,
    psp.pharmacy_zip,
    psp.state_code AS search_state,
    psp.pharmacies_id,
    psp.states_id,
    psp.validated_id,
    sr.id AS result_id,
    sr.search_name,
    sr.license_number,
    sr.license_status,
    sr.license_name,
    sr.license_type,
    sr.issue_date,
    sr.expiration_date,
    sr.address AS result_address,
    sr.city AS result_city,
    sr.state AS result_state,
    sr.zip AS result_zip,
    sr.result_status,
    sr.search_ts AS search_timestamp,
    ms.score_overall,
    ms.score_street,
    ms.score_city_state_zip,
    CASE 
      WHEN img.organized_path IS NOT NULL 
      THEN 'image_cache/' || img.organized_path 
      ELSE NULL 
    END AS screenshot_path,
    img.storage_type AS screenshot_storage_type,
    img.file_size AS screenshot_file_size
  FROM pharmacy_state_pairs psp
  LEFT JOIN search_results sr 
    ON sr.search_name = psp.pharmacy_name
    AND sr.search_state = psp.state_code
    AND sr.dataset_id = psp.states_id
  LEFT JOIN match_scores ms 
    ON ms.result_id = sr.id
    AND ms.pharmacy_id = psp.pharmacy_id
    AND ms.states_dataset_id = psp.states_id
    AND ms.pharmacies_dataset_id = psp.pharmacies_id
  LEFT JOIN images img
    ON img.search_result_id = sr.id
),
with_overrides AS (
  -- Add validated overrides
  SELECT
    ar.*,
    vo.override_type,
    vo.license_number AS validated_license
  FROM all_results ar
  LEFT JOIN validated_overrides vo 
    ON vo.pharmacy_name = ar.pharmacy_name
    AND vo.state_code = ar.search_state
    AND (
      -- Match on license number for "present" overrides
      (vo.override_type = 'present' AND vo.license_number = ar.license_number)
      -- Match on name+state only for "empty" overrides
      OR (vo.override_type = 'empty')
    )
    AND vo.dataset_id = ar.validated_id
)
-- Return all records without aggregation
SELECT
  pharmacy_id,
  pharmacy_name,
  search_state,
  result_id,
  search_name,
  license_number,
  license_status,
  license_name,
  license_type,
  issue_date,
  expiration_date,
  score_overall,
  score_street,
  score_city_state_zip,
  override_type,
  validated_license,
  result_status,
  search_timestamp,
  screenshot_path,
  screenshot_storage_type,
  screenshot_file_size,
  pharmacy_address,
  pharmacy_city,
  pharmacy_state,
  pharmacy_zip,
  result_address,
  result_city,
  result_state,
  result_zip,
  pharmacies_id as pharmacy_dataset_id,
  states_id as states_dataset_id,
  validated_id as validated_dataset_id
FROM with_overrides
ORDER BY pharmacy_name, search_state, search_timestamp DESC NULLS LAST, result_id;

$$ LANGUAGE SQL;