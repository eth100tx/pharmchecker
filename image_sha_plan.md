# PharmChecker Image SHA256 Deduplication Plan

## Overview

This plan migrates PharmChecker's image handling system from timestamp-based filenames to SHA256 content-hash based deduplication. The new system will eliminate duplicate image storage, support both local and Supabase storage, and provide efficient cleanup mechanisms.

## Current System Analysis

### Current Architecture
- **Storage**: Local `imagecache/` directory with organized paths: `{tag}/{state}/{filename}.{timestamp}.{ext}`
- **Database**: `images` table linking to `search_results` via `search_result_id`
- **Import Flow**: Copy images during state search import, generate timestamp-based filenames
- **Issues**: 
  - Duplicate images stored multiple times
  - No true deduplication (timestamp ≠ content hash)
  - Supabase storage not implemented
  - Potential orphaned images after dataset deletion

### Current Schema
```sql
CREATE TABLE images (
  id               SERIAL PRIMARY KEY,
  dataset_id       INT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  search_result_id INT REFERENCES search_results(id) ON DELETE CASCADE,
  state            CHAR(2) NOT NULL,
  search_name      TEXT NOT NULL,
  organized_path   TEXT NOT NULL,  -- Current: tag/state/name.timestamp.ext
  storage_type     TEXT NOT NULL CHECK (storage_type IN ('local','supabase')),
  file_size        BIGINT,
  created_at       TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE(dataset_id, organized_path, search_result_id)
);
```

## New SHA256-Based Architecture

### Design Goals
1. **Exact Deduplication**: Store each unique image only once based on SHA256 hash
2. **Minimal Schema Changes**: Add one field to `search_results`, create asset management table
3. **Dual Storage Support**: Seamless operation with local filesystem and Supabase Storage
4. **Orphan Cleanup**: Efficient identification and removal of unused images
5. **Backward Compatibility**: Smooth migration from existing system

### New Database Schema

#### Option A: Assets Table + search_results.image_hash (Recommended)
```sql
-- New asset management table
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

-- Add image reference to search_results
ALTER TABLE search_results ADD COLUMN image_hash CHAR(64) REFERENCES image_assets(content_hash);
CREATE INDEX ix_search_results_image ON search_results(image_hash);

-- DO NOT Keep images table for backward compatibility during migration, drop the legacy and start fresh. there are no images in teh cache or DB we want to keep
```

#### Migration Schema Changes
```sql
-- Migration: Add new column
ALTER TABLE search_results ADD COLUMN image_hash CHAR(64);

-- Migration: Create assets table
CREATE TABLE image_assets (
  content_hash     CHAR(64) PRIMARY KEY,
  storage_path     TEXT NOT NULL,
  storage_type     TEXT NOT NULL CHECK (storage_type IN ('local', 'supabase')),
  file_size        BIGINT NOT NULL,
  content_type     TEXT,
  width            INT,
  height           INT,
  first_seen       TIMESTAMP NOT NULL DEFAULT now(),
  last_accessed    TIMESTAMP DEFAULT now(),
  access_count     INT DEFAULT 1
);

-- Migration: Create indexes
CREATE INDEX ix_search_results_image ON search_results(image_hash);
CREATE INDEX ix_assets_storage ON image_assets(storage_type, storage_path);
CREATE INDEX ix_assets_access ON image_assets(last_accessed);
```

### Storage Path Structure

#### Local Storage
```
imagecache/
├── sha256/
│   ├── ab/
│   │   ├── cd/
│   │   │   └── abcd1234...5678.png    # Full SHA256 as filename
│   └── ef/
│       └── gh/
│           └── efgh5678...9abc.jpg
```

#### Supabase Storage
```
Bucket: imagecache
├── sha256/ab/cd/abcd1234...5678.png
├── sha256/ef/gh/efgh5678...9abc.jpg
```

The 2-level directory structure (`ab/cd/`) prevents filesystem performance issues with large numbers of files in single directories.

## Implementation Plan

### Phase 1: Database Migration
1. **Create Migration File**: `migrations/migrations/20240814000000_image_sha256.sql`
2. **Add image_hash Column**: To `search_results` table
3. **Create image_assets Table**: With SHA256 primary key
4. **Update Migration System**: Run via `python migrations/migrate.py`
5. **Supabase Support**: Add to `supabase_setup_consolidated.sql`

### Phase 2: Storage Infrastructure
1. **Create Storage Helper Class**: `utils/image_storage.py`
   - SHA256 computation utilities
   - Local filesystem operations
   - Supabase Storage integration
   - Path generation (2-level directory structure)
