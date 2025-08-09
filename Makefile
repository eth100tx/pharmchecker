# PharmChecker Makefile
# Convenient commands for development and testing

.PHONY: help clean_states import_test_states import_test_states2 clean_all setup status migrate

# Default target
help:
	@echo "PharmChecker Development Commands"
	@echo "================================="
	@echo ""
	@echo "Database Management:"
	@echo "  clean_states        - Remove all search data (preserves pharmacies)"
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
	@echo "Development:"
	@echo "  setup              - Initialize database and dependencies"
	@echo "  status             - Show database status and counts"
	@echo "  test               - Run import tests"
	@echo ""
	@echo "Examples:"
	@echo "  make clean_states import_test_states  # Clean and import baseline"
	@echo "  make status                           # Check current data"

# Clean search data only (preserve pharmacies)
clean_states:
	@echo "🧹 Cleaning search database..."
	@python3 clean_search_db.py

# Import states_baseline data
import_test_states:
	@echo "📥 Importing states_baseline..."
	@python3 -c "\
import os; \
from pathlib import Path; \
from dotenv import load_dotenv; \
load_dotenv(); \
from imports.states import StateImporter; \
importer = StateImporter(); \
success = importer.import_directory('data/states_baseline', tag='states_baseline', created_by='makefile_user', description='states_baseline test data'); \
print('✅ Import successful!' if success else '❌ Import failed!')"

# Import states_baseline2 data  
import_test_states2:
	@echo "📥 Importing states_baseline2..."
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
	@echo "📥 Importing pharmacy data..."
	@python3 -c "\
import os; \
from pathlib import Path; \
from dotenv import load_dotenv; \
load_dotenv(); \
from imports.pharmacies import PharmacyImporter; \
importer = PharmacyImporter(); \
success = importer.import_csv('data/pharmacies_new.csv', tag='test_pharmacies', created_by='makefile_user', description='Converted pharmacy test data'); \
print('✅ Import successful!' if success else '❌ Import failed!')"

# Database status
status:
	@echo "📊 Database Status"
	@echo "=================="
	@python3 show_status.py

# Full database setup
setup:
	@echo "🏗️ Setting up PharmChecker database..."
	@python3 setup.py

# Clean everything and rebuild
clean_all:
	@echo "🗑️ Full database reset..."
	@python3 -c "\
import os; \
from dotenv import load_dotenv; \
load_dotenv(); \
import psycopg2; \
conn = psycopg2.connect(host=os.getenv('DB_HOST', 'localhost'), port=int(os.getenv('DB_PORT', 5432)), database=os.getenv('DB_NAME', 'pharmchecker'), user=os.getenv('DB_USER', 'postgres'), password=os.getenv('DB_PASSWORD')); \
cur = conn.cursor(); \
tables = ['search_results', 'searches', 'images', 'match_scores', 'validated_overrides', 'pharmacies', 'datasets', 'app_users']; \
for table in tables: \
    cur.execute(f'TRUNCATE TABLE {table} RESTART IDENTITY CASCADE'); \
    print(f'  Cleared {table}'); \
conn.commit(); \
conn.close(); \
print('✅ Database cleared')"
	@make setup

# Run basic import tests
test:
	@echo "🧪 Running import tests..."
	@make clean_states
	@make import_pharmacies  
	@make import_test_states
	@make status
	@echo "✅ Test complete!"

# Quick clean and reload workflow
reload: clean_states import_test_states

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
dev: clean_states import_pharmacies import_test_states import_test_states2 status