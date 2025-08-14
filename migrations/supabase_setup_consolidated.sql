-- PharmChecker Complete Database Schema for Supabase
-- Run this entire script in Supabase SQL Editor to set up the complete database

-- =============================================================================
-- MIGRATION 1: Initial Schema and Extensions
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create migration tracking table if it doesn't exist
CREATE TABLE IF NOT EXISTS pharmchecker_migrations (
  version VARCHAR(255) PRIMARY KEY,
  name VARCHAR(255),
  applied_at TIMESTAMP DEFAULT NOW()
);

-- Versioned datasets (no global active state)
CREATE TABLE IF NOT EXISTS datasets (
  id          SERIAL PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('states','pharmacies','validated')),
  tag         TEXT NOT NULL,
  description TEXT,
  created_by  TEXT,
  created_at  TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE(kind, tag)
);

-- Pharmacy master records
CREATE TABLE IF NOT EXISTS pharmacies (
  id              SERIAL PRIMARY KEY,
  dataset_id      INT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,  -- Exact string used for searching
  alias           TEXT,
  address         TEXT,
  suite           TEXT,
  city            TEXT,
  state           CHAR(2),
  zip             TEXT,
  state_licenses  JSONB,  -- ["TX","FL",...]
  additional_info JSONB,
  created_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- Merged search results from state boards (combines search parameters + results)
CREATE TABLE IF NOT EXISTS search_results (
  id               SERIAL PRIMARY KEY,
  dataset_id       INT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  
  -- Search parameters (formerly in searches table)
  search_name      TEXT NOT NULL,      -- From pharmacies.name
  search_state     CHAR(2) NOT NULL,
  search_ts        TIMESTAMP,
  
  -- Result fields
  license_number   TEXT,
  license_status   TEXT,
  license_name     TEXT,              -- Can vary: "Empower TX", "Empower LLC", etc.
  license_type     TEXT,              -- Type from JSON: "Pharmacy Special Non-Resident", etc.
  address          TEXT,
  city             TEXT,
  state            TEXT,               -- State from result (can differ from search_state)
  zip              TEXT,
  issue_date       DATE,
  expiration_date  DATE,
  result_status    TEXT,
  
  -- Metadata
  meta             JSONB,              -- Combined metadata from search and result
  raw              JSONB,              -- Raw result data
  image_hash       CHAR(64),           -- SHA256 reference to image_assets
  created_at       TIMESTAMP NOT NULL DEFAULT now(),
  
  -- Unique constraint to handle deduplication during import
  CONSTRAINT unique_search_result UNIQUE(dataset_id, search_state, license_number)
);

-- Computed match scores (uses IDs within dataset pairs)  
CREATE TABLE IF NOT EXISTS match_scores (
  id                    SERIAL PRIMARY KEY,
  states_dataset_id     INT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  pharmacies_dataset_id INT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  pharmacy_id           INT NOT NULL REFERENCES pharmacies(id) ON DELETE CASCADE,
  result_id             INT NOT NULL REFERENCES search_results(id) ON DELETE CASCADE,
  score_overall         NUMERIC NOT NULL,
  score_street          NUMERIC,
  score_city_state_zip  NUMERIC,
  scoring_meta          JSONB,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE (states_dataset_id, pharmacies_dataset_id, pharmacy_id, result_id)
);

-- Validated overrides (snapshot of search_results + validation fields)
CREATE TABLE IF NOT EXISTS validated_overrides (
  id               SERIAL PRIMARY KEY,
  dataset_id       INT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  
  -- Key matching fields (natural keys, not IDs)
  pharmacy_name    TEXT NOT NULL,        -- From searches.search_name
  state_code       CHAR(2) NOT NULL,     -- From searches.search_state
  license_number   TEXT,                 -- From search_results.license_number
  
  -- Snapshot of search_results fields at validation time
  license_status   TEXT,
  license_name     TEXT,
  address          TEXT,
  city             TEXT,
  state            TEXT,
  zip              TEXT,
  issue_date       DATE,
  expiration_date  DATE,
  result_status    TEXT,
  
  -- Validation specific fields
  override_type    TEXT NOT NULL CHECK (override_type IN ('present','empty')),
  reason           TEXT,
  validated_by     TEXT,
  validated_at     TIMESTAMP NOT NULL DEFAULT now(),
  
  -- Note: UNIQUE constraint with COALESCE needs to be handled with partial index
  CONSTRAINT unique_validated_override UNIQUE (dataset_id, pharmacy_name, state_code, license_number)
);

-- SHA256-based image asset deduplication
CREATE TABLE IF NOT EXISTS image_assets (
  content_hash     CHAR(64) PRIMARY KEY,        -- SHA256 hex string
  storage_path     TEXT NOT NULL,               -- Storage-specific path
  storage_type     TEXT NOT NULL CHECK (storage_type IN ('local', 'supabase')),
  file_size        BIGINT NOT NULL,
  content_type     TEXT,                        -- 'image/png', 'image/jpeg'
  width            INT,                         -- Image dimensions (optional metadata)
  height           INT,
  first_seen       TIMESTAMP NOT NULL DEFAULT now(),
  last_accessed    TIMESTAMP DEFAULT now(),
  access_count     INT DEFAULT 1
);

-- User allowlist with session storage
CREATE TABLE IF NOT EXISTS app_users (
  id           SERIAL PRIMARY KEY,
  github_login TEXT UNIQUE,
  email        TEXT UNIQUE,
  role         TEXT NOT NULL CHECK (role IN ('admin','user')),
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  session_data JSONB,  -- For storing user session preferences
  created_at   TIMESTAMP NOT NULL DEFAULT now(),
  updated_at   TIMESTAMP DEFAULT now()
);

-- =============================================================================
-- MIGRATION 2: Custom Functions
-- =============================================================================

-- Drop the function if it exists (for clean reinstallation)
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
      WHEN ia.storage_path IS NOT NULL 
      THEN ia.storage_path 
      ELSE NULL 
    END AS screenshot_path,
    ia.storage_type AS screenshot_storage_type,
    ia.file_size AS screenshot_file_size
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
  LEFT JOIN image_assets ia
    ON ia.content_hash = sr.image_hash
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

-- =============================================================================
-- MIGRATION 3: Performance Indexes
-- =============================================================================

-- Pharmacies table indexes
CREATE INDEX IF NOT EXISTS ix_pharm_dataset ON pharmacies(dataset_id);
CREATE INDEX IF NOT EXISTS ix_pharm_name ON pharmacies(name);
CREATE INDEX IF NOT EXISTS ix_pharm_name_trgm ON pharmacies USING gin (name gin_trgm_ops);

-- Search results (merged table) indexes
CREATE INDEX IF NOT EXISTS ix_results_dataset ON search_results(dataset_id);
CREATE INDEX IF NOT EXISTS ix_results_search_name_state ON search_results(dataset_id, search_name, search_state, search_ts DESC);
CREATE INDEX IF NOT EXISTS ix_results_license ON search_results(license_number);
CREATE INDEX IF NOT EXISTS ix_results_dates ON search_results(issue_date, expiration_date);
CREATE INDEX IF NOT EXISTS ix_results_unique_lookup ON search_results(dataset_id, search_state, license_number);

-- Match scores indexes
CREATE INDEX IF NOT EXISTS ix_scores_composite ON match_scores(
  states_dataset_id, pharmacies_dataset_id, pharmacy_id, score_overall DESC
);

-- Validated overrides indexes
CREATE INDEX IF NOT EXISTS ix_validated_dataset ON validated_overrides(dataset_id);
CREATE INDEX IF NOT EXISTS ix_validated_lookup ON validated_overrides(pharmacy_name, state_code);
CREATE INDEX IF NOT EXISTS ix_validated_license ON validated_overrides(state_code, license_number);

-- Image assets indexes  
CREATE INDEX IF NOT EXISTS ix_search_results_image ON search_results(image_hash);
CREATE INDEX IF NOT EXISTS ix_assets_storage ON image_assets(storage_type, storage_path);
CREATE INDEX IF NOT EXISTS ix_assets_access ON image_assets(last_accessed);

-- Additional performance indexes for common query patterns

-- Datasets table for quick tag lookups
CREATE INDEX IF NOT EXISTS ix_datasets_kind_tag ON datasets(kind, tag);

-- App users for session management
CREATE INDEX IF NOT EXISTS ix_app_users_github_login ON app_users(github_login) WHERE github_login IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_app_users_email ON app_users(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_app_users_active ON app_users(is_active) WHERE is_active = true;

-- =============================================================================
-- RECORD MIGRATIONS AS APPLIED
-- =============================================================================

-- Record that all migrations have been applied
INSERT INTO pharmchecker_migrations (version, name) VALUES
  ('20240101000000_initial_schema', '20240101000000 Initial Schema'),
  ('20240101000001_comprehensive_functions', '20240101000001 Comprehensive Functions'),
  ('20240101000002_indexes_and_performance', '20240101000002 Indexes And Performance'),
  ('20240814000000_image_sha256_clean', '20240814000000 Clean SHA256 Image System')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
-- SETUP COMPLETE
-- =============================================================================
-- Your Supabase database now has the complete PharmChecker schema!
-- This includes all tables, functions, indexes, and migration tracking.
-- Both local PostgreSQL and Supabase now have identical schemas.