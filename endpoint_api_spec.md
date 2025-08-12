# PharmChecker API Specification v1

## Overview

This document provides detailed specifications for the PharmChecker REST API v1. The API provides programmatic access to pharmacy license verification data through clean, RESTful endpoints.

## Base Configuration

- **Base URL**: `http://localhost:8000/v1` (development)
- **Authentication**: Bearer token (Supabase JWT)
- **Content-Type**: `application/json`
- **API Version**: v1

## Authentication

All endpoints require authentication via Supabase JWT token:

```http
Authorization: Bearer <supabase_jwt_token>
```

## Common Response Patterns

### Success Response
```json
{
  "data": { ... },
  "meta": {
    "total_count": 150,
    "limit": 100,
    "offset": 0
  }
}
```

### Error Response
```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid parameter value",
    "details": {
      "field": "override_type",
      "allowed_values": ["present", "empty"]
    }
  }
}
```

### Pagination
- **Query Parameters**: `limit` (default: 100, max: 1000), `offset` (default: 0)
- **Response Headers**: `X-Total-Count: 1500`

## Endpoints

### Health & System

#### GET /v1/health
**Description**: Service health check
**Auth Required**: No

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "database": "connected"
}
```

#### GET /v1/version
**Description**: API version information
**Auth Required**: No

**Response**:
```json
{
  "version": "1.0.0",
  "git_sha": "abc123def",
  "build_date": "2024-01-15T10:00:00Z"
}
```

### Datasets

#### GET /v1/datasets
**Description**: List all available datasets with filtering
**Auth Required**: Yes

**Query Parameters**:
- `kind` (optional): Filter by dataset kind (`states`, `pharmacies`, `validated`)
- `q` (optional): Search by tag or description
- `limit` (optional): Number of results (default: 100, max: 1000)
- `offset` (optional): Pagination offset (default: 0)

**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "kind": "pharmacies",
      "tag": "jan_2024",
      "description": "January 2024 pharmacy dataset",
      "created_by": "admin@pharmchecker.com",
      "created_at": "2024-01-15T10:00:00Z",
      "record_count": 1250,
      "metadata": {
        "source_file": "pharmacies_jan_2024.csv",
        "import_duration": "45.2s"
      }
    }
  ],
  "meta": {
    "total_count": 15,
    "limit": 100,
    "offset": 0
  }
}
```

#### GET /v1/datasets/{kind}/{tag}
**Description**: Get specific dataset details and statistics
**Auth Required**: Yes

**Path Parameters**:
- `kind`: Dataset kind (`states`, `pharmacies`, `validated`)
- `tag`: Dataset tag (e.g., "jan_2024")

**Response**:
```json
{
  "data": {
    "id": 1,
    "kind": "pharmacies",
    "tag": "jan_2024",
    "description": "January 2024 pharmacy dataset",
    "created_by": "admin@pharmchecker.com",
    "created_at": "2024-01-15T10:00:00Z",
    "record_count": 1250,
    "statistics": {
      "total_pharmacies": 1250,
      "states_covered": ["FL", "TX", "CA", "NY"],
      "license_claims": 2847
    },
    "metadata": {
      "source_file": "pharmacies_jan_2024.csv",
      "import_duration": "45.2s",
      "validation_status": "passed"
    }
  }
}
```

### Results

#### GET /v1/results
**Description**: Get comprehensive results with full context (core functionality)
**Auth Required**: Yes

**Query Parameters**:
- `states_tag` (required): States dataset tag
- `pharmacies_tag` (required): Pharmacies dataset tag  
- `validated_tag` (optional): Validated dataset tag
- `state` (optional): Filter by state code (e.g., "FL,TX")
- `pharmacy_name` (optional): Filter by pharmacy name (partial match)
- `license_number` (optional): Filter by license number
- `min_score` (optional): Minimum score threshold (0-100)
- `max_score` (optional): Maximum score threshold (0-100)
- `status` (optional): Filter by status (`match`, `weak_match`, `no_match`, `validated_present`, `validated_empty`, `no_data`)
- `limit` (optional): Number of results (default: 100, max: 1000)
- `offset` (optional): Pagination offset (default: 0)

