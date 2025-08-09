# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PharmChecker is a lightweight internal tool for verifying pharmacy licenses across U.S. states through manual review of automated search results. This repository contains comprehensive implementation documentation and database configurations.

## Key Design Principles

- **Dataset Independence**: Pharmacies, state searches, and validated overrides can be imported and combined in any order
- **Natural Key Linking**: Cross-dataset relationships use pharmacy names and license numbers, not internal IDs
- **Multi-User Support**: Multiple users can work with different dataset combinations simultaneously
- **Lazy Scoring**: Address match scores computed on-demand when needed
- **Manual Control**: All refresh and recalculation actions are explicit
- **Validation as Snapshot**: Validated overrides capture the full search result at validation time

## Database Access

This project uses MCP (Model Context Protocol) servers to connect to PostgreSQL databases:

- **postgres-prod**: Production database at `localhost:5432/pharmchecker`
- **postgres-sbx**: Sandbox database at `localhost:5432/testing_sandbox_db`
- **supabase**: Supabase project integration (requires project-ref configuration)

Use the MCP tools (`mcp__postgres-prod__query`, `mcp__postgres-sbx__query`, `mcp__supabase__*`) to interact with databases.

## Core Architecture Components

1. **PostgreSQL Database** - Stores all datasets and computed scores
2. **Import Scripts** - Load pharmacies, state searches, and validated overrides  
3. **Scoring Engine** - Computes address match scores on-demand
4. **Streamlit UI** - Review interface with GitHub authentication
5. **Storage Layer** - Local filesystem (dev) or Supabase Storage (production)

## Database Schema

### Core Tables
- `datasets` - Versioned datasets (states, pharmacies, validated)
- `pharmacies` - Pharmacy master records with state licenses
- `searches` - State board searches by pharmacy name and state
- `search_results` - Results from state board searches
- `match_scores` - Computed address match scores (lazy calculation)
- `validated_overrides` - Manual validation snapshots
- `images` - Screenshot storage metadata
- `app_users` - User allowlist for authentication

### Key Functions
- `get_results_matrix(states_tag, pharmacies_tag, validated_tag)` - Main view combining all data
- `find_missing_scores(states_tag, pharmacies_tag)` - Identifies pairs needing scoring

## Implementation Architecture

The system follows a versioned dataset approach where:
- Data imports are tagged (e.g., "2024-01-15", "pilot-test")
- No global "active" state - views are generated for specific tag combinations  
- Scoring is computed lazily only for needed pharmacy/state pairs
- Manual validations create complete snapshots of search results

## Status Classification

Results are classified into status buckets:
- **match**: Score ≥ 85 (or validated as present with good score)
- **weak match**: Score 60-84
- **no match**: Score < 60
- **no data**: No search conducted or no results found

## Address Scoring Algorithm

The scoring plugin (`scoring_plugin.py`) implements:
- Street address matching (70% weight) with fuzzy string matching
- City/State/ZIP matching (30% weight) with exact matching
- Suite/apartment number consideration
- Normalization of common address abbreviations