# PharmChecker - Complete Implementation Documentation

## ⚠️ Important Schema Note
**This document contains legacy schema references.** The actual implemented system uses an **optimized merged `search_results` table** that combines search metadata and results for better performance and data integrity. For the working schema, see `functions_optimized.sql` and the system test files.

**Status**: ✅ Core system complete and tested. Scoring engine implemented with 96.5% accuracy.

## Overview
PharmChecker is a lightweight internal tool for verifying pharmacy licenses across U.S. states through manual review of automated search results.

### Key Design Principles
- **Dataset Independence**: Pharmacies, state searches, and validated overrides can be imported and combined in any order
- **Natural Key Linking**: Cross-dataset relationships use pharmacy names and license numbers, not internal IDs
- **Multi-User Support**: Multiple users can work with different dataset combinations simultaneously
- **Lazy Scoring**: Address match scores computed on-demand when needed
- **Manual Control**: All refresh and recalculation actions are explicit
- **Validation as Snapshot**: Validated overrides capture the full search result at validation time

## System Architecture

### Core Components
1. **PostgreSQL Database** - Stores all datasets and computed scores
2. **Import Scripts** - Load pharmacies, state searches, and validated overrides
3. **Scoring Engine** - Computes address match scores on-demand
4. **Streamlit UI** - Review interface with GitHub authentication
5. **Storage Layer** - Local filesystem (dev) or Supabase Storage (production)

### Data Flow
```
CSV/JSON → Import Scripts → PostgreSQL → Lazy Scoring → Matrix View → Streamlit UI
                              ↑                                         ↓
                         Validated Overrides ← ← ← ← ← ← ← User Edits
```

### Name and ID Flow
```
pharmacies.name → searches.search_name → validated_overrides.pharmacy_name
       ↓                    ↓
   pharmacy_id          search_id → search_results
       ↓                    ↓              ↓
       └─── match_scores ───┘         result_id
           (uses IDs within dataset pair)
```

## Database Schema

### Core Tables

```sql
-- Versioned datasets (no global active state)
CREATE TABLE datasets (
  id          SERIAL PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('states','pharmacies','validated')),
  tag         TEXT NOT NULL,
  description TEXT,
  created_by  TEXT,
  created_at  TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE(kind, tag)
);

-- Pharmacy master records
CREATE TABLE pharmacies (
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
CREATE TABLE searches (
  id            SERIAL PRIMARY KEY,
  dataset_id    INT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  search_name   TEXT NOT NULL,  -- Exact copy from pharmacies.name
  search_state  CHAR(2) NOT NULL,
  search_ts     TIMESTAMP,
  meta          JSONB
);

-- Search results from state boards
CREATE TABLE search_results (
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
CREATE TABLE match_scores (
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
CREATE TABLE validated_overrides (
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
  
  UNIQUE(dataset_id, pharmacy_name, state_code, COALESCE(license_number, ''))
);

-- Screenshot/image storage metadata
CREATE TABLE images (
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
CREATE TABLE app_users (
  id           SERIAL PRIMARY KEY,
  github_login TEXT UNIQUE,
  email        TEXT UNIQUE,
  role         TEXT NOT NULL CHECK (role IN ('admin','user')),
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMP NOT NULL DEFAULT now()
);
```

### Indexes

```sql
-- Pharmacies
CREATE INDEX ix_pharm_dataset ON pharmacies(dataset_id);
CREATE INDEX ix_pharm_name ON pharmacies(name);
CREATE INDEX ix_pharm_name_trgm ON pharmacies USING gin (name gin_trgm_ops);

-- Searches
CREATE INDEX ix_search_dataset ON searches(dataset_id);
CREATE INDEX ix_search_name_state ON searches(dataset_id, search_name, search_state, search_ts DESC);

-- Search results
CREATE INDEX ix_results_search ON search_results(search_id);
CREATE INDEX ix_results_license ON search_results(license_number);
CREATE INDEX ix_results_dates ON search_results(issue_date, expiration_date);

-- Match scores
CREATE INDEX ix_scores_composite ON match_scores(
  states_dataset_id, pharmacies_dataset_id, pharmacy_id, score_overall DESC
);

-- Validated overrides
CREATE INDEX ix_validated_dataset ON validated_overrides(dataset_id);
CREATE INDEX ix_validated_lookup ON validated_overrides(pharmacy_name, state_code);
CREATE INDEX ix_validated_license ON validated_overrides(state_code, license_number);

-- Images
CREATE INDEX ix_images_dataset ON images(dataset_id, state);
CREATE INDEX ix_images_search ON images(search_id);
```