**Response**:
```json
{
  "data": [
    {
      "pharmacy_id": 123,
      "pharmacy_name": "Belmar Pharmacy",
      "search_state": "FL",
      "result_id": 456,
      "search_name": "Belmar Pharmacy",
      "license_number": "FL12345",
      "license_status": "Active",
      "license_name": "Belmar Pharmacy LLC",
      "license_type": "Community Pharmacy",
      "issue_date": "2020-01-15",
      "expiration_date": "2025-01-15",
      "score_overall": 98.5,
      "score_street": 100.0,
      "score_city_state_zip": 95.0,
      "override_type": null,
      "validated_license": null,
      "result_status": "results_found",
      "search_timestamp": "2024-01-15T10:30:00Z",
      "screenshot_path": "image_cache/states_jan_2024/FL/Belmar_Pharmacy.20240115_1030.png",
      "screenshot_storage_type": "local",
      "screenshot_file_size": 245760,
      "pharmacy_address": "123 Main St",
      "pharmacy_city": "Orlando",
      "pharmacy_state": "FL",
      "pharmacy_zip": "32801",
      "result_address": "123 Main Street",
      "result_city": "Orlando",
      "result_state": "FL",
      "result_zip": "32801",
      "pharmacy_dataset_id": 1,
      "states_dataset_id": 2,
      "validated_dataset_id": null
    }
  ],
  "meta": {
    "total_count": 1500,
    "limit": 100,
    "offset": 0,
    "dataset_tags": {
      "states": "states_jan_2024",
      "pharmacies": "pharmacies_jan_2024", 
      "validated": null
    },
    "cache_key": "results_states_jan_2024_pharmacies_jan_2024_null_1642248600"
  }
}
```

#### GET /v1/results/matrix
**Description**: Get aggregated matrix view (one row per pharmacy-state pair)
**Auth Required**: Yes

**Query Parameters**: Same as `/v1/results` plus:
- `aggregate_method` (optional): How to aggregate multiple results (`latest`, `best_score`, `all`) - default: `latest`

**Response**:
```json
{
  "data": [
    {
      "pharmacy_name": "Belmar Pharmacy",
      "search_state": "FL",
      "status_bucket": "match",
      "result_count": 3,
      "latest_result_id": 456,
      "best_score": 98.5,
      "latest_score": 98.5,
      "license_numbers": ["FL12345", "FL12346"],
      "license_statuses": ["Active", "Active"],
      "override_type": null,
      "has_screenshot": true,
      "search_timestamp": "2024-01-15T10:30:00Z",
      "warnings": []
    }
  ],
  "meta": {
    "total_count": 150,
    "limit": 100,
    "offset": 0,
    "summary": {
      "total_pharmacy_state_pairs": 150,
      "matches": 85,
      "weak_matches": 23,
      "no_matches": 15,
      "validated_present": 12,
      "validated_empty": 8,
      "no_data": 7
    }
  }
}
```

#### GET /v1/results/{pharmacy_name}/{state}
**Description**: Get detailed view for specific pharmacy-state combination
**Auth Required**: Yes

**Path Parameters**:
- `pharmacy_name`: Exact pharmacy name (URL encoded)
- `state`: State code (e.g., "FL")

**Query Parameters**:
- `states_tag` (required): States dataset tag
- `pharmacies_tag` (required): Pharmacies dataset tag
- `validated_tag` (optional): Validated dataset tag

**Response**:
```json
{
  "data": {
    "pharmacy_info": {
      "pharmacy_id": 123,
      "pharmacy_name": "Belmar Pharmacy",
      "pharmacy_address": "123 Main St",
      "pharmacy_city": "Orlando",
      "pharmacy_state": "FL",
      "pharmacy_zip": "32801"
    },
    "search_info": {
      "search_state": "FL",
      "search_name": "Belmar Pharmacy",
      "search_timestamp": "2024-01-15T10:30:00Z"
    },
    "results": [
      {
        "result_id": 456,
        "license_number": "FL12345",
        "license_status": "Active",
        "license_name": "Belmar Pharmacy LLC",
        "score_overall": 98.5,
        "score_breakdown": {
          "street": 100.0,
          "city_state_zip": 95.0
        },
        "result_address": "123 Main Street",
        "result_city": "Orlando",
        "result_state": "FL",
        "result_zip": "32801"
      }
    ],
    "validation": {
      "override_type": null,
      "validated_license": null,
      "validated_by": null,
      "validated_at": null,
      "reason": null
    },
    "screenshots": [
      {
        "path": "image_cache/states_jan_2024/FL/Belmar_Pharmacy.20240115_1030.png",
        "storage_type": "local",
        "file_size": 245760,
        "created_at": "2024-01-15T10:30:00Z"
      }
    ]
  }
}
```

