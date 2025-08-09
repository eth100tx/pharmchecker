# PharmChecker Implementation Plan

## Project Overview
PharmChecker is a pharmacy license verification tool with:
- PostgreSQL database for storing versioned datasets
- Python import scripts for different data types (pharmacies, state searches, validated overrides)
- Address matching scoring engine with lazy computation
- Streamlit UI for review and validation

## Implementation Status: ✅ PLANNING PHASE

### Phase 1: Foundation (Status: PENDING)
1. **Project Structure Setup**
   - Create directory structure
   - Set up Python package structure with imports/ module
   - Create requirements.txt with dependencies
   - Initialize git repository properly

2. **Database Setup** 
   - Create database schema (tables, indexes, constraints)
   - Implement database functions (get_results_matrix, find_missing_scores)
   - Add trigram extension for fuzzy text matching
   - Set up initial app_users table with test user

3. **Configuration System**
   - Database connection configuration
   - Environment variable management
   - Logging configuration

### Phase 2: Import System (Status: PENDING)
4. **Base Import Infrastructure**
   - BaseImporter class with database connection and batch operations
   - Error handling and logging
   - Dataset creation and management

5. **Specialized Importers**
   - PharmacyImporter for CSV pharmacy data
   - StateImporter for JSON search results with screenshot handling
   - ValidatedImporter for validation override CSV data

### Phase 3: Scoring Engine (Status: PENDING)  
6. **Address Scoring Plugin**
   - Address normalization with abbreviation handling
   - Fuzzy string matching using SequenceMatcher
   - Component scoring (street, city/state/zip, overall)

7. **Lazy Scoring Engine**
   - Find missing scores functionality
   - Batch scoring with database upserts
   - Error handling and progress tracking

### Phase 4: User Interface (Status: PENDING)
8. **Streamlit Application**
   - Authentication system with app_users table
   - Dataset selection and tag management
   - Results matrix display with filtering
   - Detail view with all search results
   - Override creation/editing interface
   - Screenshot display integration

### Phase 5: Testing & Integration (Status: PENDING)
9. **Testing Setup**
   - Create sample data generation scripts
   - Test import workflows
   - Test scoring calculations
   - Test UI functionality

10. **Documentation & Deployment**
    - Usage instructions
    - Sample data formats
    - Database setup scripts

## Current Implementation Focus
**Currently working on:** Implementing remaining importers and scoring engine

### Completed ✅
- Project structure and dependencies
- Database schema with tables, indexes, and functions
- Configuration system with environment variables
- Setup script for database initialization
- BaseImporter class with batch operations and error handling  
- PharmacyImporter for CSV pharmacy data
- StateImporter for JSON search results with screenshot handling

### In Progress 🚧
- ValidatedImporter for validation override CSV data
- Address scoring plugin with fuzzy matching
- Lazy scoring engine
- Streamlit UI application

### Remaining Tasks 📋
- Complete all importer classes
- Implement scoring system
- Build Streamlit UI
- Create sample data and test end-to-end workflow

## Dependencies Required
- Python 3.8+
- PostgreSQL 13+ with trigram extension
- Python packages:
  - psycopg2-binary (database)
  - pandas (data processing)
  - streamlit (UI)
  - python-slugify (URL-safe names)
  - python-dotenv (environment variables)

## Key Design Decisions
- **Versioned Datasets**: No global "active" state, everything tagged
- **Natural Key Relationships**: Use pharmacy names/license numbers vs internal IDs
- **Lazy Scoring**: Only compute scores when needed for specific dataset pairs
- **Snapshot Validations**: Capture full search result state during validation
- **Flexible Authentication**: GitHub username or email-based allowlist

## Next Steps
1. Set up project structure and dependencies
2. Create PostgreSQL schema
3. Build import system foundation
4. Implement scoring engine
5. Build Streamlit UI
6. Test with sample data

## Notes
- The existing .mcp.json shows database connections are already configured
- Screenshots stored as metadata with organized paths
- UI supports both local and Supabase storage modes
- Complex SQL function for matrix view handles all data relationships