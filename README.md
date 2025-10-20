# Dominion – AI-Powered Real Estate Intelligence Agent  
**AWS AI Agent Global Hackathon Submission**

Dominion is an autonomous AI agent designed to discover, track, and analyze real estate development signals across diverse data sources. It leverages advanced entity resolution, multi-source reasoning, and pattern detection to uncover hidden development opportunities before they become public knowledge.

---

## Problem Statement

Real estate investors and developers often face delayed discovery of investment opportunities. By the time development plans surface publicly, competition has already begun. Manual research across fragmented data sources—permits, LLC filings, property records, and public documents—leads to missed insights and inefficiencies.

Dominion solves this challenge through a fully autonomous agent that continuously monitors more than ten data sources in real time. Using AI-powered entity resolution and reasoning, it connects related entities and detects early indicators of real estate activity.

---

## AI Agent Capabilities

### 1. Autonomous Data Collection and Processing
- Automated scraping across permits, business registries, crime data, council meetings, and news sources.  
- Context-aware extraction and adaptive parsing for each source.  
- Intelligent scheduling and error recovery for continuous, unattended operation.

### 2. AI-Powered Entity Resolution
Dominion employs a hierarchical, confidence-based matching system to link entities across sources:
- **Tier 1:** Definitive key matching (document numbers, tax IDs, parcel IDs).  
- **Tier 2:** Multi-signal scoring (name similarity, address matching, ownership overlap).  
- **Tier 3:** LLM-based reasoning for ambiguous matches.  

This system enables accurate cross-referencing of companies, individuals, and properties.

### 3. Intelligent Enrichment System
- Conditional enrichment retrieves only missing data to reduce API overhead.  
- Smart search differentiates between companies and individuals.  
- Fuzzy matching and context-based disambiguation handle variations and incomplete data.

### 4. Pattern Detection and Market Intelligence
- Detects **property assemblage** patterns (entities acquiring adjacent lots).  
- Tracks **LLC formations** associated with new developments.  
- Correlates **permits, sales, and entity changes** to identify development sequences.  
- Conducts **sentiment analysis** from local and business news coverage.

---

## Architecture

### Core Stack
- **Database:** PostgreSQL 16 + PostGIS + pgvector  
- **AI/ML:** AWS Bedrock (Claude, Nova), Amazon SageMaker AI  
- **Web Scraping:** Patchright, BeautifulSoup, Requests  
- **Data Processing:** Pandas, GeoPandas, Pydantic  
- **Integrations:** Census Bureau, Socrata, SFTP sources  

### Data Pipeline Overview
1. **Autonomous Collection:** Ten scrapers execute on a schedule with adaptive throttling.  
2. **Ingestion and Deduplication:** All raw data is hashed, versioned, and stored immutably.  
3. **AI Enrichment:** Missing data is selectively retrieved and contextually validated.  
4. **Entity Resolution:** Multi-signal scoring and LLM reasoning for cross-source linkage.  
5. **Relationship Graph:** Structured mapping between entities, properties, and developments.  
6. **Intelligence Layer:** Detection of assemblage patterns, development trends, and early signals.

---

## AWS Integration

### Amazon Bedrock
- **Entity Extraction:** Process unstructured text (council minutes, permits, articles).  
- **Reasoning:** Handle uncertain matches with contextual interpretation.  
- **Pattern Analysis:** Identify clusters and development trends.

### Amazon SageMaker AI
- **Confidence Calibration:** Train models for entity match prediction.  
- **Pattern Detection:** Supervised learning for property assemblage and ownership networks.

### Amazon Q
- **Natural Language Querying:** Users can ask domain questions such as:  
  “Show all LLCs that acquired three or more properties in Gainesville during Q4 2024.”

### AWS Infrastructure
- **Lambda:** Event-driven scraper orchestration.  
- **S3:** Document and raw data storage.  
- **API Gateway:** RESTful endpoints for queries.  
- **RDS (PostgreSQL):** Vector-enabled relational data store.  

---

## Demo Scenario

**Query:** Find property assemblage opportunities in Gainesville, FL.

**Workflow:**
1. Agent autonomously scrapes recent permit data.  
2. Identifies contractor “Infinity Development LLC” on three projects.  
3. Enriches data via business registry and property records.  
4. Detects ownership of five adjacent parcels.  
5. Flags pattern as “pre-development assemblage.”  

**Result:** The agent surfaces actionable intelligence weeks before public announcement.

---

## Key Metrics
- **Data Sources:** 10+ autonomous scrapers.  
- **Entity Resolution Accuracy:** ≥95% on auto-accepts (≥0.85 confidence).  
- **API Efficiency:** 80% reduction in enrichment calls.  
- **Autonomy:** Full operation without human intervention.  
- **Traceability:** 100% data provenance via source URLs and timestamps.

---

## How to Build and Deploy

### Requirements
- Python 3.11+  
- PostgreSQL 16+ (with PostGIS, pgvector)  
- Redis (optional for caching and queues)  

### Quick Start
```bash
# Clone repository
git clone https://github.com/XxMasterepicxX/Dominion.git
cd Dominion

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add your AWS keys and API credentials

# Start database and services
docker-compose up -d

# Initialize schema
python -m src.database.init_database

# Run scrapers
python -m src.scrapers.city_permits --market gainesville_fl
python -m src.scrapers.sunbiz --market florida

# Test entity resolution
python -m tests.services.test_entity_resolution

*Dominion: Autonomous Intelligence for Real Estate Development Discovery*
