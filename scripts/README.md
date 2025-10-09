# Scripts Directory

**Purpose**: Production utilities, data management scripts, and agent development tools

**Total Active Scripts**: 15
**Last Cleanup**: October 9, 2025

---

## Production Scripts (12 files)

### Data Management
- `bulk_data_sync.py` - Synchronize bulk property data from CAMA files
- `load_cama_bulk_to_database.py` - Initial bulk load of property appraiser data
- `enrich_qpublic_batch.py` - Batch enrichment of properties with qPublic data
- `run_entity_resolution.py` - Execute entity resolution matching

### Scraper Operations
- `run_all_scrapers.py` - Orchestrate all scrapers (permits, crime, news, council)
- `run_daily_scrapers.py` - Daily incremental scraping
- `backfill_3_months.py` - Historical data backfill
- `backfill_3_months_parallel.py` - Parallel backfill (faster)
- `run_permits_yesterday_only.py` - Single-day permit scraping

### Utilities
- `check_db_status.py` - Database health checks
- `verify_database_completeness.py` - Comprehensive data validation
- `check_permits_saved.py` - Permit data verification

---

## Agent Development (3 files)

### Testing & Analysis
- `test_agent_and_save.py` - Run Dominion agent and save JSON output
  - Usage: `python scripts/test_agent_and_save.py`
  - Saves to: `scripts/outputs/agent_output_YYYYMMDD_HHMMSS.json`

- `analyze_agent_output.py` - Analyze saved agent JSON output
  - Usage: `python scripts/analyze_agent_output.py <json_file>`
  - Shows: tool calls, verification checklist, reasoning summary

- `comprehensive_data_check.py` - Verify data available for agent
  - Checks: sales history, permits, comps, neighborhood stats
  - Identifies: missing data, hallucination sources

---

## Output Files

Agent test outputs are stored in `scripts/outputs/`:
- `latest_agent_output.json` - Symlink to most recent successful output

---

## Archived Tests

Historical test scripts are in `scripts/archived_tests/` for reference:
- 12 legacy test scripts from agent development
- Kept for reference but not actively used

---

## How to Run the Program

### Prerequisites

1. Ensure you have the virtual environment activated:
```bash
# Windows
venv_src\Scripts\activate

# Linux/Mac
source venv_src/bin/activate
```

2. Verify database connection is configured in `.env`

### Running the Dominion Agent

**Basic Usage:**

```bash
# Run the agent with a query
python scripts/test_agent_and_save.py
```

The script will:
1. Initialize database connection
2. Run the Dominion agent with the configured query
3. Save output to `scripts/outputs/agent_output_YYYYMMDD_HHMMSS.json`
4. Display results and save location

**Analyze the Results:**

```bash
# Analyze the most recent output
python scripts/analyze_agent_output.py scripts/latest_agent_output.json

# Or analyze a specific output file
python scripts/analyze_agent_output.py scripts/outputs/agent_output_20251009_035541.json
```

**Check Available Data:**

```bash
# Verify what data the agent has access to
python scripts/comprehensive_data_check.py
```

This will show:
- Sales history data
- D.R. Horton permit activity
- Recent vacant lot comps
- Neighborhood statistics

---

## Usage Examples

### Production Operations

**Daily Operations:**
```bash
# Run daily scrapers (incremental updates)
python scripts/run_daily_scrapers.py

# Check database health
python scripts/check_db_status.py
```

**Initial Setup/Backfill:**
```bash
# Run all scrapers (full backfill)
python scripts/run_all_scrapers.py

# Or use parallel backfill (faster)
python scripts/backfill_3_months_parallel.py

# Load bulk CAMA data
python scripts/load_cama_bulk_to_database.py
```

**Data Validation:**
```bash
# Verify data completeness
python scripts/verify_database_completeness.py

# Check permit data specifically
python scripts/check_permits_saved.py
```

**Data Enrichment:**
```bash
# Enrich properties with qPublic data
python scripts/enrich_qpublic_batch.py

# Run entity resolution
python scripts/run_entity_resolution.py
```

### Agent Development

**Run Agent:**
```bash
# Test agent and save output
python scripts/test_agent_and_save.py
```

**Analyze Output:**
```bash
# Analyze most recent run
python scripts/analyze_agent_output.py scripts/latest_agent_output.json

# View raw JSON
cat scripts/latest_agent_output.json | python -m json.tool | less
```

**Verify Data:**
```bash
# Check what data agent can access
python scripts/comprehensive_data_check.py
```

---

## Script Organization

```
scripts/
├── Production (12) - Live data operations
│   ├── Data Management (4)
│   ├── Scraper Operations (5)
│   └── Utilities (3)
│
├── Agent Development (3) - Agent testing and analysis
│
├── outputs/ - Agent JSON outputs
│   └── latest_agent_output.json (symlink)
│
└── archived_tests/ - Historical reference (12 files)
```

---

## Common Workflows

### 1. Initial Data Setup
```bash
# Step 1: Load bulk property data
python scripts/load_cama_bulk_to_database.py

# Step 2: Run backfill for historical data
python scripts/backfill_3_months_parallel.py

# Step 3: Enrich with qPublic
python scripts/enrich_qpublic_batch.py

# Step 4: Run entity resolution
python scripts/run_entity_resolution.py

# Step 5: Verify completeness
python scripts/verify_database_completeness.py
```

### 2. Daily Maintenance
```bash
# Run daily scrapers
python scripts/run_daily_scrapers.py

# Check status
python scripts/check_db_status.py
```

### 3. Testing Agent
```bash
# Run agent test
python scripts/test_agent_and_save.py

# Analyze results
python scripts/analyze_agent_output.py scripts/latest_agent_output.json

# Check data availability
python scripts/comprehensive_data_check.py
```

---

## Troubleshooting

### Database Connection Issues
```bash
# Check database status
python scripts/check_db_status.py

# Verify .env file has correct DATABASE_URL
cat .env | grep DATABASE_URL
```

### Agent Issues
```bash
# Check what data is available
python scripts/comprehensive_data_check.py

# Verify agent output
python scripts/analyze_agent_output.py scripts/latest_agent_output.json
```

### Scraper Issues
```bash
# Check permit data
python scripts/check_permits_saved.py

# Verify overall completeness
python scripts/verify_database_completeness.py
```

---

## Cleanup History

| Date | Action | Before | After | Result |
|------|--------|--------|-------|--------|
| Oct 7, 2025 | First cleanup | 36 files | 12 files | 67% reduction |
| Oct 9, 2025 | Second cleanup | 35 files | 15 files | 57% reduction, better organization |

**Archived**: 12 test scripts
**Deleted**: 2 obsolete files
**Organized**: Created outputs/ and archived_tests/ directories
