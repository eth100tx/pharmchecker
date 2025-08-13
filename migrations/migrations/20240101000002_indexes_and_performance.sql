-- PharmChecker Performance Indexes Migration
-- This migration creates all performance indexes for optimal query performance

-- Create indexes for performance

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

-- Images table indexes
CREATE INDEX IF NOT EXISTS ix_images_dataset ON images(dataset_id, state);
CREATE INDEX IF NOT EXISTS ix_images_search_name ON images(search_name, state);
CREATE INDEX IF NOT EXISTS ix_images_result ON images(search_result_id);

-- Additional performance indexes for common query patterns

-- Datasets table for quick tag lookups
CREATE INDEX IF NOT EXISTS ix_datasets_kind_tag ON datasets(kind, tag);

-- App users for session management
CREATE INDEX IF NOT EXISTS ix_app_users_github_login ON app_users(github_login) WHERE github_login IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_app_users_email ON app_users(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_app_users_active ON app_users(is_active) WHERE is_active = true;