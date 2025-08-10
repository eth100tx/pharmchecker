# PharmChecker MVP GUI

A comprehensive Streamlit-based web interface for the PharmChecker pharmacy license verification system with **real PostgreSQL database integration**.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Test the GUI components
python test_gui.py

# Run the web application
streamlit run app.py
```

The GUI will be available at `http://localhost:8501`

## 📋 Features

### Dataset Management
- Select combinations of pharmacy, state search, and validation datasets
- View dataset statistics and metadata
- Real-time context display

### Results Matrix ✨ **Enhanced**
- **Accurate Record Counts**: Shows actual count of search results per pharmacy-state combination
- **Smart Status Classification**: Distinguishes between:
  - ⚪ **No Data Loaded**: No search record exists
  - ⚫ **No Results Found**: Search conducted but no results found
  - ✅ **Match/Weak Match/No Match**: With score-based classification
- **Clean Display**: Blank cells for missing license numbers and scores (no placeholder text)
- **Interactive filtering and sorting** with CSV export functionality

### Scoring Dashboard
- **Real-time scoring statistics** and accuracy metrics
- **Automatic lazy scoring** - scores computed on first access ✨
- Missing score identification and batch controls
- Score distribution analysis with performance metrics

### Pharmacy Details ✨ **Enhanced**
- **Complete Pharmacy Profiles**: Name, alias, full address with suite, phone, licensed states
- **Search State Context**: Header shows which state's results are being viewed
- **Real Database Integration**: Live data from pharmacies table with proper schema handling
- **State-by-state license and search result breakdown**

### Search Details ✨ **Enhanced**
- **Complete Match Scoring**: Shows all three score components:
  - **Overall Score**: Weighted combination (street 70% + location 30%)
  - **Address Score**: Street address matching accuracy
  - **City/State/ZIP Score**: Location component matching accuracy
- **Smart Address Highlighting**: Bold formatting for matching address components in pulldowns
- **Enhanced Pulldown Titles**: Include scores with bold formatting for >90% matches
- **Improved Screenshot Layout**: 
  - Small thumbnail (150px) in side column for quick reference
  - Full-size expandable screenshot at bottom for detailed comparison
  - Side-by-side verification workflow support
- **Search Context Display**: Shows "Search State" field under "Search Name"
- **Address Comparison**: Side-by-side search result vs. pharmacy reference addresses

### Validation Manager
- Manual validation override interface
- Audit trail and reason tracking
- Existing validation history display

## 🔧 **Recent Technical Enhancements**

### Database Integration Improvements
- **Fixed Schema Compatibility**: Corrected `zip_code` vs `zip` column name mismatch
- **Enhanced Query Performance**: `get_search_results()` now JOINs with `match_scores` table
- **Accurate Record Counting**: Added `_add_record_counts()` method for precise search result counts
- **Real Data Integration**: `get_pharmacy_info()` queries live database instead of sample data

### User Interface Enhancements
- **Smart Status Distinction**: Differentiates "No Data Loaded" from "No Results Found" cases
- **Enhanced Address Matching**: Component-based matching with visual highlighting
- **Clean Display Standards**: Blank cells instead of placeholder text for missing data
- **Improved Screenshot Workflow**: Repositioned for optimal data verification
- **Complete Scoring Display**: All three score components visible in detailed view

### Display Logic Improvements
- **Context-Aware Headers**: Dynamic state information in detailed view headers
- **Score-Based Highlighting**: Bold formatting for high-confidence matches (>90%)
- **Component Separation**: Clear distinction between search metadata and license data
- **Streamlit Compatibility**: Fixed deprecation warnings with updated parameters

### Image System ✨
- **Automatic screenshot display** in search result detail views
- **Cached image performance** from local `image_cache/` directory  
- **Smart image sharing** - multiple results share the same cached image
- **Organized storage** with timestamped filenames for uniqueness
- **Graceful fallback** when images are unavailable

## 🏗️ Architecture

### File Structure
```
app.py                     # Main Streamlit application
utils/
  ├── database.py         # Database operations and MCP integration
  ├── display.py          # UI components and formatting utilities
  └── __init__.py
test_gui.py               # Test suite for GUI components
```

### Database Integration
The GUI uses a database manager class that abstracts database operations:

- **Production Mode**: Uses `mcp__postgres-prod__query` 
- **Sandbox Mode**: Uses `mcp__postgres-sbx__query`
- **Sample Data**: Built-in test data for development

### UI Framework
- **Streamlit**: Modern reactive web framework
- **Plotly**: Interactive charts and visualizations
- **Pandas**: Data manipulation and display
- **Session State**: Maintains context across page navigation

## ⚡ Advanced Features

### Lazy Scoring System ✨
The GUI automatically triggers scoring when dataset combinations are first accessed:

