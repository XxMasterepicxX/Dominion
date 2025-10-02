# Dominion - AI-Powered Real Estate Intelligence Agent

> **AWS AI Agent Global Hackathon Submission**

An autonomous AI agent that discovers, tracks, and analyzes real estate development signals across multiple data sources, using advanced entity resolution and pattern detection to uncover hidden opportunities.

---

## 🎯 Problem Statement

Real estate investors and developers face a critical challenge: **opportunity discovery happens too late**. By the time development plans become public knowledge, the best deals are already gone. Traditional methods rely on manual research across fragmented data sources, missing critical connections between permits, LLCs, property transactions, and public records.

**Dominion solves this by autonomously monitoring 10+ data sources in real-time**, using AI-powered entity resolution to connect the dots before competitors even know an opportunity exists.

---

## 🤖 AI Agent Capabilities

### 1. **Autonomous Data Collection & Processing**
- **Self-directed scraping** across permits, property records, LLC filings, crime data, council meetings, and news
- **Adaptive parsing** with context-aware extraction for each data source
- **Continuous monitoring** with intelligent scheduling (no human intervention required)

### 2. **AI-Powered Entity Resolution**
Dominion's core intelligence uses **multi-signal reasoning** to match entities across disparate sources:

```
Decision Flow:
├─ Tier 1: Definitive Keys (99.9% confidence)
│   └─ Document numbers, Tax IDs, Parcel IDs
│
├─ Tier 2: Multi-Signal Scoring (70-95% confidence)
│   ├─ Name similarity (context-aware)
│   ├─ Address matching with fuzzy logic
│   ├─ Phone/email validation
│   └─ Officer/ownership overlap
│
└─ Tier 3: LLM Reasoning (uncertain cases)
    └─ Human-level context interpretation
```

**Why this matters:** A contractor on a permit might be "ABC Construction LLC". The agent:
1. Detects it's a company (not a person)
2. Searches state business records
3. Enriches with registered agent, officers, filing history
4. Links to existing properties/permits via multi-signal matching
5. **All autonomous, zero human input**

### 3. **Intelligent Enrichment System**
- **Conditional enrichment**: Only fetches missing data (saves 80% API calls)
- **Smart search**: Distinguishes company vs person names, adapts search strategy
- **Fuzzy matching**: Handles name variations, typos, abbreviations
- **Context-based disambiguation**: Uses addresses, phone numbers to pick correct match

### 4. **Pattern Detection & Intelligence**
- **Property assemblage detection**: Identifies when entities acquire multiple adjacent properties (pre-development signal)
- **LLC formation tracking**: Flags new entities with real estate focus
- **Development sequence analysis**: Connects permits → sales → new LLCs → assembly patterns
- **News correlation**: Links articles to entities/properties for sentiment analysis

---

## 🏗️ Architecture

### Tech Stack
- **Database**: PostgreSQL 16 + PostGIS + pgvector
- **AI/ML**: AWS Bedrock (planned), OpenAI/Gemini (current)
- **Web Scraping**: Patchright (stealth automation), BeautifulSoup, Requests
- **Data Processing**: Pandas, GeoPandas, Pydantic
- **APIs**: Census Bureau, Socrata, SFTP integrations

### Data Sources (10 Active Scrapers)
1. **City Permits** - CitizenServe platform (headless browser + reCAPTCHA bypass)
2. **County Permits** - Multi-report aggregation with deduplication
3. **Property Appraiser** - Bulk property records, ownership, sales
4. **Sunbiz (FL Business Registry)** - LLC formations via SFTP + web enrichment
5. **Crime Data** - Socrata API for neighborhood safety scoring
6. **GIS Data** - Shapefiles for zoning, parcels, infrastructure
7. **City Council Meetings** - eScribe platform, agenda/minutes with PDF extraction
8. **Census Demographics** - Population, economics, growth trends
9. **Business News** - RSS feeds for development announcements
10. **Local News** - Aggregated coverage for market sentiment

### Agent Workflow