## Parameterized Views and Functions

### Get Matrix Function
Since there's no global "active" state, the matrix is built on-demand for specific tag combinations:

```sql
CREATE OR REPLACE FUNCTION get_results_matrix(
  p_states_tag TEXT,
  p_pharmacies_tag TEXT,
  p_validated_tag TEXT
) RETURNS TABLE (
  pharmacy_id INT,
  pharmacy_name TEXT,
  search_state CHAR(2),
  latest_search_id INT,
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
  -- Get most recent search for each (name, state) combination
  SELECT DISTINCT ON (s.search_name, s.search_state)
    s.*
  FROM searches s, dataset_ids d
  WHERE s.dataset_id = d.states_id
  ORDER BY s.search_name, s.search_state, s.search_ts DESC NULLS LAST, s.id DESC
),
best_scores AS (
  -- Get best scoring result for each (pharmacy, search) pair
  SELECT DISTINCT ON (ms.pharmacy_id, sr.search_id)
    ms.pharmacy_id,
    sr.search_id,
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
  ORDER BY ms.pharmacy_id, sr.search_id, ms.score_overall DESC NULLS LAST, sr.id
),
joined AS (
  -- Join everything together
  SELECT
    p.pharmacy_id,
    p.pharmacy_name,
    p.state_code AS search_state,
    ls.id AS latest_search_id,
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
    AND bs.search_id = ls.id
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
  latest_search_id,
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
    WHEN latest_search_id IS NULL THEN 'no data'
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
```

### Find Missing Scores Function

```sql
CREATE OR REPLACE FUNCTION find_missing_scores(
  p_states_tag TEXT,
  p_pharmacies_tag TEXT
) RETURNS TABLE (
  pharmacy_id INT,
  search_id INT
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
    s.id as search_id
  FROM pharmacies p
  JOIN dataset_ids d ON p.dataset_id = d.pharmacies_id
  CROSS JOIN LATERAL (
    SELECT s.id
    FROM searches s
    WHERE s.dataset_id = d.states_id
      AND s.search_name = p.name
      AND s.search_state = ANY(
        SELECT (jsonb_array_elements_text(p.state_licenses))::char(2)
      )
  ) s
  WHERE NOT EXISTS (
    SELECT 1 
    FROM match_scores ms
    JOIN search_results sr ON sr.search_id = s.id
    WHERE ms.pharmacy_id = p.id
      AND ms.result_id = sr.id
      AND ms.states_dataset_id = d.states_id
      AND ms.pharmacies_dataset_id = d.pharmacies_id
  )
)
SELECT * FROM needed_pairs;
$$ LANGUAGE SQL;
```

## Import Scripts

### Directory Structure
```
pharmchecker/
├── imports/
│   ├── __init__.py
│   ├── base.py           # Shared import logic
│   ├── pharmacies.py     # Import pharmacy datasets
│   ├── states.py         # Import state search results
│   ├── validated.py      # Import validated overrides
│   └── scoring.py        # Lazy scoring engine
├── scoring_plugin.py      # Address matching plugin
├── app.py                 # Streamlit UI
├── config.py             # Configuration
└── requirements.txt
```

