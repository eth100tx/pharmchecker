-- PharmChecker Database Schema
-- This script creates all tables, indexes, and functions needed for PharmChecker

-- Enable trigram extension for fuzzy text matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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

-- State board searches
CREATE TABLE IF NOT EXISTS searches (
  id            SERIAL PRIMARY KEY,
  dataset_id    INT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  search_name   TEXT NOT NULL,  -- Exact copy from pharmacies.name
  search_state  CHAR(2) NOT NULL,
  search_ts     TIMESTAMP,
  meta          JSONB
);

-- Search results from state boards
CREATE TABLE IF NOT EXISTS search_results (
  id               SERIAL PRIMARY KEY,
  search_id        INT NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
  license_number   TEXT,
  license_status   TEXT,
  license_name     TEXT,  -- Can vary: "Empower TX", "Empower LLC", etc.
  address          TEXT,
  city             TEXT,
  state            CHAR(2),
  zip              TEXT,
  issue_date       DATE,
  expiration_date  DATE,
  result_status    TEXT,
  raw              JSONB,
  created_at       TIMESTAMP NOT NULL DEFAULT now()
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
  state            CHAR(2),
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

-- Screenshot/image storage metadata
CREATE TABLE IF NOT EXISTS images (
  id             SERIAL PRIMARY KEY,
  dataset_id     INT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  state          CHAR(2) NOT NULL,
  search_id      INT REFERENCES searches(id) ON DELETE SET NULL,
  search_name    TEXT,  -- Captured for reference even if search deleted
  organized_path TEXT NOT NULL,  -- "<states_tag>/<STATE>/<search_name_slug>.import_timestamp"
  storage_type   TEXT NOT NULL CHECK (storage_type IN ('local','supabase')),
  file_size      BIGINT,
  created_at     TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE(dataset_id, organized_path)
);

-- User allowlist
CREATE TABLE IF NOT EXISTS app_users (
  id           SERIAL PRIMARY KEY,
  github_login TEXT UNIQUE,
  email        TEXT UNIQUE,
  role         TEXT NOT NULL CHECK (role IN ('admin','user')),
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMP NOT NULL DEFAULT now()
);

-- Create indexes for performance

-- Pharmacies
CREATE INDEX IF NOT EXISTS ix_pharm_dataset ON pharmacies(dataset_id);
CREATE INDEX IF NOT EXISTS ix_pharm_name ON pharmacies(name);
CREATE INDEX IF NOT EXISTS ix_pharm_name_trgm ON pharmacies USING gin (name gin_trgm_ops);

-- Searches
CREATE INDEX IF NOT EXISTS ix_search_dataset ON searches(dataset_id);
CREATE INDEX IF NOT EXISTS ix_search_name_state ON searches(dataset_id, search_name, search_state, search_ts DESC);

-- Search results
CREATE INDEX IF NOT EXISTS ix_results_search ON search_results(search_id);
CREATE INDEX IF NOT EXISTS ix_results_license ON search_results(license_number);
CREATE INDEX IF NOT EXISTS ix_results_dates ON search_results(issue_date, expiration_date);

-- Match scores
CREATE INDEX IF NOT EXISTS ix_scores_composite ON match_scores(
  states_dataset_id, pharmacies_dataset_id, pharmacy_id, score_overall DESC
);

-- Validated overrides
CREATE INDEX IF NOT EXISTS ix_validated_dataset ON validated_overrides(dataset_id);
CREATE INDEX IF NOT EXISTS ix_validated_lookup ON validated_overrides(pharmacy_name, state_code);
CREATE INDEX IF NOT EXISTS ix_validated_license ON validated_overrides(state_code, license_number);

-- Images
CREATE INDEX IF NOT EXISTS ix_images_dataset ON images(dataset_id, state);
CREATE INDEX IF NOT EXISTS ix_images_search ON images(search_id);