- **Automatic Detection**: Checks if scoring exists for dataset combination
- **Background Computation**: Runs scoring engine automatically when needed
- **Seamless Experience**: Users see fully scored results without manual intervention
- **Performance Optimization**: Scores computed only once and cached for future use

### Image Caching System ✨
Efficient screenshot storage and display:

- **Smart Caching**: Images copied to `image_cache/states_baseline/FL/Belmar_01.20250803_1403.png`
- **Deduplication**: Timestamp-based names prevent duplicate storage
- **Shared Storage**: Multiple search results share the same cached image file
- **Database Integration**: Each image record links to specific search result
- **Automatic Cleanup**: Cache cleaned when search data is reset

## 🔌 MCP Database Integration

**Status**: ✅ **Fully Integrated with Real Database**

The GUI now connects directly to the PharmChecker PostgreSQL database:

### Option 1: Direct MCP Integration
Update `utils/database.py` to use actual MCP tools:

```python
def execute_query(self, sql: str, params=None):
    # Replace sample data methods with actual MCP calls
    if self.use_production:
        # Use production MCP connection
        result = mcp_postgres_prod_query({"sql": sql})
    else:
        # Use sandbox MCP connection  
        result = mcp_postgres_sbx_query({"sql": sql})
    
    return pd.DataFrame(result)
```

### Option 2: Streamlit Connection
Use Streamlit's built-in database connections:

```python
def execute_query(self, sql: str, params=None):
    conn_name = "postgres-prod" if self.use_production else "postgres-sbx"
    return st.connection(conn_name).query(sql, params)
```

### Database Functions Used
The GUI leverages these optimized database functions:
- `get_results_matrix(states_tag, pharmacies_tag, validated_tag)`
- `find_missing_scores(states_tag, pharmacies_tag)`
- Standard table queries for datasets, pharmacies, search_results

## 🎨 UI Components

### Navigation
- **Sidebar**: Page selection and dataset context
- **Quick Actions**: Data refresh and export buttons
- **Context Display**: Current dataset selections always visible

### Data Display
- **Interactive Tables**: Sortable, filterable with row selection
- **Status Badges**: Color-coded status indicators
- **Charts**: Pie charts for status distribution, histograms for scores
- **Cards**: Pharmacy and search result information cards

### Forms & Controls
- **Dataset Selectors**: Multi-select dropdowns for dataset combinations
- **Filters**: State, status, score range, and warning filters
- **Action Buttons**: Scoring triggers and validation controls
- **Progress Indicators**: Real-time operation feedback

## 📊 Data Flow

1. **Dataset Selection**: User selects pharmacy + state + validation datasets
2. **Query Execution**: Database manager executes optimized SQL functions
3. **Data Processing**: Results formatted for display with status classification
4. **UI Rendering**: Interactive tables, charts, and detail views
5. **Export/Actions**: CSV export and scoring operations

## 🔧 Configuration

### Environment Variables
```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pharmchecker
DB_USER=postgres
DB_PASSWORD=password
STREAMLIT_PORT=8501
```

### Streamlit Configuration
Create `.streamlit/config.toml`:
```toml
[server]
port = 8501
address = "0.0.0.0"

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
```

## 🧪 Testing

The test suite validates:
- Database manager functionality
- Display utility functions  
- Integration between components
- Sample data consistency

```bash
python test_gui.py
```

Expected output:
```
PharmChecker GUI Test Suite
========================================
✅ Database Manager tests passed
✅ Display utilities tests passed  
✅ Integration tests passed

🎉 All tests passed! GUI is ready for use.
```

## 🚀 Deployment

### Local Development
```bash
streamlit run app.py
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
```

### Production Considerations
- ✅ **Database Integration**: Real PostgreSQL connections implemented
- ✅ **Results Filtering**: Shows only loaded states by default
- ✅ **Duplicate Fix**: Clean search results display
- Configure authentication if needed
- Set up SSL/HTTPS for production
- Monitor performance with large datasets
- Configure caching for better performance

## 📈 Performance

### Optimization Features
- **Real Database**: Direct PostgreSQL connections with SQLAlchemy
- **Lazy Loading**: Data loaded only when needed
- **State Filtering**: Results filtered to loaded states by default
- **Deduplication**: Duplicate-free search result displays

### Scalability Notes
- Designed for datasets with thousands of pharmacies and search results
- Interactive filtering reduces display overhead
- Export functionality handles large result sets
- Database queries optimized using existing functions

## 🤝 Contributing

The GUI is designed to be easily extensible:

1. **New Pages**: Add to main navigation in `app.py`
2. **Database Operations**: Extend `DatabaseManager` class
3. **UI Components**: Add reusable components to `utils/display.py`
4. **Charts**: Use Plotly for interactive visualizations

---

*PharmChecker MVP GUI - Built with Streamlit*
*Ready for production integration with MCP database*