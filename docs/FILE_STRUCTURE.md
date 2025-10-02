# Dominion File Structure

**Last Updated:** 2025-10-02
**Status:** Clean & Organized

---

## Root Level (Clean!)

```
dominion/
├── docs/                    # All documentation (NEW!)
├── scripts/                 # Utility scripts (NEW!)
├── src/                     # Source code
├── tests/                   # Test suite
├── data/                    # Data files
├── logs/                    # Log files
│
├── Dockerfile.api           # API container
├── Dockerfile.scrapers      # Scrapers container
├── Dockerfile.workers       # Workers container
├── docker-compose.yml       # Docker orchestration
├── dominion-scheduler.service  # Systemd service
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (not in git)
└── .env.example             # Environment template
```

---

## Documentation (`docs/`)

### Architecture Docs
```
docs/architecture/
├── DATABASE_ARCHITECTURE_FINAL.md
└── PIPELINE_ANALYSIS.md
```

### Planning Docs
```
docs/planning/
├── dominion_engineering_plan_v2.md
└── dominion_mvp_implementation_plan.md
```

### Reports
```
docs/reports/
├── ENRICHMENT_INTEGRATION_COMPLETE.md
├── FINAL_ENRICHMENT_REPORT.md
├── IMPROVEMENTS_RECOMMENDATIONS.md
└── SYSTEM_AUDIT_REPORT.md
```

---

## Scripts (`scripts/`)

Utility scripts for maintenance:

```
scripts/
├── cleanup_db_auto.py        # Database cleanup
├── export_ml_data.py          # ML data export
└── run_all_scrapers.py        # Run all scrapers
```

**Usage:**
```bash
python scripts/run_all_scrapers.py
python scripts/export_ml_data.py
```

---

## Source Code (`src/`)

### Current Structure
```
src/
├── config/                   # Market configurations
│   ├── markets/
│   │   ├── gainesville_fl.yaml
│   │   └── tampa_fl.yaml
│   ├── loader.py
│   └── schemas.py
│
├── database/                 # Data layer
│   ├── migrations/           # SQL migrations (NEW!)
│   │   ├── 001_add_jurisdiction.sql
│   │   ├── 002_schema_enhancements.sql
│   │   └── 003_entity_resolution.sql
│   ├── schema.sql
│   ├── connection.py
│   ├── models.py
│   └── init_database.py
│
├── scrapers/                 # Data collection
│   ├── BypassV3/             # reCAPTCHA bypass
│   ├── permits/
│   │   ├── city_permits.py
│   │   └── county_permits.py
│   ├── government/
│   │   └── city_council_scraper.py
│   ├── demographics/
│   │   └── census_demographics.py
│   ├── business/
│   │   ├── business_journal_scraper.py
│   │   └── news_rss_extractor.py
│   ├── data_sources/
│   │   ├── crime_data_socrata.py
│   │   ├── gis_shapefile_downloader.py
│   │   ├── property_appraiser_bulk.py
│   │   ├── sunbiz.py                    # SFTP scraper
│   │   └── sunbiz_website.py            # Website enrichment
│   ├── base/
│   │   ├── change_detector.py
│   │   └── resilient_scraper.py
│   └── utilities/
│
├── services/                 # Business logic
│   ├── data_ingestion.py              # Universal pipeline
│   ├── entity_resolution.py           # Entity matching
│   ├── sunbiz_enrichment.py           # LLC enrichment
│   └── metrics_aggregator.py          # Monitoring
│
├── scheduler/                # Task scheduling
│   └── scraper_scheduler.py
│
├── cli/                      # Command line interface
│   └── scheduler_cli.py
│
├── api/                      # REST API (optional)
│   ├── routes/
│   └── middleware/
│
└── utils/                    # Shared utilities
    └── pdf_extractor.py
```

### Removed (Cleaned Up!)
- ❌ `src/ai/` - Empty placeholder (create when needed)
- ❌ `src/intelligence/` - Empty placeholder
- ❌ `src/monitoring/` - Empty placeholder
- ❌ `src/workers/` - Empty placeholder
- ❌ `src/parsers/` - Deprecated (parsing in data_ingestion now)

---

## Tests (`tests/`)

```
tests/
├── database/
│   ├── test_database_setup.py
│   ├── test_models.py
│   └── check_environment.py
│
├── services/
│   ├── test_data_ingestion.py
│   ├── test_entity_resolution.py
│   ├── test_entity_resolution_comprehensive.py
│   ├── test_entity_resolution_realworld.py
│   └── test_entity_resolution_stress.py
│
└── requirements.txt
```

---

## Data (`data/`)

```
data/
├── raw/                      # Raw scraper outputs
│   ├── CAMA_2025-09-25.zip
│   ├── city_council_*.json
│   └── crime_data_*.json
│
└── sunbiz/                   # Sunbiz SFTP downloads
    ├── 20251001c.txt
    └── 20251002c.txt
```

---

## Removed Duplicates

### BypassV3 (was duplicated)
- ❌ Removed: `/BypassV3/` (git submodule, unused)
- ✅ Kept: `/src/scrapers/BypassV3/` (actively used)

### Test Folders (was duplicated)
- ❌ Removed: `/testing/` (old venv folder)
- ✅ Kept: `/tests/` (real test suite)

---

## File Count Summary

**Before Cleanup:**
- Root level files: ~20+
- Empty folders: 5
- Duplicate folders: 2
- Scattered SQL files: 4

**After Cleanup:**
- Root level files: 7 (only essentials!)
- Empty folders: 0
- Duplicate folders: 0
- Organized SQL migrations: 3

**Improvement: 60% cleaner!** ✅

---

## Benefits of New Structure

### 1. Clear Organization
- **Documentation** → `/docs`
- **Scripts** → `/scripts`
- **Migrations** → `/src/database/migrations`
- **Source code** → `/src` (clean, no empty folders)

### 2. Easier Navigation
- Find docs quickly
- Scripts in one place
- No confusion from duplicates

### 3. Professional Structure
- Follows industry standards
- Easy for new developers
- Scalable as project grows

### 4. Docker-Friendly
- Dockerfiles at root (standard)
- docker-compose.yml at root (standard)
- Clean separation of concerns

---

## Adding New Components

### Add New Market:
```bash
# Create config file
cp src/config/markets/gainesville_fl.yaml src/config/markets/orlando_fl.yaml

# Edit URLs/credentials
# That's it!
```

### Add New Scraper:
```bash
# Create in appropriate category
src/scrapers/category/new_scraper.py

# Register in __init__.py
# Add parser to data_ingestion.py
```

### Add New Migration:
```bash
# Create numbered file
src/database/migrations/004_my_change.sql

# Document what it does
# Run manually or via init script
```

### Add New Documentation:
```bash
# Architecture docs
docs/architecture/my_architecture.md

# Planning docs
docs/planning/my_plan.md

# Reports
docs/reports/my_report.md
```

---

## Summary

**The project structure is now clean, organized, and production-ready.**

Key improvements:
- ✅ No duplicates
- ✅ No empty folders
- ✅ Clear organization
- ✅ Easy to navigate
- ✅ Scalable structure

**Everything has its place!** 📁
