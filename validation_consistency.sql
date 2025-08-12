-- Validation consistency checker - detects issues between validations and search data
CREATE OR REPLACE FUNCTION check_validation_consistency(
    p_states_tag TEXT,
    p_pharmacies_tag TEXT, 
    p_validated_tag TEXT
) RETURNS TABLE (
    issue_type TEXT,
    pharmacy_name TEXT,
    state_code TEXT,
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