### Validations

#### GET /v1/validations
**Description**: List validation overrides with filtering
**Auth Required**: Yes

**Query Parameters**:
- `validated_tag` (required): Validated dataset tag
- `pharmacy_name` (optional): Filter by pharmacy name
- `state` (optional): Filter by state code
- `override_type` (optional): Filter by override type (`present`, `empty`)
- `validated_by` (optional): Filter by validator
- `limit` (optional): Number of results (default: 100, max: 1000)
- `offset` (optional): Pagination offset (default: 0)

**Response**:
```json
{
  "data": [
    {
      "id": 789,
      "pharmacy_name": "Example Pharmacy",
      "state_code": "FL", 
      "license_number": "FL12345",
      "override_type": "present",
      "reason": "Manual verification via phone call",
      "validated_by": "admin@pharmchecker.com",
      "validated_at": "2024-01-15T14:30:00Z",
      "license_status": "Active",
      "license_name": "Example Pharmacy LLC",
      "address": "456 Oak Ave",
      "city": "Tampa",
      "state": "FL",
      "zip": "33601",
      "expiration_date": "2025-06-30"
    }
  ],
  "meta": {
    "total_count": 45,
    "limit": 100,
    "offset": 0
  }
}
```

#### POST /v1/validations
**Description**: Create or update validation override
**Auth Required**: Yes

**Request Body**:
```json
{
  "validated_tag": "validated_jan_2024",
  "pharmacy_name": "Example Pharmacy",
  "state_code": "FL",
  "license_number": "FL12345",
  "override_type": "present",
  "reason": "Manual verification via phone call",
  "license_status": "Active",
  "license_name": "Example Pharmacy LLC", 
  "address": "456 Oak Ave",
  "city": "Tampa",
  "state": "FL",
  "zip": "33601",
  "expiration_date": "2025-06-30"
}
```

**Response**:
```json
{
  "data": {
    "id": 789,
    "pharmacy_name": "Example Pharmacy",
    "state_code": "FL",
    "license_number": "FL12345",
    "override_type": "present",
    "reason": "Manual verification via phone call",
    "validated_by": "admin@pharmchecker.com",
    "validated_at": "2024-01-15T14:30:00Z",
    "license_status": "Active",
    "license_name": "Example Pharmacy LLC",
    "address": "456 Oak Ave",
    "city": "Tampa",
    "state": "FL",
    "zip": "33601",
    "expiration_date": "2025-06-30"
  },
  "warnings": [
    {
      "code": "field_mismatch",
      "message": "Validated address differs from current search result",
      "details": {
        "field": "address",
        "validated": "456 Oak Ave",
        "current": "456 Oak Avenue"
      }
    }
  ]
}
```

#### DELETE /v1/validations/{id}
**Description**: Remove validation override
**Auth Required**: Yes

**Path Parameters**:
- `id`: Validation ID

**Response**:
```json
{
  "data": {
    "id": 789,
    "deleted": true,
    "deleted_at": "2024-01-15T15:00:00Z"
  }
}
```

### Scoring

#### GET /v1/scores/missing
**Description**: List pharmacy-result pairs that need scoring
**Auth Required**: Yes

**Query Parameters**:
- `states_tag` (required): States dataset tag
- `pharmacies_tag` (required): Pharmacies dataset tag
- `limit` (optional): Number of results (default: 100, max: 1000)
- `offset` (optional): Pagination offset (default: 0)

**Response**:
```json
{
  "data": [
    {
      "pharmacy_id": 123,
      "pharmacy_name": "Belmar Pharmacy",
      "result_id": 456,
      "search_state": "FL",
      "license_number": "FL12345",
      "pharmacy_address": "123 Main St, Orlando, FL 32801",
      "result_address": "123 Main Street, Orlando, FL 32801"
    }
  ],
  "meta": {
    "total_count": 25,
    "limit": 100,
    "offset": 0,
    "estimated_processing_time": "2.5 minutes"
  }
}
```

#### POST /v1/scores/compute
**Description**: Trigger scoring computation (asynchronous)
**Auth Required**: Yes

**Request Body**:
```json
{
  "states_tag": "states_jan_2024",
  "pharmacies_tag": "pharmacies_jan_2024",
  "batch_size": 100,
  "priority": "normal"
}
```

