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

### Results Matrix
- Comprehensive results view with filtering and sorting
- Status classification (match/weak match/no match/no data)
- Interactive charts and visualizations
- CSV export functionality

### Scoring Dashboard
- Real-time scoring statistics and accuracy metrics
- Missing score identification
- Batch scoring trigger controls
- Score distribution analysis

### Pharmacy Details
- Detailed pharmacy profiles with contact information
- State-by-state license and search result breakdown
- Address and license verification status

### Search Details
- In-depth search result analysis
- Address scoring comparisons
- Screenshot integration for validation

### Validation Manager
- Manual validation override interface
- Audit trail and reason tracking
- Existing validation history display

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

## 🔌 MCP Database Integration

Currently uses sample data for development. To connect to real PharmChecker database:

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