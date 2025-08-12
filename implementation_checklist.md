# PharmChecker API Implementation Checklist

## Prerequisites
- [ ] Review existing codebase and understand data flow
- [ ] Confirm Supabase setup and credentials
- [ ] Test existing database connections and functions
- [ ] Understand current import and scoring patterns

## Phase 1: Project Setup (Day 1-2)

### Directory Structure
- [ ] Create `/api_poc/` directory
- [ ] Setup `/api_poc/api/` for FastAPI backend
- [ ] Setup `/api_poc/gui/` for new Streamlit frontend
- [ ] Create proper Python package structure with `__init__.py` files

### Environment Setup
- [ ] Create requirements.txt for API (FastAPI, uvicorn, pydantic, sqlalchemy)
- [ ] Create requirements.txt for GUI (streamlit, requests, pandas)
- [ ] Setup .env.example with all required environment variables
- [ ] Create docker-compose.yml for local development

### FastAPI Foundation
- [ ] Create `api/main.py` with basic FastAPI app
- [ ] Setup CORS middleware for local development
- [ ] Add health endpoint (`/v1/health`)
- [ ] Test basic server startup

### Database Connection
- [ ] Create `api/deps/database.py` with connection pooling
- [ ] Reuse existing config.py patterns for DB credentials
- [ ] Test connection to existing PostgreSQL database
- [ ] Verify access to existing tables and functions

## Phase 2: Core API Implementation (Day 3-7)

### Data Models
- [ ] Create `api/models/common.py` with base models and enums
- [ ] Create `api/models/dataset.py` for dataset-related models
- [ ] Create `api/models/result.py` for results and matrix models
- [ ] Create `api/models/validation.py` for validation models
- [ ] Add proper validation rules and field descriptions

### Authentication
- [ ] Create `api/deps/auth.py` for Supabase JWT verification
- [ ] Implement user context extraction from JWT
- [ ] Add authentication dependency for protected endpoints
- [ ] Test auth flow with existing Supabase setup

### Dataset Endpoints
- [ ] Implement `GET /v1/datasets` with filtering and pagination
- [ ] Implement `GET /v1/datasets/{kind}/{tag}` for dataset details
- [ ] Add proper error handling and validation
- [ ] Test with existing dataset data

### Results Endpoints (Core Feature)
- [ ] Implement `GET /v1/results` using `get_all_results_with_context()`
- [ ] Add comprehensive filtering (state, score, status, etc.)
- [ ] Implement pagination with X-Total-Count header
- [ ] Create aggregation service for matrix view
- [ ] Implement `GET /v1/results/matrix` endpoint
- [ ] Add `GET /v1/results/{pharmacy_name}/{state}` detail endpoint
- [ ] Test with existing comprehensive results data

### Error Handling
- [ ] Create custom exception classes
- [ ] Implement global exception handler
- [ ] Add proper HTTP status codes and error responses
- [ ] Add request validation middleware

## Phase 3: Advanced Features (Day 8-12)

### Validation System
- [ ] Implement `GET /v1/validations` with filtering
- [ ] Implement `POST /v1/validations` for creating/updating validations
- [ ] Implement `DELETE /v1/validations/{id}` for removal
- [ ] Add validation consistency checking
- [ ] Test integration with existing validation data

### Scoring System
- [ ] Implement `GET /v1/scores/missing` to find unscored pairs
- [ ] Design async job system (simple in-memory queue for POC)
- [ ] Implement `POST /v1/scores/compute` for triggering scoring
- [ ] Implement `GET /v1/jobs/{job_id}` for job status
- [ ] Integrate with existing scoring engine (`scoring_plugin.py`)

### Performance Optimization
- [ ] Add response caching with ETags based on dataset tags
- [ ] Implement connection pooling optimization
- [ ] Add query performance monitoring
- [ ] Test with larger datasets

### API Documentation
- [ ] Setup automatic OpenAPI documentation generation
- [ ] Add comprehensive endpoint descriptions
- [ ] Include example requests and responses
- [ ] Test documentation accuracy

## Phase 4: GUI Development (Day 13-16)

### API Client
- [ ] Create `gui/client.py` with API wrapper class
- [ ] Implement retry logic and error handling
- [ ] Add response caching for better performance
- [ ] Add authentication token management