2. **Storage API Methods**:
   ```python
   def store_image(image_data: bytes, content_type: str = None) -> str:
       """Store image and return SHA256 hash"""
   
   def get_image_url(content_hash: str, expires_in: int = 3600) -> str:
       """Get signed URL for image access"""
   
   def delete_image(content_hash: str) -> bool:
       """Remove image from storage and database"""
   
   def cleanup_orphans() -> List[str]:
       """Find and remove unreferenced images"""
   ```

### Phase 3: Import System Updates

Assume we're starting for a cleam implemention. no legacy support needed. use new schema only

1. **Update StateImporter**: Modify `imports/states.py`
   - Replace `_store_screenshot_metadata_linked()` with SHA256 approach
   - Compute SHA256 hash of image content
   - Check if hash exists in `image_assets`
   - Store image only if new, always update `search_results.image_hash`


### Phase 4: Display System Updates
1. **Update Database Queries**: Modify functions to join with `image_assets`
2. **Create Image Access Functions**:
   ```sql
   CREATE OR REPLACE FUNCTION get_image_url_for_result(search_result_id INT)
   RETURNS TEXT AS $$
   BEGIN
       RETURN (
           SELECT CASE 
               WHEN ia.storage_type = 'local' THEN 
                   'file://' || ia.storage_path
               WHEN ia.storage_type = 'supabase' THEN 
                   -- Generate Supabase signed URL
                   get_supabase_signed_url(ia.storage_path)
               END
           FROM search_results sr
           JOIN image_assets ia ON sr.image_hash = ia.content_hash
           WHERE sr.id = search_result_id
       );
   END;
   $$ LANGUAGE plpgsql;
   ```

### Phase 5: Cleanup Tools

2. **Cleanup Tools**:
 
   def find_orphaned_images() 
       """Find images not referenced by any search_results and remove"""
    
   def clear_cache()
     """clean image meta data and delete images from cache"""
   

## Detailed Implementation Components

### 1. Storage Utilities (`utils/image_storage.py`)

```python
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Tuple
from supabase import create_client

class ImageStorage:
    def __init__(self, backend_type: str = 'local'):
        self.backend_type = backend_type
        self.local_cache_dir = Path('imagecache')
        
    def compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def get_storage_path(self, content_hash: str, extension: str = '.png') -> str:
        """Generate 2-level directory storage path"""
        return f"sha256/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}{extension}"
    
    def store_local(self, source_path: Path, content_hash: str) -> str:
        """Store image in local filesystem"""
        storage_path = self.get_storage_path(content_hash, source_path.suffix)
        full_path = self.local_cache_dir / storage_path
        
        # Create directories
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file if not exists
        if not full_path.exists():
            shutil.copy2(source_path, full_path)
        
        return str(storage_path)
    
    def store_supabase(self, source_path: Path, content_hash: str) -> str:
        """Store image in Supabase Storage"""
        storage_path = self.get_storage_path(content_hash, source_path.suffix)
        
        # Upload to Supabase bucket
        with open(source_path, 'rb') as f:
            response = self.supabase.storage.from_('imagecache').upload(
                storage_path, f, file_options={'content-type': 'image/png'}
            )
        
        return storage_path
```

### 2. Database Integration Updates

```python
# In imports/states.py - Replace image handling
def _store_image_with_deduplication(self, result_id: int, image_path: Path):
    """Store image with SHA256 deduplication"""
    
    # Compute hash
    storage = ImageStorage(self.backend)
    content_hash = storage.compute_sha256(image_path)
    
    # Check if asset already exists
    existing_asset = self.execute_query(
        "SELECT content_hash FROM image_assets WHERE content_hash = %s",
        (content_hash,)
    )
    
    if not existing_asset:
        # Store new image
        if self.backend == 'supabase':
            storage_path = storage.store_supabase(image_path, content_hash)
            storage_type = 'supabase'
        else:
            storage_path = storage.store_local(image_path, content_hash)
            storage_type = 'local'
        
        # Get image metadata
        file_size = image_path.stat().st_size
        content_type = 'image/png'  # Could detect from extension
        
        # Create asset record
        self.execute_statement("""
            INSERT INTO image_assets (content_hash, storage_path, storage_type, 
                                    file_size, content_type)
            VALUES (%s, %s, %s, %s, %s)
        """, (content_hash, storage_path, storage_type, file_size, content_type))
    
    # Link to search result
    self.execute_statement("""
        UPDATE search_results SET image_hash = %s WHERE id = %s
    """, (content_hash, result_id))
    
    self.logger.info(f"Image linked: {content_hash[:8]}... -> result_id {result_id}")
```


