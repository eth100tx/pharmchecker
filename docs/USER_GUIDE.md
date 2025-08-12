# PharmChecker User Guide

## Overview

PharmChecker is a web-based tool for reviewing and validating pharmacy license verification results. It compares pharmacy records against state board search results and provides automated address matching scores to help identify correct matches.

## Accessing the Application

1. Open your web browser
2. Navigate to the PharmChecker URL (typically http://localhost:8501)
3. The application will load with the main dashboard

## Main Interface

### Sidebar (Dataset Selection)

The left sidebar contains dataset selection controls:

#### 1. Dataset Manager
- **Pharmacies Dataset**: Select which pharmacy list to use
- **States Dataset**: Select which state search results to review
- **Validated Dataset**: (Optional) Load previous validation decisions

Click "Load Selected Datasets" to apply your selections.

#### 2. Dataset Information
Shows currently loaded:
- Number of pharmacies
- States with search data (e.g., "FL, PA")
- Number of validated records

### Main Dashboard Tabs

#### Results Matrix Tab

The primary view showing all pharmacy-state combinations:

**Columns:**
- **Pharmacy**: Name of the pharmacy
- **State**: State being verified (FL, PA, TX, etc.)
- **Status**: Match classification
  - ✅ Match (green): High confidence match (score ≥ 85)
  - ⚠️ Weak Match (yellow): Needs review (score 60-84)
  - ❌ No Match (red): Low confidence (score < 60)
  - 📭 No Data (gray): No search conducted
- **Best Score**: Highest address match score
- **License #**: License number from search
- **License Status**: Active, Expired, etc.
- **Details**: Quick summary of findings

**Filtering Options:**
- Search by pharmacy name
- Filter by state
- Filter by status (match, weak match, no match, no data)
- Show only validated/unvalidated results

**Row Actions:**
- Click any row to see detailed information
- Use checkbox to select for validation
- Export selected rows to CSV

#### Detail View (Row Expansion)

When you click a row, you see:

1. **Pharmacy Information**
   - Full name and address
   - States where licensed
   - Dataset source

2. **Search Results**
   - All results found for this pharmacy-state
   - Each result shows:
     - License number and status
     - Name on license
     - Address on file
     - Issue and expiration dates
     - Match score with breakdown

3. **Screenshots**
   - Images from state board website
   - Click to enlarge
   - Timestamp showing when captured

4. **Validation Section**
   - Mark as "Verified Present" or "Verified Empty"
   - Add reason for decision
   - View validation history

#### Scoring Dashboard Tab

Monitor address matching computation:

**Metrics:**
- Total combinations requiring scores
- Scores computed
- Scores remaining
- Average processing time

**Score Distribution Chart:**
- Histogram showing score ranges
- Helps identify clustering patterns

**Controls:**
- "Compute Missing Scores" button
- Batch size adjustment
- Progress indicator

#### Data Export Tab

Export results for reporting:

**Export Options:**
- Full results (all columns)
- Summary only (key fields)
- Filtered results (current view)
- Include/exclude validations

**Formats:**
- CSV for Excel
- JSON for systems integration

## Understanding Match Scores

### Score Ranges

- **85-100**: Strong Match - High confidence this is the correct pharmacy
- **60-84**: Weak Match - Possible match, requires manual review
- **0-59**: No Match - Likely different pharmacy

### Score Components

Each score has two parts:
1. **Street Score (70% weight)**: How well street addresses match
2. **City/State/ZIP Score (30% weight)**: How well locations match

Example interpretations:
- Street: 95, City: 100 = Same address (strong match)
- Street: 95, City: 0 = Same street, different city (weak match)
- Street: 30, City: 50 = Completely different address (no match)

## Validation Process

### When to Validate

Validate results when:
- Reviewing weak matches (60-84 scores)
- Confirming critical licenses
- Overriding automatic scoring
- Creating audit trail for compliance

### How to Validate

1. **Review the Details**
   - Compare pharmacy address vs. license address
   - Check license status and expiration
   - View screenshots for additional context

2. **Make a Decision**
   - **Verified Present**: Confirm pharmacy has valid license
   - **Verified Empty**: Confirm no license exists
   - **Skip**: Leave unvalidated for now

3. **Document Reason**
   - Add explanation for decision
   - Reference specific evidence
   - Note any discrepancies

### Validation Best Practices

- Always check screenshots when scores are 60-84
- Look for name variations (LLC, Inc., DBA)
- Verify expiration dates are current
- Document suite/unit number differences
- Flag addresses that need updating

## Common Scenarios

### Scenario 1: Perfect Match
- Score: 95+
- Same address, active license
- Action: Generally no validation needed

### Scenario 2: Name Variation
- Score: 60-84
- "Pharmacy LLC" vs "Pharmacy Inc"
- Action: Review screenshots, validate if same entity

### Scenario 3: Address Change
- Score: 40-60
- Old address in system
- Action: Validate and note address update needed

### Scenario 4: No Results Found
- Status: No Data
- State board returned no results
- Action: Validate as empty if confirmed

### Scenario 5: Multiple Licenses
- Multiple results for same pharmacy
- Different license types or locations
- Action: Review each, validate primary license

## Tips and Tricks

### Keyboard Shortcuts
- `Enter`: Expand selected row
- `Esc`: Close detail view
- `Ctrl+F`: Search on page
- `Ctrl+S`: Export current view

### Performance Tips
- Filter by state to reduce data
- Use search to find specific pharmacies
- Export smaller batches for Excel
- Clear filters to reset view

### Troubleshooting

**Page Not Loading:**
- Refresh browser (F5)
- Clear browser cache
- Check internet connection

**Data Not Showing:**
- Verify datasets are loaded (sidebar)
- Check filters aren't too restrictive
- Click "Clear Filters" to reset

**Scores Missing:**
- Go to Scoring Dashboard
- Click "Compute Missing Scores"
- Wait for processing to complete

**Can't Validate:**
- Ensure you have proper permissions
- Check validation dataset is loaded
- Verify you're in edit mode

## Data Quality Indicators

### High Confidence Indicators
- Score ≥ 85
- Exact name match
- Current license (not expired)
- Recent search date

### Warning Signs
- Score < 60 with active license
- Expired license with recent dates
- Name significantly different
- Address completely different

### Requires Investigation
- Multiple licenses same state
- Conflicting status information
- Missing screenshots
- Validation warnings (data changed)

## Reporting

### Creating Reports

1. Filter data to desired subset
2. Review and validate key records
3. Export to CSV
4. Open in Excel for formatting

### Report Contents

Standard export includes:
- Pharmacy identification
- State and license details
- Match scores and status
- Validation decisions
- Timestamps and metadata

### Compliance Documentation

For audit trails:
- Include validation reasons
- Export with full timestamps
- Document reviewer information
- Maintain version history

## Getting Help

### In-Application Help
- Hover over ℹ️ icons for tooltips
- Check sidebar for dataset info
- View metrics for system status

### Common Questions

**Q: Why are some scores missing?**
A: Scores are computed on-demand. Use Scoring Dashboard to compute.

**Q: Can I undo a validation?**
A: Create a new validation with updated decision and reason.

**Q: How do I handle multiple locations?**
A: Each location-state combination is evaluated separately.

**Q: What if the screenshot is wrong?**
A: Report to administrator for re-import of search data.

### Support Contacts

For technical issues:
- Check system status: Admin Dashboard
- Review logs: Settings → Debug Mode
- Contact: [Your IT Support]

For data questions:
- Validation policy: [Compliance Team]
- Data updates: [Data Management]
- Training: [Training Team]