### Streamlit App Conversion
- [ ] Create `gui/app.py` as main entry point
- [ ] Convert dataset selection functionality to use API
- [ ] Convert results matrix view to use API endpoints
- [ ] Convert validation system to use API
- [ ] Maintain exact feature parity with original app

### UI Components
- [ ] Create reusable components in `gui/components/`
- [ ] Implement dataset selector component
- [ ] Implement results table component
- [ ] Implement validation form component
- [ ] Test all UI interactions

### Integration Testing
- [ ] Test full workflow: dataset selection → results viewing → validation
- [ ] Compare performance vs. original direct DB app
- [ ] Validate data consistency between old and new systems
- [ ] Test error handling and edge cases

## Phase 5: Testing & Documentation (Day 17-20)

### Unit Tests
- [ ] Write tests for all API endpoints
- [ ] Write tests for data models and validation
- [ ] Write tests for authentication and authorization
- [ ] Write tests for business logic services

### Integration Tests
- [ ] Test API with real database data
- [ ] Test GUI with API backend
- [ ] Test authentication flow end-to-end
- [ ] Test error scenarios and edge cases

### Performance Testing
- [ ] Load test API endpoints with realistic data volumes
- [ ] Compare API performance vs. direct DB queries
- [ ] Test concurrent user scenarios
- [ ] Optimize based on results

### Documentation
- [ ] Complete API specification documentation
- [ ] Write deployment guide for local development
- [ ] Create user migration guide
- [ ] Document configuration options

## Deployment Preparation

### Local Development
- [ ] Ensure docker-compose setup works correctly
- [ ] Test environment variable configuration
- [ ] Verify hot reload for development
- [ ] Document local setup process

### Production Considerations
- [ ] Add proper logging configuration
- [ ] Implement health checks and monitoring
- [ ] Add rate limiting middleware
- [ ] Configure security headers

### Migration Strategy
- [ ] Document parallel deployment approach
- [ ] Create feature comparison checklist
- [ ] Plan rollback procedures
- [ ] Test migration with sample users

## Key Files to Create

### API Backend (`/api_poc/api/`)
```
main.py                 # FastAPI application
config.py              # Configuration management
requirements.txt       # Dependencies

models/
├── __init__.py
├── common.py          # Base models, enums
├── dataset.py         # Dataset models  
├── result.py          # Results models
└── validation.py      # Validation models

routes/
├── __init__.py
├── datasets.py        # Dataset endpoints
├── results.py         # Results endpoints
├── validations.py     # Validation endpoints
├── scores.py          # Scoring endpoints
└── health.py          # Health endpoints

deps/
├── __init__.py
├── auth.py            # Authentication
├── database.py        # DB connection
└── pagination.py      # Pagination helpers

services/
├── __init__.py
├── dataset.py         # Dataset business logic
├── result.py          # Results aggregation
├── validation.py      # Validation logic
└── scoring.py         # Scoring orchestration
```

### GUI Frontend (`/api_poc/gui/`)
```
app.py                 # Main Streamlit app
client.py              # API client wrapper
config.py              # GUI configuration
requirements.txt       # Dependencies

components/
├── __init__.py
├── dataset_selector.py
├── results_table.py
└── validation_form.py

pages/
├── datasets.py        # Dataset management
└── results.py         # Results matrix
```

## Success Metrics
- [ ] All existing functionality replicated via API
- [ ] API response times < 2x direct DB queries
- [ ] New GUI provides identical user experience
- [ ] Zero data inconsistencies between systems
- [ ] Comprehensive test coverage (>80%)
- [ ] Complete documentation for deployment

## Critical Checkpoints

### Day 7 Checkpoint
- [ ] Core API endpoints working with real data
- [ ] Authentication integrated and working
- [ ] Basic error handling implemented
- [ ] API documentation accessible

### Day 14 Checkpoint  
- [ ] GUI fully functional with API backend
- [ ] All major features working end-to-end
- [ ] Performance acceptable for production use
- [ ] Integration tests passing

### Day 20 Checkpoint
- [ ] Complete system tested and documented
- [ ] Deployment ready
- [ ] Migration plan finalized
- [ ] User acceptance criteria met

This checklist provides a structured approach to implementing the PharmChecker API while maintaining quality and ensuring nothing is missed.