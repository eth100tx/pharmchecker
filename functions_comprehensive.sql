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

-- Drop existing function if it exists (for clean reinstallation)
DROP FUNCTION IF EXISTS check_validation_consistency(TEXT, TEXT, TEXT);

-- Validation consistency checker - detects issues between validations and search data
CREATE OR REPLACE FUNCTION check_validation_consistency(
    p_states_tag TEXT,
    p_pharmacies_tag TEXT, 
    p_validated_tag TEXT
) RETURNS TABLE (
    issue_type TEXT,
    pharmacy_name TEXT,
    state_code CHAR(2),
    license_number TEXT,
    description TEXT,
    severity TEXT
) AS $$
BEGIN
    -- Return empty if no validation dataset
    IF p_validated_tag IS NULL THEN
        RETURN;
    END IF;

    -- Issue 1: Empty validations but search results found
    RETURN QUERY
    SELECT 
        'empty_validation_with_results'::TEXT as issue_type,
        vo.pharmacy_name,
        vo.state_code,
        vo.license_number,
        'Validated as empty but search results exist for this pharmacy-state'::TEXT as description,
        'warning'::TEXT as severity
    FROM validated_overrides vo
    JOIN datasets vd ON vo.dataset_id = vd.id AND vd.tag = p_validated_tag
    WHERE vo.override_type = 'empty'
      AND EXISTS (
          SELECT 1 FROM search_results sr
          JOIN datasets sd ON sr.dataset_id = sd.id AND sd.tag = p_states_tag
          WHERE sr.search_name = vo.pharmacy_name 
            AND sr.search_state = vo.state_code
            AND sr.result_status = 'results_found'
      );

    -- Issue 2: Present validations but no search results found
    RETURN QUERY
    SELECT 
        'present_validation_missing_results'::TEXT as issue_type,
        vo.pharmacy_name,
        vo.state_code,
        vo.license_number,
        'Validated as present but no search results found for this license'::TEXT as description,
        'warning'::TEXT as severity
    FROM validated_overrides vo
    JOIN datasets vd ON vo.dataset_id = vd.id AND vd.tag = p_validated_tag
    WHERE vo.override_type = 'present'
      AND NOT EXISTS (
          SELECT 1 FROM search_results sr
          JOIN datasets sd ON sr.dataset_id = sd.id AND sd.tag = p_states_tag
          WHERE sr.search_name = vo.pharmacy_name 
            AND sr.search_state = vo.state_code
            AND sr.license_number = vo.license_number
      );

    -- Issue 3: Validated pharmacy not in current pharmacy dataset
    RETURN QUERY
    SELECT 
        'validated_pharmacy_not_found'::TEXT as issue_type,
        vo.pharmacy_name,
        vo.state_code,
        vo.license_number,
        'Validated pharmacy not found in current pharmacy dataset'::TEXT as description,
        'error'::TEXT as severity
    FROM validated_overrides vo
    JOIN datasets vd ON vo.dataset_id = vd.id AND vd.tag = p_validated_tag
    WHERE NOT EXISTS (
        SELECT 1 FROM pharmacies p
        JOIN datasets pd ON p.dataset_id = pd.id AND pd.tag = p_pharmacies_tag
        WHERE p.name = vo.pharmacy_name
    );

    -- Issue 4: Present validation for license not claimed by pharmacy
    RETURN QUERY
    SELECT 
        'license_not_claimed'::TEXT as issue_type,
        vo.pharmacy_name,
        vo.state_code,
        vo.license_number,
        'Validated license in state not claimed by pharmacy in current dataset'::TEXT as description,
        'warning'::TEXT as severity
    FROM validated_overrides vo
    JOIN datasets vd ON vo.dataset_id = vd.id AND vd.tag = p_validated_tag
    WHERE vo.override_type = 'present'
      AND NOT EXISTS (
          SELECT 1 FROM pharmacies p
          JOIN datasets pd ON p.dataset_id = pd.id AND pd.tag = p_pharmacies_tag
          WHERE p.name = vo.pharmacy_name
            AND p.state_licenses ? vo.state_code
      );

END;
$$ LANGUAGE plpgsql;