# API Conversion and Legacy Cleanup Prompt

## Background

PharmChecker has successfully implemented a dual backend system with API-first architecture. The current system supports:

1. **Supabase (Cloud)**: `USE_API_BACKEND=true, USE_CLOUD_DB=true`
2. **PostgREST (Local)**: `USE_API_BACKEND=true, USE_CLOUD_DB=false` 
3. **Direct Database (Legacy)**: `USE_API_BACKEND=false, USE_CLOUD_DB=false`

All system tests pass on configurations 1 and 2. Configuration 3 exists for backwards compatibility but should be eliminated to complete the API-first migration.

## Current Status

### ✅ Completed
- Renamed `PREFER_SUPABASE` → `USE_CLOUD_DB` for clearer semantics
- Eliminated fallback behavior - systems fail fast if backend unavailable
- UnifiedClient (`api_poc/gui/client.py`) works with both Supabase and PostgREST
- App.py uses API client and displays correct backend in sidebar
- System tests pass on both Supabase and PostgREST APIs
- No silent fallbacks - deterministic backend selection

### 🔄 Current Environment Variables
```bash
# These control database backend:
USE_API_BACKEND=true    # true = API mode, false = direct database (legacy)
USE_CLOUD_DB=true      # true = Supabase, false = PostgreSQL

# Default configuration (.env):
USE_API_BACKEND=true
USE_CLOUD_DB=true
```

## Task: Complete API-First Migration

### Objective
Eliminate all direct database access and make API the only way to interact with the database. Remove `USE_API_BACKEND` variable since API will be the only option.

### Steps Required

#### 1. Audit Current Direct Database Usage
Find all remaining direct database connections:
```bash
# Search for direct psycopg2 usage
grep -r "psycopg2" --include="*.py" .
grep -r "get_db_config" --include="*.py" .
grep -r "USE_API_BACKEND" --include="*.py" .

# Check imports that might use direct database
find . -name "*.py" -exec grep -l "import psycopg2\|from psycopg2" {} \;
```

#### 2. Convert Remaining Direct Database Code

**Key files that likely need conversion:**
- `system_test.py` - Currently uses psycopg2 directly for some operations
- Any remaining importers or utilities using direct connections
- Database management scripts

**Conversion pattern:**
```python
# OLD: Direct database
import psycopg2
from config import get_db_config

conn = psycopg2.connect(**get_db_config())

# NEW: API client
import sys, os
sys.path.append(os.path.join('api_poc', 'gui'))
from client import create_client
from config import use_cloud_database

client = create_client(prefer_supabase=use_cloud_database())
```

#### 3. Update Configuration System

**Remove USE_API_BACKEND:**
- Update `config.py` to remove `USE_API_BACKEND` variable
- Update `.env.example` to remove `USE_API_BACKEND` 
- Simplify configuration to only `USE_CLOUD_DB`
- Update `get_backend_type()` to only return 'supabase' or 'postgrest'

**New simplified config:**
```bash
# Only this variable needed:
USE_CLOUD_DB=true  # true = Supabase, false = PostgREST+PostgreSQL
```

#### 4. Remove Legacy Database Utilities

**Files to examine for removal:**
- Direct database connection code in `utils/database.py`
- Legacy database manager classes that use psycopg2
- Any fallback logic remaining in importers

**Keep:**
- API client (`api_poc/gui/client.py`)
- API database manager (`utils/api_database.py`)
- Database adapter pattern for importers (if using APIs)

#### 5. Update System Test

Convert `system_test.py` to use pure API calls:
- Replace direct psycopg2 queries with API client calls
- Use client.get_comprehensive_results() instead of raw SQL
- Use client methods for data validation

#### 6. Update Documentation

Update these files to reflect API-only architecture:
- `README.md` - Remove direct database setup instructions
- `CLAUDE.md` - Update database connection info
- Configuration examples in docs/

#### 7. Test Migration

**Verify these work:**
```bash
# Default Supabase configuration
USE_CLOUD_DB=true python system_test.py
USE_CLOUD_DB=true streamlit run app.py

# Local PostgREST configuration (requires PostgREST running)
USE_CLOUD_DB=false python system_test.py
USE_CLOUD_DB=false streamlit run app.py
```

**Verify these are removed:**
- No direct psycopg2 connections in any code
- `USE_API_BACKEND` variable eliminated
- Simplified configuration with only `USE_CLOUD_DB`

## Important Context

### Database Schema
Both Supabase and PostgreSQL use identical schemas via the unified migration system:
- Tables: `datasets`, `pharmacies`, `search_results`, `match_scores`, `validated_overrides`
- Functions: `get_all_results_with_context()`, scoring functions
- APIs: Both expose same REST endpoints

### PostgREST Setup
Local PostgreSQL is accessible via PostgREST at `http://localhost:3000`:
```bash
cd api_poc/postgrest
./postgrest postgrest.conf  # Starts PostgREST server
```

### UnifiedClient Architecture
The `api_poc/gui/client.py` provides:
- `create_client(prefer_supabase=bool)` - Factory function
- Same methods work with both Supabase and PostgREST
- Automatic backend detection and connection
- Client-side scoring computation
- Comprehensive results API

### Critical Success Criteria
1. **System tests pass** on both `USE_CLOUD_DB=true/false`
2. **App.py works** on both configurations  
3. **No direct database** connections anywhere in codebase
4. **Simplified config** with only `USE_CLOUD_DB` variable
5. **Same functionality** as before migration
6. **Clean codebase** with legacy code removed

## Files Most Likely to Need Changes

### High Priority
- `system_test.py` - Convert direct psycopg2 to API calls
- `config.py` - Remove `USE_API_BACKEND`, simplify functions
- `.env.example` - Remove `USE_API_BACKEND` references
- `utils/database.py` - Remove direct database managers

### Medium Priority  
- Import modules that might use direct connections
- Any scripts in root directory using database
- Database management utilities

### Low Priority
- Documentation files
- Comments referencing old configuration
- Test files using direct database

## Expected Outcome

After completion:
```bash
# Single environment variable controls backend
USE_CLOUD_DB=true   # Supabase API
USE_CLOUD_DB=false  # PostgREST + PostgreSQL API

# No direct database connections anywhere
# Simplified, clean API-first architecture
# Same functionality, better maintainability
```

The system will be purely API-driven with clean, maintainable code and deterministic backend selection.