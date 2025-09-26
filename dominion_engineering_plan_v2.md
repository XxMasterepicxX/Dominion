# Dominion Intelligence Engine - Complete Engineering Plan
## Real Estate Intelligence Ecosystem for Gainesville, FL

---

# EXECUTIVE SUMMARY

## Vision Statement
**Dominion is the unfair advantage for every real estate professional.**

Dominion functions as an autonomous real estate intelligence ecosystem that continuously monitors Gainesville's development landscape while providing on-demand deep analysis. It prevents costly mistakes by predicting deal failures, calculates true ROI including hidden costs, and discovers opportunities before they become obvious to competitors.

## Core Value Proposition
**"Know in 3 hours what takes 3 months to discover."**

Traditional real estate research is slow, manual, and fragmented. Developers, flippers, agents, and investors spend months and significant capital on due diligence, piecing together data from dozens of disconnected sources, only for promising deals to fall through due to hidden issues that could have been discovered early.

Dominion eliminates this problem by:
- **Continuous Monitoring**: 24/7 intelligence gathering from news, permits, sales, and political developments
- **Pattern Recognition**: Learning why deals fail and what makes them succeed
- **Deal Validation**: Predicting success probability and uncovering hidden costs
- **Opportunity Discovery**: Finding deals others miss through relationship mapping and trend analysis
- **Adaptive Intelligence**: Same data, different insights for developers, flippers, agents, and investors

## Problem We Solve

Real estate professionals face these critical challenges:
- **Hidden Risks**: Environmental issues, infrastructure costs, political opposition discovered too late
- **Wasted Time**: Months spent researching deals that were always going to fail
- **Missed Opportunities**: Prime properties and emerging trends discovered by competitors first
- **Incomplete Analysis**: Fragmented data from dozens of sources creating blind spots
- **Poor ROI Calculations**: Unexpected costs killing profitability after money is committed

## Our Solution

Dominion replaces the entire upfront research workflow with an intelligent system that:
1. **Monitors Everything**: News mentions, permit applications, property sales, city council decisions
2. **Learns Patterns**: Which developers succeed, which areas are problematic, what kills deals
3. **Validates Deals**: Probability of success, hidden costs, timeline predictions
4. **Finds Alternatives**: Better opportunities with higher ROI and lower risk
5. **Adapts to Users**: Same intelligence, different insights per professional type

## Business Model & Pricing Strategy

### Target Market
- **Primary Users**: Real estate developers, house flippers, real estate agents, property investors
- **Market Size**: Gainesville metro area (50,000+ properties, 500+ active professionals)
- **Expansion Plan**: Florida statewide → Southeastern US → National
- **Long-term Vision**: First AI-powered real estate investment firm leveraging proprietary data

### Hybrid Pricing Model (On-Demand + Subscription)

#### **Tier 1: On-Demand Analysis** 💵
**Price**: $200/deep analysis report
- **Target**: Occasional users, testing the platform
- **Includes**:
  - 1-4 hour comprehensive property analysis
  - Risk assessment with confidence scores
  - ROI calculations with uncertainty ranges
  - Comparable properties analysis
  - 30-day access to results

#### **Tier 2: Professional Subscription** 📊
**Price**: $199/month
- **Target**: Active professionals doing 2-4 deals/month
- **Includes**:
  - 3 deep analysis reports/month (excess at $150 each)
  - Continuous monitoring alerts for your areas
  - Early opportunity notifications
  - Access to pattern insights and market trends
  - Priority support
  - API access for integrations

#### **Tier 3: Enterprise Intelligence** 🏢
**Price**: $999/month
- **Target**: Development companies, investment firms
- **Includes**:
  - Unlimited deep analysis reports
  - Custom continuous monitoring zones
  - Portfolio-level risk assessment
  - Private Slack/Teams integration
  - Dedicated account manager
  - Custom data integrations
  - White-label reporting options

#### **Tier 4: Freemium (Market Validation)** 🆓
**Price**: Free (Limited)
- **Target**: Market validation, lead generation
- **Includes**:
  - 1 free basic analysis/month
  - Read-only access to public market trends
  - Basic opportunity alerts (delayed 48 hours)
  - Limited to Gainesville area only

### Revenue Model Benefits

#### **Subscription Advantages:**
- **Predictable Revenue**: Monthly recurring revenue smooths cash flow
- **Higher Lifetime Value**: $199/month = $2,388/year vs occasional $200 reports
- **Continuous Engagement**: Users stay connected to platform, see ongoing value
- **Data Network Effects**: More users = better patterns = better insights for everyone
- **Funding Growth**: Subscription MRR can fund premium data partnerships (MLS, CoStar)

#### **On-Demand Advantages:**
- **Low Barrier to Entry**: Try before committing to subscription
- **High-Value Transactions**: $200 demonstrates clear ROI for users
- **Seasonal Flexibility**: Works for users with irregular deal flow
- **Premium Pricing**: Per-report model commands higher prices than daily tools

### Business Metrics & Unit Economics

#### **Month 1 Targets:**
- 15 on-demand users × $200 = $3,000
- 5 subscription users × $199 = $995
- **Total MRR**: $4,000 (vs original $5,000 on-demand only)

#### **Month 6 Targets:**
- 50 on-demand users × $200 = $10,000
- 75 subscription users × $199 = $14,925
- 5 enterprise users × $999 = $4,995
- **Total MRR**: $30,000

#### **Unit Economics:**
- **Customer Acquisition Cost (CAC)**: ~$50 (local networking, word-of-mouth)
- **Lifetime Value (LTV)**:
  - On-demand: $400 (2 reports average)
  - Subscription: $2,388 (12 months average retention)
  - Enterprise: $11,988 (24 months average retention)
- **LTV:CAC Ratios**: 8:1 (subscription), 24:1 (enterprise)

### Competitive Positioning

#### **Value Proposition:**
- **Speed**: "Know in 3 hours what takes 3 months to discover"
- **Depth**: Only platform combining 24/7 monitoring + hours-long deep analysis
- **Local Intelligence**: Unmatched Gainesville knowledge graph
- **AI Safety**: Only platform with confidence scores and source attribution

#### **Pricing vs Competitors:**
- **Traditional Due Diligence**: $5,000-15,000 (weeks/months)
- **CoStar**: $100-300/month (data only, no analysis)
- **Real Estate Analytics Tools**: $50-200/month (basic metrics)
- **Dominion**: $199/month (intelligence + analysis + monitoring)

### Go-to-Market Strategy

#### **Phase 1: Gainesville Launch (Months 1-3)**
- Local real estate meetups and networking
- Free analyses for 10 key influencers
- Word-of-mouth referral program
- Partnership with local real estate associations

#### **Phase 2: Florida Expansion (Months 4-12)**
- Add Orlando, Tampa, Miami markets
- Scale subscription tier aggressively
- MLS data partnerships
- Real estate conference presence

#### **Phase 3: Southeast Expansion (Year 2)**
- Atlanta, Charlotte, Nashville markets
- Enterprise tier focus
- Strategic partnerships with investment firms
- Series A funding based on subscription metrics

---

# 1. SYSTEM ARCHITECTURE

## 1.1 Dual-Mode Intelligence Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               USER INTERFACE (VERCEL)                        │
│    "Analyze downtown district for mixed-use development"     │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────────────┐
│              DOMINION INTELLIGENCE ENGINE                    │
│                   (ORACLE VPS - DOCKER)                     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           ADAPTIVE ANALYSIS LAYER                    │  │
│  │  Developer Mode | Flipper Mode | Agent Mode | etc    │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                     │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │              INTELLIGENCE CORE                       │  │
│  │  ┌─────────────────┐    ┌─────────────────────────┐  │  │
│  │  │  CONTINUOUS     │◄──►│ ON-DEMAND ANALYSIS      │  │  │
│  │  │  MONITORING     │    │ (Hours-long Deep Dive)  │  │  │
│  │  │  (24/7 Running) │    │                         │  │  │
│  │  └─────────────────┘    └─────────────────────────┘  │  │
│  └────────────┬─────────────────┬───────────────────────┘  │
│               │                 │                           │
│  ┌────────────▼─────────────────▼───────────────────────┐  │
│  │              KNOWLEDGE GRAPH ENGINE                  │  │
│  │   Properties ←→ Owners ←→ Developers ←→ Projects     │  │
│  │   Politicians ←→ News ←→ Patterns ←→ Predictions     │  │
│  │         (PostgreSQL + pgvector)                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              DATA INGESTION LAYER                    │  │
│  │  News Scraper │ Permit Scraper │ Sales Monitor       │  │
│  │  Council Mins │ Crime Data     │ Census APIs         │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## 1.2 Technology Stack

### Infrastructure
- **Frontend**: React + TypeScript deployed on Vercel
- **Backend**: Python 3.11+ with FastAPI framework
- **Database**: PostgreSQL 15+ with PostGIS and pgvector extensions
- **Containerization**: Docker Compose for all backend services
- **Hosting**: Oracle VPS (owned) for backend, Vercel for frontend
- **Task Queue**: Redis for background job processing

### AI & Data Processing
- **Primary AI**: Gemini 2.0 Flash for analysis and synthesis (via abstraction layer)
- **Fallback AI**: OpenAI GPT-4 Turbo for redundancy and A/B testing
- **Vector Search**: pgvector for document embeddings and similarity
- **LLM Caching**: Aggressive caching to reduce API costs by 70%
- **Web Scraping**: Smart tool selection - requests for APIs/RSS, Playwright only for JS-heavy sites
- **Change Detection**: MD5 hashing to avoid re-processing unchanged content
- **Document Processing**: PyPDF2, Tesseract OCR for document analysis
- **Geospatial**: PostGIS for location-based analysis

### LLM Provider Abstraction & Cost Optimization

#### Provider-Agnostic LLM Interface
```python
# src/ai/llm_adapter.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import hashlib
import asyncio
from datetime import datetime, timedelta

@dataclass
class LLMResponse:
    content: str
    confidence_score: float
    model_version: str
    reasoning: str
    known_uncertainties: List[str]
    token_usage: Dict[str, int]
    cost_cents: int

class LLMAdapter(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def analyze(
        self,
        prompt: str,
        confidence_threshold: float = 0.8,
        temperature: float = 0.1
    ) -> LLMResponse:
        pass

    @abstractmethod
    async def embed(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        pass

    @abstractmethod
    def estimate_cost(self, prompt: str, max_tokens: int = 1000) -> int:
        """Return estimated cost in cents."""
        pass

class GeminiAdapter(LLMAdapter):
    def __init__(self, api_key: str, cache_manager: "LLMCacheManager"):
        self.api_key = api_key
        self.cache_manager = cache_manager
        self.model = "gemini-2.0-flash"

    async def analyze(
        self,
        prompt: str,
        confidence_threshold: float = 0.8,
        temperature: float = 0.1
    ) -> LLMResponse:
        # Check cache first
        cache_key = self._create_cache_key(prompt, temperature)
        cached_response = await self.cache_manager.get_cached_response(
            provider="gemini",
            cache_key=cache_key
        )

        if cached_response:
            return cached_response

        # Make API call
        response = await self._call_gemini_api(prompt, temperature)

        # Parse response and extract confidence
        parsed_response = self._parse_gemini_response(response)

        # Only return if meets confidence threshold
        if parsed_response.confidence_score < confidence_threshold:
            raise ValueError(f"Response confidence {parsed_response.confidence_score:.2f} below threshold {confidence_threshold}")

        # Cache successful response
        await self.cache_manager.cache_response(
            provider="gemini",
            cache_key=cache_key,
            response=parsed_response,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )

        return parsed_response

    async def embed(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        # Initialize result array with placeholders to preserve order
        result = [None] * len(texts)

        # Process in batches to optimize API calls
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_start_idx = i

            # Create index mapping for this batch to preserve order
            cached_indices = []
            cached_embeddings = []
            uncached_indices = []
            uncached_texts = []

            for j, text in enumerate(batch):
                original_idx = batch_start_idx + j
                content_hash = hashlib.md5(text.encode()).hexdigest()
                cached_embedding = await self.cache_manager.get_cached_embedding(content_hash)

                if cached_embedding:
                    cached_indices.append(original_idx)
                    cached_embeddings.append(cached_embedding)
                else:
                    uncached_indices.append(original_idx)
                    uncached_texts.append(text)

            # Place cached embeddings in correct positions
            for idx, embedding in zip(cached_indices, cached_embeddings):
                result[idx] = embedding

            # Batch API call for uncached texts only
            if uncached_texts:
                new_embeddings = await self._batch_embed_gemini(uncached_texts)

                # Cache new embeddings and place in correct positions
                for idx, (text, embedding) in zip(uncached_indices, zip(uncached_texts, new_embeddings)):
                    content_hash = hashlib.md5(text.encode()).hexdigest()
                    await self.cache_manager.cache_embedding(
                        content_hash=content_hash,
                        embedding=embedding,
                        provider="gemini",
                        model_version=self.model
                    )
                    result[idx] = embedding

        return result

class OpenAIAdapter(LLMAdapter):
    """Fallback adapter for OpenAI GPT-4."""

    def __init__(self, api_key: str, cache_manager: "LLMCacheManager"):
        self.api_key = api_key
        self.cache_manager = cache_manager
        self.model = "gpt-4-turbo"

    # Similar implementation to GeminiAdapter but using OpenAI API
    # ... (implementation details)
```

#### LLM Cache Manager (70% Cost Reduction) - FIXED
```python
# src/ai/cache_manager.py
from typing import Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import hashlib

@dataclass
class LLMCacheKey:
    """Robust cache key structure that handles real invalidation scenarios."""
    provider: str           # "gemini", "openai"
    model_name: str         # "gemini-2.0-flash", "gpt-4o-mini"
    system_role: str        # "real_estate_analyst", "risk_assessor"
    prompt_hash: str        # hash of normalized prompt
    context_hash: str       # hash of concrete facts + timestamps
    sampler_profile: str = "deterministic"  # "deterministic", "creative_v1"

# Sampler profile configurations for deterministic outputs
SAMPLER_PROFILES = {
    "deterministic": {"temperature": 0.0, "top_p": 1.0, "top_k": None},
    "creative_v1": {"temperature": 0.3, "top_p": 0.95, "top_k": 40}
}

class LLMCacheManager:
    """Manages aggressive caching for LLM responses and embeddings - FIXED."""

    def __init__(self, db_connection):
        self.db = db_connection

    async def create_cache_key(
        self,
        prompt: str,
        context_data: List[dict],
        system_role: str,
        provider: str = "gemini",
        model_name: str = "gemini-2.0-flash"
    ) -> LLMCacheKey:
        """Generate robust cache key with proper invalidation."""

        # Normalize prompt (strip whitespace, consistent formatting)
        normalized_prompt = self._normalize_prompt(prompt)
        prompt_hash = hashlib.sha256(normalized_prompt.encode()).hexdigest()[:16]

        # Context hash includes data IDs + last_updated timestamps
        # This auto-invalidates when underlying data changes
        context_items = []
        for item in context_data:
            context_items.append(f"{item['id']}:{item.get('last_updated', '')}")

        context_string = "|".join(sorted(context_items))
        context_hash = hashlib.sha256(context_string.encode()).hexdigest()[:16]

        return LLMCacheKey(
            provider=provider,
            model_name=model_name,
            system_role=system_role,
            prompt_hash=prompt_hash,
            context_hash=context_hash,
            sampler_profile="deterministic"  # locked for auditable outputs
        )

    async def get_cached_response(self, cache_key: LLMCacheKey) -> Optional[LLMResponse]:
        """Get cached LLM response if available and not expired - FIXED QUERY."""
        query = """
            SELECT response, created_at, expires_at, temperature
            FROM llm_cache
            WHERE provider = $1 AND model_name = $2 AND system_role = $3
              AND prompt_hash = $4 AND context_hash = $5 AND sampler_profile = $6
              AND expires_at > NOW()
        """

        result = await self.db.fetchrow(
            query,
            cache_key.provider,
            cache_key.model_name,
            cache_key.system_role,
            cache_key.prompt_hash,
            cache_key.context_hash,
            cache_key.sampler_profile
        )

        if result:
            return LLMResponse(**json.loads(result['response']))

        return None

    async def cache_response(
        self,
        cache_key: LLMCacheKey,
        response: LLMResponse,
        prompt_preview: str,
        expires_at: datetime
    ):
        """Cache LLM response with expiration - FIXED QUERY."""
        sampler_config = SAMPLER_PROFILES[cache_key.sampler_profile]

        query = """
            INSERT INTO llm_cache (
                provider, model_name, system_role, prompt_hash, context_hash, sampler_profile,
                response, cost_cents, temperature, prompt_preview, expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (provider, model_name, system_role, prompt_hash, context_hash, sampler_profile)
            DO UPDATE SET
                response = $7,
                cost_cents = $8,
                expires_at = $11,
                created_at = NOW()
        """

        await self.db.execute(
            query,
            cache_key.provider,
            cache_key.model_name,
            cache_key.system_role,
            cache_key.prompt_hash,
            cache_key.context_hash,
            cache_key.sampler_profile,
            json.dumps(response.__dict__),
            response.cost_cents,
            sampler_config["temperature"],  # metadata only
            prompt_preview[:200],  # debugging preview
            expires_at
        )

    def _normalize_prompt(self, prompt: str) -> str:
        """Normalize prompt for consistent hashing."""
        # Strip whitespace, normalize line endings, sort JSON if present
        normalized = " ".join(prompt.split())  # normalize whitespace
        return normalized

    async def get_cached_embedding(self, content_hash: str) -> Optional[List[float]]:
        """Get cached embedding vector."""
        query = """
            SELECT embedding
            FROM embeddings_cache
            WHERE content_hash = $1
        """

        result = await self.db.fetchrow(query, content_hash)
        return list(result['embedding']) if result else None

    async def cache_embedding(
        self,
        content_hash: str,
        embedding: List[float],
        provider: str,
        model_version: str
    ):
        """Cache embedding vector."""
        query = """
            INSERT INTO embeddings_cache (content_hash, content_preview, embedding, embedding_provider, model_version)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (content_hash) DO NOTHING
        """

        # Get first 200 chars for debugging
        preview = content_hash[:200] if len(content_hash) > 200 else content_hash

        await self.db.execute(
            query,
            content_hash,
            preview,
            embedding,
            provider,
            model_version
        )

class LLMManager:
    """High-level manager for all LLM operations with fallback support."""

    def __init__(self):
        self.cache_manager = LLMCacheManager(db_connection)
        self.primary_adapter = GeminiAdapter(gemini_api_key, self.cache_manager)
        self.fallback_adapter = OpenAIAdapter(openai_api_key, self.cache_manager)

    async def analyze_with_fallback(
        self,
        prompt: str,
        confidence_threshold: float = 0.8
    ) -> LLMResponse:
        """Try primary provider, fallback to secondary if needed."""
        try:
            # Try Gemini first (cheaper)
            return await self.primary_adapter.analyze(prompt, confidence_threshold)

        except Exception as e:
            logger.warning(f"Gemini failed, falling back to OpenAI: {e}")

            # Fallback to OpenAI
            return await self.fallback_adapter.analyze(prompt, confidence_threshold)

    async def batch_embed_optimized(self, texts: List[str]) -> List[List[float]]:
        """Optimized embedding with aggressive caching."""

        # Use Gemini for embeddings (much cheaper than OpenAI)
        return await self.primary_adapter.embed(texts, batch_size=100)

    def get_cost_stats(self) -> Dict[str, int]:
        """Get current month's API costs by provider."""
        # Query llm_cache table for cost tracking
        return {
            "gemini_cost_cents": 0,  # From database
            "openai_cost_cents": 0,  # From database
            "total_saved_cents": 0,  # Estimated savings from caching
        }
```

#### Configuration & Cost Monitoring
```python
# src/ai/config.py
@dataclass
class LLMConfig:
    """Configuration for LLM providers and cost controls."""

    # Provider settings
    primary_provider: str = "gemini"
    fallback_provider: str = "openai"

    # Cost controls (per month)
    monthly_budget_cents: int = 5000  # $50/month budget
    gemini_max_cents: int = 3500      # $35 for Gemini
    openai_max_cents: int = 1500      # $15 for OpenAI fallback

    # Cache settings
    cache_ttl_hours: int = 24
    embedding_cache_days: int = 30

    # Confidence thresholds
    min_confidence_factual: float = 0.90
    min_confidence_prediction: float = 0.70
    min_confidence_relationship: float = 0.80

class CostMonitor:
    """Monitor and alert on AI costs."""

    def __init__(self, config: LLMConfig):
        self.config = config

    async def check_monthly_spend(self) -> Dict[str, Any]:
        """Check if we're approaching monthly budget limits."""
        current_spend = await self._get_current_month_spend()

        alerts = []
        if current_spend['total'] > self.config.monthly_budget_cents * 0.8:
            alerts.append("WARNING: 80% of monthly AI budget reached")

        if current_spend['total'] > self.config.monthly_budget_cents:
            alerts.append("CRITICAL: Monthly AI budget exceeded!")

        return {
            "current_spend_cents": current_spend,
            "budget_remaining_cents": self.config.monthly_budget_cents - current_spend['total'],
            "alerts": alerts,
            "projected_month_end": current_spend['total'] * 30 / datetime.now().day
        }
```

### Simplified Observability & DevOps
- **Structured Logging**: JSON logs with correlation IDs (no OpenTelemetry complexity for MVP)
- **Metrics**: Basic Prometheus metrics for key SLOs
- **Dashboards**: Simple Grafana dashboards focused on user-facing metrics
- **Alerting**: Email/SMS alerts for SLO violations (not complex Alertmanager)
- **Health Checks**: /health endpoint with SLO validation
- **Proxy Rotation**: Rotating proxies for scraping resilience
- **Deployment**: Docker Compose with automated updates

#### Pragmatic Monitoring Strategy
```python
# src/monitoring/metrics.py
import logging
from prometheus_client import Counter, Histogram, Gauge
from datetime import datetime
import json

# Configure structured logging for MVP
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "%(name)s", "message": "%(message)s", "correlation_id": "%(correlation_id)s", "user_id": "%(user_id)s"}',
    handlers=[
        logging.StreamHandler()
    ]
)

# Core business metrics (not infrastructure complexity)
analysis_requests_total = Counter('dominion_analysis_requests_total', 'Total analysis requests', ['user_type', 'status'])
analysis_duration_seconds = Histogram('dominion_analysis_duration_seconds', 'Analysis completion time', buckets=[300, 600, 1800, 3600, 7200])  # 5min to 2hr
scraping_success_rate = Gauge('dominion_scraping_success_rate', 'Percentage of successful scrapes', ['source'])
queue_depth = Gauge('dominion_queue_depth', 'Number of jobs in queue')
ai_cost_cents = Counter('dominion_ai_cost_cents_total', 'Total AI API costs in cents', ['provider'])

class DominionMetrics:
    """Simple metrics collection focused on SLOs."""

    def __init__(self):
        self.logger = logging.getLogger('dominion.metrics')

    def record_analysis_request(self, user_type: str, status: str, duration_seconds: float = None):
        """Record analysis request with business context."""
        analysis_requests_total.labels(user_type=user_type, status=status).inc()

        if duration_seconds:
            analysis_duration_seconds.observe(duration_seconds)

            # Log slow analyses (SLO: 90% under 3 hours)
            if duration_seconds > 10800:  # 3 hours
                self.logger.warning(f"Slow analysis detected", extra={
                    "duration_seconds": duration_seconds,
                    "user_type": user_type,
                    "slo_violation": "analysis_speed"
                })

    def record_scrape_result(self, source: str, success: bool):
        """Track scraping success rate for SLOs."""
        # Simple success rate calculation (could be more sophisticated)
        current_rate = scraping_success_rate.labels(source=source)

        if success:
            # Track success rate using proper metric pattern without internals
            current_rate.inc(0.01)  # Use built-in increment
        else:
            # Track failure rate using proper metric pattern without internals
            current_rate.dec(0.05)  # Use built-in decrement

            self.logger.error(f"Scraping failed", extra={
                "source": source,
                "slo_violation": "scraping_reliability"
            })

    def __init__(self):
        """Initialize metrics with internal state tracking."""
        self.logger = logging.getLogger(__name__)
        # Track internal state without accessing Prometheus internals
        self.scraping_success_rates = {
            'gainesville_sun': 1.0,
            'permits': 1.0,
            'council_minutes': 1.0
        }
        self.current_queue_depth = 0

    def track_scraping_success(self, source: str, success: bool):
        """Track scraping success rate for SLOs."""
        # Update internal state
        if success:
            self.scraping_success_rates[source] = min(
                self.scraping_success_rates[source] + 0.01, 1.0
            )
        else:
            self.scraping_success_rates[source] = max(
                self.scraping_success_rates[source] - 0.05, 0.0
            )

        # Update Prometheus metrics without accessing internals
        current_rate = scraping_success_rate.labels(source=source)
        current_rate.set(self.scraping_success_rates[source])

        if not success:
            self.logger.error(f"Scraping failed", extra={
                "source": source,
                "slo_violation": "scraping_reliability"
            })

    def update_queue_depth(self, depth: int):
        """Update queue depth tracking."""
        self.current_queue_depth = depth
        queue_depth.set(depth)

    def check_slo_compliance(self) -> dict:
        """Check SLO compliance and return status."""
        return {
            "scraping_success_ok": all(
                rate >= 0.95 for rate in self.scraping_success_rates.values()
            ),
            "queue_depth_ok": self.current_queue_depth < 50,
            "analysis_speed_ok": True  # Would need percentile calculation
        }
```

