# PharmChecker Endpoint Development Plan

## Executive Summary

This plan outlines the development of a REST API layer for PharmChecker while maintaining full backward compatibility with the existing Streamlit application. The new architecture will introduce a clean separation between frontend and backend, enabling future scalability and integration capabilities.

## Current State Analysis

### Existing Architecture
- **Database**: PostgreSQL with well-designed schema using merged `search_results` table
- **Frontend**: Streamlit app (`app.py`) with direct database connections
- **Data Import**: Modular import system (`imports/` directory) with dataset versioning
- **Core Function**: `get_all_results_with_context()` SQL function providing comprehensive data
- **Authentication**: Basic auth system with session management
- **Configuration**: Environment-based config with Supabase integration capabilities

### Key Strengths to Preserve
1. **Dataset Versioning**: Natural key-based system with tags (e.g., "jan_2024")
2. **Lazy Scoring**: On-demand computation with permanent caching
3. **Comprehensive Results**: Single query returns all context for client-side processing
4. **Merged Search Results**: Eliminates timing conflicts with unified table
5. **Natural Key Linking**: No hardcoded IDs, uses pharmacy names + license numbers

## Target Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  Streamlit Frontend │    │   FastAPI Service   │    │  Supabase Postgres  │
│  (Enhanced)         │◄──►│   (BFF Layer)       │◄──►│  (Existing Schema)  │
│                     │    │                     │    │                     │
│ /api_poc/           │    │ /api_poc/          │    │ - Tables            │
│ └── gui/            │    │ └── api/           │    │ - Functions         │
│     ├── app.py      │    │     ├── main.py    │    │ - RLS Policies      │
│     ├── client.py   │    │     ├── models/    │    │ - Constraints       │
│     └── pages/      │    │     ├── routes/    │    │                     │
└─────────────────────┘    │     └── deps/      │    └─────────────────────┘
                           └─────────────────────┘