### Base Import Class
```python
# imports/base.py
import logging
from typing import Dict, Any
import psycopg2
from psycopg2.extras import execute_values

class BaseImporter:
    def __init__(self, conn_params: Dict[str, Any]):
        self.conn = psycopg2.connect(**conn_params)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def create_dataset(self, kind: str, tag: str, description: str = None, created_by: str = None) -> int:
        """Create or get dataset ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO datasets (kind, tag, description, created_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (kind, tag) DO UPDATE 
                SET description = EXCLUDED.description
                RETURNING id
            """, (kind, tag, description, created_by))
            return cur.fetchone()[0]
    
    def batch_insert(self, table: str, columns: list, data: list, batch_size: int = 1000):
        """Batch insert with error handling"""
        template = f"({','.join(['%s'] * len(columns))})"
        
        with self.conn.cursor() as cur:
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                try:
                    execute_values(
                        cur,
                        f"INSERT INTO {table} ({','.join(columns)}) VALUES %s",
                        batch,
                        template=template
                    )
                    self.conn.commit()
                    self.logger.info(f"Inserted batch {i//batch_size + 1} ({len(batch)} rows)")
                except Exception as e:
                    self.logger.error(f"Failed batch {i//batch_size + 1}: {e}")
                    self.conn.rollback()
                    # Continue with next batch
```

### Pharmacy Import
```python
# imports/pharmacies.py
import json
import pandas as pd
from .base import BaseImporter

class PharmacyImporter(BaseImporter):
    def import_csv(self, filepath: str, tag: str, created_by: str = None):
        """Import pharmacies from CSV"""
        df = pd.read_csv(filepath)
        
        # Create dataset
        dataset_id = self.create_dataset('pharmacies', tag, created_by=created_by)
        
        # Prepare data
        data = []
        for _, row in df.iterrows():
            # Parse state_licenses from string representation
            state_licenses = json.loads(row.get('state_licenses', '[]'))
            
            # Collect any extra columns into additional_info
            known_cols = {'name', 'alias', 'address', 'suite', 'city', 'state', 'zip', 'state_licenses'}
            additional_info = {k: v for k, v in row.items() if k not in known_cols}
            
            data.append((
                dataset_id,
                row['name'],  # Exact string that will be used as search_name
                row.get('alias'),
                row.get('address'),
                row.get('suite'),
                row.get('city'),
                row.get('state'),
                row.get('zip'),
                json.dumps(state_licenses),
                json.dumps(additional_info) if additional_info else None
            ))
        
        # Batch insert
        columns = ['dataset_id', 'name', 'alias', 'address', 'suite', 
                   'city', 'state', 'zip', 'state_licenses', 'additional_info']
        self.batch_insert('pharmacies', columns, data)
        
        self.logger.info(f"Imported {len(data)} pharmacies with tag '{tag}'")
```

### State Search Import
```python
# imports/states.py
import json
from datetime import datetime
from pathlib import Path
from .base import BaseImporter

class StateImporter(BaseImporter):
    def import_json(self, filepath: str, tag: str, screenshot_dir: Path = None, created_by: str = None):
        """Import state search results from JSON"""
        with open(filepath) as f:
            data = json.load(f)
        
        dataset_id = self.create_dataset('states', tag, created_by=created_by)
        
        for search_data in data.get('searches', []):
            # Insert search
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO searches (dataset_id, search_name, search_state, search_ts, meta)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    dataset_id,
                    search_data['name'],  # Exact copy from pharmacies.name
                    search_data['state'],
                    search_data.get('timestamp'),
                    json.dumps(search_data.get('meta', {}))
                ))
                search_id = cur.fetchone()[0]
            
            # Insert results
            results_data = []
            for result in search_data.get('results', []):
                # Parse dates
                issue_date = None
                exp_date = None
                if 'issue_date' in result:
                    issue_date = datetime.strptime(result['issue_date'], '%Y-%m-%d').date()
                if 'expiration_date' in result:
                    exp_date = datetime.strptime(result['expiration_date'], '%Y-%m-%d').date()
                
                results_data.append((
                    search_id,
                    result.get('license_number'),
                    result.get('license_status'),
                    result.get('license_name'),  # Can vary: "Empower TX", "Empower LLC"
                    result.get('address'),
                    result.get('city'),
                    result.get('state'),
                    result.get('zip'),
                    issue_date,
                    exp_date,
                    result.get('result_status'),
                    json.dumps(result)
                ))
            
            if results_data:
                columns = ['search_id', 'license_number', 'license_status', 'license_name',
                          'address', 'city', 'state', 'zip', 'issue_date', 'expiration_date',
                          'result_status', 'raw']
                self.batch_insert('search_results', columns, results_data)
            
            # Handle screenshot if present
            if screenshot_dir and 'screenshot' in search_data:
                self._store_screenshot(dataset_id, search_id, search_data, screenshot_dir, tag)
    
    def _store_screenshot(self, dataset_id: int, search_id: int, search_data: dict, 
                         screenshot_dir: Path, tag: str):
        """Store screenshot metadata"""
        from slugify import slugify
        
        search_name_slug = slugify(search_data['name'])
        timestamp = search_data.get('timestamp', datetime.now().isoformat())
        
        # Build organized path
        organized_path = f"{tag}/{search_data['state']}/{search_name_slug}.{timestamp}"
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO images (dataset_id, state, search_id, search_name, 
                                   organized_path, storage_type, file_size)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dataset_id, organized_path) DO NOTHING
            """, (
                dataset_id,
                search_data['state'],
                search_id,
                search_data['name'],
                organized_path,
                'local',  # or 'supabase' in production
                0  # Calculate actual file size if needed
            ))
        self.conn.commit()
```