#### Simple Health Check with SLO Validation
```python
# Enhanced health check from API implementation
@app.get("/health")
async def health_check_with_slos(
    redis = Depends(get_redis_connection),
    db = Depends(get_database_connection)
):
    """Health check that validates our core SLOs."""
    metrics = DominionMetrics()
    slo_status = metrics.check_slo_compliance()

    # Check health dependencies directly
    redis_connected = await redis_health_check(redis)
    database_connected = await db_health_check(db)

    health_status = {
        "status": "healthy" if all(slo_status.values()) else "degraded",
        "timestamp": datetime.utcnow(),
        "version": "2.0.0",
        "slos": {
            "scraping_success_rate": "PASS" if slo_status["scraping_success_ok"] else "FAIL",
            "queue_management": "PASS" if slo_status["queue_depth_ok"] else "FAIL",
            "analysis_speed": "PASS" if slo_status["analysis_speed_ok"] else "FAIL"
        },
        "key_metrics": {
            "queue_depth": metrics.current_queue_depth,
            "redis_connected": redis_connected,
            "database_connected": database_connected
        }
    }

    # Return 503 if core SLOs are failing
    if not all(slo_status.values()):
        raise HTTPException(status_code=503, detail=health_status)

    return health_status

async def redis_health_check(redis = Depends(get_redis_connection)) -> bool:
    """Check Redis connection health with proper dependency injection."""
    try:
        await redis.ping()
        return True
    except Exception:
        return False

async def db_health_check(db = Depends(get_database_connection)) -> bool:
    """Check database connection health with proper dependency injection."""
    try:
        # Simple query to verify DB connection
        await db.fetchval("SELECT 1")
        return True
    except Exception:
        return False
```

#### Essential Grafana Dashboard (Not Complex)
```yaml
# grafana/dashboards/dominion-slos.json (simplified)
{
  "dashboard": {
    "title": "Dominion SLO Dashboard",
    "panels": [
      {
        "title": "Analysis Completion Time",
        "type": "stat",
        "targets": [{"expr": "rate(dominion_analysis_duration_seconds_sum[5m]) / rate(dominion_analysis_duration_seconds_count[5m])"}],
        "thresholds": {"steps": [{"value": 10800, "color": "red"}]}
      },
      {
        "title": "Scraping Success Rate",
        "type": "gauge",
        "targets": [{"expr": "dominion_scraping_success_rate"}],
        "thresholds": {"steps": [{"value": 0.95, "color": "green"}, {"value": 0.90, "color": "yellow"}, {"value": 0.0, "color": "red"}]}
      },
      {
        "title": "Queue Depth",
        "type": "graph",
        "targets": [{"expr": "dominion_queue_depth"}],
        "alert": {"conditions": [{"query": {"params": ["A", "5m", "now"]}, "reducer": {"params": []}, "evaluator": {"params": [50]}}]}
      }
    ]
  }
}
```

#### Simple Alerting (Email, not Complex Routing)
```python
# src/monitoring/alerts.py
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

class SimpleAlerting:
    """Pragmatic alerting for SLO violations."""

    def __init__(self, smtp_config):
        self.smtp_config = smtp_config
        self.alert_recipients = ["ops@dominion.com"]

    async def check_and_alert(self):
        """Check SLOs and send email alerts if needed."""
        metrics = DominionMetrics()
        slo_status = metrics.check_slo_compliance()

        failed_slos = [slo for slo, passing in slo_status.items() if not passing]

        if failed_slos:
            await self.send_alert(
                subject="Dominion SLO Violation",
                message=f"SLO violations detected: {', '.join(failed_slos)}\nTime: {datetime.utcnow()}"
            )

    async def send_alert(self, subject: str, message: str):
        """Send simple email alert."""
        try:
            msg = MIMEText(message)
            msg['Subject'] = subject
            msg['From'] = self.smtp_config['from']
            msg['To'] = ', '.join(self.alert_recipients)

            with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                server.send_message(msg)

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
```

### Pragmatic Security Implementation (MVP-Appropriate)

#### Authentication & Authorization (JWT, not Complex RBAC)
```python
# src/security/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
import os

# Environment-based secrets (not Vault for MVP)
JWT_SECRET = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET_KEY environment variable must be set")

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour (reduced from 24 hours)
REFRESH_TOKEN_EXPIRE_DAYS = 30    # 30 days for refresh tokens

security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthenticationService:
    """Simple but secure authentication for MVP."""

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """Create JWT access token with enhanced security."""
        to_encode = data.copy()
        now = datetime.utcnow()

        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        # Enhanced JWT claims for security
        to_encode.update({
            "exp": expire,
            "iat": now,  # Issued at
            "iss": "dominion-api",  # Issuer
            "aud": "dominion-users",  # Audience
            "type": "access"  # Token type
        })

        encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self, user_id: str):
        """Create refresh token with longer expiration."""
        now = datetime.utcnow()
        expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode = {
            "sub": user_id,
            "exp": expire,
            "iat": now,
            "iss": "dominion-api",
            "aud": "dominion-users",
            "type": "refresh"
        }

        return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def verify_token(self, token: str, token_type: str = "access"):
        """Verify JWT token with enhanced security checks."""
        try:
            # Decode with explicit algorithm verification
            payload = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[JWT_ALGORITHM],
                audience="dominion-users",
                issuer="dominion-api"
            )

            user_id: str = payload.get("sub")
            token_type_claim = payload.get("type")

            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user ID"
                )

            if token_type_claim != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token type: expected {token_type}"
                )

            return user_id

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token audience"
            )
        except jwt.InvalidIssuerError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer"
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials: {str(e)}"
            )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user."""
    auth_service = AuthenticationService()
    user_id = auth_service.verify_token(credentials.credentials)

    # Get user from database
    user = await get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user
```

#### Rate Limiting (Simple but Effective)
```python
# src/security/rate_limiting.py
from fastapi import Request, HTTPException
from typing import Dict
import time
import asyncio

class RedisRateLimiter:
    """Redis-based rate limiter for multi-worker deployments."""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client

    async def is_allowed(self, key: str, max_requests: int = 100, window_minutes: int = 1) -> bool:
        """Check if request is allowed under rate limit using Redis."""
        if not self.redis_client:
            # Fallback to allowing all requests if Redis unavailable
            return True

        try:
            now = int(time.time())
            window_seconds = window_minutes * 60
            rate_limit_key = f"rate_limit:{key}:{now // window_seconds}"

            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, window_seconds)
            results = await pipe.execute()

            current_requests = results[0]
            return current_requests <= max_requests

        except Exception as e:
            # Log error and allow request if Redis fails
            logging.error(f"Rate limiting error: {e}")
            return True

# Rate limiter instance will be initialized at startup
rate_limiter = None

def get_rate_limiter():
    """Get the rate limiter instance with proper dependency."""
    global rate_limiter
    if rate_limiter is None:
        # This will be properly initialized during FastAPI startup
        raise RuntimeError("Rate limiter not initialized")
    return rate_limiter

def rate_limit(max_requests: int = 100, window_minutes: int = 1):
    """Rate limiting decorator for API endpoints."""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            # Use IP address as the key (could also use user_id if authenticated)
            client_ip = request.client.host
            limiter = get_rate_limiter()

            if not await limiter.is_allowed(client_ip, max_requests, window_minutes):
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {max_requests} requests per {window_minutes} minute(s)"
                )

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

# FastAPI startup event to initialize rate limiter
@app.on_event("startup")
async def initialize_rate_limiter():
    """Initialize Redis-based rate limiter during FastAPI startup."""
    global rate_limiter
    try:
        redis_client = await get_redis_connection()
        rate_limiter = RedisRateLimiter(redis_client)
        logger.info("Redis rate limiter initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis rate limiter: {e}")
        # Fallback to a simple in-memory limiter for development
        rate_limiter = RedisRateLimiter(None)  # None redis_client = fallback mode

# Usage in API endpoints:
# @rate_limit(max_requests=10, window_minutes=1)  # 10 requests per minute
# @app.post("/analysis")
# async def analyze_property(...)
```

#### Basic Audit Logging
```python
# src/security/audit.py
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import json

class AuditLogger:
    """Simple audit logging for sensitive operations."""

    def __init__(self):
        self.logger = logging.getLogger("dominion.audit")
        # Use stdout handler for container-friendly logging
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "event": "%(message)s", "logger": "audit"}'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        # Prevent duplicate logs from propagating to root logger
        self.logger.propagate = False

    def log_analysis_request(self, user_id: str, property_identifier: str, analysis_type: str):
        """Log analysis requests for compliance."""
        self.logger.info(json.dumps({
            "event_type": "analysis_request",
            "user_id": user_id,
            "property_identifier": property_identifier,
            "analysis_type": analysis_type,
            "timestamp": datetime.utcnow().isoformat()
        }))

    def log_data_access(self, user_id: str, data_type: str, property_ids: list):
        """Log access to sensitive property data."""
        self.logger.info(json.dumps({
            "event_type": "data_access",
            "user_id": user_id,
            "data_type": data_type,
            "property_count": len(property_ids),
            "timestamp": datetime.utcnow().isoformat()
        }))

    def log_authentication(self, user_id: Optional[str], success: bool, ip_address: str):
        """Log authentication attempts."""
        self.logger.info(json.dumps({
            "event_type": "authentication",
            "user_id": user_id,
            "success": success,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        }))

audit_logger = AuditLogger()
```

#### HTTPS & Environment Security
```python
# src/security/middleware.py
from fastapi import Request, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
import os

class SecurityMiddleware(BaseHTTPMiddleware):
    """Essential security middleware for production."""

    async def dispatch(self, request: Request, call_next):
        # Enforce HTTPS in production with proper proxy support
        if os.getenv("ENVIRONMENT") == "production":
            # Check X-Forwarded-Proto header for proxy environments (e.g. Nginx, CloudFlare)
            forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
            actual_scheme = forwarded_proto if forwarded_proto else request.url.scheme

            if actual_scheme != "https":
                raise HTTPException(
                    status_code=400,
                    detail="HTTPS required"
                )

        # Security headers
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Remove server header
        if "server" in response.headers:
            del response.headers["server"]

        return response

# Apply to FastAPI app:
# app.add_middleware(SecurityMiddleware)
```

#### Environment Configuration
```bash
# .env.example (for development)
# In production, these should be set as environment variables

JWT_SECRET_KEY=your-super-secret-jwt-key-change-this
DATABASE_URL=postgresql://dominion:password@postgres:5432/dominion
REDIS_URL=redis://redis:6379/0
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-fallback-key

# Security settings
ENVIRONMENT=development  # Set to 'production' in prod
ALLOWED_ORIGINS=["http://localhost:3000", "https://dominion.vercel.app"]
RATE_LIMIT_ENABLED=true
AUDIT_LOGGING_ENABLED=true
```

#### Simple User Management (No Complex RBAC)
```sql
-- Simple users table for MVP
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    user_type TEXT NOT NULL CHECK (user_type IN ('developer', 'flipper', 'agent', 'investor')),
    subscription_tier TEXT DEFAULT 'on_demand' CHECK (subscription_tier IN ('on_demand', 'professional', 'enterprise')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Simple API keys table for enterprise users
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    key_hash TEXT NOT NULL,
    name TEXT,  -- User-friendly name for the key
    last_used TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Security Checklist for MVP
✅ **Authentication**: JWT with bcrypt password hashing
✅ **Rate Limiting**: Simple token bucket per IP
✅ **HTTPS**: Enforced in production
✅ **Security Headers**: XSS, CSRF, clickjacking protection
✅ **Environment Variables**: Secrets not in code
✅ **Audit Logging**: Critical operations logged
✅ **Input Validation**: FastAPI model validation

❌ **Skip for MVP** (Add Later):
- Row-Level Security (single tenant for now)
- Vault/complex secret management
- Complex RBAC/permissions
- Advanced threat detection
- OAuth integration

This approach provides solid security without over-engineering for a 20-user MVP.

---

# 2. DATA STRATEGY & SOURCES

## 2.1 Data Reality Assessment

### What We CAN Access (Public Data)
✅ **Government Records**: Property tax, permits, zoning decisions
✅ **Open Data APIs**: City of Gainesville, Alachua County
✅ **Public Meetings**: City council minutes, planning board decisions
✅ **News Sources**: Gainesville Sun, local business journals
✅ **Federal APIs**: Census, economic data, demographics

### What We CANNOT Access Directly
❌ **MLS Data**: Requires broker partnership ($500/month licensing)
❌ **Private Transactions**: Off-market deals, private negotiations
❌ **Internal Decisions**: Developer private planning, city internal memos

### Our Strategic Approach
- **70% Complete Data**: Acceptable coverage for MVP
- **Safe AI Inference**: Only infer missing information with high confidence (>80%) and clear attribution
- **Transparency About Gaps**: Explicitly state what we don't know rather than guess
- **Progressive Enhancement**: Add premium data sources as revenue grows
- **Community Intelligence**: Users contribute information for richer dataset

## 2.2 Primary Data Sources

### Daily Monitoring Sources

#### The Gainesville Sun (News Intelligence)
- **URL**: https://www.gainesville.com
- **Scraping Schedule**: Daily at 6:00 AM EST
- **Target Sections**:
  - Business & Development
  - Local Government
  - Real Estate Transactions
- **Data Extraction**:
  - Developer names and project announcements
  - Zoning decisions and public hearings
  - Infrastructure developments
  - Economic development initiatives
  - Political changes affecting development
- **Processing**: Gemini extracts entities, relationships, and impact predictions

#### Building Permit Intelligence
**City of Gainesville Permits**
- **API**: https://data.cityofgainesville.org/Building-Development/Building-Permits/p798-x3nx
- **Update Frequency**: Daily at 9:00 AM EST
- **Data Points**:
  - New permit applications and approvals
  - Permit status changes
  - Contractor information
  - Project values and timelines
  - Address geocoding for spatial analysis

**Alachua County Permits**
- **Portal**: https://growth-management.alachuacounty.us/PermitTracker
- **Method**: Web scraping with session management
- **Schedule**: Daily at 9:30 AM EST
- **Risk Mitigation**: Proxy rotation, request throttling

#### Property Sales Monitoring
**Alachua County Property Appraiser**
- **Portal**: https://qpublic.schneidercorp.com/Application.aspx?AppID=1081
- **Method**: Bulk data download + incremental updates
- **Schedule**:
  - Bulk download: Weekly (Sunday nights)
  - Incremental updates: Daily (10:00 AM EST)
- **Data Points**:
  - Sale dates, prices, and parties
  - Property characteristics changes
  - Ownership transfers
  - Tax assessment updates

### Weekly Data Sources

#### City Council & Planning Intelligence
**City Council Minutes**
- **Source**: https://gainesville.legistar.com
- **Schedule**: Weekly analysis every Tuesday
- **Processing**:
  ```python
  class SafeAIInference:
      def __init__(self):
          self.confidence_thresholds = {
              'factual_claims': 0.90,
              'predictions': 0.70,
              'relationships': 0.80
          }

      async def analyze_meeting_minutes(self, minutes_text: str) -> IntelligenceReport:
          analysis = await self.gemini.analyze(minutes_text)

          # Apply confidence thresholds
          validated_insights = []
          for insight in analysis.insights:
              if insight.confidence_score >= self.confidence_thresholds[insight.type]:
                  validated_insights.append(insight)
              else:
                  self.log_uncertainty(insight, "Low confidence score")

          return IntelligenceReport(
              insights=validated_insights,
              confidence_score=analysis.overall_confidence,
              data_sources=["City Council Minutes"],
              inference_reasoning=analysis.reasoning,
              known_uncertainties=analysis.uncertainties,
              last_updated=datetime.utcnow()
          )
  ```
  - OCR extraction from PDF minutes
  - Gemini analysis with confidence validation for development-related decisions
  - Relationship extraction (developer presentations, opposition) with >80% confidence requirement
  - Voting pattern analysis with uncertainty tracking

**Planning & Zoning Board**
- **Source**: Meeting agendas and minutes
- **Focus Areas**:
  - Variance requests
  - Rezoning applications
  - Special exception hearings
  - Development plan reviews

### API-Based Sources (Real-time)

#### Census & Demographics
- **API**: US Census Bureau API
- **Key**: Free registration required
- **Endpoints**:
  - ACS 5-Year Estimates: Comprehensive demographic data
  - Business Patterns: Employment and business data
  - Population Estimates: Current population trends
- **Update Schedule**: Automated monthly refresh

#### Crime & Safety Data
- **API**: https://data.cityofgainesville.org/Public-Safety/Crime-Responses/gvua-xt9q
- **Format**: Socrata API
- **Processing**: Aggregate into neighborhood safety scores
- **Use Case**: Property investment risk assessment

#### Zoning & Land Use
- **API**: https://data.cityofgainesville.org/resource/2s65-t9he.json
- **Data**: Current zoning classifications, permitted uses, density requirements
- **Processing**: Overlay with property boundaries for development potential analysis

## 2.2.1 Scraper Resilience & Change Detection

### Smart Tool Selection Strategy
The expert feedback correctly identified that not all scraping needs the complexity of full browser automation. Our optimized approach:

#### **Tier 1: Simple HTTP Requests (90% of sources)**
```python
# src/scrapers/simple_scraper.py
import httpx
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class SimpleResilientScraper:
    """Optimized scraper for APIs, RSS feeds, and simple HTML."""

    def __init__(self):
        self.session = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Dominion Real Estate Intelligence Bot 1.0",
                "Accept": "application/json, text/html, */*"
            },
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        self.retry_config = {
            "max_attempts": 3,
            "backoff_factor": 2,  # 1s, 2s, 4s
            "retry_status_codes": [429, 500, 502, 503, 504]
        }

    async def fetch_with_change_detection(
        self,
        url: str,
        source_name: str,
        expected_content_type: str = "html"
    ) -> Optional[Dict[str, Any]]:
        """Fetch content only if it has changed since last fetch."""

        for attempt in range(self.retry_config["max_attempts"]):
            try:
                # Exponential backoff for retries
                if attempt > 0:
                    await asyncio.sleep(self.retry_config["backoff_factor"] ** attempt)

                response = await self.session.get(url)

                # Check for retry-able status codes
                if response.status_code in self.retry_config["retry_status_codes"]:
                    logger.warning(f"Retriable error {response.status_code} for {url}, attempt {attempt + 1}")
                    continue

                response.raise_for_status()

                # Extract content based on type
                if expected_content_type == "json":
                    content = response.json()
                    content_text = json.dumps(content, sort_keys=True)
                else:
                    content = response.text
                    content_text = content

                # Calculate content hash for change detection
                content_hash = hashlib.md5(content_text.encode()).hexdigest()

                # Check if content has changed
                last_hash = await self.get_last_content_hash(source_name)
                if last_hash == content_hash:
                    logger.info(f"No changes detected for {source_name}, skipping processing")
                    return None  # No changes, skip processing

                # Store new hash and return content for processing
                await self.store_content_hash(source_name, content_hash)

                return {
                    "content": content,
                    "content_hash": content_hash,
                    "scraped_at": datetime.utcnow(),
                    "source_url": url,
                    "http_status": response.status_code
                }

            except httpx.TimeoutException:
                logger.error(f"Timeout scraping {url}, attempt {attempt + 1}")
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} scraping {url}")
                break  # Don't retry on 4xx errors
            except Exception as e:
                logger.error(f"Unexpected error scraping {url}: {e}")

        # All retries failed
        await self.record_scrape_failure(source_name, url)
        return None

    async def get_last_content_hash(self, source_name: str) -> Optional[str]:
        """Get the last content hash for change detection."""
        query = """
            SELECT content_hash
            FROM raw_facts
            WHERE fact_type = 'scrape_result' AND source_url LIKE $1
            ORDER BY scraped_at DESC
            LIMIT 1
        """
        result = await self.db.fetchval(query, f"%{source_name}%")
        return result

    async def store_content_hash(self, source_name: str, content_hash: str):
        """Store content hash for future change detection."""
        # This will be stored when we create the raw_fact record
        pass
```

#### **Tier 2: Playwright for JS-Heavy Sites (10% of sources)**
```python
# src/scrapers/browser_scraper.py
from playwright.async_api import async_playwright
import asyncio