## Migration Steps

### Step 1: Database Schema Update
```bash
# Create migration file
cd migrations/migrations
cat > 20240814000000_image_sha256.sql << 'EOF'
-- Add image_hash column to search_results
ALTER TABLE search_results ADD COLUMN image_hash CHAR(64);

-- Create image_assets table
CREATE TABLE IF NOT EXISTS image_assets (
  content_hash     CHAR(64) PRIMARY KEY,
  storage_path     TEXT NOT NULL,
  storage_type     TEXT NOT NULL CHECK (storage_type IN ('local', 'supabase')),
  file_size        BIGINT NOT NULL,
  content_type     TEXT,
  width            INT,
  height           INT,
  first_seen       TIMESTAMP NOT NULL DEFAULT now(),
  last_accessed    TIMESTAMP DEFAULT now(),
  access_count     INT DEFAULT 1
);

-- Create indexes
CREATE INDEX ix_search_results_image ON search_results(image_hash);
CREATE INDEX ix_assets_storage ON image_assets(storage_type, storage_path);
CREATE INDEX ix_assets_access ON image_assets(last_accessed);
EOF

# Run migration
python migrations/migrate.py
```

### Step 2: Update Supabase Setup
```sql
-- Add to migrations/supabase_setup_consolidated.sql
-- (Schema changes from Step 1)
```

### Step 3: Implement Storage Classes
```bash
# Create storage utilities
touch utils/image_storage.py
# Implement ImageStorage class with local and Supabase support
```

### Step 4: Update Import System
```bash
# Update imports/states.py
# Replace _store_screenshot_metadata_linked with SHA256 approach
```

### Step 5: Data Migration
```bash
# Create migration tool
python utils/migrate_images_to_sha256.py
# This will:
# 1. Compute SHA256 for existing images
# 2. Populate image_assets table
# 3. Update search_results.image_hash
# 4. Reorganize local storage
```

### Step 6: Update Display System
```bash
# Update app.py to use new image access methods
# Update comprehensive results functions to join with image_assets
```

### Step 7: Cleanup
```bash
# After successful migration and testing:
# 1. Drop old images table
# 2. Remove old timestamp-based image directories
# 3. Update documentation
```

## Benefits of New System

### Storage Efficiency
- **Exact Deduplication**: Same image stored only once regardless of import frequency
- **Space Savings**: Potentially 50-90% reduction in storage usage for redundant screenshots
- **Organized Structure**: 2-level directory prevents filesystem performance issues

### Operational Benefits
- **Cloud Ready**: Seamless Supabase Storage integration
- **Cleanup Tools**: Easy identification and removal of orphaned images
- **Audit Trail**: Track when images were first seen and last accessed
- **Performance**: Direct hash-based lookups vs. complex path joins

### Development Benefits
- **Simple API**: Clean interface for image storage and retrieval
- **Backward Compatible**: Gradual migration without breaking existing functionality
- **Testable**: Clear separation of concerns for storage vs. database logic
- **Scalable**: Supports horizontal scaling with shared storage backends

## Risk Mitigation

### Data Safety
- **Migration Validation**: Verify all existing images migrated successfully
- **Backup Strategy**: Keep old images table until migration fully validated
- **Rollback Plan**: Ability to revert to timestamp-based system if needed

### Performance Considerations
- **Batch Processing**: Migrate images in batches to avoid memory issues
- **Index Strategy**: Proper indexing on hash columns for fast lookups
- **Concurrent Access**: Handle multiple import processes safely

### Error Handling
- **Partial Migration**: Continue processing even if individual images fail
- **Duplicate Detection**: Handle edge cases where same hash appears multiple times
- **Storage Failures**: Graceful degradation when storage backends unavailable

## Future Enhancements

### Advanced Features
- **Image Compression**: Automatic optimization for web display
- **Thumbnail Generation**: Create smaller preview images
- **CDN Integration**: Serve images via CloudFront or similar
- **Metadata Extraction**: Store EXIF data, creation timestamps
- **Access Analytics**: Track which images are viewed most frequently

### Monitoring & Maintenance
- **Storage Usage Tracking**: Monitor space usage trends
- **Orphan Detection**: Automated cleanup of unreferenced images
- **Health Checks**: Verify image accessibility and integrity
- **Performance Metrics**: Track image access patterns and response times

This plan provides a comprehensive roadmap for migrating PharmChecker to a modern, efficient, and scalable image storage system while maintaining data integrity and system reliability.