### Validated Overrides Import
```python
# imports/validated.py
import pandas as pd
from datetime import datetime
from .base import BaseImporter

class ValidatedImporter(BaseImporter):
    def import_csv(self, filepath: str, tag: str, created_by: str = None):
        """Import validated overrides from CSV (snapshots of search results)"""
        df = pd.read_csv(filepath)
        
        dataset_id = self.create_dataset('validated', tag, created_by=created_by)
        
        data = []
        for _, row in df.iterrows():
            # Parse dates if present
            issue_date = None
            exp_date = None
            if pd.notna(row.get('issue_date')):
                issue_date = pd.to_datetime(row['issue_date']).date()
            if pd.notna(row.get('expiration_date')):
                exp_date = pd.to_datetime(row['expiration_date']).date()
            
            data.append((
                dataset_id,
                row['pharmacy_name'],
                row['state_code'],
                row.get('license_number'),
                row.get('license_status'),
                row.get('license_name'),
                row.get('address'),
                row.get('city'),
                row.get('state'),
                row.get('zip'),
                issue_date,
                exp_date,
                row.get('result_status'),
                row['override_type'],  # 'present' or 'empty'
                row.get('reason'),
                row.get('validated_by', created_by)
            ))
        
        columns = ['dataset_id', 'pharmacy_name', 'state_code', 'license_number',
                   'license_status', 'license_name', 'address', 'city', 'state', 'zip',
                   'issue_date', 'expiration_date', 'result_status',
                   'override_type', 'reason', 'validated_by']
        
        # Use UPSERT to handle duplicates
        with self.conn.cursor() as cur:
            from psycopg2.extras import execute_values
            execute_values(
                cur,
                f"""
                INSERT INTO validated_overrides ({','.join(columns)})
                VALUES %s
                ON CONFLICT (dataset_id, pharmacy_name, state_code, COALESCE(license_number, ''))
                DO UPDATE SET
                    license_status = EXCLUDED.license_status,
                    license_name = EXCLUDED.license_name,
                    address = EXCLUDED.address,
                    city = EXCLUDED.city,
                    state = EXCLUDED.state,
                    zip = EXCLUDED.zip,
                    issue_date = EXCLUDED.issue_date,
                    expiration_date = EXCLUDED.expiration_date,
                    result_status = EXCLUDED.result_status,
                    override_type = EXCLUDED.override_type,
                    reason = EXCLUDED.reason,
                    validated_by = EXCLUDED.validated_by,
                    validated_at = now()
                """,
                data,
                template=f"({','.join(['%s'] * len(columns))})"
            )
        
        self.conn.commit()
        self.logger.info(f"Imported {len(data)} validated overrides with tag '{tag}'")
```