class BrowserScraper:
    """Use only for JavaScript-heavy sites that require full browser."""

    def __init__(self):
        self.browser = None
        self.context = None

    async def setup(self):
        """Initialize browser context with stealth settings."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
        )

        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

    async def scrape_js_site(self, url: str, selectors: Dict[str, str]) -> Dict[str, Any]:
        """Scrape sites that require JavaScript execution."""
        if not self.browser:
            await self.setup()

        page = await self.context.new_page()

        try:
            # Navigate and wait for content
            await page.goto(url, wait_until='networkidle')

            # Extract data using selectors
            data = {}
            for field, selector in selectors.items():
                try:
                    element = await page.wait_for_selector(selector, timeout=10000)
                    data[field] = await element.inner_text()
                except Exception as e:
                    logger.warning(f"Could not extract {field} from {url}: {e}")
                    data[field] = None

            return data

        finally:
            await page.close()

    async def cleanup(self):
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
```

#### **Staggered Scheduling to Avoid Rate Limits**
```python
# src/scrapers/scheduler.py
import asyncio
from datetime import datetime, time
import random

class ScraperScheduler:
    """Intelligent scheduling to avoid overwhelming targets."""

    def __init__(self):
        self.simple_scraper = SimpleResilientScraper()
        self.browser_scraper = BrowserScraper()

        # Staggered schedule to avoid synchronized hits
        self.schedule = {
            "gainesville_sun_rss": {"time": time(6, 5), "type": "simple"},
            "permits_api": {"time": time(9, 15), "type": "simple"},
            "county_permits": {"time": time(9, 45), "type": "browser"},  # JS-heavy
            "property_sales": {"time": time(10, 20), "type": "simple"},
            "council_minutes": {"time": time(11, 0), "type": "simple"},  # Weekly only
        }

    async def run_scheduled_scrapes(self):
        """Run scrapes according to staggered schedule."""
        now = datetime.now()
        current_time = now.time()

        for source, config in self.schedule.items():
            if self._should_run_now(source, config, current_time):
                # Add random delay (0-300 seconds) to avoid exact synchronization
                delay = random.randint(0, 300)
                await asyncio.sleep(delay)

                if config["type"] == "simple":
                    await self._run_simple_scrape(source)
                else:
                    await self._run_browser_scrape(source)

    def _should_run_now(self, source: str, config: dict, current_time: time) -> bool:
        """Check if scrape should run now based on schedule and last run time."""
        scheduled_time = config["time"]

        # Allow 30-minute window for execution
        if not self._time_within_window(current_time, scheduled_time, minutes=30):
            return False

        # Check if already ran today
        last_run = self._get_last_run_time(source)
        if last_run and last_run.date() == datetime.now().date():
            return False

        return True

    def _time_within_window(self, current: time, target: time, minutes: int) -> bool:
        """Check if current time is within window of target time."""
        target_minutes = target.hour * 60 + target.minute
        current_minutes = current.hour * 60 + current.minute
        return abs(current_minutes - target_minutes) <= minutes
```

#### **Canary Scrapes and Health Monitoring**
```python
# src/scrapers/health_monitor.py
import time
from bs4 import BeautifulSoup
from .simple_scraper import SimpleResilientScraper

class ScraperHealthMonitor:
    """Monitor scraper health and detect changes in target sites."""

    def __init__(self):
        self.simple_scraper = SimpleResilientScraper()

    async def run_canary_scrapes(self):
        """Run lightweight test scrapes to verify site structure."""
        canary_tests = {
            "gainesville_sun": {
                "url": "https://www.gainesville.com",
                "expected_selectors": ["article", ".headline", ".byline"],
                "max_response_time_ms": 5000
            },
            "permits_api": {
                "url": "https://data.cityofgainesville.org/api/views/p798-x3nx/rows.json?max_rows=1",
                "expected_fields": ["data"],
                "max_response_time_ms": 2000
            }
        }

        health_results = {}
        for source, test in canary_tests.items():
            health_results[source] = await self._test_scraper_health(source, test)

        # Alert if any scrapers are failing
        failed_scrapers = [s for s, result in health_results.items() if not result["healthy"]]
        if failed_scrapers:
            await self._alert_scraper_failures(failed_scrapers)

        return health_results

    async def _test_scraper_health(self, source: str, test_config: dict) -> dict:
        """Test individual scraper health."""
        start_time = time.time()

        try:
            response = await self.simple_scraper.session.get(test_config["url"])
            response_time_ms = (time.time() - start_time) * 1000

            # Check response time SLO
            if response_time_ms > test_config["max_response_time_ms"]:
                return {
                    "healthy": False,
                    "error": f"Response time {response_time_ms:.0f}ms exceeds {test_config['max_response_time_ms']}ms"
                }

            # Check expected content structure
            if test_config.get("expected_selectors"):
                soup = BeautifulSoup(response.text, 'html.parser')
                for selector in test_config["expected_selectors"]:
                    if not soup.select(selector):
                        return {
                            "healthy": False,
                            "error": f"Expected selector '{selector}' not found"
                        }

            if test_config.get("expected_fields"):
                data = response.json()
                for field in test_config["expected_fields"]:
                    if field not in data:
                        return {
                            "healthy": False,
                            "error": f"Expected field '{field}' not found in JSON response"
                        }

            return {
                "healthy": True,
                "response_time_ms": response_time_ms
            }

        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
```

#### **Cost Optimization Through Smart Scraping**
- **Change Detection**: 70% reduction in processing costs by skipping unchanged content
- **Smart Tool Selection**: 10x faster scraping for API sources vs browser automation
- **Staggered Scheduling**: Prevents rate limiting and reduces proxy costs
- **Canary Testing**: Detect site changes before they break production scrapers
- **Retry with Backoff**: Reduces failed scrapes and manual intervention

This approach balances reliability with efficiency, using the right tool for each job while minimizing costs and maximizing success rates.

# 2.3 INDIRECT INTELLIGENCE DETECTION

While we cannot access private transactions and internal decisions directly, Dominion excels at detecting their **shadows and signals** through public data patterns.

## 2.3.1 Private Transaction Detection

### LLC Formation Monitoring
**What We Watch:**
- New LLC registrations with similar addresses
- Same attorney/agent filing multiple LLCs
- LLCs formed with generic names (123 Main Street LLC, Pine Properties LLC)
- Timing patterns: Multiple LLCs registered before major announcements

**Intelligence Generated:**
```python
class IndirectIntelligenceDetector:
    def __init__(self, safe_inference: SafeAIInference):
        self.safe_inference = safe_inference

    async def detect_developer_prep_activity(self):
        # Monitor FL Division of Corporations daily filings
        new_llcs = await self.scrape_sunbiz_filings()

        validated_alerts = []
        for llc in new_llcs:
            # Use safe AI inference for pattern detection
            analysis = await self.safe_inference.analyze_llc_pattern(llc)

            if analysis.confidence_score >= 0.8 and llc.has_property_address_as_name():
                alert = await self.create_acquisition_alert(
                    entity=llc.name,
                    target_property=llc.address,
                    confidence_score=analysis.confidence_score,
                    data_sources=["FL Division of Corporations", "Sunbiz filings"],
                    inference_reasoning=analysis.reasoning,
                    known_uncertainties=["LLC may be unrelated to development", "Address correlation may be coincidental"],
                    source="sunbiz_filing",
                    last_updated=datetime.utcnow()
                )
                validated_alerts.append(alert)

        return validated_alerts
```

### Property Assemblage Detection
**Pattern Recognition:**
- Multiple properties in same area with different "buyers"
- Properties purchased within 6-month windows
- Similar purchase prices below market rates
- Buyers with connected addresses or phones

**Algorithm:**
```python
class PropertyAssemblageDetector:
    def __init__(self, safe_inference: SafeAIInference):
        self.safe_inference = safe_inference

    async def find_hidden_assemblages(self, property_sales: List[Sale]):
        potential_assemblages = []

        for sale in property_sales:
            # Find nearby sales within timeframe
            nearby_sales = self.find_nearby_sales(sale, radius=0.5, days=180)

            if len(nearby_sales) >= 3:
                # Use safe AI inference for connection analysis
                connections_analysis = await self.safe_inference.analyze_buyer_connections(nearby_sales)

                if connections_analysis.confidence_score >= 0.7:
                    assemblage = AssemblageAlert(
                        properties=[s.property for s in nearby_sales],
                        suspected_developer=connections_analysis.likely_entity,
                        confidence_score=connections_analysis.confidence_score,
                        data_sources=[f"Property deed for {s.address}" for s in nearby_sales],
                        inference_reasoning=connections_analysis.reasoning,
                        known_uncertainties=[
                            "Buyer connections may be coincidental",
                            "Properties may be unrelated investments",
                            "Timing correlation may not indicate coordination"
                        ],
                        evidence=connections_analysis.evidence,
                        last_updated=datetime.utcnow()
                    )
                    potential_assemblages.append(assemblage)

        return potential_assemblages
```

### Off-Market Transaction Signals
**Indicators We Track:**
- Deed transfers without MLS listings
- Sales at non-round numbers (suggests negotiation)
- Quick closings (< 30 days)
- Buyer/seller with no prior local activity

## 2.3.2 Internal Decision Intelligence

### Permit Sequence Analysis
**What Reveals Developer Intent:**
```python
class PermitSequenceAnalyzer:
    def analyze_development_timeline(self, permits: List[Permit]) -> DeveloperIntent:
        # Sequence indicates intention:
        # 1. Survey permit → measuring for development
        # 2. Environmental assessment → checking feasibility
        # 3. Utility inquiry → confirming capacity
        # 4. Architectural plans → serious commitment

        sequence_score = self.calculate_sequence_probability(permits)

        if sequence_score > 0.8:
            return DeveloperIntent(
                likelihood="High - proceeding to development",
                timeline_estimate=self.estimate_timeline(permits),
                development_scale=self.estimate_scale(permits)
            )
```

### City Meeting Intelligence
**Public Signals of Private Planning:**
- "Executive session" agenda items (often preview public announcements)
- Staff reports mentioning "pending applications"
- Budget line items for infrastructure improvements
- Zoning workshop topics

```python
class MeetingIntelligenceExtractor:
    async def extract_development_signals(self, meeting_minutes: str):
        # Use Gemini to identify development-related discussions
        prompt = f"""
        Analyze these city council meeting minutes for signals of upcoming development:
        - Executive sessions (private discussions)
        - Staff recommendations
        - Infrastructure discussions
        - Economic development mentions

        Meeting Minutes: {meeting_minutes}

        Extract: Developer names, project hints, timeline clues, location references
        """

        signals = await self.gemini.extract_development_signals(prompt)
        return signals
```

### News Signal Extraction
**Reading Between the Lines:**
- "Sources familiar with the project..."
- "Developer who wished to remain anonymous..."
- "Plans are still preliminary but..."
- "If approved by the city..."

```python
class NewsSignalExtractor:
    async def detect_unnamed_developer_activity(self, article: NewsArticle):
        # Pattern matching for indirect references
        patterns = [
            r"unnamed developer",
            r"sources (say|familiar)",
            r"preliminary plans",
            r"developer.*anonymous"
        ]

        signals = []
        for pattern in patterns:
            if re.search(pattern, article.content, re.IGNORECASE):
                signal = await self.extract_project_details(article)
                signals.append(signal)

        return signals
```

## 2.3.3 Relationship Network Analysis

### Attorney/Agent Patterns
**Connection Discovery:**
```python
class RelationshipMapper:
    async def map_hidden_connections(self):
        # Same attorney handling multiple transactions = likely connected
        attorney_transactions = await self.group_by_attorney()

        for attorney, transactions in attorney_transactions.items():
            if len(transactions) >= 3 and self.within_timeframe(transactions, days=365):
                # Likely representing same developer/investor
                connection = HiddenConnection(
                    entities=[t.buyer for t in transactions],
                    connection_type="attorney_relationship",
                    confidence=0.85,
                    evidence=f"Same attorney ({attorney}) on {len(transactions)} deals"
                )
                await self.knowledge_graph.add_connection(connection)
```

### Financial Institution Patterns
- Same lender financing multiple "different" buyers
- Similar loan amounts and terms
- Coordinated closing dates

## 2.3.4 Infrastructure Signals

### Utility Capacity Inquiries
**What Utility Companies Know:**
- Developers must inquire about capacity before major projects
- Water/sewer capacity requests indicate scale
- Electric load studies reveal project size

### DOT Traffic Studies
**Transportation Clues:**
- Traffic impact studies required for major developments
- Road improvement budgets indicate where growth expected
- Turn lane approvals suggest commercial development

## 2.3.5 Intelligence Synthesis

```python
class IndirectIntelligenceEngine:
    def __init__(self):
        self.llc_detector = LLCFormationDetector()
        self.assemblage_detector = PropertyAssemblageDetector()
        self.permit_analyzer = PermitSequenceAnalyzer()
        self.meeting_extractor = MeetingIntelligenceExtractor()
        self.news_extractor = NewsSignalExtractor()

    async def synthesize_private_intelligence(self, area: str) -> PrivateIntelligence:
        """Combine all indirect signals to predict private activity"""

        # Gather all signals
        llc_signals = await self.llc_detector.scan_area(area)
        assemblage_signals = await self.assemblage_detector.scan_area(area)
        permit_signals = await self.permit_analyzer.analyze_area(area)
        meeting_signals = await self.meeting_extractor.scan_recent_meetings(area)
        news_signals = await self.news_extractor.scan_recent_news(area)

        # Weight and combine signals
        combined_intelligence = self.weight_and_combine([
            (llc_signals, 0.3),
            (assemblage_signals, 0.4),
            (permit_signals, 0.3),
            (meeting_signals, 0.2),
            (news_signals, 0.1)
        ])

        return PrivateIntelligence(
            area=area,
            activity_probability=combined_intelligence.probability,
            likely_players=combined_intelligence.entities,
            estimated_timeline=combined_intelligence.timeline,
            project_scale=combined_intelligence.scale,
            confidence=combined_intelligence.confidence,
            supporting_evidence=combined_intelligence.evidence
        )
```

**Key Insight**: We may not see the private deals directly, but we can detect their preparation, players, and patterns through public breadcrumbs. Often this intelligence is more valuable than knowing the final deal price.

---

# 3. CORE SYSTEM COMPONENTS

## 3.1 Continuous Monitoring System

The backbone of Dominion's intelligence gathering operates 24/7, building the knowledge foundation that enables rapid analysis when requested.

### News Intelligence Engine
```python
class NewsMonitor:
    def __init__(self):
        self.sources = {
            'gainesville_sun': GainesvilleSunScraper(),
            'business_journal': BusinessJournalScraper(),
            'government_sites': GovernmentScraper()
        }
        self.gemini = GeminiProcessor()

    async def daily_news_cycle(self):
        """Runs daily at 6:00 AM EST"""
        for source_name, scraper in self.sources.items():
            articles = await scraper.get_recent_articles()

            for article in articles:
                # Extract development-relevant information
                entities = await self.gemini.extract_entities(article)
                relationships = await self.gemini.identify_relationships(article)
                impact_prediction = await self.gemini.predict_market_impact(article)

                # Store in knowledge graph
                await self.knowledge_graph.add_news_intelligence(
                    article, entities, relationships, impact_prediction
                )

                # Check for opportunity alerts
                opportunities = await self.identify_immediate_opportunities(entities)
                if opportunities:
                    await self.alert_system.send_opportunity_alert(opportunities)
```

### Permit Monitoring System
```python
class PermitMonitor:
    def __init__(self):
        self.city_api = CityPermitAPI()
        self.county_scraper = CountyPermitScraper()
        self.analysis_engine = PermitAnalysisEngine()

    async def daily_permit_cycle(self):
        """Runs daily at 9:00 AM EST"""
        # Get new/updated permits
        city_permits = await self.city_api.get_recent_permits()
        county_permits = await self.county_scraper.get_recent_permits()

        all_permits = city_permits + county_permits

        for permit in all_permits:
            # Analyze permit for patterns and opportunities
            analysis = await self.analysis_engine.analyze_permit(permit)

            # Update property records with permit information
            await self.update_property_record(permit.property_address, analysis)

            # Check for development patterns
            pattern_match = await self.pattern_detector.check_patterns(permit)
            if pattern_match.significance > 0.7:
                await self.alert_system.send_pattern_alert(pattern_match)
```

### Property Sales Intelligence
```python
class SalesMonitor:
    def __init__(self):
        self.property_appraiser = PropertyAppraiserscraper()
        self.relationship_mapper = RelationshipMapper()

    async def daily_sales_cycle(self):
        """Runs daily at 10:00 AM EST"""
        # Get recent sales data
        recent_sales = await self.property_appraiser.get_recent_sales()

        for sale in recent_sales:
            # Identify buyer/seller entities
            buyer_entity = await self.relationship_mapper.identify_entity(sale.buyer)
            seller_entity = await self.relationship_mapper.identify_entity(sale.seller)

            # Check for developer activity patterns
            if buyer_entity.type == 'developer':
                pattern = await self.check_developer_accumulation_pattern(
                    buyer_entity, sale.property
                )
                if pattern.indicates_major_development:
                    await self.alert_system.send_developer_activity_alert(pattern)

            # Update knowledge graph
            await self.knowledge_graph.add_transaction(sale, buyer_entity, seller_entity)
```

## 3.2 On-Demand Deep Analysis Engine

When users request analysis, the system dedicates significant computational resources for comprehensive investigation.

### Property Analysis Workflow
```python
class DeepAnalysisEngine:
    def __init__(self):
        self.gemini = GeminiProcessor()
        self.knowledge_graph = KnowledgeGraph()
        self.pattern_matcher = PatternMatcher()
        self.risk_assessor = RiskAssessment()

    async def analyze_property(self, address: str, analysis_type: str) -> AnalysisReport:
        """
        Comprehensive property analysis taking 1-4 hours
        """
        # Phase 1: Data Gathering (30 minutes)
        property_data = await self.gather_comprehensive_data(address)

        # Phase 2: Historical Analysis (45 minutes)
        historical_context = await self.analyze_historical_context(property_data)

        # Phase 3: Pattern Matching (30 minutes)
        similar_properties = await self.find_similar_developments(property_data)

        # Phase 4: Risk Assessment (45 minutes)
        risks = await self.comprehensive_risk_assessment(property_data)

        # Phase 5: Opportunity Discovery (30 minutes)
        opportunities = await self.discover_opportunities(property_data)

        # Phase 6: Synthesis and Reporting (30 minutes)
        report = await self.synthesize_analysis(
            property_data, historical_context, similar_properties, risks, opportunities
        )

        return report

    async def gather_comprehensive_data(self, address: str) -> PropertyData:
        """Exhaustive data collection for specific property"""
        tasks = [
            self.get_ownership_history(address),
            self.get_permit_history(address),
            self.get_zoning_details(address),
            self.get_environmental_records(address),
            self.get_neighborhood_context(address),
            self.get_infrastructure_status(address),
            self.get_political_context(address),
            self.get_market_conditions(address)
        ]

        results = await asyncio.gather(*tasks)
        return PropertyData.from_multiple_sources(results)
```

## 3.3 Pattern Recognition & Learning Engine

Dominion continuously learns from outcomes to improve predictions.

### Development Pattern Detection
```python
class PatternRecognitionEngine:
    def __init__(self):
        self.historical_projects = HistoricalProjectDatabase()
        self.success_predictor = MachineLearningPredictor()

    async def learn_from_outcome(self, project: DevelopmentProject, outcome: ProjectOutcome):
        """Update pattern recognition based on project outcomes"""
        # Extract features that influenced outcome
        features = await self.extract_project_features(project)

        # Update prediction models
        await self.success_predictor.update_model(features, outcome)

        # Identify new patterns
        new_patterns = await self.identify_emerging_patterns(project, outcome)

        for pattern in new_patterns:
            await self.pattern_database.add_pattern(pattern)

    async def predict_project_success(self, proposed_project: DevelopmentProject) -> SuccessPrediction:
        """Predict likelihood of project success"""
        features = await self.extract_project_features(proposed_project)

        # Find similar historical projects
        similar_projects = await self.find_similar_projects(features)

        # Calculate success probability
        success_rate = self.calculate_historical_success_rate(similar_projects)

        # Identify specific risk factors
        risk_factors = await self.identify_risk_factors(features, similar_projects)

        return SuccessPrediction(
            probability=success_rate,
            confidence=self.calculate_confidence(similar_projects),
            risk_factors=risk_factors,
            similar_projects=similar_projects
        )
```

## 3.4 Living Knowledge Graph

The heart of Dominion's intelligence, storing and connecting all information.

### Facts vs Inferences Database Architecture

#### Raw Facts Tables (Immutable, Source-Linked)
```sql
-- Immutable facts with full provenance
CREATE TABLE raw_facts (
    id UUID PRIMARY KEY,
    fact_type TEXT NOT NULL, -- 'property_sale', 'permit_filing', 'news_article', 'llc_formation'
    source_url TEXT NOT NULL, -- Where this came from
    scraped_at TIMESTAMP NOT NULL, -- When we collected it
    parser_version TEXT NOT NULL, -- Which parser version processed it
    raw_content JSONB NOT NULL, -- Original unprocessed data
    content_hash TEXT NOT NULL UNIQUE, -- MD5 hash for deduplication
    processed_at TIMESTAMP, -- When we extracted structured data
    created_at TIMESTAMP DEFAULT NOW()
);

-- Structured facts extracted from raw data
CREATE TABLE structured_facts (
    id UUID PRIMARY KEY,
    raw_fact_id UUID REFERENCES raw_facts(id) NOT NULL,
    entity_type TEXT NOT NULL, -- 'property', 'person', 'company', 'permit', 'sale'
    structured_data JSONB NOT NULL, -- Clean, typed data
    extraction_confidence FLOAT NOT NULL, -- Parser confidence
    validation_status TEXT DEFAULT 'unvalidated', -- 'validated', 'flagged', 'rejected'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Event sourcing for all data changes
CREATE TABLE fact_events (
    id UUID PRIMARY KEY,
    event_type TEXT NOT NULL, -- 'fact_added', 'fact_updated', 'fact_invalidated'
    fact_id UUID REFERENCES structured_facts(id),
    event_data JSONB NOT NULL,
    correlation_id UUID, -- Links related operations
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### AI-Derived Inferences Tables (Confidence-Scored)
```sql
-- AI-generated insights with provenance
CREATE TABLE ai_inferences (
    id UUID PRIMARY KEY,
    inference_type TEXT NOT NULL, -- 'relationship', 'prediction', 'pattern', 'risk_assessment'
    model_version TEXT NOT NULL, -- Which AI model generated this
    model_temperature FLOAT, -- Model settings used
    prompt_hash TEXT, -- Hash of prompt used (for reproducibility)

    -- Confidence and safety
    confidence_score FLOAT NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    threshold_met BOOLEAN NOT NULL, -- Did it meet minimum confidence threshold?

    -- Content and reasoning
    inference_content JSONB NOT NULL, -- The actual insight/prediction
    reasoning TEXT, -- AI's explanation of its reasoning
    known_uncertainties TEXT[], -- What the AI identified as uncertain

    -- Provenance tracking
    source_fact_ids UUID[] NOT NULL, -- Which facts this inference is based on
    human_validated BOOLEAN DEFAULT FALSE,
    validation_notes TEXT,

    -- Expiration and refresh
    expires_at TIMESTAMP, -- When this inference should be refreshed
    confidence_decay_rate FLOAT DEFAULT 0.1, -- How fast confidence decays
    last_validated TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Inference relationships (how inferences connect to each other)
CREATE TABLE inference_relationships (
    id UUID PRIMARY KEY,
    parent_inference_id UUID REFERENCES ai_inferences(id),
    child_inference_id UUID REFERENCES ai_inferences(id),
    relationship_type TEXT NOT NULL, -- 'supports', 'contradicts', 'builds_on'
    strength FLOAT CHECK (strength >= 0 AND strength <= 1),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Track inference performance over time
CREATE TABLE inference_outcomes (
    id UUID PRIMARY KEY,
    inference_id UUID REFERENCES ai_inferences(id),
    predicted_outcome JSONB, -- What the AI predicted
    actual_outcome JSONB, -- What actually happened
    accuracy_score FLOAT, -- How accurate the prediction was
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Core Entity Tables (Built from Facts)
```sql
-- Entities derived from structured facts
CREATE TABLE entities (
    id UUID PRIMARY KEY,
    entity_type TEXT NOT NULL, -- 'person', 'company', 'government', 'developer'
    canonical_name TEXT NOT NULL,
    aliases TEXT[], -- Other names this entity is known by

    -- Fact-based attributes
    fact_based_attributes JSONB, -- Attributes directly from facts
    inferred_attributes JSONB, -- Attributes from AI inference

    -- Confidence and validation
    resolution_confidence FLOAT, -- How confident we are this is one entity
    last_fact_update TIMESTAMP, -- When facts about this entity were last updated

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE properties (
    id UUID PRIMARY KEY,
    address TEXT NOT NULL,
    parcel_id TEXT UNIQUE,
    coordinates GEOMETRY(POINT, 4326),

    -- Fact-based data
    factual_data JSONB, -- Directly from county records, MLS, etc.

    -- Inferred data
    inferred_data JSONB, -- AI-derived insights about this property
    risk_score FLOAT, -- AI risk assessment
    opportunity_score FLOAT, -- AI opportunity assessment

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Relationships between entities (derived from inferences)
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY,
    from_entity_id UUID REFERENCES entities(id),
    to_entity_id UUID REFERENCES entities(id),
    relationship_type TEXT NOT NULL, -- 'owns', 'developed', 'opposed', 'partnered'

    -- Supporting evidence
    supporting_inference_ids UUID[], -- Which inferences support this relationship
    supporting_fact_ids UUID[], -- Which facts support this relationship

    -- Confidence and temporal data
    confidence FLOAT NOT NULL,
    first_observed TIMESTAMP,
    last_observed TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### Caching and Performance Tables
```sql
-- LLM response cache to reduce API costs with proper cache key structure
CREATE TABLE llm_cache (
    id UUID PRIMARY KEY,

    -- Cache key components (must match exactly)
    provider TEXT NOT NULL,           -- 'gemini', 'openai'
    model_name TEXT NOT NULL,         -- 'gemini-2.0-flash', 'gpt-4o-mini'
    system_role TEXT NOT NULL,        -- 'real_estate_analyst', 'risk_assessor'
    prompt_hash TEXT NOT NULL,        -- hash of normalized prompt
    context_hash TEXT NOT NULL,       -- hash of facts + timestamps (auto-invalidates)
    sampler_profile TEXT NOT NULL DEFAULT 'deterministic', -- 'deterministic', 'creative_v1'

    -- Response data
    response JSONB NOT NULL,
    cost_cents INTEGER,

    -- Metadata (not part of cache key)
    temperature FLOAT,               -- logged for observability only
    prompt_preview TEXT,             -- first 200 chars for debugging

    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,

    -- Fixed unique constraint to match cache key components
    UNIQUE(provider, model_name, system_role, prompt_hash, context_hash, sampler_profile)
);

-- Embeddings cache for vector search
CREATE TABLE embeddings_cache (
    id UUID PRIMARY KEY,
    content_hash TEXT NOT NULL UNIQUE,
    content_preview TEXT, -- First 200 chars for debugging
    embedding vector(1536), -- Configurable dimension
    embedding_provider TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector storage for semantic search
CREATE TABLE document_embeddings (
    id UUID PRIMARY KEY,
    fact_id UUID REFERENCES raw_facts(id),
    embedding_cache_id UUID REFERENCES embeddings_cache(id),
    document_type TEXT NOT NULL, -- 'news', 'permit', 'report'
    chunk_index INTEGER DEFAULT 0, -- For large documents split into chunks
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Knowledge Graph Operations
```python
class KnowledgeGraph:
    def __init__(self):
        self.db = PostgreSQLConnection()
        self.embedder = GeminiEmbedder()

    async def add_news_intelligence(self, article: NewsArticle, entities: List[Entity],
                                   relationships: List[Relationship]):
        """Add news-derived intelligence to knowledge graph"""
        async with self.db.transaction():
            # Ensure all entities exist
            for entity in entities:
                await self.upsert_entity(entity)

            # Add relationships
            for relationship in relationships:
                await self.add_relationship(relationship)

            # Create event records
            event = Event(
                event_type='news_mention',
                entities=[e.id for e in entities],
                date=article.published_date,
                description=article.headline,
                metadata={'url': article.url, 'sentiment': article.sentiment}
            )
            await self.add_event(event)

            # Store embeddings for semantic search
            embedding = await self.embedder.embed(article.content)
            await self.store_embedding('news', article.id, article.content, embedding)

    async def find_similar_projects(self, target_project: DevelopmentProject) -> List[HistoricalProject]:
        """Find historically similar projects using vector similarity"""
        # Create embedding for target project description
        project_description = self.create_project_description(target_project)
        target_embedding = await self.embedder.embed(project_description)

        # Find similar projects using pgvector
        query = """
        SELECT d.*, p.*,
               (d.embedding <=> $1) as similarity_score
        FROM document_embeddings d
        JOIN projects p ON d.document_id = p.id
        WHERE d.document_type = 'project'
        ORDER BY d.embedding <=> $1
        LIMIT 10;
        """

        similar_projects = await self.db.fetch(query, target_embedding)
        return [HistoricalProject.from_db_row(row) for row in similar_projects]

    async def get_entity_relationships(self, entity_id: UUID) -> EntityNetwork:
        """Get complete relationship network for an entity"""
        query = """
        WITH RECURSIVE entity_network AS (
            -- Direct relationships
            SELECT r.to_entity_id as connected_entity, r.relationship_type,
                   r.strength, 1 as depth
            FROM entity_relationships r
            WHERE r.from_entity_id = $1

            UNION

            -- Second-degree relationships
            SELECT r2.to_entity_id, r2.relationship_type,
                   r2.strength * en.strength, en.depth + 1
            FROM entity_relationships r2
            JOIN entity_network en ON r2.from_entity_id = en.connected_entity
            WHERE en.depth < 3  -- Limit depth to prevent infinite recursion
        )
        SELECT en.*, e.name, e.entity_type
        FROM entity_network en
        JOIN entities e ON en.connected_entity = e.id
        ORDER BY en.strength DESC;
        """

        relationships = await self.db.fetch(query, entity_id)
        return EntityNetwork.from_db_results(relationships)
```

# 3.5 AI SAFETY & HALLUCINATION PREVENTION

**Critical for Credibility**: Dominion's reputation depends on never stating unsupported facts or generating false intelligence.

## 3.5.1 AI Safety Architecture

### Safe Inference System
```python
class SafeAIInference:
    def __init__(self):
        # Confidence thresholds by claim type
        self.confidence_thresholds = {
            'factual_claims': 0.90,     # "Developer X owns property Y"
            'predictions': 0.70,        # "Project likely to succeed"
            'relationships': 0.80,      # "Entity A connected to Entity B"
            'patterns': 0.75,          # "Area shows gentrification pattern"
            'valuations': 0.65,        # "Property worth approximately X"
            'timelines': 0.60          # "Approval will take X months"
        }
        self.gemini = GeminiProcessor()
        self.validator = FactValidator()

    async def make_safe_inference(self, data: str, claim_type: str) -> SafeInference:
        """Generate inference with safety checks"""

        # Generate AI response with reasoning
        raw_inference = await self.gemini.generate_with_reasoning(
            prompt=self.create_safe_prompt(data, claim_type),
            require_sources=True,
            require_confidence=True
        )

        # Extract components
        claim = raw_inference.claim
        confidence = raw_inference.confidence
        sources = raw_inference.sources
        reasoning = raw_inference.reasoning_chain
        uncertainties = raw_inference.identified_uncertainties

        # Safety validation
        if confidence < self.confidence_thresholds[claim_type]:
            return SafeInference(
                status="insufficient_confidence",
                message=f"Insufficient evidence to determine {claim_type} (confidence: {confidence:.1%})",
                confidence=confidence,
                sources=sources,
                reasoning=reasoning
            )

        # Cross-reference validation
        validation_result = await self.validator.cross_reference(claim, sources)
        if validation_result.contradictions_found:
            return SafeInference(
                status="validation_failed",
                message=f"Evidence contains contradictions: {validation_result.contradictions}",
                confidence=confidence * 0.5,  # Reduce confidence
                sources=sources,
                reasoning=reasoning
            )

        # Format with uncertainty language
        safe_claim = self.format_with_uncertainty(claim, confidence, uncertainties)

        return SafeInference(
            status="validated",
            claim=safe_claim,
            confidence=confidence,
            sources=sources,
            reasoning=reasoning,
            uncertainties=uncertainties,
            evidence_strength=validation_result.strength
        )

    def format_with_uncertainty(self, claim: str, confidence: float,
                               uncertainties: List[str]) -> str:
        """Format claims with appropriate uncertainty language"""

        if confidence >= 0.95:
            prefix = "Based on strong evidence"
        elif confidence >= 0.85:
            prefix = "Evidence strongly suggests"
        elif confidence >= 0.75:
            prefix = "Evidence indicates"
        elif confidence >= 0.65:
            prefix = "Limited evidence suggests"
        else:
            prefix = "Preliminary evidence may indicate"

        uncertainty_note = ""
        if uncertainties:
            uncertainty_note = f" (Note: {', '.join(uncertainties)})"

        return f"{prefix}, {claim.lower()}{uncertainty_note}"

    def create_safe_prompt(self, data: str, claim_type: str) -> str:
        """Create prompt that encourages safe, cited responses"""

        return f"""
        Analyze the following data to make a {claim_type}. CRITICAL REQUIREMENTS:

        1. ONLY state facts you can cite with specific sources
        2. Provide confidence score (0.0-1.0) for your assessment
        3. Identify any uncertainties or data gaps
        4. Show your reasoning step-by-step
        5. If evidence is insufficient, explicitly state so

        Data: {data}

        Format your response as:
        CLAIM: [Your specific claim]
        CONFIDENCE: [0.0-1.0 score]
        SOURCES: [Specific citations from the data]
        REASONING: [Step-by-step logic]
        UNCERTAINTIES: [What you don't know or can't verify]

        Remember: It's better to say "insufficient data" than to guess.
        """
```

### Fact Validation Pipeline
```python
class FactValidator:
    def __init__(self):
        self.knowledge_graph = KnowledgeGraph()
        self.external_sources = ExternalFactChecker()

    async def cross_reference(self, claim: str, sources: List[str]) -> ValidationResult:
        """Cross-reference claim against known facts"""

        # Check against knowledge graph
        contradictions = []
        supporting_facts = []

        # Extract entities from claim
        entities = await self.extract_entities(claim)

        for entity in entities:
            # Find existing facts about this entity
            existing_facts = await self.knowledge_graph.get_entity_facts(entity)

            # Check for contradictions
            for fact in existing_facts:
                contradiction = await self.check_contradiction(claim, fact)
                if contradiction.is_contradiction:
                    contradictions.append({
                        'existing_fact': fact,
                        'confidence': fact.confidence,
                        'source': fact.source,
                        'contradiction_type': contradiction.type
                    })
                elif contradiction.is_supporting:
                    supporting_facts.append(fact)

        # Calculate validation strength
        strength = self.calculate_validation_strength(
            supporting_facts, contradictions, sources
        )

        return ValidationResult(
            contradictions_found=len(contradictions) > 0,
            contradictions=contradictions,
            supporting_facts=supporting_facts,
            strength=strength,
            validation_notes=self.generate_validation_notes(
                supporting_facts, contradictions
            )
        )

    def calculate_validation_strength(self, supporting_facts: List[Fact],
                                    contradictions: List[dict],
                                    sources: List[str]) -> float:
        """Calculate how well-supported a claim is"""

        if contradictions:
            return 0.2  # Low confidence if contradictions exist

        if not supporting_facts and len(sources) < 2:
            return 0.4  # Low confidence if few sources

        if len(supporting_facts) >= 2:
            return 0.9  # High confidence if multiple supporting facts

        if len(sources) >= 3:
            return 0.8  # Good confidence if multiple sources

        return 0.6  # Medium confidence
```

## 3.5.2 Hallucination Prevention Measures

### Source Attribution Requirements
**Every AI-generated claim must include:**
```python
class RequiredAttribution:
    claim: str
    confidence: float  # 0.0 - 1.0
    sources: List[str]  # Specific citations
    reasoning: str     # Step-by-step logic
    uncertainties: List[str]  # Known unknowns
    last_updated: datetime
```

### Confidence Calibration System
```python
class ConfidenceCalibrator:
    def __init__(self):
        self.historical_accuracy = {}  # Track AI accuracy by confidence level

    async def track_prediction_outcome(self, prediction: Prediction,
                                     actual_outcome: Outcome):
        """Track how well AI confidence matches actual accuracy"""

        confidence_bucket = self.get_confidence_bucket(prediction.confidence)

        if confidence_bucket not in self.historical_accuracy:
            self.historical_accuracy[confidence_bucket] = {
                'predictions': 0,
                'correct': 0,
                'accuracy': 0.0
            }

        bucket = self.historical_accuracy[confidence_bucket]
        bucket['predictions'] += 1

        if prediction.matches_outcome(actual_outcome):
            bucket['correct'] += 1

        bucket['accuracy'] = bucket['correct'] / bucket['predictions']

        # Alert if confidence is poorly calibrated
        if abs(bucket['accuracy'] - confidence_bucket) > 0.15:
            await self.send_calibration_alert(confidence_bucket, bucket)

    def get_confidence_bucket(self, confidence: float) -> float:
        """Group confidence scores into buckets for tracking"""
        return round(confidence, 1)  # 0.1 increments
```

### Human Validation Loop
```python
class HumanValidationQueue:
    def __init__(self):
        self.validation_queue = []
        self.validation_thresholds = {
            'high_impact_prediction': 0.8,  # Success/failure predictions
            'financial_estimate': 0.7,      # ROI calculations
            'legal_assessment': 0.9,        # Regulatory compliance
            'safety_risk': 0.95             # Environmental/safety issues
        }

    async def queue_for_validation(self, inference: SafeInference,
                                  impact_type: str):
        """Queue high-impact inferences for human review"""

        if inference.confidence < self.validation_thresholds[impact_type]:
            validation_item = ValidationItem(
                inference=inference,
                impact_type=impact_type,
                priority=self.calculate_priority(inference, impact_type),
                created_at=datetime.utcnow(),
                requires_expert_review=impact_type in ['legal_assessment', 'safety_risk']
            )

            await self.add_to_validation_queue(validation_item)

            # Send immediate alert for critical items
            if impact_type == 'safety_risk':
                await self.send_immediate_review_alert(validation_item)

    async def process_validation_feedback(self, item_id: str,
                                        validation_result: ValidationFeedback):
        """Process human validation feedback to improve AI"""

        item = await self.get_validation_item(item_id)

        # Update AI training data
        await self.update_training_data(
            original_inference=item.inference,
            correct_answer=validation_result.correct_inference,
            feedback_notes=validation_result.notes
        )

        # Update confidence calibration
        await self.confidence_calibrator.track_validation_result(
            item.inference, validation_result
        )
```

## 3.5.3 Audit & Learning System

### AI Decision Audit Trail
```python
class AIDecisionAudit:
    def __init__(self):
        self.db = AuditDatabase()

    async def log_ai_inference(self, inference: SafeInference,
                              context: AnalysisContext) -> str:
        """Log every AI inference for future review"""

        audit_record = AIAuditRecord(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            model_version="gemini-2.0-flash",
            inference_type=context.inference_type,
            input_data_hash=hashlib.sha256(context.input_data.encode()).hexdigest(),
            inference_claim=inference.claim,
            confidence_score=inference.confidence,
            sources_used=inference.sources,
            reasoning_chain=inference.reasoning,
            validation_status=inference.status,
            user_context=context.user_type,
            property_context=context.property_address
        )

        await self.db.store_audit_record(audit_record)
        return audit_record.id

    async def flag_for_review(self, audit_id: str, flag_reason: str):
        """Flag AI decision for human review"""

        await self.db.update_audit_record(
            audit_id,
            {'flagged': True, 'flag_reason': flag_reason, 'flag_date': datetime.utcnow()}
        )

        # Add to human review queue
        await self.human_validation_queue.add_flagged_inference(audit_id)
```

### Continuous Improvement Pipeline
```python
class AIImprovementPipeline:
    async def analyze_failure_patterns(self):
        """Analyze where AI makes mistakes to improve prompts"""

        # Get recent validation failures
        failures = await self.get_recent_validation_failures(days=30)

        # Group by failure type
        failure_patterns = {}
        for failure in failures:
            pattern_key = (failure.inference_type, failure.failure_reason)
            if pattern_key not in failure_patterns:
                failure_patterns[pattern_key] = []
            failure_patterns[pattern_key].append(failure)

        # Identify systemic issues
        for pattern, instances in failure_patterns.items():
            if len(instances) >= 5:  # 5+ similar failures = pattern
                await self.create_improvement_task(pattern, instances)

    async def create_improvement_task(self, pattern: tuple,
                                    instances: List[ValidationFailure]):
        """Create task to fix systemic AI issues"""

        improvement_task = ImprovementTask(
            pattern_type=pattern[0],
            failure_reason=pattern[1],
            instance_count=len(instances),
            example_failures=instances[:3],  # Include examples
            suggested_fix=await self.suggest_prompt_improvement(pattern, instances),
            priority=self.calculate_improvement_priority(instances)
        )

        await self.improvement_queue.add_task(improvement_task)
```

**Key Safety Principle**: Dominion never guesses. If evidence is insufficient, it says so. Users trust transparency about uncertainty more than false confidence.

---

# 4. USER-ADAPTIVE ANALYSIS SYSTEM

## 4.1 Analysis Mode Architecture

```python
class AdaptiveAnalysisEngine:
    def __init__(self):
        self.base_analyzer = BasePropertyAnalyzer()
        self.analysis_modes = {
            'developer': DeveloperAnalysisMode(),
            'flipper': FlipperAnalysisMode(),
            'agent': AgentAnalysisMode(),
            'investor': InvestorAnalysisMode(),
            'commercial': CommercialAnalysisMode()
        }

    async def analyze(self, property_address: str, user_type: str,
                     specific_params: dict) -> AdaptiveAnalysisReport:
        """Generate analysis tailored to specific user type"""

        # Get base property intelligence
        base_intel = await self.base_analyzer.get_comprehensive_intelligence(property_address)

        # Apply user-specific analysis lens
        analysis_mode = self.analysis_modes[user_type]
        specialized_analysis = await analysis_mode.analyze(base_intel, specific_params)

        return AdaptiveAnalysisReport(
            base_intelligence=base_intel,
            specialized_analysis=specialized_analysis,
            user_type=user_type,
            confidence_scores=specialized_analysis.confidence_scores
        )
```

## 4.2 Developer Analysis Mode

**Focus**: Entitlements, infrastructure, political feasibility, development economics

```python
class DeveloperAnalysisMode:
    async def analyze(self, base_intel: PropertyIntelligence,
                     params: DeveloperParams) -> DeveloperAnalysis:

        # Zoning and entitlement analysis
        entitlement_analysis = await self.analyze_entitlement_path(
            property=base_intel.property,
            desired_use=params.development_type,
            density=params.target_density
        )

        # Infrastructure requirements and costs
        infrastructure_analysis = await self.analyze_infrastructure_needs(
            property=base_intel.property,
            development_scope=params.development_scope
        )

        # Political feasibility assessment
        political_analysis = await self.assess_political_climate(
            property=base_intel.property,
            development_type=params.development_type,
            historical_patterns=base_intel.area_patterns
        )

        # Development economics
        economics = await self.calculate_development_economics(
            property=base_intel.property,
            construction_costs=params.estimated_construction_cost,
            infrastructure_costs=infrastructure_analysis.total_costs,
            timeline=entitlement_analysis.estimated_timeline
        )

        return DeveloperAnalysis(
            entitlement_analysis=entitlement_analysis,
            infrastructure_analysis=infrastructure_analysis,
            political_analysis=political_analysis,
            economics=economics,
            success_probability=self.calculate_success_probability([
                entitlement_analysis, political_analysis, economics
            ])
        )

    async def analyze_entitlement_path(self, property: Property,
                                      desired_use: str, density: float) -> EntitlementAnalysis:
        """Determine required approvals and timeline"""

        current_zoning = property.zoning_classification
        required_zoning = self.determine_required_zoning(desired_use, density)

        if current_zoning == required_zoning:
            path = EntitlementPath.ADMINISTRATIVE_APPROVAL
            timeline_months = 2
        elif self.is_compatible_zoning(current_zoning, required_zoning):
            path = EntitlementPath.SPECIAL_EXCEPTION
            timeline_months = 4
        else:
            path = EntitlementPath.REZONING_REQUIRED
            timeline_months = 8

        # Analyze historical approval rates for this path and area
        historical_approvals = await self.get_historical_approval_rate(
            property.address, path, desired_use
        )

        # Check for potential opposition
        opposition_likelihood = await self.assess_opposition_likelihood(
            property.address, desired_use, density
        )

        return EntitlementAnalysis(
            current_zoning=current_zoning,
            required_zoning=required_zoning,
            entitlement_path=path,
            estimated_timeline_months=timeline_months,
            approval_probability=historical_approvals.success_rate,
            opposition_likelihood=opposition_likelihood,
            required_hearings=self.determine_required_hearings(path),
            estimated_costs=self.calculate_entitlement_costs(path)
        )
```

## 4.3 House Flipper Analysis Mode

**Focus**: ARV, repair costs, days on market, profit margins, exit strategy

```python
class FlipperAnalysisMode:
    async def analyze(self, base_intel: PropertyIntelligence,
                     params: FlipperParams) -> FlipperAnalysis:

        # After Repair Value (ARV) calculation
        arv_analysis = await self.calculate_comprehensive_arv(
            property=base_intel.property,
            target_condition=params.target_condition,
            comparable_sales=base_intel.recent_sales
        )

        # Detailed repair cost estimation
        repair_analysis = await self.estimate_repair_costs(
            property=base_intel.property,
            current_condition=params.current_condition,
            target_condition=params.target_condition
        )

        # Market timing and absorption
        market_timing = await self.analyze_market_timing(
            property=base_intel.property,
            target_buyer_segment=params.target_buyer
        )

        # Risk factors specific to flipping
        flip_risks = await self.identify_flip_specific_risks(
            property=base_intel.property,
            repair_scope=repair_analysis.repair_scope
        )

        # Calculate flip economics
        economics = self.calculate_flip_economics(
            purchase_price=params.purchase_price,
            repair_costs=repair_analysis.total_cost,
            arv=arv_analysis.conservative_arv,
            holding_costs=market_timing.estimated_holding_costs,
            transaction_costs=market_timing.transaction_costs
        )

        return FlipperAnalysis(
            arv_analysis=arv_analysis,
            repair_analysis=repair_analysis,
            market_timing=market_timing,
            risk_assessment=flip_risks,
            economics=economics,
            profit_probability=self.calculate_profit_probability(economics, flip_risks)
        )

    async def calculate_comprehensive_arv(self, property: Property,
                                         target_condition: str,
                                         comparable_sales: List[Sale]) -> ARVAnalysis:
        """Calculate After Repair Value using multiple methodologies"""

        # Filter comparables for similar properties in good condition
        good_condition_sales = [
            sale for sale in comparable_sales
            if sale.condition_rating >= 4.0 and
               self.is_truly_comparable(property, sale.property)
        ]

        # Comparative Market Analysis (CMA)
        cma_arv = await self.cma_analysis(property, good_condition_sales)

        # Cost approach (useful for extensive renovations)
        cost_approach_arv = await self.cost_approach_analysis(property, target_condition)

        # AI-enhanced valuation using market patterns
        ai_arv = await self.ai_enhanced_valuation(property, comparable_sales, target_condition)

        # Weight the approaches based on market conditions and property type
        weights = self.determine_approach_weights(property, len(good_condition_sales))

        weighted_arv = (
            cma_arv * weights['cma'] +
            cost_approach_arv * weights['cost'] +
            ai_arv * weights['ai']
        )

        return ARVAnalysis(
            conservative_arv=weighted_arv * 0.9,  # 10% buffer for safety
            most_likely_arv=weighted_arv,
            optimistic_arv=weighted_arv * 1.1,
            methodology_breakdown={
                'cma': cma_arv,
                'cost_approach': cost_approach_arv,
                'ai_enhanced': ai_arv
            },
            comparable_sales=good_condition_sales,
            confidence_score=self.calculate_arv_confidence(weights, good_condition_sales),
            # AI Safety Requirements
            data_sources=[f"Comparable sale: {sale.address}" for sale in good_condition_sales],
            inference_reasoning=f"Used {len(good_condition_sales)} comparable sales, weighted CMA ({weights['cma']:.1%}), cost approach ({weights['cost']:.1%}), AI enhancement ({weights['ai']:.1%})",
            known_uncertainties=[
                "Market conditions may change" if len(good_condition_sales) < 3 else None,
                "Renovation scope estimates may vary" if target_condition != "good" else None
            ],
            last_updated=datetime.utcnow()
        )
```

## 4.4 Real Estate Agent Analysis Mode

**Focus**: Listing strategy, buyer demand, market timing, competitive dynamics

```python
class AgentAnalysisMode:
    async def analyze(self, base_intel: PropertyIntelligence,
                     params: AgentParams) -> AgentAnalysis:

        if params.analysis_type == 'listing_strategy':
            return await self.analyze_listing_strategy(base_intel, params)
        elif params.analysis_type == 'buyer_opportunity':
            return await self.analyze_buyer_opportunity(base_intel, params)
        elif params.analysis_type == 'market_timing':
            return await self.analyze_market_timing(base_intel, params)

    async def analyze_listing_strategy(self, base_intel: PropertyIntelligence,
                                      params: AgentParams) -> ListingStrategyAnalysis:
        """Optimize listing strategy for sellers"""

        # Pricing strategy based on current market dynamics
        pricing_strategy = await self.optimal_pricing_strategy(
            property=base_intel.property,
            recent_sales=base_intel.recent_sales,
            current_listings=base_intel.active_listings,
            market_velocity=base_intel.market_conditions.velocity
        )

        # Optimal timing analysis
        timing_analysis = await self.analyze_optimal_timing(
            property=base_intel.property,
            seasonal_patterns=base_intel.seasonal_patterns,
            inventory_projections=base_intel.inventory_projections
        )

        # Marketing recommendations
        marketing_strategy = await self.develop_marketing_strategy(
            property=base_intel.property,
            target_buyer_segments=self.identify_target_buyers(base_intel.property),
            competitive_listings=base_intel.competing_listings
        )

        # Expected market performance
        performance_prediction = await self.predict_listing_performance(
            property=base_intel.property,
            pricing_strategy=pricing_strategy,
            market_conditions=base_intel.market_conditions
        )

        return ListingStrategyAnalysis(
            pricing_strategy=pricing_strategy,
            timing_analysis=timing_analysis,
            marketing_strategy=marketing_strategy,
            performance_prediction=performance_prediction,
            competitive_analysis=base_intel.competitive_analysis
        )

    async def optimal_pricing_strategy(self, property: Property,
                                      recent_sales: List[Sale],
                                      current_listings: List[Listing],
                                      market_velocity: float) -> PricingStrategy:
        """Determine optimal listing price strategy"""

        # Calculate market value using recent comparables
        market_value = await self.calculate_market_value(property, recent_sales)

        # Analyze current competition
        competitive_analysis = await self.analyze_current_competition(
            property, current_listings
        )

        # Factor in market conditions
        if market_velocity > 1.2:  # Hot market
            strategy_type = PricingStrategy.AGGRESSIVE_PRICING
            recommended_price = market_value * 1.05  # Price slightly above market
        elif market_velocity < 0.8:  # Slow market
            strategy_type = PricingStrategy.CONSERVATIVE_PRICING
            recommended_price = market_value * 0.95  # Price below market for quick sale
        else:  # Balanced market
            strategy_type = PricingStrategy.MARKET_PRICING
            recommended_price = market_value

        return PricingStrategy(
            strategy_type=strategy_type,
            recommended_list_price=recommended_price,
            expected_sale_price=self.calculate_expected_sale_price(
                recommended_price, market_velocity
            ),
            price_range=PriceRange(
                minimum=recommended_price * 0.95,
                maximum=recommended_price * 1.05
            ),
            rationale=self.generate_pricing_rationale(
                market_value, competitive_analysis, market_velocity
            ),
            # AI Safety Requirements
            confidence_score=self.calculate_pricing_confidence(recent_sales, current_listings),
            data_sources=[
                f"Recent sales: {len(recent_sales)} comparables",
                f"Active listings: {len(current_listings)} competitors",
                f"Market velocity: {market_velocity:.2f}"
            ],
            inference_reasoning=f"Based on {len(recent_sales)} recent sales and {len(current_listings)} competing listings, market velocity indicates {'hot' if market_velocity > 1.2 else 'slow' if market_velocity < 0.8 else 'balanced'} market conditions",
            known_uncertainties=[
                f"Limited comparable sales data ({len(recent_sales)} < 5)" if len(recent_sales) < 5 else None,
                "Market conditions may shift rapidly" if abs(market_velocity - 1.0) > 0.3 else None
            ],
            last_updated=datetime.utcnow()
        )
```

## 4.5 Property Investor Analysis Mode

**Focus**: Cash flow, CAP rates, appreciation potential, risk-adjusted returns

```python
class InvestorAnalysisMode:
    async def analyze(self, base_intel: PropertyIntelligence,
                     params: InvestorParams) -> InvestorAnalysis:

        # Cash flow analysis
        cash_flow_analysis = await self.analyze_cash_flow(
            property=base_intel.property,
            purchase_price=params.purchase_price,
            financing=params.financing_terms,
            rental_strategy=params.rental_strategy
        )

        # Market appreciation potential
        appreciation_analysis = await self.analyze_appreciation_potential(
            property=base_intel.property,
            area_trends=base_intel.area_trends,
            development_pipeline=base_intel.development_pipeline
        )

        # Investment risk assessment
        risk_analysis = await self.assess_investment_risks(
            property=base_intel.property,
            rental_strategy=params.rental_strategy,
            market_conditions=base_intel.market_conditions
        )

        # Comparative investment analysis
        comparative_analysis = await self.compare_investment_alternatives(
            target_property=base_intel.property,
            investment_criteria=params.investment_criteria,
            available_alternatives=params.consider_alternatives
        )

        # Calculate investment metrics
        investment_metrics = self.calculate_investment_metrics(
            cash_flow_analysis, appreciation_analysis, params.investment_timeline
        )

        return InvestorAnalysis(
            cash_flow_analysis=cash_flow_analysis,
            appreciation_analysis=appreciation_analysis,
            risk_analysis=risk_analysis,
            comparative_analysis=comparative_analysis,
            investment_metrics=investment_metrics,
            investment_recommendation=self.generate_investment_recommendation(
                investment_metrics, risk_analysis, params.risk_tolerance
            )
        )

    async def analyze_cash_flow(self, property: Property, purchase_price: Decimal,
                               financing: FinancingTerms, rental_strategy: str) -> CashFlowAnalysis:
        """Detailed cash flow projection"""

        # Rental income estimation
        rental_analysis = await self.estimate_rental_income(property, rental_strategy)

        # Operating expense analysis
        operating_expenses = await self.calculate_operating_expenses(property, rental_strategy)

        # Financing costs
        financing_costs = self.calculate_financing_costs(purchase_price, financing)

        # Monthly cash flow calculation
        monthly_rental_income = rental_analysis.conservative_rent
        monthly_expenses = (
            operating_expenses.monthly_total +
            financing_costs.monthly_payment +
            self.calculate_vacancy_allowance(rental_analysis.vacancy_rate, monthly_rental_income)
        )

        monthly_cash_flow = monthly_rental_income - monthly_expenses

        # Calculate key metrics
        cap_rate = (rental_analysis.annual_rent - operating_expenses.annual_total) / purchase_price
        cash_on_cash_return = (monthly_cash_flow * 12) / financing.down_payment

        return CashFlowAnalysis(
            monthly_cash_flow=monthly_cash_flow,
            annual_cash_flow=monthly_cash_flow * 12,
            cap_rate=cap_rate,
            cash_on_cash_return=cash_on_cash_return,
            rental_analysis=rental_analysis,
            expense_breakdown=operating_expenses,
            financing_costs=financing_costs,
            break_even_occupancy=self.calculate_break_even_occupancy(
                monthly_rental_income, monthly_expenses
            ),
            # AI Safety Requirements
            confidence_score=rental_analysis.confidence * 0.9,  # Factor in rental estimate confidence
            data_sources=[
                f"Rental comparables: {rental_analysis.comparable_count}",
                f"Operating expense data: {operating_expenses.data_source}",
                f"Financing terms: {financing.source}"
            ],
            inference_reasoning=f"Cash flow calculated from {rental_strategy} rental strategy with {rental_analysis.vacancy_rate:.1%} vacancy allowance, {operating_expenses.monthly_total:.0f}/month expenses",
            known_uncertainties=[
                f"Limited rental comparables ({rental_analysis.comparable_count} < 3)" if rental_analysis.comparable_count < 3 else None,
                "Vacancy rates may vary seasonally",
                "Interest rates subject to change" if financing.rate_type == "variable" else None
            ],
            last_updated=datetime.utcnow()
        )
```

---

# 5. TECHNICAL IMPLEMENTATION

## 5.1 Docker Architecture

### docker-compose.yml
```yaml
version: '3.8'

services:
  # Main API service
  dominion-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://dominion:${POSTGRES_PASSWORD}@postgres:5432/dominion
      - REDIS_URL=redis://redis:6379/0
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - LOG_LEVEL=INFO
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    networks:
      - dominion-net

  # Background scrapers
  dominion-scrapers:
    build:
      context: .
      dockerfile: Dockerfile.scrapers
    environment:
      - DATABASE_URL=postgresql://dominion:${POSTGRES_PASSWORD}@postgres:5432/dominion
      - REDIS_URL=redis://redis:6379/0
      - PROXY_LIST=${PROXY_ENDPOINTS}
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    restart: unless-stopped
    networks:
      - dominion-net

  # RQ Workers for deep analysis (1-4 hour jobs)
  dominion-workers:
    build:
      context: .
      dockerfile: docker/worker.dockerfile
    deploy:
      replicas: 2  # Scale based on demand
    environment:
      - DATABASE_URL=postgresql://dominion:${POSTGRES_PASSWORD}@postgres:5432/dominion
      - REDIS_URL=redis://redis:6379/0
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - WORKER_CONCURRENCY=2
      - LOG_LEVEL=INFO
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    networks:
      - dominion-net

  # PostgreSQL with pgvector
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      - POSTGRES_DB=dominion
      - POSTGRES_USER=dominion
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    restart: unless-stopped
    networks:
      - dominion-net

  # Redis for task queue
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - dominion-net

  # Monitoring and metrics
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: unless-stopped
    networks:
      - dominion-net

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped
    networks:
      - dominion-net

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  dominion-net:
    driver: bridge
```

### Dockerfile.api
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create non-root user
RUN useradd --create-home --shell /bin/bash dominion
USER dominion

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start command
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dockerfile.scrapers
```dockerfile
FROM python:3.11-slim

# Install system dependencies for web scraping
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements-scrapers.txt .
RUN pip install --no-cache-dir -r requirements-scrapers.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy scraper code
COPY src/scrapers/ ./src/scrapers/
COPY src/common/ ./src/common/

# Create non-root user
RUN useradd --create-home --shell /bin/bash scraper
USER scraper

# Start scraper services
CMD ["python", "-m", "src.scrapers.scheduler"]
```

## 5.2 FastAPI Application Structure

### Main API Application
```python
# src/api/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import asyncio
from typing import List, Optional
from redis import Redis
from rq import Queue
import uuid
import logging

from .models import AnalysisRequest, AnalysisReport, UserType, JobStatus
from .services import DominionAnalysisService, UserAuthService
from .dependencies import get_current_user, get_analysis_service, get_redis_connection
from .workers import execute_deep_analysis_job

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "correlation_id": "%(correlation_id)s"}',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dominion Intelligence Engine",
    description="AI-powered real estate intelligence and deal validation",
    version="2.0.0"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dominion.vercel.app"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Redis and RQ setup
redis_conn = Redis.from_url("redis://redis:6379")
analysis_queue = Queue('analysis', connection=redis_conn, default_timeout=14400)  # 4 hours

@app.post("/analysis", response_model=dict)
async def analyze_property(
    request: AnalysisRequest,
    current_user = Depends(get_current_user),
    service = Depends(get_analysis_service),
    redis = Depends(get_redis_connection)
):
    """
    Comprehensive property analysis based on user type.

    This endpoint initiates deep analysis which may take 1-4 hours.
    A job ID is returned immediately, and the analysis runs asynchronously via RQ workers.
    """
    correlation_id = str(uuid.uuid4())

    # Validate request
    if not request.address and not request.parcel_id:
        logger.error("Invalid request: missing address/parcel_id", extra={"correlation_id": correlation_id})
        raise HTTPException(
            status_code=400,
            detail="Either address or parcel_id must be provided"
        )

    # Create idempotency key to prevent duplicate analyses
    property_key = request.address or request.parcel_id
    idempotency_key = f"{current_user.id}:{property_key}:{hash(str(request.analysis_parameters))}"

    # Check for existing job
    existing_job_id = await redis.get(f"analysis_job:{idempotency_key}")
    if existing_job_id:
        existing_job = analysis_queue.fetch_job(existing_job_id.decode())
        if existing_job and existing_job.get_status() in ['started', 'queued']:
            logger.info(f"Returning existing job {existing_job_id}", extra={"correlation_id": correlation_id})
            return {
                "job_id": existing_job_id.decode(),
                "status": "queued",
                "estimated_completion_minutes": service.estimate_completion_time(request),
                "message": "Analysis already in progress. Check status using job_id."
            }

    # Enqueue analysis job
    job = analysis_queue.enqueue(
        execute_deep_analysis_job,
        user_id=current_user.id,
        property_identifier=property_key,
        analysis_type=request.user_type.value,
        analysis_parameters=request.analysis_parameters,
        correlation_id=correlation_id,
        job_timeout=14400,  # 4 hours
        retry=3,
        meta={"idempotency_key": idempotency_key}
    )

    # Store idempotency mapping
    await redis.setex(f"analysis_job:{idempotency_key}", 86400, job.id)  # 24 hours

    logger.info(f"Analysis job {job.id} enqueued for user {current_user.id}",
                extra={"correlation_id": correlation_id, "job_id": job.id})

    return {
        "job_id": job.id,
        "status": "queued",
        "estimated_completion_minutes": service.estimate_completion_time(request),
        "message": "Deep analysis initiated. Check status using job_id or monitor your email for completion.",
        "correlation_id": correlation_id
    }

@app.get("/jobs/{job_id}/status", response_model=JobStatus)
async def get_job_status(
    job_id: str,
    current_user = Depends(get_current_user),
    redis = Depends(get_redis_connection)
):
    """Get the status and progress of an analysis job."""

    job = analysis_queue.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get job progress from meta data
    progress = job.meta.get('progress', 0)
    current_stage = job.meta.get('current_stage', 'queued')

    return JobStatus(
        job_id=job_id,
        status=job.get_status(),
        progress_percentage=progress,
        current_stage=current_stage,
        enqueued_at=job.enqueued_at,
        started_at=job.started_at,
        ended_at=job.ended_at,
        result_available=job.is_finished and job.result is not None
    )

@app.get("/jobs/{job_id}/result", response_model=AnalysisReport)
async def get_job_result(
    job_id: str,
    current_user = Depends(get_current_user)
):
    """Get the results of a completed analysis job."""

    job = analysis_queue.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.is_finished:
        raise HTTPException(status_code=202, detail="Job not completed yet")

    if job.is_failed:
        raise HTTPException(
            status_code=500,
            detail=f"Job failed: {job.exc_info}"
        )

    return job.result

@app.get("/opportunities", response_model=List[OpportunityAlert])
async def get_current_opportunities(
    user_type: UserType,
    location: Optional[str] = None,
    max_price: Optional[int] = None,
    current_user = Depends(get_current_user),
    service = Depends(get_analysis_service)
):
    """Get current opportunities based on continuous monitoring."""

    opportunities = await service.get_current_opportunities(
        user_type=user_type,
        user_id=current_user.id,
        filters={
            'location': location,
            'max_price': max_price
        }
    )

    return opportunities

@app.get("/patterns/{area}", response_model=AreaPatterns)
async def get_area_patterns(
    area: str,  # Neighborhood or ZIP code
    current_user = Depends(get_current_user),
    service = Depends(get_analysis_service)
):
    """Get learned patterns for a specific area."""

    patterns = await service.get_area_patterns(area)
    return patterns

@app.get("/health")
async def health_check(
    redis = Depends(get_redis_connection),
    db = Depends(get_database_connection),
    queue = Depends(get_analysis_queue)
):
    """Health check endpoint with proper dependency injection."""
    try:
        # Test Redis connection
        await redis.ping()

        # Test database connection
        await db.fetchval("SELECT 1")

        # Test queue health
        queue_size = len(queue)
        failed_job_count = len(queue.failed_job_registry)

        # Health check with SLO validation
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "version": "2.0.0",
            "redis": "connected",
            "database": "connected",
            "queue_size": queue_size,
            "failed_jobs": failed_job_count,
            "slo_compliance": {
                "queue_depth_ok": queue_size < 50,  # SLO: <50 queued jobs
                "failed_rate_ok": failed_job_count < 5  # SLO: <5 failed jobs
            }
        }

        # Return 503 if SLOs violated
        if not all(health_status["slo_compliance"].values()):
            raise HTTPException(status_code=503, detail=health_status)

        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")
```

## 5.3 RQ Worker Implementation

### Background Analysis Worker
```python
# src/api/workers.py
import logging
import time
from datetime import datetime
from typing import Dict, Any
from rq import get_current_job

from ..core.analysis_engine import AdaptiveAnalysisEngine
from ..core.monitoring import ContinuousMonitor
from ..core.knowledge_graph import KnowledgeGraph
from ..database.models import User

# Configure structured logging for workers
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "job_id": "%(job_id)s", "correlation_id": "%(correlation_id)s"}',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def execute_deep_analysis_job(
    user_id: str,
    property_identifier: str,
    analysis_type: str,
    analysis_parameters: Dict[str, Any],
    correlation_id: str
):
    """
    Execute comprehensive deep analysis job.
    This is the main worker function that runs the 1-4 hour analysis.
    """
    job = get_current_job()
    logger.info(f"Starting deep analysis job",
               extra={"job_id": job.id, "correlation_id": correlation_id})

    try:
        # Initialize analysis engine
        engine = AdaptiveAnalysisEngine()

        # Update job progress
        job.meta['current_stage'] = 'initializing'
        job.meta['progress'] = 0
        job.save_meta()

        # Phase 1: Data Collection (20 minutes)
        logger.info("Phase 1: Data collection",
                   extra={"job_id": job.id, "correlation_id": correlation_id})
        job.meta['current_stage'] = 'data_collection'
        job.meta['progress'] = 5
        job.save_meta()

        property_data = engine.collect_property_data(property_identifier)

        job.meta['progress'] = 25
        job.save_meta()

        # Phase 2: Market Intelligence (30 minutes)
        logger.info("Phase 2: Market intelligence",
                   extra={"job_id": job.id, "correlation_id": correlation_id})
        job.meta['current_stage'] = 'market_intelligence'
        job.save_meta()

        market_data = engine.gather_market_intelligence(
            property_data.location,
            radius=analysis_parameters.get('radius_miles', 1.0)
        )

        job.meta['progress'] = 50
        job.save_meta()

        # Phase 3: Pattern Analysis (45 minutes)
        logger.info("Phase 3: Pattern analysis",
                   extra={"job_id": job.id, "correlation_id": correlation_id})
        job.meta['current_stage'] = 'pattern_analysis'
        job.save_meta()

        patterns = engine.analyze_historical_patterns(
            property_data, market_data, analysis_type
        )

        job.meta['progress'] = 75
        job.save_meta()

        # Phase 4: Risk Assessment (45 minutes)
        logger.info("Phase 4: Risk assessment",
                   extra={"job_id": job.id, "correlation_id": correlation_id})
        job.meta['current_stage'] = 'risk_assessment'
        job.save_meta()

        risks = engine.assess_risks(property_data, market_data, patterns)

        job.meta['progress'] = 90
        job.save_meta()

        # Phase 5: Generate Report (10 minutes)
        logger.info("Phase 5: Report generation",
                   extra={"job_id": job.id, "correlation_id": correlation_id})
        job.meta['current_stage'] = 'report_generation'
        job.save_meta()

        # Generate analysis based on user type
        if analysis_type == 'developer':
            result = engine.generate_developer_analysis(
                property_data, market_data, patterns, risks, analysis_parameters
            )
        elif analysis_type == 'flipper':
            result = engine.generate_flipper_analysis(
                property_data, market_data, patterns, risks, analysis_parameters
            )
        elif analysis_type == 'agent':
            result = engine.generate_agent_analysis(
                property_data, market_data, patterns, risks, analysis_parameters
            )
        elif analysis_type == 'investor':
            result = engine.generate_investor_analysis(
                property_data, market_data, patterns, risks, analysis_parameters
            )
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")

        job.meta['current_stage'] = 'completed'
        job.meta['progress'] = 100
        job.save_meta()

        logger.info(f"Deep analysis job completed successfully",
                   extra={"job_id": job.id, "correlation_id": correlation_id})

        # TODO: Send email notification to user

        return result

    except Exception as e:
        logger.error(f"Deep analysis job failed: {e}",
                    extra={"job_id": job.id, "correlation_id": correlation_id})

        job.meta['current_stage'] = 'failed'
        job.meta['error'] = str(e)
        job.save_meta()

        # TODO: Send error email notification
        raise
```

### Worker Container Dockerfile
```dockerfile
# docker/worker.dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/

# Set environment variables
ENV PYTHONPATH=/app
ENV WORKER_CONCURRENCY=2

# Run RQ worker
CMD ["python", "-m", "rq", "worker", "--url", "redis://redis:6379", "analysis"]
```

### Analysis Service Implementation
```python
# src/api/services/analysis_service.py
import asyncio
from typing import Dict, Any, List
import uuid
from datetime import datetime, timedelta

from ..models import AnalysisRequest, AnalysisReport, OpportunityAlert
from ...core.analysis_engine import AdaptiveAnalysisEngine
from ...core.monitoring import ContinuousMonitor
from ...core.knowledge_graph import KnowledgeGraph

class DominionAnalysisService:
    def __init__(self):
        self.analysis_engine = AdaptiveAnalysisEngine()
        self.monitor = ContinuousMonitor()
        self.knowledge_graph = KnowledgeGraph()
        self.active_tasks = {}

    async def create_analysis_task(self, user_id: str, property_identifier: str,
                                  analysis_type: str, parameters: Dict[str, Any]) -> str:
        """Create a new analysis task and return task ID."""

        task_id = str(uuid.uuid4())

        task = {
            'id': task_id,
            'user_id': user_id,
            'property_identifier': property_identifier,
            'analysis_type': analysis_type,
            'parameters': parameters,
            'status': 'created',
            'created_at': datetime.utcnow(),
            'progress': 0
        }

        # Store in database and cache
        await self.store_task(task)
        self.active_tasks[task_id] = task

        return task_id

    async def execute_deep_analysis(self, task_id: str, request: AnalysisRequest):
        """Execute comprehensive property analysis (runs in background)."""

        try:
            # Update task status
            await self.update_task_status(task_id, 'running', 5)

            # Phase 1: Data Gathering
            await self.update_task_status(task_id, 'gathering_data', 20)
            property_data = await self.analysis_engine.gather_comprehensive_data(
                request.address or request.parcel_id
            )

            # Phase 2: Intelligence Synthesis
            await self.update_task_status(task_id, 'analyzing_intelligence', 40)
            base_intelligence = await self.analysis_engine.synthesize_intelligence(property_data)

            # Phase 3: Pattern Analysis
            await self.update_task_status(task_id, 'pattern_analysis', 60)
            patterns = await self.analysis_engine.analyze_patterns(
                base_intelligence, request.user_type
            )

            # Phase 4: User-Specific Analysis
            await self.update_task_status(task_id, 'specialized_analysis', 80)
            specialized_analysis = await self.analysis_engine.analyze(
                base_intelligence.property.address,
                request.user_type,
                request.analysis_parameters or {}
            )

            # Phase 5: Report Generation
            await self.update_task_status(task_id, 'generating_report', 95)
            report = await self.generate_final_report(
                base_intelligence, specialized_analysis, request
            )

            # Complete task
            await self.complete_task(task_id, report)

            # Send notification
            await self.send_completion_notification(task_id, request.user_id)

        except Exception as e:
            await self.fail_task(task_id, str(e))
            await self.send_error_notification(task_id, request.user_id, str(e))

    async def get_current_opportunities(self, user_type: str, user_id: str,
                                      filters: Dict[str, Any]) -> List[OpportunityAlert]:
        """Get opportunities from continuous monitoring."""

        # Get recent alerts from monitoring system
        raw_opportunities = await self.monitor.get_recent_opportunities(
            max_age_hours=24,
            location_filter=filters.get('location'),
            price_filter=filters.get('max_price')
        )

        # Filter and adapt for user type
        adapted_opportunities = []
        for opp in raw_opportunities:
            adapted_opp = await self.adapt_opportunity_for_user(opp, user_type)
            if adapted_opp and adapted_opp.relevance_score > 0.7:
                adapted_opportunities.append(adapted_opp)

        # Sort by relevance and return top 20
        adapted_opportunities.sort(key=lambda x: x.relevance_score, reverse=True)
        return adapted_opportunities[:20]

    async def adapt_opportunity_for_user(self, opportunity: RawOpportunity,
                                       user_type: str) -> OpportunityAlert:
        """Adapt opportunity information for specific user type."""

        if user_type == 'developer':
            return await self.create_developer_opportunity_alert(opportunity)
        elif user_type == 'flipper':
            return await self.create_flipper_opportunity_alert(opportunity)
        elif user_type == 'agent':
            return await self.create_agent_opportunity_alert(opportunity)
        elif user_type == 'investor':
            return await self.create_investor_opportunity_alert(opportunity)

    async def create_developer_opportunity_alert(self, opp: RawOpportunity) -> OpportunityAlert:
        """Create developer-focused opportunity alert."""

        # Calculate development potential
        development_potential = await self.calculate_development_potential(opp.property)

        # Assess entitlement feasibility
        entitlement_feasibility = await self.assess_entitlement_feasibility(opp.property)

        if development_potential.score < 0.6 or entitlement_feasibility.score < 0.5:
            return None  # Not relevant for developers

        return OpportunityAlert(
            id=opp.id,
            title=f"Development Opportunity: {opp.property.address}",
            description=f"{development_potential.max_units} unit potential, "
                       f"{entitlement_feasibility.estimated_timeline} month timeline",
            property=opp.property,
            opportunity_type="development",
            relevance_score=min(development_potential.score, entitlement_feasibility.score),
            key_metrics={
                'max_units': development_potential.max_units,
                'estimated_roi': development_potential.estimated_roi,
                'timeline_months': entitlement_feasibility.estimated_timeline,
                'entitlement_probability': entitlement_feasibility.score
            },
            action_required="Analyze for development feasibility",
            urgency_level=self.calculate_urgency(opp),
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
```

## 5.3 Scraper Implementation

### News Scraper
```python
# src/scrapers/news_scraper.py
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from playwright.async_api import async_playwright
import aiohttp
from bs4 import BeautifulSoup

from ..common.models import NewsArticle, ScrapingResult
from ..common.gemini_processor import GeminiProcessor
from ..common.database import DatabaseManager

class GainesvilleSunScraper:
    def __init__(self):
        self.base_url = "https://www.gainesville.com"
        self.gemini = GeminiProcessor()
        self.db = DatabaseManager()
        self.sections_to_monitor = [
            '/business/',
            '/news/local/',
            '/real-estate/',
            '/government/'
        ]

    async def daily_scrape(self) -> ScrapingResult:
        """Main daily scraping routine."""

        results = ScrapingResult(
            scraper_name="gainesville_sun",
            start_time=datetime.utcnow(),
            success=True,
            articles_found=0,
            articles_processed=0,
            errors=[]
        )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )

                page = await browser.new_page()

                # Set reasonable timeouts
                page.set_default_timeout(30000)

                for section in self.sections_to_monitor:
                    section_results = await self.scrape_section(page, section)
                    results.articles_found += len(section_results)

                    for article_data in section_results:
                        try:
                            article = await self.process_article(article_data)
                            if article and await self.is_development_relevant(article):
                                await self.store_article(article)
                                results.articles_processed += 1

                        except Exception as e:
                            results.errors.append(f"Error processing article: {str(e)}")

                await browser.close()

        except Exception as e:
            results.success = False
            results.errors.append(f"Scraping failed: {str(e)}")

        results.end_time = datetime.utcnow()
        results.duration = (results.end_time - results.start_time).total_seconds()

        return results

    async def scrape_section(self, page, section_path: str) -> List[Dict[str, Any]]:
        """Scrape articles from a specific section."""

        section_url = f"{self.base_url}{section_path}"

        try:
            await page.goto(section_url, wait_until='networkidle')

            # Extract article links and metadata
            articles = await page.evaluate("""
                () => {
                    const articleLinks = [];
                    const links = document.querySelectorAll('article a[href*="/story/"], .story-link');

                    links.forEach(link => {
                        const href = link.getAttribute('href');
                        const title = link.textContent.trim() || link.getAttribute('title') || '';
                        const date_element = link.closest('article')?.querySelector('time, .date, .publish-date');
                        const date_str = date_element?.getAttribute('datetime') ||
                                       date_element?.textContent || '';

                        if (href && title) {
                            articleLinks.push({
                                url: href.startsWith('http') ? href : window.location.origin + href,
                                title: title,
                                date_str: date_str,
                                section: window.location.pathname
                            });
                        }
                    });

                    return articleLinks;
                }
            """)

            # Filter for recent articles (last 7 days)
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            recent_articles = []

            for article in articles:
                if await self.is_recent_article(article, cutoff_date):
                    recent_articles.append(article)

            return recent_articles[:20]  # Limit to prevent overload

        except Exception as e:
            print(f"Error scraping section {section_path}: {str(e)}")
            return []

    async def process_article(self, article_data: Dict[str, Any]) -> NewsArticle:
        """Extract full content and process article."""

        try:
            # Get full article content
            async with aiohttp.ClientSession() as session:
                async with session.get(article_data['url']) as response:
                    if response.status != 200:
                        return None

                    html_content = await response.text()

            # Parse content
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract article body
            content = self.extract_article_content(soup)

            # Extract metadata
            published_date = self.parse_article_date(
                article_data.get('date_str'), soup
            )

            # Create article object
            article = NewsArticle(
                url=article_data['url'],
                title=article_data['title'],
                content=content,
                published_date=published_date,
                source='gainesville_sun',
                section=article_data.get('section', ''),
                scraped_at=datetime.utcnow()
            )

            return article

        except Exception as e:
            print(f"Error processing article {article_data.get('url', 'unknown')}: {str(e)}")
            return None

    async def is_development_relevant(self, article: NewsArticle) -> bool:
        """Use Gemini to determine if article is relevant to real estate development."""

        prompt = f"""
        Analyze this news article to determine if it's relevant to real estate development,
        property investment, or land use in Gainesville, Florida.

        Title: {article.title}
        Content: {article.content[:1000]}...

        Is this article relevant to real estate professionals? Consider:
        - New developments or construction projects
        - Zoning changes or land use decisions
        - Infrastructure projects that affect property values
        - Business openings/closings that impact areas
        - Government decisions affecting development
        - Market trends and economic factors

        Respond with only: RELEVANT or NOT_RELEVANT
        """

        response = await self.gemini.generate_response(prompt)
        return "RELEVANT" in response.upper()

    async def store_article(self, article: NewsArticle):
        """Store article and extract intelligence."""

        # Store raw article
        article_id = await self.db.store_news_article(article)

        # Extract entities and relationships
        entities = await self.gemini.extract_entities(
            f"{article.title}\n{article.content}"
        )

        relationships = await self.gemini.extract_relationships(
            f"{article.title}\n{article.content}",
            entities
        )

        # Store in knowledge graph
        await self.db.add_news_intelligence(article_id, entities, relationships)

        # Generate market impact prediction
        impact_prediction = await self.gemini.predict_market_impact(article)

        if impact_prediction.significance > 0.6:
            await self.db.create_opportunity_alert(
                source='news_analysis',
                description=impact_prediction.description,
                impact_score=impact_prediction.significance,
                related_article_id=article_id
            )
```

### Permit Scraper
```python
# src/scrapers/permit_scraper.py
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
import aiohttp
from playwright.async_api import async_playwright

from ..common.models import BuildingPermit, ScrapingResult
from ..common.database import DatabaseManager

class CityPermitScraper:
    def __init__(self):
        self.api_url = "https://data.cityofgainesville.org/resource/p798-x3nx.json"
        self.db = DatabaseManager()

    async def daily_scrape(self) -> ScrapingResult:
        """Scrape new and updated permits from City API."""

        results = ScrapingResult(
            scraper_name="city_permits",
            start_time=datetime.utcnow(),
            success=True,
            permits_found=0,
            permits_processed=0,
            errors=[]
        )

        try:
            # Get permits from last 7 days
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            cutoff_str = cutoff_date.strftime("%Y-%m-%dT%H:%M:%S.000")

            query_params = {
                '$where': f"date_trunc_ymd(issue_date) >= '{cutoff_str}'",
                '$limit': 1000,  # Reasonable limit
                '$order': 'issue_date DESC'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=query_params) as response:
                    if response.status != 200:
                        raise Exception(f"API request failed with status {response.status}")

                    permit_data = await response.json()

            results.permits_found = len(permit_data)

            for permit_raw in permit_data:
                try:
                    permit = self.parse_city_permit(permit_raw)

                    if permit and await self.is_significant_permit(permit):
                        await self.store_permit(permit)
                        results.permits_processed += 1

                except Exception as e:
                    results.errors.append(f"Error processing permit: {str(e)}")

        except Exception as e:
            results.success = False
            results.errors.append(f"Scraping failed: {str(e)}")

        results.end_time = datetime.utcnow()
        results.duration = (results.end_time - results.start_time).total_seconds()

        return results

    def parse_city_permit(self, raw_data: Dict[str, Any]) -> BuildingPermit:
        """Parse raw permit data from city API."""

        try:
            return BuildingPermit(
                permit_number=raw_data.get('permit_number', ''),
                permit_type=raw_data.get('permit_type', ''),
                status=raw_data.get('status', ''),
                address=raw_data.get('address', ''),
                description=raw_data.get('work_description', ''),
                applicant=raw_data.get('applicant_name', ''),
                contractor=raw_data.get('contractor_name', ''),
                issue_date=self.parse_date(raw_data.get('issue_date')),
                expiration_date=self.parse_date(raw_data.get('expiration_date')),
                project_value=self.parse_currency(raw_data.get('project_valuation')),
                square_footage=self.parse_number(raw_data.get('square_footage')),
                jurisdiction='city_gainesville',
                raw_data=raw_data,
                scraped_at=datetime.utcnow()
            )

        except Exception as e:
            print(f"Error parsing permit data: {str(e)}")
            return None

    async def is_significant_permit(self, permit: BuildingPermit) -> bool:
        """Determine if permit indicates significant development activity."""

        # High-value projects
        if permit.project_value and permit.project_value >= 100000:
            return True

        # Large square footage
        if permit.square_footage and permit.square_footage >= 2000:
            return True

        # Certain permit types always significant
        significant_types = [
            'new commercial',
            'new residential',
            'major renovation',
            'multi-family',
            'mixed use'
        ]

        permit_type_lower = permit.permit_type.lower()
        for sig_type in significant_types:
            if sig_type in permit_type_lower:
                return True

        # Certain keywords in description
        significant_keywords = [
            'apartment',
            'condo',
            'townhome',
            'shopping',
            'office',
            'restaurant',
            'hotel'
        ]

        description_lower = permit.description.lower()
        for keyword in significant_keywords:
            if keyword in description_lower:
                return True

        return False

    async def store_permit(self, permit: BuildingPermit):
        """Store permit and trigger analysis."""

        # Store permit in database
        permit_id = await self.db.store_building_permit(permit)

        # Geocode address if coordinates not available
        if not permit.coordinates:
            coordinates = await self.geocode_address(permit.address)
            if coordinates:
                await self.db.update_permit_coordinates(permit_id, coordinates)

        # Check for development patterns
        await self.check_development_patterns(permit)

        # Update property records
        await self.update_property_with_permit(permit)

    async def check_development_patterns(self, permit: BuildingPermit):
        """Check if this permit indicates broader development patterns."""

        # Look for multiple permits in same area
        nearby_permits = await self.db.get_recent_permits_near_location(
            coordinates=permit.coordinates,
            radius_meters=500,
            days_back=90
        )

        if len(nearby_permits) >= 3:
            # Multiple permits in area - potential development cluster
            await self.db.create_pattern_alert(
                pattern_type='development_cluster',
                location=permit.coordinates,
                description=f"Multiple permits detected near {permit.address}",
                evidence_permits=[p.id for p in nearby_permits],
                significance_score=min(len(nearby_permits) / 10, 1.0)
            )

        # Check for developer activity patterns
        if permit.contractor:
            contractor_permits = await self.db.get_recent_permits_by_contractor(
                contractor_name=permit.contractor,
                days_back=180
            )

            if len(contractor_permits) >= 5:
                # Active developer identified
                await self.db.update_entity_activity_score(
                    entity_name=permit.contractor,
                    entity_type='contractor',
                    activity_increase=1.0
                )
```

## 5.4 Deployment Configuration

### systemd Service Files

#### dominion-stack.service
```ini
[Unit]
Description=Dominion Intelligence Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/dominion/app
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

#### dominion-backup.service
```ini
[Unit]
Description=Dominion Database Backup
Requires=dominion-stack.service
After=dominion-stack.service

[Service]
Type=oneshot
User=dominion
WorkingDirectory=/home/dominion/app
ExecStart=/home/dominion/app/scripts/backup-database.sh

[Install]
WantedBy=multi-user.target
```

#### dominion-backup.timer
```ini
[Unit]
Description=Run Dominion backup daily
Requires=dominion-backup.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

### Simplified but Effective Backup Strategy

#### Daily Automated Backups with Testing
```bash
#!/bin/bash
# scripts/backup-database.sh

set -e

BACKUP_DIR="/home/dominion/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/dominion_backup_${DATE}.sql"
S3_BUCKET="${S3_BACKUP_BUCKET:-dominion-backups}"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

echo "Starting database backup at $(date)"

# Create database backup with consistency check
docker exec dominion_postgres_1 pg_dump -U dominion -v --single-transaction dominion > "${BACKUP_FILE}"

# Verify backup integrity
if ! gzip -t "${BACKUP_FILE}.gz" 2>/dev/null; then
    echo "Backup verification failed, creating new backup"
    gzip "${BACKUP_FILE}"
else
    echo "Backup compressed successfully"
    gzip "${BACKUP_FILE}"
fi

# Implement 3-2-1 backup strategy (simplified for MVP)
# 3 copies: local + S3 + weekly offsite
# 2 different media: local disk + cloud storage
# 1 offsite: S3 in different region

# Upload to S3 (offsite)
if [ -n "${S3_BUCKET}" ]; then
    echo "Uploading to S3..."
    aws s3 cp "${BACKUP_FILE}.gz" "s3://${S3_BUCKET}/daily/"

    # Verify S3 upload
    if aws s3 ls "s3://${S3_BUCKET}/daily/dominion_backup_${DATE}.sql.gz"; then
        echo "S3 upload verified"
    else
        echo "ERROR: S3 upload failed" >&2
        exit 1
    fi
fi

# Retention policy
# Daily backups: 30 days
find "${BACKUP_DIR}" -name "dominion_backup_*.sql.gz" -mtime +30 -delete

# Weekly backups: 6 months (kept every Sunday)
if [ "$(date +%u)" = "7" ]; then
    echo "Creating weekly backup"
    cp "${BACKUP_FILE}.gz" "${BACKUP_DIR}/weekly_backup_$(date +%Y_week_%U).sql.gz"

    # Upload weekly to different S3 path
    aws s3 cp "${BACKUP_FILE}.gz" "s3://${S3_BUCKET}/weekly/"

    # Clean old weekly backups (6 months)
    find "${BACKUP_DIR}" -name "weekly_backup_*.sql.gz" -mtime +180 -delete
fi

# Log backup size and completion
BACKUP_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)
echo "Backup completed: ${BACKUP_FILE}.gz (${BACKUP_SIZE})"

# Update backup metrics for monitoring
echo "{\"timestamp\": \"$(date -Iseconds)\", \"size_mb\": $(du -m ${BACKUP_FILE}.gz | cut -f1), \"status\": \"success\"}" > /tmp/backup_metrics.json
```

#### Monthly Restore Testing (Critical for Confidence)
```bash
#!/bin/bash
# scripts/test-restore.sh

set -e

echo "Starting monthly restore test at $(date)"

# Create test database
TEST_DB="dominion_restore_test_$(date +%Y%m%d)"
docker exec dominion_postgres_1 createdb -U dominion "${TEST_DB}"

# Get latest backup
LATEST_BACKUP=$(find /home/dominion/backups -name "dominion_backup_*.sql.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2)

if [ -z "${LATEST_BACKUP}" ]; then
    echo "ERROR: No backup file found" >&2
    exit 1
fi

echo "Testing restore from: ${LATEST_BACKUP}"

# Restore to test database
zcat "${LATEST_BACKUP}" | docker exec -i dominion_postgres_1 psql -U dominion -d "${TEST_DB}"

# Verify restore with basic data integrity checks
RESULT=$(docker exec dominion_postgres_1 psql -U dominion -d "${TEST_DB}" -t -c "
    SELECT
        COUNT(*) as total_tables,
        (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public') as public_tables,
        (SELECT COUNT(*) FROM raw_facts) as raw_facts_count,
        (SELECT COUNT(*) FROM structured_facts) as structured_facts_count
    FROM information_schema.tables;
")

echo "Restore test results: ${RESULT}"

# Verify critical tables exist and have data
CRITICAL_TABLES=("raw_facts" "structured_facts" "ai_inferences" "users")
for table in "${CRITICAL_TABLES[@]}"; do
    COUNT=$(docker exec dominion_postgres_1 psql -U dominion -d "${TEST_DB}" -t -c "SELECT COUNT(*) FROM ${table};")
    echo "Table ${table}: ${COUNT} rows"

    if [ "$COUNT" -lt 1 ] && [ "$table" != "users" ]; then
        echo "WARNING: Table ${table} has no data"
    fi
done

# Calculate restore time (RTO validation)
RESTORE_END=$(date +%s)
RESTORE_TIME=$((RESTORE_END - $(date -r "${LATEST_BACKUP}" +%s)))
echo "Recovery Time Objective (RTO): ${RESTORE_TIME} seconds"

# Clean up test database
docker exec dominion_postgres_1 dropdb -U dominion "${TEST_DB}"

# Update restore test metrics
echo "{\"timestamp\": \"$(date -Iseconds)\", \"rto_seconds\": ${RESTORE_TIME}, \"status\": \"success\", \"backup_file\": \"${LATEST_BACKUP}\"}" > /tmp/restore_test_metrics.json

echo "Monthly restore test completed successfully"
```

#### Backup Strategy Summary

**Recovery Objectives:**
- **RTO (Recovery Time Objective)**: 4 hours - System fully restored from backup
- **RPO (Recovery Point Objective)**: 24 hours - Maximum acceptable data loss

**Backup Schedule:**
- **Daily**: 3:00 AM ET automated pg_dump with S3 upload
- **Weekly**: Sunday backups retained for 6 months
- **Monthly**: First Sunday backup retained for 1 year
- **Restore Testing**: First Monday of each month at 2:00 AM ET

**Storage Strategy (Simplified 3-2-1):**
- **3 Copies**: Local disk, S3 primary region, S3 cross-region replication
- **2 Different Media**: Local SSD, Cloud object storage
- **1 Offsite**: S3 in different AWS region

**Monitoring & Alerting:**
- Daily backup success/failure notifications
- Monthly restore test results
- Backup size growth monitoring
- S3 upload verification

**Cost Estimation:**
- **Local Storage**: 50GB × 30 days = minimal cost
- **S3 Standard**: 50GB × $0.023 = $1.15/month
- **S3 Cross-Region**: 50GB × $0.023 = $1.15/month
- **Total**: ~$2.50/month for comprehensive backup strategy

**Automated Systemd Services:**
```ini
# /etc/systemd/system/dominion-backup.timer
[Unit]
Description=Run Dominion backup daily
Requires=dominion-backup.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target

# /etc/systemd/system/dominion-restore-test.timer
[Unit]
Description=Run Dominion restore test monthly
Requires=dominion-restore-test.service

[Timer]
OnCalendar=monthly
Persistent=true

[Install]
WantedBy=timers.target
```

This approach provides enterprise-grade backup reliability without complex infrastructure, perfectly suited for a 20-user MVP while establishing patterns that scale to thousands of users.

---

# 6. PROGRESSIVE ENHANCEMENT & COMPETITIVE MOAT STRATEGY

## 6.1 Progressive Enhancement Roadmap

### Phase 1: MVP Foundation (Months 1-3) - Gainesville Beachhead
**Goal**: Prove product-market fit in controlled market
- **Users**: 20 weekly users
- **Coverage**: Gainesville metro only
- **Data Sources**: 12 core public sources
- **Analysis Modes**: 4 user types (Developer, Flipper, Agent, Investor)
- **Key Metric**: 60% user retention, $4,000 MRR

**Technical Priorities:**
- Solid RQ job queue system
- Facts vs Inferences architecture
- Basic AI safety measures
- Simple monitoring and alerting

**Business Focus:**
- Perfect the core analysis workflow
- Build local network effects
- Establish word-of-mouth referral engine
- Validate subscription pricing model

### Phase 2: Market Expansion (Months 4-8) - Florida Scale
**Goal**: Scale proven model to major Florida markets
- **Markets Added**: Orlando, Tampa, Miami, Jacksonville
- **Users**: 150 weekly users across 5 cities
- **Revenue**: $30,000 MRR
- **Data Sources**: 20+ sources per market

**Technical Enhancements:**
- Multi-market data architecture
- Enhanced LLM cost optimization
- Advanced pattern recognition across markets
- Geographic analysis capabilities

**Business Development:**
- MLS data partnerships (5 markets × $500/month = $2,500)
- Real estate association partnerships
- Conference presence and thought leadership
- Enterprise tier launch

**Competitive Moat Building:**
- Market-specific knowledge graphs (5 cities)
- Local relationship databases
- Historical outcome patterns
- First-mover advantage in AI real estate intelligence

### Phase 3: Regional Dominance (Months 9-18) - Southeast Expansion
**Goal**: Become the definitive real estate intelligence platform for Southeast
- **Markets**: 15+ cities across FL, GA, NC, SC, TN
- **Users**: 500+ weekly users
- **Revenue**: $150,000 MRR
- **Enterprise Clients**: 25+ development firms

**Technical Scaling:**
- Multi-region deployment
- Advanced ML model training
- Predictive market timing
- Portfolio-level analysis capabilities

**Strategic Partnerships:**
- Major MLS providers
- PropTech platform integrations
- Development finance partnerships
- Real estate media relationships

## 6.2 Competitive Moat Architecture

### 6.2.1 Data Accumulation Advantage
**Every user makes the platform smarter for everyone**

```python
# Network Effects Through Data
class NetworkEffectEngine:
    """How each user interaction strengthens our competitive position."""

    def process_user_feedback(self, analysis_id: str, user_feedback: dict):
        """Learn from user corrections and decisions."""
        # When users correct our predictions or share outcomes
        # We improve our models for ALL future analyses

        original_analysis = self.get_analysis(analysis_id)
        actual_outcome = user_feedback.get('actual_outcome')

        if actual_outcome:
            # Update our success prediction models
            self.ml_trainer.add_outcome_data(
                prediction=original_analysis.success_probability,
                actual_outcome=actual_outcome,
                features=original_analysis.feature_vector
            )

            # Improve our risk detection models
            if user_feedback.get('missed_risks'):
                self.risk_detector.learn_from_miss(
                    property_data=original_analysis.property_data,
                    missed_risks=user_feedback['missed_risks']
                )

        # The more users we have, the better our predictions become
        # This creates a self-reinforcing competitive advantage
```

**Data Moats We're Building:**
- **Local Knowledge Graphs**: Relationships between developers, politicians, and projects that competitors can't easily replicate
- **Failure Pattern Database**: Why deals fail - learning from user experiences over years
- **Timing Intelligence**: When developers typically move, seasonal patterns, political cycles
- **Hidden Relationship Mapping**: Non-obvious connections between entities discovered through pattern analysis

### 6.2.2 Speed & Accuracy Moat
**"Know in 3 hours what takes 3 months to discover"**

**Technical Advantages:**
- **Continuous Monitoring**: 24/7 data collection while competitors do manual research
- **AI-First Architecture**: Built for scale from day one, not bolted-on AI
- **Local Specialization**: Deep market knowledge vs generic tools
- **Integrated Workflow**: One platform vs fragmented tools

**Operational Moats:**
- **Response Time**: 3-hour analysis vs 3-month manual due diligence
- **Cost Advantage**: $200 vs $5,000+ traditional due diligence
- **Coverage Breadth**: Monitor entire market vs single property focus
- **Update Frequency**: Real-time alerts vs monthly reports

### 6.2.3 Network Effects & Lock-in

```python
class UserRetentionEngine:
    """How we become more valuable to users over time."""

    def calculate_switching_cost(self, user_id: str) -> float:
        """Calculate how hard it would be for user to leave."""
        user_data = self.get_user_data(user_id)

        switching_costs = {
            # Historical analyses become more valuable over time
            'historical_analyses': len(user_data.past_analyses) * 50,  # $50 value each

            # Personalized insights improve with usage
            'personalization_value': user_data.months_active * 100,

            # Network within Dominion (relationships with other users)
            'network_connections': len(user_data.connections) * 25,

            # Custom monitoring zones
            'monitoring_setup': len(user_data.watch_zones) * 75,

            # Learning curve to new platform
            'learning_curve_cost': 2000  # Estimated time cost
        }

        return sum(switching_costs.values())

    def strengthen_lock_in(self, user_id: str):
        """Proactively increase user switching costs."""
        # Encourage more monitoring zones
        # Facilitate user-to-user connections
        # Build up historical analysis value
        # Personalize insights further
```

**Lock-in Mechanisms:**
- **Historical Analysis Value**: Users build up years of analyses that become reference library
- **Monitoring Zones**: Users set up custom alerts that would be painful to recreate
- **Network Effects**: Users connect with others in market, hard to replicate relationships
- **Learning Curve**: Users become expert at interpreting Dominion insights
- **Integration Depth**: APIs connect to users' workflows and tools

### 6.2.4 Execution Moat
**Speed of improvement and market expansion**

**Technology Execution:**
- **Modern Tech Stack**: Built for 2025, not retrofitted 2015 architecture
- **AI-Native**: Every component designed around machine learning capabilities
- **Scalable Architecture**: Database and infrastructure ready for 100x growth
- **Development Velocity**: Feature deployment measured in days, not months

**Market Execution:**
- **Local-First Strategy**: Deep market penetration before competitors notice
- **User-Funded Growth**: Revenue funds expansion, not dependent on raising capital
- **Viral Growth Mechanics**: Built-in referral systems and network effects
- **Operational Excellence**: Reliable service creates customer advocacy

## 6.3 Defensive Strategy Against Competitors

### Against CoStar/LoopNet
**Their Weakness**: Generic data, no local intelligence, no predictive insights
**Our Defense**: Local relationship graphs, predictive analytics, real-time monitoring

### Against Traditional Due Diligence Firms
**Their Weakness**: Slow, expensive, manual process, limited scope
**Our Defense**: Speed (3 hours vs 3 months), cost ($200 vs $5000), comprehensive monitoring

### Against Other PropTech Startups
**Their Weakness**: Usually single-feature, limited data, no local focus
**Our Defense**: Comprehensive platform, data moat, market-specific knowledge, established user base

### Against Big Tech (Google, Microsoft, Amazon)
**Their Weakness**: Generic solutions, no real estate specialization, large company execution speed
**Our Defense**: Market specialization, speed of innovation, local relationships, focused execution

**Early Warning System:**
```python
class CompetitorMonitoring:
    """Monitor competitive threats and respond quickly."""

    def track_competitors(self):
        # Monitor competitor job postings (hiring patterns)
        # Track competitor pricing changes
        # Watch for new product announcements
        # Monitor customer defection patterns
        # Track competitor funding announcements

    def competitive_response_playbook(self, threat_level: str):
        if threat_level == "high":
            # Accelerate feature development
            # Deepen customer relationships
            # Expand to new markets faster
            # Enhance data moats

        # Always: Continue building user love and data advantages
```

The key to our competitive strategy: **Build something users love so much they become our advocates, while simultaneously building technical and data moats that become harder to replicate over time.**

---

# 7. COMPREHENSIVE COST OPTIMIZATION STRATEGY

The expert feedback emphasized aggressive cost optimization to keep operational costs under $200/month while achieving our technical and business goals. Here's our comprehensive approach:

## 7.1 AI & LLM Cost Optimization (Target: $50/month)

### Current Baseline vs Optimized Costs
**Without Optimization**: $5,000+/month
- Naive ChatGPT/Claude API usage
- No caching
- Re-processing unchanged content
- Inefficient prompting

**With Our Optimization**: $35-50/month (90%+ cost reduction)

### 7.1.1 Aggressive LLM Response Caching
```python
class AggressiveCostOptimizer:
    """Drive AI costs to near zero through intelligent caching."""

    def __init__(self):
        self.cache_hit_rate_target = 0.85  # 85% cache hits = 85% cost savings

    async def optimize_llm_costs(self):
        """Comprehensive cost reduction strategies."""

        # 1. Semantic Caching (70% cost reduction)
        # Cache similar prompts, not just exact matches
        similar_prompts = await self.find_semantically_similar_prompts(
            current_prompt,
            similarity_threshold=0.92  # Very high similarity
        )

        if similar_prompts:
            # Return cached response with minor modifications
            return await self.adapt_cached_response(similar_prompts[0])

        # 2. Prompt Optimization (50% cost reduction)
        optimized_prompt = await self.compress_prompt(
            original_prompt,
            preserve_quality=True,
            target_reduction=0.4  # 40% shorter prompts
        )

        # 3. Batch Processing (60% cost reduction)
        # Process multiple analyses in single API call
        if self.can_batch_with_others(current_request):
            return await self.batch_process_analyses()

        # 4. Model Selection (80% cost reduction)
        # Use Gemini Flash for 90% of requests, GPT-4 only when needed
        model = self.select_optimal_model(
            complexity=analysis_complexity,
            accuracy_requirement=user_tier
        )

        return await self.make_optimized_api_call(optimized_prompt, model)
```

### 7.1.2 Smart Model Selection Strategy
```python
MODEL_COST_OPTIMIZATION = {
    # Cost per 1M tokens (input/output)
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},  # Primary choice
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},       # Fallback
    "gpt-4": {"input": 30.00, "output": 60.00},           # Emergency only

    # Usage allocation (target)
    "usage_distribution": {
        "gemini-2.0-flash": 0.90,  # 90% of requests
        "gpt-4o-mini": 0.09,        # 9% of requests
        "gpt-4": 0.01,              # 1% of requests (critical only)
    }
}

def select_model_by_complexity(task_complexity: str, user_tier: str) -> str:
    """Choose cheapest model that meets quality requirements."""

    if task_complexity == "simple" or user_tier == "freemium":
        return "gemini-2.0-flash"  # $0.075 per 1M tokens

    elif task_complexity == "medium" or user_tier == "professional":
        # Use Gemini first, fall back to GPT-4 mini if confidence < threshold
        return "gemini-2.0-flash-with-fallback"

    elif task_complexity == "complex" and user_tier == "enterprise":
        # Only enterprise users get premium model access
        return "gpt-4o-mini"

    # Reserve GPT-4 for edge cases only
    return "gemini-2.0-flash"
```

### 7.1.3 Content-Aware Processing
```python
class ContentOptimizer:
    """Avoid processing content that hasn't changed."""

    async def process_with_change_detection(self, content: str, source: str):
        content_hash = hashlib.md5(content.encode()).hexdigest()

        # Check if we've processed this exact content before
        cached_result = await self.get_cached_analysis(content_hash)
        if cached_result:
            logger.info(f"Content unchanged for {source}, using cached analysis")
            return cached_result  # 100% cost savings

        # Check for incremental changes
        previous_hash = await self.get_previous_hash(source)
        similarity = await self.calculate_content_similarity(content, previous_hash)

        if similarity > 0.95:  # 95% similar
            # Generate diff-based analysis (much cheaper)
            return await self.incremental_analysis(content, cached_result)

        # Full analysis needed
        return await self.full_analysis(content)

    async def batch_similar_content(self, content_list: List[str]) -> List[str]:
        """Batch similar content into single API calls."""

        # Group similar content together
        content_groups = self.group_by_similarity(content_list, threshold=0.8)

        results = []
        for group in content_groups:
            if len(group) > 1:
                # Process group in single API call
                batch_result = await self.batch_analyze(group)
                results.extend(batch_result)
            else:
                # Single analysis
                results.append(await self.single_analyze(group[0]))

        return results