```

## Project Structure

```
pharmchecker/
├── api_poc/                    # New development directory
│   ├── api/                    # FastAPI backend
│   │   ├── main.py            # FastAPI application entry point
│   │   ├── config.py          # API configuration
│   │   ├── models/            # Pydantic models
│   │   │   ├── __init__.py
│   │   │   ├── dataset.py     # Dataset models
│   │   │   ├── result.py      # Results models  
│   │   │   ├── validation.py  # Validation models
│   │   │   └── common.py      # Common/shared models
│   │   ├── routes/            # API endpoint handlers
│   │   │   ├── __init__.py
│   │   │   ├── datasets.py    # Dataset CRUD endpoints
│   │   │   ├── results.py     # Results/matrix endpoints
│   │   │   ├── validations.py # Validation endpoints
│   │   │   ├── scores.py      # Scoring endpoints
│   │   │   └── health.py      # Health/admin endpoints
│   │   ├── deps/              # Dependencies
│   │   │   ├── __init__.py
│   │   │   ├── auth.py        # Authentication dependencies
│   │   │   ├── database.py    # Database connection
│   │   │   └── pagination.py  # Pagination helpers
│   │   ├── services/          # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── dataset.py     # Dataset service
│   │   │   ├── result.py      # Results aggregation
│   │   │   ├── validation.py  # Validation logic
│   │   │   └── scoring.py     # Scoring orchestration
│   │   └── requirements.txt   # API dependencies
│   │
│   ├── gui/                   # New Streamlit frontend
│   │   ├── app.py            # Main Streamlit app (API-based)
│   │   ├── client.py         # API client wrapper
│   │   ├── config.py         # GUI configuration
│   │   ├── components/       # UI components
│   │   │   ├── __init__.py
│   │   │   ├── dataset_selector.py
│   │   │   ├── results_table.py
│   │   │   └── validation_form.py
│   │   ├── pages/            # Streamlit pages
│   │   │   ├── datasets.py   # Dataset management
│   │   │   └── results.py    # Results matrix
│   │   └── requirements.txt  # GUI dependencies
│   │
│   ├── docker-compose.yml    # Local development setup
│   ├── .env.example         # Environment template
│   └── README.md            # POC documentation
│
├── [existing files remain unchanged]
```

## API Design (v1)

### Authentication & Security
- **JWT Authentication**: Supabase Auth tokens
- **Row Level Security**: Postgres RLS policies for multi-tenant data
- **CORS**: Configured for local development and production domains
- **Rate Limiting**: Basic protection for production deployment

### Core Endpoints

#### Health & Admin
```
GET  /v1/health              # Service health check
GET  /v1/version             # API version info
```

#### Datasets
```
GET  /v1/datasets            # List all datasets (with filtering)
GET  /v1/datasets/{kind}/{tag}  # Get specific dataset details
POST /v1/datasets           # Create new dataset (import trigger)
```

#### Results (Core Functionality)
```
GET  /v1/results             # Get comprehensive results (replaces current GUI query)
GET  /v1/results/matrix      # Get aggregated matrix view
GET  /v1/results/{pharmacy_name}/{state}  # Get detail view for specific pharmacy-state
```

#### Validations
```
GET  /v1/validations         # List validations with filtering
POST /v1/validations        # Create/update validation
DELETE /v1/validations/{id} # Remove validation
```

#### Scoring
```
GET  /v1/scores/missing      # List missing scores
POST /v1/scores/compute     # Trigger scoring job (async)
GET  /v1/jobs/{job_id}      # Check job status
```

### Request/Response Patterns

#### Pagination
- Standard `limit` and `offset` parameters
- `X-Total-Count` header for total records
- Default limit: 100, max limit: 1000

#### Filtering
- Query parameters for common filters (state, score_range, status)
- Support for multiple values: `?state=FL,TX&status=match,weak`

#### Caching & ETags
- ETag generation based on dataset tags + last modification
- Cache-friendly responses with appropriate headers

### Error Handling
```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid override_type value",
    "details": {
      "field": "override_type",
      "allowed_values": ["present", "empty"]
    }
  }
}
```

## Implementation Plan

### Phase 1: API Foundation (Week 1)
1. **Setup Project Structure**
   - Create `/api_poc/` directory structure
   - Setup FastAPI application skeleton
   - Configure development environment

2. **Database Integration**
   - Reuse existing database connection patterns
   - Implement connection pooling for API
   - Test against existing schema and functions

3. **Core Models**
   - Define Pydantic models for all entities
   - Implement request/response serialization
   - Add validation rules

4. **Basic Endpoints**
   - Implement health endpoints
   - Create dataset listing endpoints
   - Test with existing data

### Phase 2: Core API Features (Week 2)
1. **Results Endpoints**
   - Implement `/v1/results` using existing `get_all_results_with_context()`
   - Add pagination and filtering
   - Implement matrix aggregation endpoint

2. **Authentication Integration**
   - Integrate Supabase Auth JWT verification
   - Implement user context resolution
   - Add RLS policy support

3. **Error Handling & Validation**
   - Implement comprehensive error responses
   - Add input validation for all endpoints
   - Create error middleware

### Phase 3: Advanced Features (Week 3)
1. **Validation Endpoints**
   - Implement validation CRUD operations
   - Add validation consistency checking
   - Integrate with existing validation system

2. **Scoring Integration**
   - Implement async scoring job triggers
   - Add job status tracking
   - Integrate with existing scoring engine

3. **Performance Optimization**
   - Add response caching with ETags
   - Implement connection pooling
   - Add query optimization

### Phase 4: GUI Development (Week 4)
1. **API Client Development**
   - Create Python client wrapper for API
   - Implement retry logic and error handling
   - Add response caching

2. **Streamlit App Conversion**
   - Create new Streamlit app in `/api_poc/gui/`
   - Convert existing pages to use API client
   - Maintain feature parity with original app

3. **Testing & Validation**
   - Ensure full feature compatibility
   - Test performance vs. direct DB access
   - Validate data consistency

## Development Guidelines

### Backward Compatibility
- **Zero Breaking Changes**: Existing app continues to work unchanged
- **Parallel Development**: New API developed alongside existing system
- **Gradual Migration**: Optional transition path for users

### Data Consistency
- **Single Source of Truth**: Both old and new systems use same database
- **Shared Functions**: Reuse existing SQL functions (`get_all_results_with_context`)
- **Consistent Validation**: Use same business rules and validation logic

### Performance Considerations
- **Efficient Queries**: Leverage existing optimized SQL functions
- **Connection Pooling**: Proper database connection management
- **Response Caching**: Cache responses based on dataset tags
- **Pagination**: Limit data transfer for large result sets

### Security
- **Authentication**: Integrate with existing auth system
- **Authorization**: Implement RLS for multi-tenant security
- **Input Validation**: Validate all inputs server-side
- **SQL Injection Prevention**: Use parameterized queries

## Testing Strategy

### Unit Tests
- API endpoint testing with FastAPI test client
- Model validation testing
- Service layer unit tests

### Integration Tests
- Database integration tests
- Authentication flow tests  
- End-to-end API workflows

### Compatibility Tests
- Compare API responses with direct DB queries
- Validate data consistency between old/new systems
- Performance comparison testing

### Load Testing
- API performance under load
- Database connection pool testing
- Memory usage optimization

## Deployment Considerations

### Local Development
- Docker Compose setup for full stack
- Environment variable configuration
- Hot reload for development

### Production Readiness
- Proper logging and monitoring
- Health checks and metrics
- Graceful error handling
- Rate limiting and security headers

### Migration Strategy
- Parallel deployment option
- Feature flag support for gradual rollout
- Rollback plan if issues arise

## Success Criteria

1. **API Functionality**: All core operations available via REST endpoints
2. **Performance**: API response times comparable to direct DB access
3. **Compatibility**: New GUI provides identical functionality to existing app
4. **Security**: Proper authentication and authorization implemented
5. **Maintainability**: Clear separation of concerns and clean code structure
6. **Documentation**: Complete API documentation and integration guides

## Risk Mitigation

### Technical Risks
- **Performance Impact**: Mitigate with caching and connection pooling
- **Data Consistency**: Use shared database functions and validation rules
- **Complexity Growth**: Keep API focused and well-documented

### Operational Risks
- **Breaking Changes**: Develop in isolation, maintain backward compatibility
- **User Disruption**: Provide parallel access during transition
- **Data Loss**: Use existing backup and recovery procedures

## Future Enhancements

### Post-POC Opportunities
1. **Multi-tenant Support**: Full RLS implementation for enterprise customers
2. **API Versioning**: v2 endpoints for enhanced features
3. **Real-time Updates**: WebSocket support for live data updates
4. **Advanced Analytics**: Enhanced reporting and visualization APIs
5. **Integration APIs**: Webhooks and third-party integration support

This plan provides a solid foundation for building a modern, scalable API while preserving all existing functionality and ensuring a smooth transition path for users.