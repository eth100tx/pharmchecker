-- PharmChecker Database Functions - Optimized Schema
-- Updated to work with the actual merged search_results table

-- Function to get the results matrix for specific dataset combinations
CREATE OR REPLACE FUNCTION get_results_matrix(
  p_states_tag TEXT,
  p_pharmacies_tag TEXT,
  p_validated_tag TEXT
) RETURNS TABLE (
  pharmacy_id INT,
  pharmacy_name TEXT,
  search_state CHAR(2),
  latest_result_id INT,
  result_id INT,
  license_number TEXT,
  license_status TEXT,
  issue_date DATE,
  expiration_date DATE,
  score_overall NUMERIC,
  score_street NUMERIC,
  score_city_state_zip NUMERIC,
  override_type TEXT,
  validated_license TEXT,
  status_bucket TEXT,
  warnings TEXT[]
) AS $$
WITH 
dataset_ids AS (
  SELECT 
    (SELECT id FROM datasets WHERE kind = 'states' AND tag = p_states_tag) as states_id,
    (SELECT id FROM datasets WHERE kind = 'pharmacies' AND tag = p_pharmacies_tag) as pharmacies_id,
    (SELECT id FROM datasets WHERE kind = 'validated' AND tag = p_validated_tag) as validated_id
),
pairs AS (
  -- Get all (pharmacy, state) pairs from claimed licenses
  SELECT 
    p.id AS pharmacy_id,
    p.name AS pharmacy_name,
    (jsonb_array_elements_text(p.state_licenses))::char(2) AS state_code
  FROM pharmacies p, dataset_ids d
  WHERE p.dataset_id = d.pharmacies_id
    AND p.state_licenses IS NOT NULL 
    AND p.state_licenses <> '[]'::jsonb
),
latest_searches AS (
  -- Get most recent search parameters for each (name, state) combination
  SELECT DISTINCT ON (sr.search_name, sr.search_state)
    sr.search_name,
    sr.search_state,
    sr.search_ts,
    sr.id AS latest_result_id  -- Representative result for this search
  FROM search_results sr, dataset_ids d
  WHERE sr.dataset_id = d.states_id
  ORDER BY sr.search_name, sr.search_state, sr.search_ts DESC NULLS LAST, sr.id DESC
),
best_scores AS (
  -- Get best scoring result for each (pharmacy, search_name, search_state) pair
  SELECT DISTINCT ON (ms.pharmacy_id, sr.search_name, sr.search_state)
    ms.pharmacy_id,
    sr.search_name,
    sr.search_state,
    sr.id AS result_id,
    sr.license_number,
    sr.license_status,
    sr.license_name,
    sr.address,
    sr.city,
    sr.state,
    sr.zip,
    sr.issue_date,
    sr.expiration_date,
    sr.result_status,
    ms.score_overall,
    ms.score_street,
    ms.score_city_state_zip
  FROM match_scores ms
  JOIN search_results sr ON sr.id = ms.result_id
  JOIN dataset_ids d ON ms.states_dataset_id = d.states_id 
    AND ms.pharmacies_dataset_id = d.pharmacies_id
  ORDER BY ms.pharmacy_id, sr.search_name, sr.search_state, ms.score_overall DESC NULLS LAST, sr.id
),
joined AS (
  -- Join everything together
  SELECT
    p.pharmacy_id,
    p.pharmacy_name,
    p.state_code AS search_state,
    ls.latest_result_id,
    bs.result_id,
    bs.license_number,
    bs.license_status,
    bs.license_name,
    bs.address,
    bs.city,
    bs.zip,
    bs.issue_date,
    bs.expiration_date,
    bs.result_status,
    bs.score_overall,
    bs.score_street,
    bs.score_city_state_zip
  FROM pairs p
  LEFT JOIN latest_searches ls 
    ON ls.search_name = p.pharmacy_name
    AND ls.search_state = p.state_code
  LEFT JOIN best_scores bs
    ON bs.pharmacy_id = p.pharmacy_id
    AND bs.search_name = p.pharmacy_name
    AND bs.search_state = p.state_code
),
with_overrides AS (
  SELECT
    j.*,
    vo.override_type,
    vo.license_number AS validated_license,
    vo.license_status AS validated_lic_status,
    vo.address AS validated_address,
    vo.city AS validated_city,
    vo.expiration_date AS validated_exp_date,
    vo.issue_date AS validated_issue_date
  FROM joined j
  LEFT JOIN validated_overrides vo 
    ON vo.pharmacy_name = j.pharmacy_name
    AND vo.state_code = j.search_state
    AND (
      -- Match on license number for "present" overrides
      (vo.override_type = 'present' AND vo.license_number = j.license_number)
      -- Match on name+state only for "empty" overrides
      OR (vo.override_type = 'empty')
    )
    AND vo.dataset_id = (SELECT validated_id FROM dataset_ids)
)
SELECT
  pharmacy_id,
  pharmacy_name,
  search_state,
  latest_result_id,
  result_id,
  license_number,
  license_status,
  issue_date,
  expiration_date,
  score_overall,
  score_street,
  score_city_state_zip,
  override_type,
  validated_license,
  -- Status bucket calculation
  CASE
    WHEN override_type = 'empty' THEN 'no data'
    WHEN override_type = 'present' THEN
      CASE
        WHEN COALESCE(score_overall, 0) >= 85 THEN 'match'
        WHEN COALESCE(score_overall, 0) >= 60 THEN 'weak match'
        WHEN score_overall IS NULL THEN 'no data'
        ELSE 'no match'
      END
    WHEN latest_result_id IS NULL THEN 'no data'
    WHEN score_overall IS NULL THEN 'no data'
    WHEN score_overall >= 85 THEN 'match'
    WHEN score_overall >= 60 THEN 'weak match'
    ELSE 'no match'
  END AS status_bucket,
  -- Comprehensive warnings array (4 cases)
  ARRAY_REMOVE(ARRAY[
    -- Warning 1: Pharmacy not in current dataset
    CASE 
      WHEN NOT EXISTS (
        SELECT 1 FROM pharmacies p, dataset_ids d
        WHERE p.dataset_id = d.pharmacies_id
        AND p.name = pharmacy_name
      )
      THEN 'Pharmacy not in current dataset'
    END,
    -- Warning 2: Validated "present" but no matching result
    CASE 
      WHEN override_type = 'present'
      AND result_id IS NULL
      THEN 'Validated present but result not found'
    END,
    -- Warning 3: Validated "empty" but results exist
    CASE 
      WHEN override_type = 'empty'
      AND result_id IS NOT NULL
      THEN 'Validated empty but results now exist'
    END,
    -- Warning 4: Fields changed since validation
    CASE 
      WHEN override_type = 'present'
      AND result_id IS NOT NULL
      AND (
        COALESCE(license_status,'') <> COALESCE(validated_lic_status,'')
        OR COALESCE(address,'') <> COALESCE(validated_address,'')
        OR COALESCE(city,'') <> COALESCE(validated_city,'')
        OR expiration_date <> validated_exp_date
        OR issue_date <> validated_issue_date
      )
      THEN 'Search result fields changed since validation'
    END
  ], NULL) AS warnings