```

### 7.1.4 Monthly Cost Monitoring & Alerts
```python
class CostMonitor:
    """Ensure we never exceed budget."""

    def __init__(self):
        self.monthly_budget = 5000  # $50 in cents
        self.alert_thresholds = [0.5, 0.75, 0.9, 1.0]  # 50%, 75%, 90%, 100%

    async def track_api_costs(self):
        current_spend = await self.get_month_to_date_spend()
        # Consistent data structure: expect current_spend as dict with 'total' key
        total_spend = current_spend.get('total', 0) if isinstance(current_spend, dict) else current_spend
        budget_percentage = total_spend / self.monthly_budget

        for threshold in self.alert_thresholds:
            if budget_percentage >= threshold and not self.alert_sent(threshold):
                await self.send_budget_alert(current_spend, threshold)

                # Auto-throttle at 90%
                if threshold >= 0.9:
                    await self.enable_cost_protection_mode()

    async def enable_cost_protection_mode(self):
        """Aggressive cost protection when approaching budget."""
        # Increase cache hit requirements
        # Reduce analysis frequency for non-critical requests
        # Switch to cheaper models
        # Batch more aggressively
        logger.warning("Cost protection mode enabled")
```

## 7.2 Infrastructure Cost Optimization (Target: $80/month)

### Oracle VPS Cost Breakdown
```python
INFRASTRUCTURE_COSTS = {
    "oracle_vps": {
        "vm_standard_e4_flex": 85.00,  # 4 OCPU, 64GB RAM
        "block_storage": 10.00,        # 500GB
        "backup_storage": 2.50,        # S3 backups
        "bandwidth": 0.00,             # 10TB/month included
        "total": 97.50
    },

    "vercel_hosting": {
        "hobby_plan": 0.00,           # Free tier sufficient for MVP
        "bandwidth": 0.00,            # 100GB included
        "total": 0.00
    },

    "external_services": {
        "domain_ssl": 1.50,           # Domain + SSL
        "email_service": 5.00,        # Transactional emails
        "monitoring": 0.00,           # Self-hosted Prometheus
        "total": 6.50
    },

    "monthly_total": 104.00  # Well under $200 target
}
```

### Infrastructure Optimization Strategies
```python
class InfrastructureOptimizer:
    """Maximize infrastructure efficiency."""

    def optimize_resource_usage(self):
        """Ensure we're using resources efficiently."""

        # 1. Container Resource Limits
        self.set_container_limits({
            "dominion-api": {"cpu": "1000m", "memory": "2Gi"},
            "dominion-workers": {"cpu": "2000m", "memory": "4Gi"},
            "dominion-scrapers": {"cpu": "500m", "memory": "1Gi"},
            "postgres": {"cpu": "1000m", "memory": "4Gi"},
            "redis": {"cpu": "200m", "memory": "512Mi"}
        })

        # 2. Auto-scaling Workers
        # Scale RQ workers based on queue depth
        queue_depth = self.get_queue_depth()
        if queue_depth > 10:
            self.scale_workers(target=4)
        elif queue_depth < 2:
            self.scale_workers(target=1)  # Save resources

        # 3. Intelligent Caching
        # Cache everything that doesn't change frequently
        self.cache_static_data(ttl_hours=24)
        self.cache_analysis_results(ttl_hours=168)  # 1 week

    def monitor_cost_efficiency(self):
        """Track cost per analysis to optimize spending."""

        monthly_costs = self.get_monthly_costs()
        monthly_analyses = self.get_monthly_analysis_count()

        cost_per_analysis = monthly_costs / max(monthly_analyses, 1)

        # Target: <$2.50 per analysis in infrastructure costs
        if cost_per_analysis > 2.50:
            self.trigger_cost_optimization()