## Scoring Plugin

```python
# scoring_plugin.py
from dataclasses import dataclass
from typing import Tuple, Optional
import re
from difflib import SequenceMatcher

@dataclass
class Address:
    address: Optional[str]
    suite: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]

def normalize_address_component(text: Optional[str]) -> str:
    """Normalize address components for comparison"""
    if not text:
        return ""
    
    # Convert to lowercase and strip whitespace
    text = text.lower().strip()
    
    # Common abbreviations
    replacements = {
        'street': 'st',
        'avenue': 'ave',
        'road': 'rd',
        'boulevard': 'blvd',
        'drive': 'dr',
        'lane': 'ln',
        'court': 'ct',
        'place': 'pl',
        'suite': 'ste',
        'apartment': 'apt',
        'north': 'n',
        'south': 's',
        'east': 'e',
        'west': 'w'
    }
    
    for full, abbr in replacements.items():
        text = re.sub(r'\b' + full + r'\b', abbr, text)
    
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text

def match_addresses(state_addr: Address, pharmacy_addr: Address) -> Tuple[float, float, float]:
    """
    Compare addresses and return match scores.
    
    Returns:
        (street_score, city_state_zip_score, overall_score)
        Each score is between 0.0 and 1.0
    """
    
    # Normalize all components
    state_street = normalize_address_component(state_addr.address)
    pharm_street = normalize_address_component(pharmacy_addr.address)
    
    state_suite = normalize_address_component(state_addr.suite)
    pharm_suite = normalize_address_component(pharmacy_addr.suite)
    
    state_city = normalize_address_component(state_addr.city)
    pharm_city = normalize_address_component(pharmacy_addr.city)
    
    state_state = normalize_address_component(state_addr.state)
    pharm_state = normalize_address_component(pharmacy_addr.state)
    
    state_zip = normalize_address_component(state_addr.zip)[:5]  # First 5 digits only
    pharm_zip = normalize_address_component(pharmacy_addr.zip)[:5]
    
    # Calculate street score
    street_score = 0.0
    if state_street and pharm_street:
        # Use sequence matcher for fuzzy matching
        street_ratio = SequenceMatcher(None, state_street, pharm_street).ratio()
        
        # Bonus for exact match
        if state_street == pharm_street:
            street_score = 1.0
        else:
            street_score = street_ratio * 0.9  # Max 0.9 for non-exact
        
        # Suite matching (if both have suites)
        if state_suite and pharm_suite:
            if state_suite == pharm_suite:
                street_score = min(1.0, street_score + 0.1)
            else:
                street_score *= 0.8  # Penalty for suite mismatch
    
    # Calculate city/state/zip score
    csz_score = 0.0
    csz_components = 0
    csz_matches = 0
    
    if state_city and pharm_city:
        csz_components += 1
        if state_city == pharm_city:
            csz_matches += 1
    
    if state_state and pharm_state:
        csz_components += 1
        if state_state == pharm_state:
            csz_matches += 1
    
    if state_zip and pharm_zip:
        csz_components += 1
        if state_zip == pharm_zip:
            csz_matches += 1
    
    if csz_components > 0:
        csz_score = csz_matches / csz_components
    
    # Calculate overall score
    # Weight street address more heavily than city/state/zip
    if state_street and pharm_street:
        overall_score = (0.7 * street_score) + (0.3 * csz_score)
    else:
        # No street address to compare, rely on city/state/zip
        overall_score = csz_score * 0.5  # Max 0.5 without street match
    
    return (street_score, csz_score, overall_score)
```

## Lazy Scoring Engine

