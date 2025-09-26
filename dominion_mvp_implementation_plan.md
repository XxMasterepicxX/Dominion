# Dominion MVP Implementation Plan - Complete Data Intelligence System

## Overview

**Philosophy**: Data-first approach - Build comprehensive data collection infrastructure before intelligence layers
**Timeline**: 4 weeks to full production system
**Goal**: All 15+ data sources operational, validated, and feeding intelligence algorithms

## Project Structure

```
dominion/
├── docker-compose.yml                    # PostgreSQL + Redis + FastAPI services
├── .env.example                         # Environment variables template
├── requirements.txt                     # All Python dependencies
├── src/
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py               # Database connection manager
│   │   ├── models.py                   # SQLAlchemy models
│   │   └── schema.sql                  # Complete database schema
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base/
│   │   │   ├── __init__.py
│   │   │   ├── resilient_scraper.py   # Base scraper with all resilience features
│   │   │   ├── change_detector.py     # MD5 content hashing for change detection
│   │   │   ├── proxy_manager.py       # Proxy rotation and health checking
│   │   │   └── rate_limiter.py        # Adaptive rate limiting
│   │   ├── sources/
│   │   │   ├── __init__.py
│   │   │   ├── city_permits.py        # City of Gainesville permits API
│   │   │   ├── census_data.py         # US Census Bureau API
│   │   │   ├── crime_data.py          # Crime statistics API
│   │   │   ├── zoning_data.py         # Zoning and land use API
│   │   │   ├── gainesville_sun.py     # News scraping + RSS
│   │   │   ├── business_journal.py    # Business news scraping
│   │   │   ├── city_council.py        # Council agendas and minutes
│   │   │   ├── property_appraiser.py  # Property sales bulk download
│   │   │   ├── county_permits.py      # County permits (Playwright)
│   │   │   ├── sunbiz_llc.py          # LLC formation monitor
│   │   │   ├── pdf_extractor.py       # PDF + OCR processing
│   │   │   └── gis_downloader.py      # Shapefile downloads
│   │   └── scheduler.py               # Orchestrates all scrapers
│   ├── intelligence/
│   │   ├── __init__.py
│   │   ├── assemblage_detector.py     # Property assemblage detection
│   │   ├── llc_analyzer.py            # LLC formation pattern analysis
│   │   ├── permit_sequencer.py        # Permit sequence analysis
│   │   ├── relationship_mapper.py     # Entity relationship mapping
│   │   └── synthesis.py               # Combine all intelligence signals
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── llm_adapter.py             # Gemini/OpenAI provider abstraction
│   │   ├── cache_manager.py           # LLM response caching
│   │   ├── entity_extractor.py        # Entity extraction from text
│   │   └── safe_inference.py          # Confidence scoring and validation
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── scraper_health.py          # Monitor scraper success rates
│   │   ├── data_quality.py            # Validate incoming data
│   │   └── dashboard.py               # Monitoring dashboard
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── continuous.py              # 24/7 monitoring workers
│   │   └── analysis.py                # Deep analysis workers
│   └── api/
│       ├── __init__.py
│       ├── main.py                    # FastAPI application
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── data.py                # Data access endpoints
│       │   ├── intelligence.py        # Intelligence endpoints
│       │   └── monitoring.py          # Monitoring endpoints
│       └── middleware/
│           ├── __init__.py
│           ├── auth.py                # JWT authentication
│           └── rate_limiting.py       # API rate limiting
```

## Week 1: Complete Data Infrastructure (Days 1-7)

### Day 1: Core Infrastructure Setup
**Status**: Foundation setup
**Deliverables**:
- Docker Compose environment with PostgreSQL (pgvector) + Redis + FastAPI
- Complete database schema for all data types
- Basic FastAPI application with health checks
- Environment configuration management

**Key Files**:
- `docker-compose.yml` - Multi-service container setup
- `src/database/schema.sql` - Complete database schema from engineering plan
- `src/database/connection.py` - Database connection management
- `src/api/main.py` - Basic FastAPI app with health endpoints

### Day 2: Resilient Scraper Framework
**Status**: Core scraping infrastructure
**Deliverables**:
- Base scraper class with all resilience features
- Proxy rotation system with health checking
- Adaptive rate limiting that learns from responses
- Change detection using MD5 hashing
- Circuit breaker pattern for error handling

**Key Files**:
- `src/scrapers/base/resilient_scraper.py` - Base class with all features
- `src/scrapers/base/proxy_manager.py` - Proxy rotation and testing
- `src/scrapers/base/rate_limiter.py` - Adaptive rate limiting
- `src/scrapers/base/change_detector.py` - Content change detection

### Days 3-4: API-Based Data Sources (Easy Wins)
**Status**: Structured data sources
**Deliverables**:
- City Permits API scraper (JSON, no auth required)
- Census Bureau API scraper (demographics, economic data)
- Crime Data API scraper (Socrata format)
- Zoning API scraper (land use classifications)

**Why First**: These are reliable, structured APIs with predictable formats