**Response**:
```json
{
  "data": {
    "job_id": "score_job_abc123",
    "status": "queued",
    "created_at": "2024-01-15T15:30:00Z",
    "estimated_completion": "2024-01-15T15:35:00Z",
    "parameters": {
      "states_tag": "states_jan_2024",
      "pharmacies_tag": "pharmacies_jan_2024",
      "batch_size": 100,
      "total_pairs": 250
    }
  }
}
```

#### GET /v1/jobs/{job_id}
**Description**: Check scoring job status
**Auth Required**: Yes

**Path Parameters**:
- `job_id`: Job identifier

**Response**:
```json
{
  "data": {
    "job_id": "score_job_abc123",
    "status": "running",
    "progress": {
      "completed": 150,
      "total": 250,
      "percentage": 60.0
    },
    "created_at": "2024-01-15T15:30:00Z",
    "started_at": "2024-01-15T15:30:30Z",
    "estimated_completion": "2024-01-15T15:33:00Z",
    "message": "Processing batch 2 of 3"
  }
}
```

**Job Status Values**:
- `queued`: Job is waiting to start
- `running`: Job is currently processing
- `completed`: Job finished successfully
- `failed`: Job encountered an error
- `cancelled`: Job was cancelled by user

## Data Models

### Dataset
```json
{
  "id": 1,
  "kind": "pharmacies",
  "tag": "jan_2024", 
  "description": "January 2024 pharmacy dataset",
  "created_by": "admin@pharmchecker.com",
  "created_at": "2024-01-15T10:00:00Z",
  "record_count": 1250
}
```

### Result (Comprehensive)
```json
{
  "pharmacy_id": 123,
  "pharmacy_name": "Belmar Pharmacy",
  "search_state": "FL",
  "result_id": 456,
  "license_number": "FL12345",
  "license_status": "Active",
  "score_overall": 98.5,
  "override_type": null,
  "screenshot_path": "image_cache/...",
  "pharmacy_address": "123 Main St",
  "result_address": "123 Main Street"
}
```

### Validation Override
```json
{
  "id": 789,
  "pharmacy_name": "Example Pharmacy",
  "state_code": "FL",
  "license_number": "FL12345",
  "override_type": "present",
  "reason": "Manual verification",
  "validated_by": "admin@pharmchecker.com",
  "validated_at": "2024-01-15T14:30:00Z"
}
```

## Error Codes

### Common Error Codes
- `validation_error`: Invalid request parameters
- `not_found`: Requested resource not found
- `unauthorized`: Authentication required
- `forbidden`: Insufficient permissions
- `rate_limited`: Too many requests
- `internal_error`: Server error

### Specific Error Codes
- `dataset_not_found`: Specified dataset tag not found
- `invalid_dataset_combination`: Incompatible dataset tags
- `scoring_job_failed`: Scoring computation failed
- `validation_conflict`: Validation conflicts with existing data

## Rate Limiting

- **Default Limit**: 1000 requests per hour per user
- **Burst Limit**: 100 requests per minute
- **Headers**: 
  - `X-RateLimit-Limit`: Total requests allowed
  - `X-RateLimit-Remaining`: Requests remaining in current window
  - `X-RateLimit-Reset`: Unix timestamp when limit resets

## Caching

### Response Caching
- **ETag Generation**: Based on dataset tags + last modification time
- **Cache Headers**: Appropriate `Cache-Control` and `Last-Modified`
- **Conditional Requests**: Support for `If-None-Match` and `If-Modified-Since`

### Cache Keys
- Results: `results_{states_tag}_{pharmacies_tag}_{validated_tag}_{filters_hash}`
- Matrix: `matrix_{states_tag}_{pharmacies_tag}_{validated_tag}_{filters_hash}`
- Datasets: `datasets_{kind}_{last_modified}`

## Performance Considerations

### Query Optimization
- Use existing optimized SQL functions (`get_all_results_with_context`)
- Implement proper indexing for filter operations
- Limit result sets with pagination

### Connection Management
- Connection pooling for database operations
- Proper connection lifecycle management
- Timeout configuration for long-running queries

### Response Size Management
- Default pagination limits prevent oversized responses
- Field selection for large objects
- Compression for text responses

This specification provides a complete reference for implementing and using the PharmChecker API v1.