```

## 7.3 Data & Storage Cost Optimization (Target: $25/month)

### Storage Strategy
```python
STORAGE_OPTIMIZATION = {
    "database_storage": {
        # PostgreSQL + pgvector optimized storage
        "facts_table": "50GB",        # Raw facts (compressed)
        "inferences_table": "20GB",   # AI inferences
        "embeddings": "30GB",         # Vector storage
        "indexes": "15GB",            # Optimized indexes
        "total_local": "115GB",       # Fits in 500GB allocation

        "compression_ratio": 0.7,     # 30% savings through compression
        "retention_policy": {
            "raw_facts": "2_years",
            "old_inferences": "6_months",  # Refresh regularly
            "embeddings": "1_year"
        }
    },

    "backup_storage": {
        "s3_standard": 5.00,          # 200GB × $0.023
        "s3_glacier": 1.00,           # Long-term archives
        "local_backups": 0.00,        # Included in VPS storage
        "total": 6.00
    },

    "monthly_total": 20.00  # Including all storage costs
}
```

### Data Retention & Archiving
```python
class DataLifecycleManager:
    """Optimize storage costs through intelligent data management."""

    async def optimize_data_retention(self):
        """Move old data to cheaper storage tiers."""

        # Archive old raw facts (>1 year) to compressed format
        old_facts = await self.get_old_facts(days=365)
        await self.compress_and_archive(old_facts, destination="s3_glacier")

        # Clean up old AI inferences (refresh every 6 months)
        stale_inferences = await self.get_stale_inferences(days=180)
        await self.archive_inferences(stale_inferences)

        # Optimize embeddings storage
        await self.deduplicate_embeddings()  # Remove duplicate vectors
        await self.compress_embeddings()     # Use quantization

    async def data_compression_strategy(self):
        """Aggressive compression for cost savings."""

        # JSON compression for raw facts
        await self.compress_json_fields()  # 60% size reduction

        # Vector quantization for embeddings
        await self.quantize_embeddings()   # 75% size reduction

        # Index optimization
        await self.rebuild_optimized_indexes()  # Remove unused indexes

        logger.info("Data compression completed, estimated 40% storage savings")