**Key Files**:
- `src/scrapers/sources/city_permits.py`
- `src/scrapers/sources/census_data.py`
- `src/scrapers/sources/crime_data.py`
- `src/scrapers/sources/zoning_data.py`

### Days 5-6: Web Scraping Sources (Medium Complexity)
**Status**: HTML/RSS scraping
**Deliverables**:
- Gainesville Sun news scraper (RSS + article extraction)
- Business Journal scraper (development news focus)
- City Council agenda scraper (meeting schedules)

**Key Files**:
- `src/scrapers/sources/gainesville_sun.py`
- `src/scrapers/sources/business_journal.py`
- `src/scrapers/sources/city_council.py`

### Day 7: Complex Scraping Sources (High Value)
**Status**: JavaScript-heavy sites and bulk downloads
**Deliverables**:
- Property Appraiser bulk downloader (weekly CSV/XML)
- County Permits scraper using Playwright (complex JS site)
- Sunbiz LLC formation monitor (Florida Division of Corporations)

**Key Files**:
- `src/scrapers/sources/property_appraiser.py`
- `src/scrapers/sources/county_permits.py`
- `src/scrapers/sources/sunbiz_llc.py`

## Week 2: Data Validation & Monitoring (Days 8-14)

### Days 8-9: PDF Processing & OCR
**Status**: Document processing
**Deliverables**:
- PDF extraction system for Council Minutes
- OCR integration for scanned documents
- GIS shapefile downloader for property boundaries
- Document parsing and text extraction

**Key Files**:
- `src/scrapers/sources/pdf_extractor.py`
- `src/scrapers/sources/gis_downloader.py`

### Days 10-11: Data Quality & Monitoring
**Status**: Validation and monitoring
**Deliverables**:
- Data quality validation system
- Scraper health monitoring
- Error handling and alerting
- Success rate tracking per source

**Key Files**:
- `src/monitoring/data_quality.py`
- `src/monitoring/scraper_health.py`
- `src/monitoring/dashboard.py`

### Days 12-13: Scheduler & Orchestration
**Status**: Automated data collection
**Deliverables**:
- Scraper scheduler with daily/weekly/monthly tasks
- Task queue management with Redis
- Error recovery and retry logic
- Performance monitoring

**Key Files**:
- `src/scrapers/scheduler.py`
- `src/workers/continuous.py`

### Day 14: Historical Data Backfill
**Status**: Data accumulation
**Deliverables**:
- 6 months of permit data backfill
- 1 year of property sales backfill
- 3 months of news articles backfill
- Complete initial dataset for pattern detection

## Week 3: Intelligence Layer (Days 15-21)

### Days 15-16: Pattern Detection Algorithms
**Status**: Core intelligence
**Deliverables**:
- Property assemblage detection (geographic + temporal patterns)
- LLC formation pattern analyzer (property-related formations)
- Permit sequence analyzer (development intent signals)

**Key Files**:
- `src/intelligence/assemblage_detector.py`
- `src/intelligence/llc_analyzer.py`
- `src/intelligence/permit_sequencer.py`

### Days 17-18: AI Integration
**Status**: Entity extraction and analysis
**Deliverables**:
- Gemini API integration with provider abstraction
- Entity extraction from news and documents
- Confidence scoring system for all inferences
- LLM response caching for cost optimization

**Key Files**:
- `src/ai/llm_adapter.py`
- `src/ai/entity_extractor.py`
- `src/ai/safe_inference.py`
- `src/ai/cache_manager.py`

### Days 19-20: Relationship Mapping
**Status**: Network analysis
**Deliverables**:
- Entity relationship mapping system
- Attorney/agent pattern detection
- Developer network analysis
- Knowledge graph construction

**Key Files**:
- `src/intelligence/relationship_mapper.py`
- Knowledge graph integration in database models

### Day 21: Intelligence Synthesis
**Status**: Combine all signals
**Deliverables**:
- Multi-source signal combination
- Alert generation for high-confidence findings
- Daily intelligence reports
- Pattern confidence scoring

**Key Files**:
- `src/intelligence/synthesis.py`

## Week 4: Production Deployment (Days 22-28)

### Days 22-24: API Development
**Status**: External interfaces
**Deliverables**:
- RESTful API for all data access
- Authentication and authorization
- Rate limiting for API endpoints
- Documentation and testing

**Key Files**:
- `src/api/routes/data.py`
- `src/api/routes/intelligence.py`
- `src/api/middleware/auth.py`

### Days 25-27: Production Deployment
**Status**: Live deployment
**Deliverables**:
- Deploy to Oracle VPS with Docker
- SSL/HTTPS configuration
- Automated backups
- Production monitoring and alerting

### Day 28: System Validation
**Status**: End-to-end testing
**Deliverables**:
- Test all data sources are collecting successfully
- Validate intelligence detection accuracy
- Performance benchmarking
- Cost monitoring setup

## Database Schema (Key Tables)

