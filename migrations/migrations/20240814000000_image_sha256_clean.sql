-- Migration: Clean SHA256 Image System
-- Drop legacy images table and implement SHA256-based deduplication

-- Drop legacy images table entirely (no data to preserve)
DROP TABLE IF EXISTS images CASCADE;

-- Add image_hash column to search_results
ALTER TABLE search_results ADD COLUMN IF NOT EXISTS image_hash CHAR(64);

-- Create image_assets table with SHA256 deduplication
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

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS ix_search_results_image ON search_results(image_hash);
CREATE INDEX IF NOT EXISTS ix_assets_storage ON image_assets(storage_type, storage_path);
CREATE INDEX IF NOT EXISTS ix_assets_access ON image_assets(last_accessed);

-- Add foreign key constraint
ALTER TABLE search_results 
ADD CONSTRAINT fk_search_results_image 
FOREIGN KEY (image_hash) REFERENCES image_assets(content_hash) ON DELETE SET NULL;