# API Implementation Prompt

Use this prompt to start implementing the PostgREST API + GUI system:

---

## Implementation Request

I want to implement the PostgREST API + simple GUI for PharmChecker as outlined in the development plans. Please follow these requirements:

### What to Build
1. **PostgREST setup** with Docker Compose connecting to existing PostgreSQL database
2. **Simple Streamlit GUI** for basic database operations and API testing
3. **API client wrapper** for PostgREST endpoints
4. **Directory structure** in `/api_poc/` to keep separate from existing code

### Key Requirements
- **No changes to existing code** - everything goes in new `/api_poc/` directory
- **Use existing database** - connect to current PostgreSQL with existing schema
- **Preserve existing functions** - ensure `get_all_results_with_context()` works via RPC
- **Local development focus** - Docker setup for PostgREST on localhost:3000
- **Simple GUI on localhost:8501** - basic operations, not full feature parity yet

### Database Connection
- Use credentials from existing `config.py` and `.env` setup
- Database already has working schema with tables: datasets, pharmacies, search_results, validated_overrides, match_scores, images
- Key function to expose: `get_all_results_with_context(p_states_tag, p_pharmacies_tag, p_validated_tag)`

### Directory Structure to Create
```
api_poc/
├── postgrest/
│   ├── postgrest.conf
│   ├── docker-compose.yml
│   └── README.md
├── gui/
│   ├── app.py
│   ├── client.py
│   ├── components/
│   └── requirements.txt
├── .env.example
└── README.md
```

### GUI Features Needed
1. **Dataset Explorer** - list and view dataset details
2. **Table Export** - export any table to CSV with filtering
3. **API Testing** - test raw PostgREST endpoints interactively
4. **Comprehensive Results** - call the main function and display results

### Success Criteria
- PostgREST API accessible at http://localhost:3000
- All major tables available via REST endpoints
- `get_all_results_with_context()` function callable via `/rpc/get_all_results_with_context`
- Simple GUI working at http://localhost:8501
- Can export data and test API endpoints through GUI
- No impact on existing Streamlit app

### References
Follow the detailed plans in:
- `postgrest_dev_plan.md` - overall architecture and approach
- `postgrest_quickstart.md` - step-by-step implementation guide
- `endpoint_api_spec.md` - API endpoint specifications (adapt for PostgREST)

### Implementation Approach
1. Start with PostgREST configuration and Docker setup
2. Test basic endpoints work with existing database
3. Build simple API client wrapper
4. Create basic Streamlit GUI with core features
5. Test end-to-end functionality

Please implement this step by step, testing each component as you build it. Start with the PostgREST setup and database connection, then move to the GUI once the API is working.

---

**Use this prompt to begin implementation of the PostgREST API system.**