FROM with_overrides;
$$ LANGUAGE SQL;

-- Function to find pharmacy/result pairs that need scoring (optimized schema)
CREATE OR REPLACE FUNCTION find_missing_scores(
  p_states_tag TEXT,
  p_pharmacies_tag TEXT
) RETURNS TABLE (
  pharmacy_id INT,
  result_id INT
) AS $$
WITH 
dataset_ids AS (
  SELECT 
    (SELECT id FROM datasets WHERE kind = 'states' AND tag = p_states_tag) as states_id,
    (SELECT id FROM datasets WHERE kind = 'pharmacies' AND tag = p_pharmacies_tag) as pharmacies_id
),
needed_pairs AS (
  SELECT DISTINCT 
    p.id as pharmacy_id,
    sr.id as result_id
  FROM pharmacies p
  JOIN dataset_ids d ON p.dataset_id = d.pharmacies_id
  CROSS JOIN LATERAL (
    SELECT sr.id
    FROM search_results sr
    WHERE sr.dataset_id = d.states_id
      AND sr.search_name = p.name
      AND sr.search_state = ANY(
        SELECT (jsonb_array_elements_text(p.state_licenses))::char(2)
      )
      AND sr.result_status != 'no_results_found'
  ) sr
  WHERE NOT EXISTS (
    SELECT 1 
    FROM match_scores ms
    WHERE ms.pharmacy_id = p.id
      AND ms.result_id = sr.id
      AND ms.states_dataset_id = d.states_id
      AND ms.pharmacies_dataset_id = d.pharmacies_id
  )
)
SELECT * FROM needed_pairs;
$$ LANGUAGE SQL;