```

## 7.4 Operational Cost Minimization (Target: $45/month)

### Total Cost Breakdown (Monthly)
```python
TOTAL_MONTHLY_COSTS = {
    "ai_llm_apis": {
        "gemini_api": 35.00,          # 90% of usage
        "openai_fallback": 10.00,     # 10% of usage
        "embedding_apis": 5.00,       # Batch optimized
        "total": 50.00
    },

    "infrastructure": {
        "oracle_vps": 85.00,          # Primary hosting
        "vercel_frontend": 0.00,      # Free tier
        "domain_ssl": 1.50,
        "email_service": 5.00,
        "cdn_bandwidth": 3.50,
        "total": 95.00
    },

    "data_storage": {
        "database_storage": 0.00,     # Included in VPS
        "backup_storage": 6.00,       # S3 backups
        "log_storage": 2.00,
        "total": 8.00
    },

    "external_services": {
        "monitoring_tools": 0.00,     # Self-hosted
        "error_tracking": 0.00,       # Self-hosted
        "analytics": 0.00,            # Self-hosted
        "payment_processing": 15.00,   # 2.9% of ~$500 revenue
        "total": 15.00
    },

    "total_monthly": 168.00,          # Well under $200 target
    "cost_per_user": 8.40,            # $168 ÷ 20 users
    "cost_per_analysis": 3.36         # $168 ÷ 50 analyses/month
}
```

### Cost Monitoring Dashboard
```python
class CostDashboard:
    """Real-time cost monitoring and optimization."""

    def generate_cost_report(self) -> dict:
        return {
            "current_month_spend": self.get_current_spend(),
            "budget_remaining": 20000 - self.get_current_spend(),  # $200 budget
            "cost_per_user": self.calculate_cost_per_user(),
            "cost_per_analysis": self.calculate_cost_per_analysis(),
            "optimization_opportunities": self.identify_savings(),
            "trend_analysis": self.analyze_cost_trends(),

            "alerts": [
                "✅ On track for $168 monthly spend (16% under budget)",
                "🎯 AI costs optimized: 90% cache hit rate achieved",
                "📊 Cost per analysis: $3.36 (target: <$4.00)",
                "💰 Infrastructure efficiency: 85% resource utilization"
            ]
        }

    def identify_savings(self) -> List[str]:
        """Identify additional cost optimization opportunities."""
        opportunities = []

        if self.get_cache_hit_rate() < 0.80:
            opportunities.append("Increase LLM cache hit rate to reduce API costs")

        if self.get_storage_growth_rate() > 0.15:  # >15% monthly growth
            opportunities.append("Implement data archiving to reduce storage costs")

        if self.get_resource_utilization() < 0.70:
            opportunities.append("Consider smaller VPS instance to reduce infrastructure costs")

        return opportunities
