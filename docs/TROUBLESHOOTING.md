# PharmChecker Troubleshooting Guide

## Common Issues and Solutions

### Database Connection Issues

#### Error: Could not connect to database
```
psycopg2.OperationalError: could not connect to server
```

**Causes & Solutions:**

1. **PostgreSQL not running**
   ```bash
   # Check if PostgreSQL is running
   pg_isready
   
   # Start PostgreSQL
   # macOS:
   brew services start postgresql@14
   # Linux:
   sudo systemctl start postgresql
   # Windows:
   net start postgresql-x64-14
   ```

2. **Wrong credentials in .env**
   ```bash
   # Verify .env file exists
   ls -la .env
   
   # Check credentials
   cat .env | grep DB_
   
   # Test connection manually
   psql -h localhost -U postgres -d pharmchecker
   ```

3. **Database doesn't exist**
   ```bash
   # Create database
   psql -U postgres -c "CREATE DATABASE pharmchecker;"
   
   # Run setup
   python setup.py
   ```

#### Error: pg_trgm extension not found
```
ERROR: could not open extension control file "pg_trgm.control"
```

**Solution:**
```bash
# Install extension as superuser
psql -U postgres -d pharmchecker -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Verify installation
psql -U postgres -d pharmchecker -c "\dx"
```

### Import Issues

#### Error: Duplicate key value violates unique constraint
```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "datasets_kind_tag_key"
```

**Solution:**
```bash
# Option 1: Use different tag
python -m imports.pharmacies data.csv "pharmacy_v2"

# Option 2: Clean existing data
make clean_all
make dev

# Option 3: Use timestamp in tag
python -m imports.pharmacies data.csv "pharmacy_$(date +%Y%m%d_%H%M%S)"
```

#### Error: Invalid JSON in state_licenses
```
json.JSONDecodeError: Expecting value: line 1 column 1
```

**Solution:**
```python
# Fix CSV format - state_licenses should be JSON array
# Correct formats:
"[\"FL\",\"GA\"]"          # JSON array
"FL,GA"                    # Comma-separated (auto-converted)
[]                         # Empty array (valid)

# Check your CSV
import pandas as pd
df = pd.read_csv('pharmacies.csv')
print(df['state_licenses'].head())
```

#### Error: No results found in search directory
```
Warning: No valid search results found in directory
```

**Solution:**
```bash
# Check directory structure
tree data/states_baseline/

# Expected structure:
# data/states_baseline/
# ├── FL/
# │   ├── Pharmacy_01_parse.json
# │   └── Pharmacy_01.png
# └── PA/
#     └── Pharmacy_01_parse.json

# Verify JSON format
cat data/states_baseline/FL/*_parse.json | python -m json.tool
```

### Scoring Issues

#### Error: Scoring engine timeout
```
TimeoutError: Scoring computation exceeded time limit
```

**Solution:**
```python
# Reduce batch size
from imports.scoring import ScoringEngine
engine = ScoringEngine()
engine.compute_missing_scores(
    states_tag="states",
    pharmacies_tag="pharmacies",
    batch_size=50  # Smaller batch
)
```

#### Issue: Scores all showing as 0 or 100
```
All scores are either 0.0 or 100.0
```

**Solution:**
```python
# Check address data quality
SELECT 
    p.address as pharmacy_address,
    sr.address as result_address,
    ms.score_overall
FROM pharmacies p
JOIN search_results sr ON sr.search_name = p.name
LEFT JOIN match_scores ms ON ms.pharmacy_id = p.id
WHERE ms.score_overall IN (0, 100)
LIMIT 10;

# Recompute scores if needed
from imports.scoring import ScoringEngine
engine = ScoringEngine()
engine.recompute_all_scores("states", "pharmacies")
```

### Web Interface Issues

#### Error: Streamlit won't start
```
Error: Streamlit requires Python 3.8 or later
```

**Solution:**
```bash
# Check Python version
python --version

# Use Python 3.8+
python3.10 -m streamlit run app.py

# Or update Python
# macOS:
brew upgrade python@3.10
# Ubuntu:
sudo apt-get install python3.10
```

#### Error: Session state not found
```
StreamlitAPIException: st.session_state has no attribute 'comprehensive_results'
```

**Solution:**
```python
# Clear browser cache and reload
# Or restart Streamlit with:
streamlit run app.py --server.runOnSave false

# Force session reset in browser:
# Press Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
```

#### Issue: Screenshots not displaying
```
Images show as broken links
```

**Solution:**
```bash
# Check imagecache directory exists
ls -la imagecache/

# Check permissions
chmod -R 755 imagecache/

# Verify image paths in database
psql -U postgres -d pharmchecker -c "
SELECT organized_path, storage_type 
FROM images 
LIMIT 5;
"

# Re-import with correct paths
python -m imports.states data/states_baseline "states_fix"
```

#### Issue: Filters not working
```
Filtering by state or status has no effect
```

**Solution:**
```python
# Clear session state
import streamlit as st
if st.button("Clear Cache"):
    st.session_state.clear()
    st.rerun()

# Or restart browser session
# Close all tabs and reopen
```

### Performance Issues

#### Issue: Slow page loads
```
Page takes >10 seconds to load
```

**Solutions:**