```sql
-- Immutable raw facts with full provenance
CREATE TABLE raw_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fact_type TEXT NOT NULL, -- 'permit', 'sale', 'news', 'llc_formation'
    source_url TEXT NOT NULL,
    scraped_at TIMESTAMP NOT NULL,
    parser_version TEXT NOT NULL,
    raw_content JSONB NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI-generated inferences with confidence scores
CREATE TABLE ai_inferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inference_type TEXT NOT NULL, -- 'assemblage', 'relationship', 'pattern'
    model_version TEXT NOT NULL,
    confidence_score FLOAT NOT NULL CHECK (confidence_score <= 1),
    inference_content JSONB NOT NULL,
    reasoning TEXT,
    known_uncertainties TEXT[],
    source_fact_ids UUID[] NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Structured entities from facts and inferences
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL, -- 'person', 'company', 'government', 'developer'
    canonical_name TEXT NOT NULL,
    aliases TEXT[],
    fact_based_attributes JSONB,
    inferred_attributes JSONB,
    resolution_confidence FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Properties with factual and inferred data
CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address TEXT NOT NULL,
    parcel_id TEXT UNIQUE,
    coordinates GEOMETRY(POINT, 4326),
    factual_data JSONB, -- From official sources
    inferred_data JSONB, -- From AI analysis
    risk_score FLOAT,
    opportunity_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Entity relationships with confidence
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_id UUID REFERENCES entities(id),
    to_entity_id UUID REFERENCES entities(id),
    relationship_type TEXT NOT NULL, -- 'owns', 'developed', 'represents'
    confidence FLOAT NOT NULL,
    supporting_inference_ids UUID[],
    supporting_fact_ids UUID[],
    first_observed TIMESTAMP,
    last_observed TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- LLM cache for cost optimization
CREATE TABLE llm_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    system_role TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    context_hash TEXT NOT NULL,
    sampler_profile TEXT NOT NULL DEFAULT 'deterministic',
    response JSONB NOT NULL,
    cost_cents INTEGER,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(provider, model_name, system_role, prompt_hash, context_hash, sampler_profile)
);
```

## Daily Scraping Schedule

```python
DAILY_SCRAPING_SCHEDULE = {
    "06:00": {
        "tasks": ["news_scraping"],
        "sources": ["gainesville_sun", "business_journal"],
        "priority": "high",
        "timeout_minutes": 30
    },
    "09:00": {
        "tasks": ["permit_scraping"],
        "sources": ["city_permits", "county_permits"],
        "priority": "high",
        "timeout_minutes": 45
    },
    "10:00": {
        "tasks": ["property_monitoring"],
        "sources": ["property_appraiser"],
        "priority": "medium",
        "timeout_minutes": 60
    },
    "11:00": {
        "tasks": ["llc_monitoring", "crime_data"],
        "sources": ["sunbiz", "crime_api"],
        "priority": "medium",
        "timeout_minutes": 30
    },
    "18:00": {
        "tasks": ["pattern_analysis"],
        "sources": ["assemblage_detector", "relationship_mapper"],
        "priority": "high",
        "timeout_minutes": 90
    }
}

WEEKLY_SCHEDULE = {
    "sunday_02:00": {
        "tasks": ["bulk_property_sync"],
        "sources": ["property_bulk_downloader"],
        "timeout_hours": 4
    },
    "tuesday_08:00": {
        "tasks": ["council_minutes"],
        "sources": ["pdf_extractor"],
        "timeout_minutes": 60
    }
}
```

## Success Metrics

### Data Collection Metrics
- **Source Coverage**: 15+ active data sources
- **Success Rate**: 95%+ for each source
- **Change Detection**: 70% reduction in redundant processing
- **Data Quality**: 90%+ of records pass validation

### Intelligence Metrics
- **Assemblage Detection**: 5+ patterns found per month
- **LLC Monitoring**: 20+ property-related formations per month
- **Confidence Accuracy**: AI confidence scores ±10% of reality
- **Early Detection**: 60+ days ahead of public announcements

### System Performance
- **Uptime**: 99.5%+ for data collection
- **Response Time**: <500ms for API queries
- **Cost**: <$168/month total operational cost
- **Storage**: Efficient data growth management

## Risk Mitigation

### Technical Risks
- **Scraping Blocks**: Proxy rotation, rate limiting, user agent rotation
- **Data Source Changes**: Change detection, validation, alerts
- **API Rate Limits**: Caching, adaptive limiting, fallback sources

### Data Quality Risks
- **False Positives**: Confidence thresholds, human validation
- **Missing Data**: Multiple source redundancy, gap detection
- **Stale Data**: Automated freshness checks, source monitoring

### Cost Risks
- **API Overuse**: Aggressive caching, request monitoring, circuit breakers
- **Storage Growth**: Data retention policies, compression, archiving
- **Processing Costs**: Efficient algorithms, batch processing, optimization

This plan prioritizes getting ALL data sources operational first, then building intelligence on top of a solid foundation. Every component is designed for production reliability from day one.