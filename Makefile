# PharmChecker Makefile
# Convenient commands for development and testing

# Supabase configuration

.PHONY: help clean import_test_states import_test_states2 clean_all setup status migrate backend_info

# Default target
help:
	@echo "PharmChecker Development Commands"
	@echo "================================="
	@echo ""
	@echo "Backend Configuration:"
	@echo "  Using Supabase cloud database"
	@echo "  backend_info       - Show Supabase configuration"
	@echo ""
	@echo "Database Management:"
	@echo "  clean              - Remove all records from datasets, search_results, pharmacies, validated tables"
	@echo "  clean_all          - Full database reset and setup"
	@echo "  migrate            - Run database schema migrations"
	@echo "  migrate_merge      - Migrate to merged search_results table"
	@echo "  reset_merge        - Reset schema for merged table (DESTRUCTIVE)"
	@echo ""
	@echo "Data Import:"
	@echo "  import_test_states  - Import data/states_baseline"
	@echo "  import_test_states2 - Import data/states_baseline2" 
	@echo "  import_pharmacies   - Import converted pharmacy data"
	@echo ""
	@echo "Unit Test Data:"
	@echo "  import_sample_data           - Import all sample datasets for testing"
	@echo "  import_pharmacies_sample_data - Import pharmacies_sample_data"
	@echo "  import_states_sample_data    - Import states_sample_data"
	@echo "  import_validated_sample_data - Import validated_sample_data"
	@echo ""
	@echo "Development:"
	@echo "  setup              - Initialize database and dependencies"
	@echo "  status             - Show database status and counts"
	@echo "  test               - Run import tests"
	@echo ""
	@echo "Examples:"
	@echo "  make clean import_test_states         # Clean and import baseline"
	@echo "  make status                           # Check current data"
	@echo "  make import_sample_data              # Import all test datasets"

# Clean all data tables (preserves schema)
clean:
	@echo "🧹 Cleaning all data tables (datasets, search_results, pharmacies, validated)..."
	@python3 clean_data.py

# Show backend configuration
backend_info:
	@echo "📡 Supabase Configuration"
	@echo "========================"
	@echo ""
	@echo "🌐 Supabase Configuration:"
	@. ./.env 2>/dev/null && echo "  SUPABASE_URL: $${SUPABASE_URL:-Not set}" || echo "  SUPABASE_URL: Not set"
	@. ./.env 2>/dev/null && [ -n "$${SUPABASE_SERVICE_KEY}" ] && echo "  SUPABASE_SERVICE_KEY: Set (hidden)" || echo "  SUPABASE_SERVICE_KEY: Not set"


# Import states_baseline data  
import_test_states:
	@echo "📥 Importing states_baseline..."
	@python3 imports/resilient_importer.py \
		--states-dir data/states_baseline \
		--tag states_baseline \
		--created-by makefile_user \
		--description "states_baseline test data" \
		--max-workers 8 \
		--batch-size 10

# Import states_baseline data
import_scrape_states:
	@echo "📥 Importing scrape data..."
	@python3 imports/resilient_importer.py \
		--states-dir /home/eric/ai/pharmchecker/data/2025-08-04 \
		--tag Aug-04-scrape \
		--created-by makefile_user \
		--description "small scrape FL MI NY PA" \
		--max-workers 16 \
		--max-uploads 10 \
		--debug-log \
		--batch-size 25

# Import states_baseline2 data  
import_test_states2:
	@echo "📥 Importing states_baseline2 ..."
	@python3 -c "\
import os; \
from pathlib import Path; \
from dotenv import load_dotenv; \
load_dotenv(); \
from imports.states import StateImporter; \
importer = StateImporter(); \
success = importer.import_directory('data/states_baseline2', created_by='makefile_user', description='states_baseline2 test data with Empower'); \
print('✅ Import successful!' if success else '❌ Import failed!')"

# Import pharmacy data
import_pharmacies:
	@echo "📥 Importing pharmacy data ..."
	@python3 -m imports.api_importer pharmacies \
		data/pharmacies_new.csv \
		pharmacies_baseline \
		--created-by makefile_user \
		--description "Converted pharmacy test data" \

import_pharmacy_rows:
	@echo "📥 Importing pharmacy data ..."
	@python3 -m imports.api_importer pharmacies \
		temp/pharmacies.csv \
		pharmacy_rows \
		--created-by makefile_user \
		--description "Converted pharmacy test data" \

# Import test datasets with correct naming for unit tests
import_sample_data: import_pharmacies_sample_data import_states_sample_data import_validated_sample_data

# Import pharmacies sample data for testing
import_pharmacies_sample_data:
	@echo "📥 Importing pharmacies_sample_data ..."
	@python3 -m imports.api_importer pharmacies \
		data/pharmacies_new.csv \
		pharmacies_sample_data \
		--created-by makefile_user \
		--description "Pharmacy sample data for unit testing" \

# Import states sample data for testing
import_states_sample_data:
	@echo "📥 Importing states_sample_data ..."
	@python3 -m imports.api_importer states \
		data/states_baseline \
		states_sample_data \
		--created-by makefile_user \
		--description "States sample data for unit testing" \

# Import validated sample data for testing  
import_validated_sample_data:
	@echo "📥 Importing validated_sample_data ..."
	@python3 -m imports.api_importer validated \
		data/validated_sample_data.csv \
		validated_sample_data \
		--created-by makefile_user \
		--description "Validated sample data for unit testing" \
# Database status
status:
	@echo "📊 Database Status (Supabase)"
	@echo "================================"
	@python3 show_status.py

# Full database setup
setup:
	@echo "🏗️ Setting up PharmChecker database..."
	@python3 setup.py

# Clean everything and rebuild
clean_all:
	@echo "🗑️ Full database reset..."
	@python3 clean_data.py
	@make setup

# Run basic import tests
test:
	@echo "🧪 Running import tests..."
	@make clean
	@make import_pharmacies  
	@make import_test_states
	@make status
	@echo "✅ Test complete!"

# Quick clean and reload workflow
reload: clean import_test_states

# Run database migrations
migrate:
	@echo "🔄 Running database migrations..."
	@python3 migrate_state_to_text.py

# Migrate to merged table structure  
migrate_merge:
	@echo "🔄 Migrating to merged search_results table..."
	@python3 migrate_merge_tables.py

# Reset schema for merged table (DESTRUCTIVE)
reset_merge:
	@echo "🔄 Resetting schema for merged table structure..."
	@python3 reset_for_merge.py

# Development workflow - clean, import both datasets, show status
dev: backend_info clean import_pharmacies import_test_states import_test_states2 status