1. **Add database indexes**
   ```sql
   -- Check missing indexes
   SELECT schemaname, tablename, attname, n_distinct, correlation
   FROM pg_stats
   WHERE tablename IN ('search_results', 'pharmacies')
   AND n_distinct > 100;
   
   -- Add recommended indexes
   CREATE INDEX CONCURRENTLY ix_results_search_name 
   ON search_results(search_name);
   
   -- Vacuum and analyze
   VACUUM ANALYZE;
   ```

2. **Reduce dataset size**
   ```python
   # Filter to specific states
   df_filtered = df[df['search_state'].isin(['FL', 'PA'])]
   ```

3. **Enable caching**
   ```python
   # In utils/database.py
   @st.cache_data(ttl=600)  # Cache for 10 minutes
   def get_comprehensive_results(states_tag, pharmacies_tag):
       # ... query code
   ```

#### Issue: Out of memory errors
```
MemoryError: Unable to allocate array
```

**Solution:**
```bash
# Increase Streamlit memory limit
streamlit run app.py \
  --server.maxUploadSize 1000 \
  --server.maxMessageSize 1000

# Or process in smaller chunks
# Modify batch_size in imports
BATCH_SIZE = 500  # Instead of 1000
```

### Data Quality Issues

#### Issue: Pharmacies not matching searches
```
Pharmacy in database but showing "no data" for all states
```

**Debugging steps:**
```sql
-- Check exact names
SELECT DISTINCT name FROM pharmacies WHERE dataset_id = ?;
SELECT DISTINCT search_name FROM search_results WHERE dataset_id = ?;

-- Look for name mismatches
SELECT p.name, sr.search_name
FROM pharmacies p
LEFT JOIN search_results sr 
  ON p.name = sr.search_name
WHERE sr.search_name IS NULL;
```

**Solution:**
```python
# Standardize names before import
df['name'] = df['name'].str.strip().str.title()
```

#### Issue: Duplicate search results
```
Same license appearing multiple times
```

**Solution:**
```sql
-- Find duplicates
SELECT dataset_id, search_state, license_number, COUNT(*)
FROM search_results
GROUP BY dataset_id, search_state, license_number
HAVING COUNT(*) > 1;

-- Remove duplicates (keep latest)
DELETE FROM search_results a
USING search_results b
WHERE a.id < b.id
  AND a.dataset_id = b.dataset_id
  AND a.search_state = b.search_state
  AND a.license_number = b.license_number;
```

### Validation Issues

#### Issue: Validations not saving
```
Validation marked but doesn't persist
```

**Solution:**
```python
# Check validated dataset is loaded
SELECT * FROM datasets WHERE kind = 'validated';

# Ensure user has permission
SELECT * FROM app_users WHERE email = ?;

# Check validation was inserted
SELECT * FROM validated_overrides 
WHERE pharmacy_name = ? 
AND state_code = ?
ORDER BY validated_at DESC;
```

#### Issue: Validation warnings incorrect
```
"Data has changed since validation" but it hasn't
```

**Solution:**
```sql
-- Check for timestamp differences
SELECT 
  vo.validated_at,
  sr.created_at as search_created,
  sr.search_ts as search_timestamp
FROM validated_overrides vo
JOIN search_results sr 
  ON vo.pharmacy_name = sr.search_name
  AND vo.state_code = sr.search_state
WHERE vo.validated_at < sr.created_at;
```

## Error Messages Reference

### Database Errors

| Error | Meaning | Solution |
|-------|---------|----------|
| `FATAL: database does not exist` | Database not created | Run `python setup.py` |
| `FATAL: password authentication failed` | Wrong password | Check `.env` file |
| `ERROR: permission denied` | User lacks privileges | Grant permissions or use admin user |
| `ERROR: relation does not exist` | Table not created | Run schema.sql |

### Import Errors

| Error | Meaning | Solution |
|-------|---------|----------|
| `FileNotFoundError` | Import file missing | Check file path |
| `JSONDecodeError` | Invalid JSON format | Validate JSON syntax |
| `KeyError: 'required_field'` | Missing required field | Check data format |
| `IntegrityError` | Constraint violation | Check for duplicates |

### Application Errors

| Error | Meaning | Solution |
|-------|---------|----------|
| `StreamlitAPIException` | Streamlit error | Clear cache, restart |
| `TimeoutError` | Operation too slow | Reduce batch size |
| `MemoryError` | Out of memory | Process smaller chunks |
| `AttributeError` | Missing attribute | Check session state |

## Getting Help

### Diagnostic Commands

```bash
# System info
python -c "import sys; print(sys.version)"
pip list | grep -E "streamlit|pandas|psycopg2"

# Database info
psql -U postgres -d pharmchecker -c "\dt"
psql -U postgres -d pharmchecker -c "\df"

# Data status
python show_status.py

# Test suite
python system_test.py
```

### Log Files

Enable debug logging:
```bash
# In .env
LOGGING_LEVEL=DEBUG

# Or at runtime
LOGGING_LEVEL=DEBUG python app.py 2>&1 | tee debug.log
```

### Support Checklist

Before requesting help, collect:
1. Error message (full traceback)
2. Steps to reproduce
3. System info (OS, Python version)
4. Database status (`make status`)
5. Recent changes made
6. Log files if available