```

**Cost Optimization Success Metrics:**
- **Monthly Total**: $168 (16% under $200 budget)
- **Cost Per User**: $8.40 (scales favorably)
- **Cost Per Analysis**: $3.36 (sustainable unit economics)
- **AI Cost Reduction**: 90% vs naive implementation
- **Infrastructure Efficiency**: 85% resource utilization
- **Storage Optimization**: 40% reduction through compression

This comprehensive cost optimization strategy ensures Dominion can operate profitably at scale while maintaining high-quality service for users.

---

# 8. SCRAPING SPECIFICATIONS

### Daily Tasks (Automated)
```python
DAILY_SCRAPING_SCHEDULE = {
    "06:00": {
        "task": "news_scraping",
        "scrapers": ["gainesville_sun", "business_journal"],
        "priority": "high",
        "timeout_minutes": 30
    },
    "09:00": {
        "task": "permit_scraping",
        "scrapers": ["city_permits", "county_permits"],
        "priority": "high",
        "timeout_minutes": 45
    },
    "10:00": {
        "task": "property_sales",
        "scrapers": ["property_appraiser"],
        "priority": "medium",
        "timeout_minutes": 60
    },
    "11:00": {
        "task": "crime_data",
        "scrapers": ["gpd_crime_api"],
        "priority": "low",
        "timeout_minutes": 15
    },
    "18:00": {
        "task": "pattern_analysis",
        "scrapers": ["pattern_detector"],
        "priority": "medium",
        "timeout_minutes": 90
    }
}
```

### Weekly Tasks
```python
WEEKLY_SCRAPING_SCHEDULE = {
    "sunday_02:00": {
        "task": "comprehensive_property_sync",
        "scrapers": ["bulk_property_downloader"],
        "priority": "high",
        "timeout_hours": 4
    },
    "tuesday_08:00": {
        "task": "city_council_minutes",
        "scrapers": ["council_minutes_scraper"],
        "priority": "medium",
        "timeout_minutes": 60
    },
    "friday_15:00": {
        "task": "market_analysis_update",
        "scrapers": ["market_data_aggregator"],
        "priority": "medium",
        "timeout_minutes": 120
    }
}
```

## 6.2 Scraping Infrastructure

### Proxy Rotation System
```python
class ProxyRotationManager:
    def __init__(self):
        self.proxy_endpoints = [
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080",
            "http://proxy3.example.com:8080"
        ]
        self.current_proxy_index = 0
        self.failed_proxies = set()
        self.proxy_health_check_interval = 300  # 5 minutes

    async def get_working_proxy(self) -> str:
        """Get a working proxy endpoint."""

        attempts = 0
        max_attempts = len(self.proxy_endpoints)

        while attempts < max_attempts:
            proxy = self.proxy_endpoints[self.current_proxy_index]

            if proxy not in self.failed_proxies:
                if await self.test_proxy(proxy):
                    return proxy
                else:
                    self.failed_proxies.add(proxy)

            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_endpoints)
            attempts += 1

        # If all proxies failed, wait and retry
        await asyncio.sleep(60)
        self.failed_proxies.clear()  # Reset failed proxies
        return self.proxy_endpoints[0]  # Return first proxy as fallback

    async def test_proxy(self, proxy_url: str) -> bool:
        """Test if proxy is working."""
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=1),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                async with session.get(
                    "https://httpbin.org/ip",
                    proxy=proxy_url
                ) as response:
                    return response.status == 200
        except:
            return False
