# PharmChecker System Testing Guide

This document explains how to run and interpret the PharmChecker system tests.

## Complete End-to-End System Test

### Running the Test

```bash
python system_test.py
```

### What the Test Does

The system test performs a complete workflow validation:

1. **Clean Test Data**: Removes any existing `system_test` datasets
2. **Import Pharmacy Data**: Creates 3 test pharmacies with different state licenses
3. **Import State Search Data**: Creates 5 search results including perfect matches, partial matches, and no matches
4. **Query Initial Results**: Shows pharmacy/state combinations with no scores computed
5. **Run Scoring Engine**: Executes lazy scoring to compute address match scores
6. **Query Final Results**: Shows results with computed scores and status classification
7. **Generate Report**: Comprehensive validation report with accuracy metrics

### Expected Output

```
PharmChecker End-to-End System Test
==================================================
✅ Clean existing test data
✅ Import pharmacy data
   Imported 3 test pharmacies
✅ Import state search data
   Imported 5 search results
✅ Query initial results
   Found 6 pharmacy/state combinations, 6 without scores
✅ Run scoring engine
   Computed 4 scores in 1 batches
✅ Query final results
   Found 6 results with status distribution: {'weak match': 1, 'match': 2, 'no data': 2, 'no match': 1}

================================================================================
PHARMCHECKER SYSTEM TEST REPORT
================================================================================

Test Summary:
  Tag: system_test
  Start Time: [timestamp]
  Duration: ~0.12 seconds
  Overall Success: ✅ PASS
  Steps Completed: 6/6

Scoring Summary:
  Scores Computed: 4
  Processing Batches: 1
  Processing Errors: 0
  Score Distribution:
    Matches (≥85): 2
    Weak Matches (60-84): 1
    No Matches (<60): 1
    Average Score: 74.7

Detailed Results:
--------------------------------------------------------------------------------
✅ Test Pharmacy A → TX
   Status: match
   Overall Score: 96.5
   (Perfect address match)

⚠️ Test Pharmacy A → FL
   Status: weak match
   Overall Score: 66.5
   (Same street, different city)

✅ Test Pharmacy B → FL
   Status: match
   Overall Score: 96.5
   (Perfect address match)

❌ Test Pharmacy C → GA
   Status: no match
   Overall Score: 39.4
   (Completely different address)

📭 Test Pharmacy B → GA
   Status: no data
   (No search results found)

📭 Test Pharmacy C → TX
   Status: no data
   (No search results found)

Expected Results Analysis:
----------------------------------------
✅ Perfect match correctly identified (Test Pharmacy A → TX)
✅ Weak match correctly identified (Test Pharmacy A → FL)
✅ No match correctly identified (Test Pharmacy C → GA)
```

### Interpreting Results

#### Success Criteria
- **Overall Success**: ✅ PASS
- **All 6 steps complete** without errors
- **Score Distribution**: Matches, weak matches, and no matches correctly classified
- **Expected Results Analysis**: All 3 test scenarios correctly identified

#### Score Validation
- **Perfect Matches (96.5% score)**: Exact address matches
- **Weak Matches (66.5% score)**: Similar addresses with differences (e.g., different cities)
- **No Matches (39.4% score)**: Completely different addresses
- **No Data**: States where pharmacy has licenses but no search results exist

#### Performance Metrics
- **Duration**: Should complete in under 1 second
- **Processing Errors**: Should be 0
- **Accuracy**: 100% correct classification expected

## Address Scoring Validation Tests

### Individual Scoring Test

```bash
python test_scoring.py
```

This test uses real database data to validate scoring across all pharmacy/result combinations.

**Expected Output**: Top matches should show high scores (>85) for similar pharmacies and addresses.

### Standalone Algorithm Test

```bash
python scoring_plugin.py
```

This tests the address matching algorithm in isolation with predefined test cases.

**Expected Output**: 
- Good matches: ~91% score
- Poor matches: ~29% score  
- No street address: ~60% score

## Troubleshooting

### Test Failures

#### "Dataset IDs not found"
- **Cause**: Database functions not updated for optimized schema
- **Fix**: Run `python update_functions.py` first

#### "not all arguments converted during string formatting"
- **Cause**: SQL parameter mismatch  
- **Fix**: Check that database functions are properly updated

#### Scoring accuracy failures
- **Cause**: Address matching algorithm issues
- **Fix**: Verify RapidFuzz is installed (`pip install rapidfuzz`)

### Database Issues

#### Connection errors
- **Cause**: Database not running or configuration issues
- **Fix**: 
  1. Check PostgreSQL is running
  2. Verify `.env` file configuration
  3. Run `make status` to check database state

#### Schema errors
- **Cause**: Database schema not set up
- **Fix**: Run `python setup.py` to initialize database

### Performance Issues

#### Slow execution
- **Normal**: First run may be slower due to database initialization
- **Issue**: If consistently >5 seconds, check database indexing

#### Memory issues
- **Rare**: Should not occur with test data
- **Fix**: Reduce batch size in scoring engine if needed

## Test Data Details

### Test Pharmacies
1. **Test Pharmacy A**: Licensed in TX, FL
   - TX: Perfect address match expected (96.5%)
   - FL: Weak match expected (different city, 66.5%)

2. **Test Pharmacy B**: Licensed in FL, GA  
   - FL: Perfect address match expected (96.5%)
   - GA: No search results (no data)

3. **Test Pharmacy C**: Licensed in GA, TX
   - GA: No match expected (different pharmacy, 39.4%) 
   - TX: No search results (no data)

### Search Results
- **Perfect matches**: Exact same addresses as pharmacy records
- **Partial matches**: Same street, different cities
- **Non-matches**: Completely different pharmacies/addresses
- **No results**: `result_status = 'no_results_found'`

## Integration with CI/CD

To integrate system testing into automated workflows:

```bash
#!/bin/bash
# Test script for CI/CD
set -e

echo "Running PharmChecker system test..."
python system_test.py

if [ $? -eq 0 ]; then
    echo "✅ PharmChecker system test PASSED"
    exit 0
else
    echo "❌ PharmChecker system test FAILED"
    exit 1
fi
```

## Manual Testing Workflow

For manual validation of the complete system:

1. **Setup**: Ensure database is running and configured
2. **Clean**: `make clean_all` to reset database
3. **Initialize**: `python setup.py` to create fresh schema
4. **Test**: `python system_test.py` to validate entire workflow
5. **Verify**: Check that all expected results are correctly classified

The system test validates the complete PharmChecker workflow from data import through address scoring to results classification, ensuring all components work together correctly.