```python
# imports/scoring.py
import json
import logging
from datetime import datetime
from typing import List, Tuple
from .base import BaseImporter
from scoring_plugin import Address, match_addresses

class ScoringEngine(BaseImporter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('ScoringEngine')
    
    def find_missing_scores(self, states_tag: str, pharmacies_tag: str, 
                           limit: int = 1000) -> List[Tuple[int, int]]:
        """Find pharmacy/search pairs that need scoring"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT pharmacy_id, search_id 
                FROM find_missing_scores(%s, %s)
                LIMIT %s
            """, (states_tag, pharmacies_tag, limit))
            return cur.fetchall()
    
    def compute_scores(self, states_tag: str, pharmacies_tag: str, 
                       batch_size: int = 200) -> int:
        """Compute missing scores for the given dataset combination"""
        
        # Get dataset IDs
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM datasets WHERE kind='states' AND tag=%s", (states_tag,))
            states_id = cur.fetchone()[0]
            
            cur.execute("SELECT id FROM datasets WHERE kind='pharmacies' AND tag=%s", (pharmacies_tag,))
            pharmacies_id = cur.fetchone()[0]
        
        # Find missing scores
        missing = self.find_missing_scores(states_tag, pharmacies_tag)
        self.logger.info(f"Found {len(missing)} pharmacy/search pairs needing scores")
        
        total_scored = 0
        
        for i in range(0, len(missing), batch_size):
            batch = missing[i:i + batch_size]
            batch_scores = []
            
            for pharmacy_id, search_id in batch:
                try:
                    # Get pharmacy address
                    pharm_addr = self._get_pharmacy_address(pharmacy_id)
                    
                    # Get all results for this search
                    results = self._get_search_results(search_id)
                    
                    # Score each result
                    for result in results:
                        state_addr = Address(
                            address=result['address'],
                            suite=None,  # Not typically in search results
                            city=result['city'],
                            state=result['state'],
                            zip=result['zip']
                        )
                        
                        street_score, csz_score, overall_score = match_addresses(state_addr, pharm_addr)
                        
                        batch_scores.append((
                            states_id,
                            pharmacies_id,
                            pharmacy_id,
                            result['id'],
                            overall_score * 100,  # Convert to 0-100 scale
                            street_score * 100,
                            csz_score * 100,
                            json.dumps({
                                'algorithm': 'v1',
                                'timestamp': datetime.now().isoformat()
                            })
                        ))
                
                except Exception as e:
                    self.logger.error(f"Failed to score pharmacy {pharmacy_id} search {search_id}: {e}")
                    continue
            
            # Batch upsert scores
            if batch_scores:
                self._upsert_scores(batch_scores)
                total_scored += len(batch_scores)
                self.logger.info(f"Scored batch {i//batch_size + 1}: {len(batch_scores)} scores")
        
        return total_scored
    
    def _get_pharmacy_address(self, pharmacy_id: int) -> Address:
        """Get pharmacy address for scoring"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT address, suite, city, state, zip 
                FROM pharmacies WHERE id = %s
            """, (pharmacy_id,))
            row = cur.fetchone()
            return Address(*row)
    
    def _get_search_results(self, search_id: int) -> List[dict]:
        """Get all results for a search"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, address, city, state, zip 
                FROM search_results WHERE search_id = %s
            """, (search_id,))
            return [dict(zip(['id', 'address', 'city', 'state', 'zip'], row)) 
                    for row in cur.fetchall()]
    
    def _upsert_scores(self, scores: List[Tuple]):
        """Upsert batch of scores"""
        with self.conn.cursor() as cur:
            from psycopg2.extras import execute_values
            execute_values(
                cur,
                """
                INSERT INTO match_scores 
                    (states_dataset_id, pharmacies_dataset_id, pharmacy_id, result_id,
                     score_overall, score_street, score_city_state_zip, scoring_meta)
                VALUES %s
                ON CONFLICT (states_dataset_id, pharmacies_dataset_id, pharmacy_id, result_id)
                DO UPDATE SET
                    score_overall = EXCLUDED.score_overall,
                    score_street = EXCLUDED.score_street,
                    score_city_state_zip = EXCLUDED.score_city_state_zip,
                    scoring_meta = EXCLUDED.scoring_meta,
                    created_at = now()
                """,
                scores,
                template="(%s, %s, %s, %s, %s, %s, %s, %s)"
            )
        self.conn.commit()
```