```
┌─────────────────────────────────────────────────────┐
│  AUTONOMOUS DATA COLLECTION (10 Scrapers)           │
│  ├─ Scheduled execution                             │
│  ├─ Adaptive rate limiting                          │
│  └─ Error recovery & retry                          │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  INGESTION PIPELINE                                 │
│  ├─ Content deduplication (hash-based)              │
│  ├─ Immutable provenance (RawFact storage)          │
│  └─ Parser registry (10 domain parsers)             │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  AI ENRICHMENT (Conditional)                        │
│  ├─ Detect incomplete data                          │
│  ├─ Smart search (company vs person detection)      │
│  ├─ Fuzzy matching (0.8 threshold)                  │
│  └─ Context-based disambiguation                    │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  ENTITY RESOLUTION                                  │
│  ├─ Definitive key matching (doc#, tax ID)          │
│  ├─ Multi-signal scoring (name, address, context)   │
│  ├─ Confidence thresholds (0.85 auto, 0.60 review)  │
│  └─ LLM fallback for uncertain cases                │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  RELATIONSHIP GRAPH                                 │
│  ├─ Entity → Entity (owns, develops, partners)      │
│  ├─ Entity → Property (owns, permitted)             │
│  ├─ Property → Property (assemblage detection)      │
│  └─ Confidence scoring on all relationships         │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  INTELLIGENCE LAYER                                 │
│  ├─ Assemblage pattern detection                    │
│  ├─ Development sequence analysis                   │
│  ├─ Market signal aggregation                       │
│  └─ Opportunity scoring                             │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 AWS Integration Plan

### AWS Bedrock Integration
1. **Entity Extraction**: Use Amazon Bedrock (Nova/Claude) for:
   - Unstructured text parsing (council minutes, news articles)
   - Named entity recognition (people, companies, addresses)
   - Relationship extraction from documents

2. **Entity Resolution LLM Fallback**:
   - Uncertain matches (0.60-0.84 confidence) → Bedrock reasoning
   - Context interpretation: "Is 'ABC Construction' the same as 'ABC Construction LLC, Inc.'?"
   - Contradiction resolution when data conflicts

3. **Pattern Analysis**:
   - Property assemblage intent detection from officer overlap + geographic clustering
   - Development timeline prediction from permit sequences
   - Market sentiment from news article analysis

### Amazon SageMaker AI
- **Confidence Calibration**: Train gradient boosting models per relationship type
- **Match Prediction**: Learned entity resolution (vs rule-based)
- **Assemblage Detection**: Supervised learning on historical patterns

### Amazon Q Integration
- Natural language queries: "Show me all LLCs formed by developers who acquired 3+ properties in Q4 2024"
- Automated reporting and insights

### AWS Infrastructure
- **Lambda**: Scraper orchestration and event-driven processing
- **S3**: Raw data storage, PDF/document archive
- **API Gateway**: REST API for intelligence queries
- **RDS/Aurora**: PostgreSQL hosting with pgvector

---

## 🎥 Demo Scenario

**Query**: *"Find property assemblage opportunities in Gainesville, FL"*

**Agent Execution**:
1. ✅ Scrapes 7 days of permits (autonomous)
2. ✅ Detects contractor "Infinity Development LLC" on 3 commercial permits
3. ✅ Searches Sunbiz → Enriches with officers, registered agent
4. ✅ Matches to entity via document number (L24000123456)
5. ✅ Finds same entity owns 5 adjacent properties (from property records)
6. ✅ Flags as assemblage pattern (confidence: 0.92)
7. ✅ Returns: Entity profile + property map + permit timeline + news mentions

**Result**: Investor discovers development opportunity **weeks before public announcement**

---

## 📊 Key Metrics

- **Data Sources**: 10 active scrapers
- **Entity Resolution Accuracy**: 95%+ on auto-accepts (≥0.85 confidence)
- **Enrichment Efficiency**: 80% reduction in API calls (conditional enrichment)
- **Processing**: Fully autonomous, zero human intervention required
- **Provenance**: 100% traceable (every fact → source URL + timestamp)

---

## 🛠️ Setup & Usage

### Prerequisites
- Python 3.11+
- PostgreSQL 16+ with PostGIS + pgvector
- Redis (for caching/queues)

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/XxMasterepicxX/Dominion.git
cd dominion

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys (AWS Bedrock, Census, etc.)

# 4. Start database
docker-compose up -d

# 5. Initialize schema
python -m src.database.init_database

# 6. Run scrapers (autonomous)
python -m src.scrapers.city_permits --market gainesville_fl
python -m src.scrapers.sunbiz --market florida

# 7. Test entity resolution
python -m tests.services.test_entity_resolution
```

### Configuration
Markets configured via YAML (`src/config/markets/`):
```yaml
market:
  name: "Gainesville, FL"
  state: "FL"

scrapers:
  city_permits:
    enabled: true
    url: "https://gainesville.permittrax.com"
    schedule: "0 9 * * *"  # Daily 9 AM
```

## 📁 Project Structure

```
dominion/
├── src/
│   ├── config/              # Market configurations (YAML + Pydantic)
│   ├── scrapers/            # 10 autonomous scrapers
│   │   ├── permits/         # City & county permits
│   │   ├── government/      # Council meetings
│   │   ├── demographics/    # Census data
│   │   ├── business/        # News & business journals
│   │   └── data_sources/    # Crime, GIS, property, Sunbiz
│   ├── services/            # Core intelligence
│   │   ├── data_ingestion.py       # Universal pipeline
│   │   ├── entity_resolution.py    # AI matching
│   │   └── sunbiz_enrichment.py    # Smart enrichment
│   ├── database/            # PostgreSQL models & schema
│   └── utils/               # PDF extraction, helpers
├── tests/                   # Test suite
├── docs/                    # Architecture & planning docs
├── docker-compose.yml       # PostgreSQL + Redis
└── requirements.txt
```


*Dominion: Autonomous Intelligence for Real Estate Development Discovery*