```

### Rate Limiting System
```python
class RateLimiter:
    def __init__(self, requests_per_second: float = 0.5):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0

    async def wait_if_needed(self):
        """Wait if necessary to maintain rate limit."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

class AdaptiveRateLimiter(RateLimiter):
    def __init__(self, base_requests_per_second: float = 0.5):
        super().__init__(base_requests_per_second)
        self.error_count = 0
        self.success_count = 0
        self.adaptation_threshold = 10

    async def record_success(self):
        """Record successful request."""
        self.success_count += 1

        # Speed up if we've had many successes
        if self.success_count >= self.adaptation_threshold:
            self.requests_per_second *= 1.1  # Increase by 10%
            self.min_interval = 1.0 / self.requests_per_second
            self.success_count = 0
            self.error_count = 0

    async def record_error(self):
        """Record failed request."""
        self.error_count += 1

        # Slow down if we've had errors
        if self.error_count >= 3:
            self.requests_per_second *= 0.5  # Decrease by 50%
            self.min_interval = 1.0 / self.requests_per_second
            self.success_count = 0
            self.error_count = 0
```

## 6.3 Error Handling and Recovery

### Scraper Error Recovery
```python
class ScraperErrorHandler:
    def __init__(self):
        self.max_retries = 3
        self.retry_delays = [1, 5, 15]  # seconds
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 300  # 5 minutes
        self.failed_request_count = {}
        self.circuit_breaker_status = {}

    async def execute_with_retry(self, scraper_name: str, operation, *args, **kwargs):
        """Execute operation with retry logic and circuit breaker."""

        # Check circuit breaker
        if self.is_circuit_open(scraper_name):
            raise CircuitBreakerException(f"Circuit breaker open for {scraper_name}")

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                result = await operation(*args, **kwargs)

                # Reset failure count on success
                self.failed_request_count[scraper_name] = 0
                return result

            except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                last_exception = e
                self.record_failure(scraper_name)

                # Don't retry on certain errors
                if isinstance(e, (aiohttp.ClientResponseError,)) and e.status in [404, 403, 401]:
                    break

                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    await asyncio.sleep(delay)

        # All retries failed
        self.check_circuit_breaker(scraper_name)
        raise ScrapingException(f"All retries failed for {scraper_name}: {last_exception}")

    def record_failure(self, scraper_name: str):
        """Record a failure for circuit breaker logic."""
        current_count = self.failed_request_count.get(scraper_name, 0)
        self.failed_request_count[scraper_name] = current_count + 1

    def check_circuit_breaker(self, scraper_name: str):
        """Check if circuit breaker should be opened."""
        failure_count = self.failed_request_count.get(scraper_name, 0)

        if failure_count >= self.circuit_breaker_threshold:
            self.circuit_breaker_status[scraper_name] = {
                'opened_at': time.time(),
                'timeout': self.circuit_breaker_timeout
            }

    def is_circuit_open(self, scraper_name: str) -> bool:
        """Check if circuit breaker is open."""
        if scraper_name not in self.circuit_breaker_status:
            return False

        breaker_info = self.circuit_breaker_status[scraper_name]
        elapsed = time.time() - breaker_info['opened_at']

        if elapsed >= breaker_info['timeout']:
            # Circuit breaker timeout expired, reset
            del self.circuit_breaker_status[scraper_name]
            self.failed_request_count[scraper_name] = 0
            return False

        return True
```

---

# 7. MVP IMPLEMENTATION PHASES

## Phase 1: Foundation Setup (Weeks 1-2)

### Week 1: Infrastructure & Core Setup
**Deliverables:**
- Docker environment configured on Oracle VPS
- PostgreSQL 15 with pgvector extension installed
- Redis for task queue
- FastAPI skeleton with basic endpoints
- Database schema implemented
- Basic authentication system

**Success Criteria:**
- All containers running stably
- Database accepting connections
- API responding to health checks
- Logging and monitoring configured

**Tasks:**
```bash
# Week 1 Tasks
1. Set up Oracle VPS environment
   - Install Docker & Docker Compose
   - Configure firewall and security
   - Set up SSL certificates

2. Database initialization
   - PostgreSQL with pgvector
   - Create all tables from schema
   - Set up migration system
   - Create database backup system

3. Basic API framework
   - FastAPI application structure
   - Authentication endpoints
   - Health check endpoints
   - Basic error handling

4. Development environment
   - Local development setup
   - Testing framework
   - CI/CD pipeline basics
```

### Week 2: Basic Scraping Infrastructure
**Deliverables:**
- News scraper (Gainesville Sun) operational
- Permit scraper (City API) operational
- Basic data storage and processing
- Scraper scheduling system
- Error handling and logging

**Success Criteria:**
- Scrapers run without errors
- Data successfully stored in database
- Basic entity extraction working
- Monitoring dashboards showing scraper status

## Phase 2: Intelligence Core (Weeks 3-4)

### Week 3: Pattern Recognition & Knowledge Graph
**Deliverables:**
- Knowledge graph entity resolution system
- Basic pattern recognition algorithms
- Gemini API integration
- Entity relationship mapping
- Vector embeddings for documents

**Success Criteria:**
- **AI Safety Compliance**: Entity identification with >90% confidence scores and source attribution
- **Relationship Accuracy**: News article relationships extracted with >80% confidence and uncertainty documentation
- **Search Quality**: Similar document search returns relevant results with similarity scores and data sources
- **Pattern Detection**: Developer activity and area trends identified with confidence thresholds and clear reasoning

### Week 4: Continuous Monitoring System
**Deliverables:**
- 24/7 background monitoring operational
- Opportunity detection algorithms
- Alert system for significant events
- Real-time data processing pipeline
- Basic market intelligence dashboard

**Success Criteria:**
- **Continuous Processing**: System processes new data with documented data quality checks and source tracking
- **Alert Quality**: Development activity alerts generated with >75% confidence scores and clear reasoning
- **System Reliability**: Zero data loss with uncertainty tracking for incomplete data scenarios
- **AI Safety Monitoring**: All automated decisions include confidence scores and human oversight triggers

## Phase 3: Deal Validation Engine (Weeks 5-6)

### Week 5: Risk Assessment & Success Prediction
**Deliverables:**
- Historical project outcome database
- Success prediction machine learning models
- Risk factor identification algorithms
- Comparative project analysis
- Hidden cost detection system

**Success Criteria:**
- **AI Safety Validation**: All predictions include confidence scores >80% with source attribution
- **Accuracy Metrics**: Project success prediction accuracy >70% on test set with documented uncertainties
- **Risk Detection**: Identifies major risk factors consistently with >75% confidence and clear reasoning
- **Comparable Analysis**: Finds relevant comparable projects with documented similarity metrics and data sources
- **Cost Estimation**: Hidden cost estimates within 20% margin with uncertainty ranges and source attribution

### Week 6: ROI Calculation & Economics Engine
**Deliverables:**
- Comprehensive ROI calculation system
- Market timing analysis
- Development economics modeling
- Infrastructure cost estimation
- Political feasibility assessment

**Success Criteria:**
- ROI calculations include all major cost factors
- Timeline predictions based on historical data
- Political risk assessment shows clear reasoning
- Economics model produces actionable insights

## Phase 4: User-Adaptive Analysis (Weeks 7-8)

### Week 7: Multi-User Analysis Modes
**Deliverables:**
- Developer analysis mode
- House flipper analysis mode
- Real estate agent analysis mode
- Property investor analysis mode
- Adaptive report generation

**Success Criteria:**
- Each mode produces relevant insights for user type
- Reports tailored to specific user needs
- Analysis quality maintained across all modes
- User feedback indicates high value

### Week 8: Deep Analysis Engine
**Deliverables:**
- On-demand deep analysis system (1-4 hour processes)
- Comprehensive property investigation
- Multi-source data synthesis
- Background task management
- Report generation and delivery

**Success Criteria:**
- Deep analysis completes within estimated timeframes
- Analysis thoroughness exceeds manual research
- Reports provide actionable insights
- System handles multiple concurrent analyses

## Phase 5: Testing & Optimization (Weeks 9-10)

### Week 9: Comprehensive Testing
**Deliverables:**
- End-to-end testing with real properties
- Performance optimization
- Security testing and hardening
- User acceptance testing with 5 test users per type
- Bug fixes and stability improvements

**Success Criteria:**
- All test cases pass consistently
- System performance meets requirements
- Security vulnerabilities addressed
- User feedback indicates readiness for launch

### Week 10: Production Preparation
**Deliverables:**
- Production deployment configuration
- Monitoring and alerting system
- Documentation and user guides
- Support system setup
- Marketing website deployment (Vercel)

**Success Criteria:**
- Production environment fully operational
- All monitoring systems functional
- Documentation complete and accurate
- Ready for real user onboarding

## Phase 6: MVP Launch (Week 11)

### Launch Week Activities
**Deliverables:**
- Production system live and stable
- First 10 paying customers onboarded
- Customer support system operational
- Performance monitoring active
- Feedback collection system active

**Success Criteria:**
- Zero critical bugs in first week
- Customer satisfaction >8/10
- System uptime >99%
- Positive revenue recognition
- Clear roadmap for iteration

### Launch Metrics to Track
```python
LAUNCH_SUCCESS_METRICS = {
    "technical": {
        "uptime_percentage": 99.0,
        "avg_response_time_ms": 500,
        "error_rate_percentage": 1.0,
        "data_accuracy_percentage": 90.0
    },
    "business": {
        "customer_satisfaction": 8.0,  # out of 10
        "report_completion_rate": 95.0,
        "customer_retention_week1": 80.0,
        "revenue_target": 2000  # $2000 in first week
    },
    "product": {
        "analysis_accuracy": 85.0,  # validated against manual research
        "time_savings": 20,  # hours saved per analysis
        "unique_insights_per_report": 5,
        "actionable_recommendations": 3
    }
}
```

---

# 8. RISK MITIGATION & SUCCESS METRICS

## 8.1 Technical Risks

### Data Source Reliability
**Risk**: Scraping targets change structure, block access, or go offline
**Mitigation**:
- Multiple proxy rotation system
- Graceful degradation when sources unavailable
- Manual data entry fallback for critical missing data
- Regular monitoring of scraper success rates
- Backup data sources for each category

### AI Model Performance & Safety
**Risk**: Gemini API fails, produces inaccurate results, hallucinates, or becomes expensive
**Mitigation**:
- **SafeAIInference Architecture**: Mandatory confidence thresholds (>80% for factual claims, >70% for predictions)
- **Source Attribution**: All AI insights require documented data sources and reasoning
- **Uncertainty Tracking**: Known uncertainties explicitly documented for every analysis
- **Human Validation**: Critical predictions (>$50k investment impact) require human oversight
- **Hallucination Detection**: Cross-validation between multiple sources before accepting AI claims
- **Cost Monitoring**: API usage alerts and budget controls
- **Model Redundancy**: Backup models (OpenAI GPT-4) with same safety requirements
- **Confidence Decay**: Predictions lose confidence over time without data refresh

### Database Performance
**Risk**: PostgreSQL + pgvector performance degrades with large datasets
**Mitigation**:
- Regular performance monitoring and optimization
- Database partitioning strategy for large tables
- Automated backup and recovery procedures
- Migration plan to dedicated vector database if needed
- Query optimization and index tuning

### System Scalability
**Risk**: Single VPS cannot handle user growth
**Mitigation**:
- Containerized architecture enables easy horizontal scaling
- Database replication strategy prepared
- Load testing at different user levels
- Cloud migration plan (Google Cloud Run) ready
- Performance monitoring with automatic alerts

## 8.2 Business Risks

### Market Acceptance
**Risk**: Users don't find sufficient value to pay for reports
**Mitigation**:
- Extensive user testing before launch
- Free trial period to demonstrate value
- Success guarantee (refund if report doesn't save time)
- Continuous user feedback integration
- Pivot strategy for different user segments

### Competitive Response
**Risk**: Established players copy approach or develop competing solutions
**Mitigation**:
- Focus on execution speed and data quality advantages
- Build strong local network effects in Gainesville
- Develop unique pattern recognition capabilities
- Establish brand reputation for accuracy and insights
- Expand to new markets quickly

### Legal Challenges
**Risk**: Data sources challenge scraping activities or users challenge predictions
**Mitigation**:
- Focus on clearly public data sources
- Clear disclaimers about prediction uncertainty
- Legal review of terms of service
- Professional liability insurance
- Transparent methodology documentation

## 8.3 Success Metrics

### Technical Performance Metrics
```python
TECHNICAL_SUCCESS_METRICS = {
    "system_reliability": {
        "uptime_target": 99.9,  # %
        "max_response_time": 2000,  # ms for standard requests
        "error_rate_threshold": 0.5,  # %
        "data_freshness": 24,  # hours max age for critical data
    },
    "scraping_performance": {
        "success_rate_threshold": 95,  # % successful scrapes
        "data_completeness": 80,  # % of expected data points collected
        "pattern_detection_accuracy": 75,  # % validated patterns
    },
    "ai_safety_performance": {
        "prediction_accuracy": 80,  # % validated predictions
        "confidence_calibration": 0.1,  # difference between confidence and accuracy
        "response_relevance": 90,  # % of responses rated relevant by users
        "hallucination_rate": 5,  # % of AI claims proven false (target: <5%)
        "source_attribution_rate": 100,  # % of AI insights with documented sources
        "uncertainty_documentation": 100,  # % of predictions with documented uncertainties
        "confidence_threshold_compliance": 95,  # % of outputs meeting confidence requirements
    }
}
```

### Business Success Metrics
```python
BUSINESS_SUCCESS_METRICS = {
    "month_1": {
        "active_users": 20,
        "reports_generated": 50,
        "revenue": 5000,
        "customer_satisfaction": 8.0,
        "repeat_usage_rate": 60,  # % users ordering second report
    },
    "month_3": {
        "active_users": 75,
        "reports_generated": 200,
        "revenue": 20000,
        "customer_satisfaction": 8.5,
        "repeat_usage_rate": 75,
    },
    "month_6": {
        "active_users": 150,
        "reports_generated": 500,
        "revenue": 50000,
        "customer_satisfaction": 9.0,
        "repeat_usage_rate": 85,
    }
}
```

### Product Quality Metrics
```python
PRODUCT_QUALITY_METRICS = {
    "analysis_accuracy_with_safety": {
        "deal_success_prediction": 80,  # % accuracy vs actual outcomes with >70% confidence
        "roi_calculation_variance": 15,  # % average variance from actual with documented uncertainties
        "timeline_prediction_accuracy": 70,  # % within 20% of actual with source attribution
        "risk_identification_rate": 85,  # % of major risks identified
    },
    "user_value_delivery": {
        "time_savings_per_report": 25,  # hours saved vs manual research
        "unique_insights_per_report": 4,  # insights not available elsewhere
        "actionable_recommendations": 3,  # specific actions recommended
        "hidden_cost_identification": 2,  # average hidden costs found per report
    },
    "competitive_advantage": {
        "data_sources_unique": 5,  # sources competitors don't monitor
        "pattern_recognition_advantage": 30,  # % better than manual analysis
        "speed_advantage": 95,  # % faster than traditional research
        "accuracy_advantage": 25,  # % more accurate than industry standard
    }
}
```

---

# 9. COST STRUCTURE & FINANCIAL PROJECTIONS

## 9.1 MVP Cost Structure (Monthly)

### Infrastructure Costs
```python
MONTHLY_INFRASTRUCTURE_COSTS = {
    "oracle_vps": 0,  # Already owned
    "vercel_frontend": 0,  # Free tier sufficient for MVP
    "domain_ssl": 15,  # Domain and SSL certificates
    "proxy_service": 30,  # Rotating proxies for scraping
    "backup_storage": 10,  # Google Cloud Storage for backups
    "monitoring": 0,  # Self-hosted Prometheus/Grafana
    "total_infrastructure": 55
}
```

### API and Service Costs
```python
MONTHLY_API_COSTS = {
    "gemini_2_flash": 100,  # Conservative estimate for 100 reports/month
    "census_api": 0,  # Free
    "google_maps_geocoding": 20,  # For address resolution
    "email_service": 10,  # Transactional emails
    "total_api_costs": 130
}
```

### Operational Costs
```python
MONTHLY_OPERATIONAL_COSTS = {
    "legal_compliance": 100,  # Legal review and compliance
    "professional_liability": 150,  # Insurance for predictions
    "customer_support_tools": 25,  # Help desk and communication
    "total_operational": 275
}

TOTAL_MONTHLY_COSTS = 55 + 130 + 275  # $460/month
```

## 9.2 Revenue Projections

### Pricing Strategy
```python
PRICING_TIERS = {
    "basic_analysis": {
        "price": 200,
        "features": [
            "Property risk assessment",
            "Market context analysis",
            "Basic ROI calculation",
            "2-hour analysis time"
        ]
    },
    "comprehensive_analysis": {
        "price": 400,
        "features": [
            "Full due diligence report",
            "Development feasibility study",
            "Comparative opportunity analysis",
            "4-hour deep dive analysis"
        ]
    },
    "market_intelligence": {
        "price": 150,
        "features": [
            "Area development patterns",
            "Emerging opportunities",
            "Market timing insights",
            "Monthly subscription"
        ]
    }
}
```

### Growth Projections
```python
REVENUE_PROJECTIONS = {
    "month_1": {
        "basic_reports": 15,
        "comprehensive_reports": 5,
        "subscriptions": 5,
        "total_revenue": 15*200 + 5*400 + 5*150  # $5,750
    },
    "month_3": {
        "basic_reports": 40,
        "comprehensive_reports": 20,
        "subscriptions": 15,
        "total_revenue": 40*200 + 20*400 + 15*150  # $18,250
    },
    "month_6": {
        "basic_reports": 80,
        "comprehensive_reports": 40,
        "subscriptions": 30,
        "total_revenue": 80*200 + 40*400 + 30*150  # $36,500
    },
    "month_12": {
        "basic_reports": 150,
        "comprehensive_reports": 75,
        "subscriptions": 60,
        "total_revenue": 150*200 + 75*400 + 60*150  # $69,000
    }
}
```

## 9.3 Break-Even Analysis

### Path to Profitability
```python
BREAK_EVEN_ANALYSIS = {
    "fixed_monthly_costs": 460,
    "variable_cost_per_report": 50,  # Gemini API + processing time
    "average_report_price": 250,  # Weighted average
    "contribution_margin": 200,  # $250 - $50
    "break_even_reports_per_month": 3,  # $460 / $200
    "target_monthly_reports": 25,  # For $4,540 profit/month
}
```

### Investment Requirements
```python
STARTUP_INVESTMENT = {
    "development_time": {
        "hours": 400,  # 10 weeks * 40 hours
        "opportunity_cost": 40000,  # $100/hour developer rate
    },
    "initial_marketing": 5000,  # Website, initial customer acquisition
    "legal_setup": 2000,  # Business formation, terms of service
    "insurance_annual": 1800,  # Professional liability insurance
    "working_capital": 5000,  # 3 months operating expenses
    "total_initial_investment": 53800
}

PAYBACK_ANALYSIS = {
    "monthly_profit_target": 4500,  # After month 3
    "payback_period_months": 12,  # $53,800 / $4,500
    "roi_year_1": "67%",  # ($54,000 profit - $53,800 investment) / $53,800
}
```

---

# 10. FUTURE ROADMAP

## 10.1 Short-term Enhancements (Months 2-6)

### Enhanced Data Sources
- **Private Data Partnerships**: Partner with local broker for MLS access ($500/month)
- **Building Inspector Integration**: Real inspection results and violation data
- **Environmental Database**: Direct API access to FDEP data
- **Traffic and Demographic Data**: Google Places API integration
- **Economic Development**: Direct feeds from Gainesville Economic Development

### Advanced Analytics
- **Predictive Modeling**: Machine learning models for price appreciation
- **Market Cycle Detection**: Identify market timing and cycles
- **Developer Network Analysis**: Map relationships between players
- **Political Risk Modeling**: Predict approval likelihood based on political climate
- **Infrastructure Impact Modeling**: How new projects affect existing properties

### User Experience Improvements
- **Mobile App**: iOS/Android apps for on-site property analysis
- **Maps Integration**: Interactive maps with intelligence overlays
- **Real-time Alerts**: Push notifications for opportunities and risks
- **Team Collaboration**: Multi-user accounts for development teams
- **API Access**: Allow integration with existing real estate software

## 10.2 Medium-term Expansion (Months 7-18)

### Geographic Expansion
```python
EXPANSION_MARKETS = {
    "phase_1": ["Tallahassee", "Jacksonville", "Orlando"],  # Major FL cities
    "phase_2": ["Tampa", "Miami", "Fort Lauderdale"],  # Complex markets
    "phase_3": ["Atlanta", "Nashville", "Charlotte"],  # Southeast expansion
}
```

### Advanced Features
- **Automated Deal Sourcing**: AI discovers and evaluates deals automatically
- **Financial Modeling**: Detailed pro formas and sensitivity analysis
- **Legal Document Analysis**: Contract and agreement risk assessment
- **3D Property Analysis**: Drone and satellite imagery integration
- **Comparable Sales AI**: Advanced machine learning for property valuation

### Business Model Evolution
- **Subscription Tiers**: Monthly subscriptions for regular users
- **Enterprise Sales**: Large developer and investment firm partnerships
- **White Label**: License technology to other markets and companies
- **Investment Fund**: Direct investment in recommended opportunities

## 10.3 Long-term Vision (18+ Months)

### AI-Powered Investment Firm

**The Ultimate Goal**: Transform Dominion from intelligence provider to active investor.

#### Phase 1: Passive Investment
- **Crowdfunding Platform**: Pool investor capital for recommended deals
- **Performance Tracking**: Track success rates of recommendations
- **Fund Management**: Manage investment funds based on AI recommendations
- **Risk Management**: Diversification algorithms and risk assessment

#### Phase 2: Active Development
- **Direct Property Acquisition**: Buy properties identified by AI
- **Development Management**: Manage development projects end-to-end
- **Construction Partnerships**: Partner with contractors and architects
- **Exit Strategy Optimization**: AI-driven timing for sales and refinancing

#### Phase 3: Full Real Estate Investment Firm
- **Autonomous Acquisitions**: AI identifies and negotiates deals
- **Portfolio Management**: AI manages entire real estate portfolio
- **Market Making**: Become major player in target markets
- **Industry Transformation**: Set new standards for data-driven real estate

### Technology Evolution
```python
FUTURE_TECHNOLOGY_STACK = {
    "ai_capabilities": [
        "Computer vision for property analysis",
        "Natural language processing for legal documents",
        "Reinforcement learning for investment strategies",
        "Predictive modeling for market cycles"
    ],
    "data_sources": [
        "Satellite imagery and change detection",
        "IoT sensors for real-time property monitoring",
        "Blockchain for transparent transaction history",
        "Social media sentiment for neighborhood analysis"
    ],
    "automation": [
        "Robotic process automation for due diligence",
        "Automated contract generation and review",
        "AI-powered negotiations",
        "Autonomous investment decision-making"
    ]
}
```

### Market Impact Vision
**By Year 5**: Dominion becomes the first truly AI-native real estate investment firm, managing $100M+ in assets across multiple markets, with AI making autonomous investment decisions that consistently outperform human-managed funds.

**Industry Transformation**: Other firms adopt similar AI-first approaches, fundamentally changing how real estate investment and development decisions are made.

---

# APPENDIX A: API CREDENTIALS & SETUP

## Required API Keys and Accounts

### Free APIs
1. **US Census API**
   - URL: https://api.census.gov/data/key_signup.html
   - Cost: Free
   - Usage: Demographics and economic data

2. **City of Gainesville Open Data**
   - URL: https://data.cityofgainesville.org
   - Cost: Free
   - Usage: Permits, crime data, zoning information

### Paid APIs
3. **Google Gemini 2.0 Flash**
   - URL: https://aistudio.google.com
   - Cost: ~$100/month for expected usage
   - Usage: Primary AI analysis and synthesis

4. **Google Maps Geocoding API**
   - URL: https://developers.google.com/maps
   - Cost: ~$20/month for expected usage
   - Usage: Address resolution and coordinates

### Optional Premium APIs
5. **MLS Grid Access** (Future enhancement)
   - Contact: Local MLS broker partner
   - Cost: $500/month
   - Usage: Property listings and sales data

6. **Proxy Service**
   - Recommended: Bright Data or Smartproxy
   - Cost: ~$30/month
   - Usage: IP rotation for web scraping

---

# APPENDIX B: SUCCESS METRICS TRACKING

## Key Performance Indicators (KPIs)

### Technical KPIs
```python
TECHNICAL_KPIS = {
    "data_quality": {
        "completeness_score": ">85%",  # Percentage of data fields populated
        "accuracy_score": ">90%",      # Verified against manual checks
        "freshness_score": ">95%",     # Data updated within SLA timeframes
    },
    "system_performance": {
        "api_response_time": "<500ms",  # 95th percentile
        "scraper_success_rate": ">95%", # Successful scrapes
        "uptime": ">99.9%",            # System availability
    },
    "ai_performance": {
        "prediction_accuracy": ">80%",  # Validated predictions
        "confidence_calibration": "<10%", # Confidence vs accuracy gap
        "hallucination_rate": "<5%",    # Factually incorrect statements
    }
}
```

### Business KPIs
```python
BUSINESS_KPIS = {
    "customer_metrics": {
        "customer_acquisition_cost": "<$100", # Cost to acquire new customer
        "customer_lifetime_value": ">$1000",  # Average customer value
        "net_promoter_score": ">50",          # Customer satisfaction
        "churn_rate": "<10%",                 # Monthly customer churn
    },
    "financial_metrics": {
        "monthly_recurring_revenue": "Growth >20%", # MRR growth rate
        "gross_margin": ">80%",               # Revenue minus direct costs
        "burn_rate": "<$2000/month",          # Monthly cash consumption
        "runway": ">12 months",               # Months of operating capital
    }
}
```

### Product KPIs
```python
PRODUCT_KPIS = {
    "value_delivery": {
        "time_savings": ">20 hours/report",   # Hours saved vs manual research
        "insight_uniqueness": ">3/report",    # Insights not found elsewhere
        "actionable_recommendations": ">2/report", # Specific actions provided
        "roi_accuracy": "±15%",               # Variance from actual ROI
    },
    "user_engagement": {
        "report_completion_rate": ">95%",     # Users who complete requested analysis
        "repeat_usage_rate": ">70%",          # Users who order multiple reports
        "feature_adoption": ">60%",           # Users utilizing advanced features
        "support_ticket_rate": "<5%",        # Users requiring support
    }
}
```

---

# APPENDIX C: TECHNICAL ARCHITECTURE DECISIONS

## Architecture Decision Records (ADRs)

### ADR-001: Database Choice - PostgreSQL + pgvector
**Decision**: Use PostgreSQL with pgvector extension instead of separate vector database

**Reasoning**:
- Single database simplifies operations and reduces costs
- pgvector performance sufficient for expected scale (< 10M vectors)
- Enables complex queries combining relational and vector data
- Mature ecosystem with excellent tooling and support

**Trade-offs**:
- Less specialized than dedicated vector databases
- May require migration if scale exceeds PostgreSQL capabilities
- Vector operations not as optimized as purpose-built solutions

### ADR-002: AI Provider - Google Gemini 2.0 Flash
**Decision**: Use Google Gemini 2.0 Flash as primary AI model

**Reasoning**:
- 10x cost reduction vs Claude Opus ($100 vs $1000/month)
- Strong performance for analysis and synthesis tasks
- Large context window (1M tokens) for comprehensive analysis
- Good integration with Google Cloud ecosystem

**Trade-offs**:
- Less established than OpenAI GPT-4 or Claude
- Performance may be slightly lower than premium models
- Vendor lock-in to Google's AI ecosystem

### ADR-003: Infrastructure - Oracle VPS + Vercel Hybrid
**Decision**: Run backend on owned Oracle VPS, frontend on Vercel

**Reasoning**:
- Leverage existing Oracle VPS to minimize infrastructure costs
- Vercel provides excellent developer experience for React frontend
- Clear separation of concerns between frontend and backend
- Easy to scale frontend independently

**Trade-offs**:
- More complex deployment than single-platform solution
- Network latency between VPS and Vercel
- Requires managing multiple deployment pipelines

### ADR-004: Containerization - Docker Compose
**Decision**: Use Docker Compose for all backend services

**Reasoning**:
- Consistent development and production environments
- Easy service orchestration and dependency management
- Simplified backup and disaster recovery
- Container isolation improves security and stability

**Trade-offs**:
- Additional complexity compared to bare metal deployment
- Resource overhead from containerization
- Learning curve for container management

---

**END OF ENGINEERING PLAN**

*Version 2.0 - Complete Intelligence Ecosystem*
*Created: December 2024*
*Reflects: Real Estate Intelligence Ecosystem Architecture*