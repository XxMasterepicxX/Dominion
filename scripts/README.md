# Scripts Directory

**Purpose**: Production utilities, data management scripts, and current analysis tools

---

## Production Scripts (7 files)

### Data Management
- **`bulk_data_sync.py`** - Synchronize bulk property data from CAMA files
- **`load_cama_bulk_to_database.py`** - Initial bulk load of property appraiser data
- **`enrich_qpublic_batch.py`** - Batch enrichment of properties with qPublic data
- **`export_ml_data.py`** - Export data for machine learning model training

### Scraper Operations
- **`run_all_scrapers.py`** - Orchestrate all scrapers (permits, crime, news, council, sunbiz)
- **`run_permits_yesterday_only.py`** - Incremental daily permit scraping
- **`run_entity_resolution.py`** - Execute entity resolution matching

---

## Current Analysis Scripts (5 files)

### Agent Development & Testing
- **`simulate_agent_land_query.py`** - Full agent simulation for land speculation queries
  - Analyzes market development activity
  - Identifies active developers/contractors
  - Scores vacant land opportunities
  - Includes motivation scoring and data validation
  - **Primary agent demonstration script**

- **`hard_tests.py`** - Real investor scenario testing
  - "Would I invest $50k?" decision framework
  - Data quality stress testing
  - Exit strategy validation
  - ROI calculations

- **`test_real_investor_value.py`** - Product-market fit analysis
  - Tests actual investor needs vs capabilities
  - Identifies critical data gaps
  - Validates feature completeness

### Validation & Analysis
- **`analyze_simulation_issues.py`** - Quality analysis of simulation outputs
  - Data completeness checks
  - Recommendation quality assessment
  - Gap identification

- **`check_permits_saved.py`** - Verify permit data ingestion
  - Database integrity checks
  - Date population validation
  - Field completeness

---

## Archived Tests

See `archived_tests/` for historical test scripts:
- `comprehensive_testing.py` - Full system validation
- `deep_validation_suite.py` - Database validation patterns
- `intelligent_database_testing.py` - Smart database tests
- `demo_analyzers.py` - Analyzer demonstration patterns
- `debug_entity_analyzer.py` - Entity analyzer debugging

---

## Usage Examples

### Run All Scrapers
```bash
python scripts/run_all_scrapers.py
```

### Simulate Agent Land Query
```bash
python scripts/simulate_agent_land_query.py
```

### Run Hard Reality Tests
```bash
python scripts/hard_tests.py
```

### Check Permit Data Quality
```bash
python scripts/check_permits_saved.py
```

### Entity Resolution
```bash
python scripts/run_entity_resolution.py
```

---

## Script Organization

```
scripts/
├── Production (7) - Live data operations
├── Analysis (5) - Current development work
└── archived_tests/ - Historical reference
```

**Total**: 12 active scripts (down from 36)
**Cleanup Date**: 2025-10-07
**Cleanup Result**: 67% reduction, better organization
