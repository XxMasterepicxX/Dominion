# Dominion Database Architecture - Final Plan
**Version 1.1 | Production-Ready | Based on Expert Review**

---

## Executive Summary

**KEEP:** PostgreSQL + strategic extensions, two-tier intelligence (background/on-demand), multi-gate validation, provenance tracking, human-in-the-loop

**FIX:** Replace heuristic confidence with learned models, add proper partitioning, implement three-band thresholding, add release gates, make advanced features optional

**SHIP:** MVP with 99% precision on auto-accepts, proper SLOs, reversible operations, clear off-ramps

---

## CRITICAL CLARIFICATION: Confidence Levels

**Confidence is determined by EVIDENCE QUALITY, not processing tier:**

- **Government records API**: 95-99% confidence (both tiers can access)
- **Structured database/permit API**: 90-95% confidence (both tiers)
- **Published news articles**: 75-85% confidence (both tiers)
- **Single-source AI extraction**: 70-80% confidence (both tiers)
- **Predictive inferences**: 65-85% confidence (both tiers)

**The difference between tiers is WHAT WE SHOW TO USERS:**

```
Background Monitoring (Continuous):
├─ Ingests ALL confidence levels (60-99%)
├─ Stores everything with proper scores
├─ SHOWS only ≥95% confidence in alerts
└─ Queues 70-94% for validation before showing

Deep Analysis (On-Demand):
├─ Uses existing facts (some 99%, some 70%)
├─ Attempts to validate low-confidence facts
├─ Makes NEW predictions (70-85% confidence)
└─ SHOWS everything with appropriate uncertainty language
    ("verified 99%", "likely 85%", "possible 70%")
```

---

## Part 1: What I Got Right (Keep This)

### ✅ Core Architecture
- **PostgreSQL 15+** as foundation with PostGIS + pgvector
- **Immutable raw_facts** table (event sourcing)
- **Facts vs inferences** separation
- **JSONB** for schema flexibility
- **Two-tier intelligence system:**
  - Background monitoring: Continuous ingestion (all confidence levels), show only ≥95% to users
  - On-demand deep analysis: Exhaustive research, show all confidence levels with uncertainty language

### ✅ Quality Principles
- Never trust single source (require 2+ or high confidence)
- Confidence scores on everything
- Provenance mandatory (every claim → sources)
- Human-in-the-loop for uncertainty
- "Don't know" is acceptable

### ✅ Hybrid Search Strategy
- Lexical (PostgreSQL FTS) as precision gate
- Vector (pgvector) for semantic similarity
- Spatial (PostGIS) for geographic queries
- Graph (eventually) for relationship traversal

---

## Part 2: Critical Fixes (Expert Feedback)

### ❌ WRONG: Heuristic Confidence Math
**What I said:** Hand-weighted formula (source * 0.2 + extraction * 0.3 + validation * 0.3 + temporal * 0.2)

**What's actually needed:**
```python
# Use learned, calibrated model instead
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV

class LearnedConfidenceScorer:
    """
    Train one model per edge type (owns, developed, partnered, etc.)
    Features: IDs match, address distance, phone/email exact,
              source priors, recency, contradiction flags
    Calibration: Platt/Isotonic so 0.99 = 99% PPV on held-out data
    """

    def __init__(self, edge_type):
        self.edge_type = edge_type
        self.base_model = GradientBoostingClassifier(n_estimators=100)
        self.calibrated_model = CalibratedClassifierCV(
            self.base_model,
            method='isotonic',  # Better for small datasets
            cv=5
        )

    def train(self, labeled_examples):
        """
        Need ~2,000 labeled match/non-match pairs
        + ~500 edges per top 3 edge types
        """
        X = self.extract_features(labeled_examples)
        y = labeled_examples['is_correct']

        self.calibrated_model.fit(X, y)

        # Validate calibration
        probs = self.calibrated_model.predict_proba(X_val)[:, 1]
        self.validate_calibration(probs, y_val)

    def score_relationship(self, relationship):
        """Returns calibrated probability (0-1)"""
        features = self.extract_features([relationship])
        return self.calibrated_model.predict_proba(features)[0, 1]
```

**Action:** Label 2,000 match/non-match pairs before launch

---

### ❌ WRONG: ProvSQL as Baseline
**What I said:** Use ProvSQL extension for provenance

**What's actually needed:**
```sql
-- Start simple: JSONB provenance + lineage tables
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY,
    from_entity_id UUID,
    to_entity_id UUID,
    relationship_type TEXT,
    confidence FLOAT,

    -- Simple provenance (no extension needed)
    sources JSONB,  -- [{"type": "news", "url": "...", "date": "..."}]
    evidence_ids UUID[],  -- Links to raw_facts
    parser_version TEXT,
    model_version TEXT,
    extraction_timestamp TIMESTAMP,

    -- Human validation tracking
    validation_status TEXT CHECK (validation_status IN
        ('auto_accepted', 'under_review', 'human_validated', 'rejected')),
    validated_by UUID,
    validated_at TIMESTAMP,

    -- Reversibility
    superseded_by UUID REFERENCES entity_relationships(id),
    supersedes UUID REFERENCES entity_relationships(id),

    created_at TIMESTAMP DEFAULT NOW()
);

-- Separate lineage table for merge history
CREATE TABLE entity_merge_history (
    id UUID PRIMARY KEY,
    merged_entities UUID[],  -- IDs that were merged
    resulting_entity UUID REFERENCES entities(id),
    merge_reason TEXT,
    confidence FLOAT,
    merged_by UUID REFERENCES users(id),
    merged_at TIMESTAMP,

    -- Full snapshot for reversal
    before_state JSONB,
    after_state JSONB,

    -- Reversibility
    reversed BOOLEAN DEFAULT FALSE,
    reversed_at TIMESTAMP,
    reversed_by UUID
);
```

**Action:** Feature-flag ProvSQL - add only if provenance algebra queries are needed

---

### ❌ WRONG: Apache AGE "Zero Migration"
**What I said:** AGE reads your existing tables automatically

**What's actually needed:**
```python
class NightlyGraphBuilder:
    """
    Explicit load/adapter layer - materialize vertices/edges
    Mirror ONLY the hot subgraph (active entities + relationships)
    Run as nightly job, not on every write
    """

    async def build_nightly_graph(self):
        """
        Run at 2 AM daily
        Only load entities/relationships modified in last 90 days
        """

        # Step 1: Load active entities as vertices
        active_entities = await self.get_active_entities()

        for entity in active_entities:
            await self.age_create_vertex(
                label=entity.entity_type,
                properties={
                    'entity_id': entity.id,
                    'canonical_name': entity.canonical_name,
                    'confidence': entity.resolution_confidence
                }
            )

        # Step 2: Load validated relationships as edges
        validated_relationships = await self.get_validated_relationships()

        for rel in validated_relationships:
            await self.age_create_edge(
                from_vertex=rel.from_entity_id,
                to_vertex=rel.to_entity_id,
                label=rel.relationship_type,
                properties={
                    'confidence': rel.confidence,
                    'first_observed': rel.first_observed,
                    'evidence_count': len(rel.evidence_ids)
                }
            )

        # Step 3: Run graph integrity checks
        integrity_report = await self.check_graph_integrity()

        if integrity_report.has_violations:
            # Quarantine violating edges
            await self.quarantine_violations(integrity_report.violations)
            await self.alert_ops_team(integrity_report)

    async def check_graph_integrity(self):
        """
        Enforce: cardinality, temporal validity, acyclicity
        """
        violations = []

        # Check: Person can't own themselves
        self_loops = await self.find_self_loops()
        violations.extend(self_loops)

        # Check: Temporal consistency (can't buy before born)
        temporal_violations = await self.find_temporal_violations()
        violations.extend(temporal_violations)

        # Check: Ownership cycles (A owns B owns C owns A)
        cycles = await self.find_ownership_cycles()
        violations.extend(cycles)

        return IntegrityReport(violations=violations)
```

**Action:** Start without AGE. Add only if 3-hop queries exceed 300ms p95 at scale test

---

### ❌ WRONG: Static Source Priors
**What I said:** `'government_records': 1.0, 'news_articles': 0.8`

**What's actually needed:**
```python
class LearnedSourcePriors:
    """
    Maintain per-source confusion matrices
    Update monthly from gold set
    Decay stale claims automatically
    """

    async def update_source_priors(self):
        """Run monthly"""
        for source in self.all_sources:
            # Get validated claims from this source
            gold_set = await self.get_gold_set(source)

            # Calculate actual precision/recall
            tp = sum(1 for claim in gold_set if claim.was_correct)
            fp = sum(1 for claim in gold_set if not claim.was_correct)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.5

            # Update source reliability with confidence interval
            n = len(gold_set)
            ci_lower, ci_upper = self.wilson_ci(tp, n, confidence=0.95)

            await self.update_source_reliability(
                source=source,
                reliability=precision,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                sample_size=n
            )

    def decay_stale_claims(self, claim):
        """
        Confidence decays over time for non-renewed claims
        """
        age_days = (datetime.now() - claim.last_verified).days

        if age_days > 180:  # 6 months
            decay_factor = 0.9 ** (age_days / 180)
            return claim.confidence * decay_factor

        return claim.confidence
```

**Action:** Implement source reliability tracking from day 1

---

## Part 2A: Understanding Confidence Architecture

### How Confidence Actually Works

**Confidence = f(source quality, extraction method, cross-validation, freshness)**

```python
def calculate_confidence(fact):
    """
    Confidence determined by evidence quality, NOT processing tier
    Both background monitoring and deep analysis can achieve any confidence level
    """

    # Example 1: Property Deed (Background Monitoring)
    # Source: Government API (official record)
    # Extraction: Direct from structured API
    # Validation: Single authoritative source sufficient
    # Result: 99% confidence
    # Action: Show immediately in alerts

    # Example 2: LLC Formation (Background Monitoring)
    # Source: State records API
    # Extraction: Structured data
    # Validation: Official government record
    # Result: 97% confidence
    # Action: Show immediately in alerts

    # Example 3: News Article (Background Monitoring)
    # Source: Published journalism
    # Extraction: LLM extraction from unstructured text
    # Validation: Single source, no cross-confirmation
    # Result: 75% confidence
    # Action: Store but DON'T show until validated

    # Example 4: Future Prediction (Deep Analysis)
    # Source: Multiple historical patterns
    # Extraction: AI inference
    # Validation: Statistical model
    # Result: 70% confidence
    # Action: Show with uncertainty ("likely", "may", "possible")
```

### Confidence Tiers and Actions

```python
class ConfidenceBasedActions:
    """
    What we do with facts depends on confidence level
    NOT which tier produced them
    """

    VERIFIED = 0.95  # ≥95%
    # Examples:
    # - Property deed from county records
    # - LLC formation from state database
    # - Permit approval from city API
    #
    # Background Monitoring: Show in alerts immediately
    # Deep Analysis: Show as "verified" or "confirmed"
    # Language: "John Smith owns this property (verified from deed)"

    HIGH_CONFIDENCE = 0.85  # 85-94%
    # Examples:
    # - 2 news sources confirm relationship
    # - Deterministic key match (registered agent + address)
    # - Structured extraction from trusted source
    #
    # Background Monitoring: May show in alerts (case by case)
    # Deep Analysis: Show with mild hedging
    # Language: "John Smith is affiliated with ABC LLC (high confidence)"

    MODERATE_CONFIDENCE = 0.70  # 70-84%
    # Examples:
    # - Single news article mentions relationship
    # - Fuzzy name match + 1 other signal
    # - AI inference from patterns
    #
    # Background Monitoring: Queue for review, don't show yet
    # Deep Analysis: Show with clear uncertainty
    # Language: "John Smith is likely connected to ABC LLC (moderate confidence)"

    LOW_CONFIDENCE = 0.60  # 60-69%
    # Examples:
    # - Weak similarity match only
    # - Single source + questionable extraction
    # - Contradictory evidence exists
    #
    # Background Monitoring: Queue for validation
    # Deep Analysis: Show only if relevant, with strong hedging
    # Language: "John Smith may be affiliated with ABC LLC (low confidence)"

    INSUFFICIENT = 0.50  # <60%
    # Examples:
    # - No sources found
    # - Contradictory evidence
    # - Failed validation
    #
    # Background Monitoring: Discard or flag for investigation
    # Deep Analysis: Explicitly state lack of data
    # Language: "Insufficient data to determine relationship"
```

### The Two-Tier Strategy Clarified

```
┌─────────────────────────────────────────────────────────────┐
│         BACKGROUND MONITORING (Continuous, 24/7)            │
│  NOT "low quality mode" - captures ALL confidence levels    │
└─────────────────────────────────────────────────────────────┘

WHAT IT DOES:
├─ Scrapes all sources daily (government APIs, news, permits, etc.)
├─ Calculates proper confidence for EACH fact (60-99% range)
├─ Stores EVERYTHING in database with confidence scores
└─ Applies selective visibility:
    ├─ ≥95% confidence: Show in user alerts immediately
    │   Example: "New LLC formed by known developer (verified)"
    │
    ├─ 85-94% confidence: Store, may show in some contexts
    │   Example: High-confidence relationship stored for deep analysis
    │
    ├─ 70-84% confidence: Store, queue for review before showing
    │   Example: News article mentions developer, needs validation
    │
    └─ <70% confidence: Store, queue for validation
        Example: Weak fuzzy match needs human review

PROCESSING CHARACTERISTICS:
├─ Speed: Minutes per source
├─ Cost: ~$10/day
├─ Breadth: All sources covered
└─ User-facing: Only high-confidence facts (≥95%)

┌─────────────────────────────────────────────────────────────┐
│       DEEP ANALYSIS (On-Demand, User-Requested, 1-4 hrs)    │
│  NOT "high quality mode" - uses existing facts + validates  │
└─────────────────────────────────────────────────────────────┘

WHAT IT DOES:
├─ Pulls ALL existing facts from database (some 99%, some 70%)
├─ For low-confidence facts: Attempts to find confirming evidence
├─ Runs additional scrapers not in daily rotation
├─ Makes NEW inferences/predictions (often 70-85% confidence)
└─ Shows EVERYTHING with appropriate uncertainty language:
    ├─ 99%: "Verified from property deed"
    ├─ 90%: "High confidence based on 2 sources"
    ├─ 80%: "Likely, based on pattern analysis"
    ├─ 70%: "Possible connection, limited evidence"
    └─ <60%: "Insufficient data to determine"

PROCESSING CHARACTERISTICS:
├─ Speed: 1-4 hours per analysis
├─ Cost: ~$5-15 per analysis
├─ Depth: Exhaustive research on single property
└─ User-facing: ALL confidence levels (with appropriate language)

KEY INSIGHT:
Deep analysis doesn't magically make everything 99% confidence.
It SHOWS low-confidence facts that background monitoring hides.
User pays $150-500 for comprehensive view, including uncertainties.
```

---

## Part 3: Three-Band Thresholding System

**CRITICAL:** Replace my binary "accept/reject" with three bands per edge type

```python
class ThreeBandThresholder:
    """
    Auto-accept (≥τ_high) → Goes live immediately
    Review (τ_low...τ_high) → Human review queue
    Auto-reject (<τ_low) → Discard

    Tuned to hit 99% precision on auto-accepts
    """

    # Per edge type thresholds (learned from data)
    THRESHOLDS = {
        'owns': {
            'tau_high': 0.95,  # 99% PPV on validation set
            'tau_low': 0.60,   # Below this: noise
        },
        'developed': {
            'tau_high': 0.90,
            'tau_low': 0.65,
        },
        'partnered': {
            'tau_high': 0.88,
            'tau_low': 0.70,
        }
    }

    async def process_relationship(self, relationship):
        """Three-band decision"""
        edge_type = relationship.type
        confidence = self.scorer.score(relationship)

        thresholds = self.THRESHOLDS[edge_type]

        if confidence >= thresholds['tau_high']:
            # Auto-accept: high confidence
            await self.auto_accept(relationship)

            # But still sample 10-20% for blind audit
            if random.random() < 0.15:
                await self.queue_for_audit(relationship, priority=1)

        elif confidence >= thresholds['tau_low']:
            # Review: uncertain
            await self.queue_for_human_review(relationship, priority=3)

        else:
            # Auto-reject: low confidence
            await self.auto_reject(relationship, reason="below_threshold")

    def tune_thresholds(self, validation_set):
        """
        For each edge type:
        - Set τ_high where lower CI ≥ 0.99 precision
        - Set τ_low where precision drops below 0.6
        """
        for edge_type in self.edge_types:
            subset = validation_set.filter(type=edge_type)

            # Sort by confidence, find threshold where precision ≥ 0.99
            sorted_by_conf = subset.sort_by('confidence', desc=True)

            for i, threshold in enumerate(np.arange(0.99, 0.5, -0.01)):
                above_threshold = sorted_by_conf[sorted_by_conf.confidence >= threshold]

                precision = above_threshold.precision()
                ci_lower, _ = self.wilson_ci(
                    above_threshold.num_correct,
                    len(above_threshold),
                    confidence=0.95
                )

                if ci_lower >= 0.99:
                    self.THRESHOLDS[edge_type]['tau_high'] = threshold
                    break
```

**Action:** Tune thresholds on validation set before launch

---

## Part 4: Release Gates (Block Ship if Quality Too Low)

```python
class ReleaseGate:
    """
    Statistical quality gates - block deployment if not met
    """

    REQUIRED_METRICS = {
        'entity_resolution_precision': {
            'min_ci_lower': 0.99,  # Wilson 95% CI lower bound
            'min_sample_size': 500
        },
        'relationship_extraction_precision': {
            'min_ci_lower': 0.95,
            'min_sample_size': 200
        },
        'false_positive_rate': {
            'max_rate': 0.01,  # Max 1% FP
            'min_sample_size': 1000
        }
    }

    async def can_deploy_to_production(self):
        """
        Check all quality gates before deploy
        Return: (can_deploy: bool, failing_gates: List[str])
        """
        failing_gates = []

        # Gate 1: Entity resolution precision
        er_metrics = await self.compute_er_metrics()
        if er_metrics.ci_lower < 0.99:
            failing_gates.append(
                f"Entity resolution CI lower bound {er_metrics.ci_lower:.3f} < 0.99"
            )

        # Gate 2: Relationship extraction precision
        rel_metrics = await self.compute_relationship_metrics()
        if rel_metrics.ci_lower < 0.95:
            failing_gates.append(
                f"Relationship extraction CI lower bound {rel_metrics.ci_lower:.3f} < 0.95"
            )

        # Gate 3: False positive rate
        fp_rate = await self.compute_false_positive_rate()
        if fp_rate > 0.01:
            failing_gates.append(
                f"False positive rate {fp_rate:.3f} > 0.01"
            )

        # Gate 4: Reviewer throughput SLA
        review_metrics = await self.compute_reviewer_metrics()
        if review_metrics.p95_latency_hours > 24:
            failing_gates.append(
                f"Review p95 latency {review_metrics.p95_latency_hours:.1f}h > 24h SLA"
            )

        return (len(failing_gates) == 0, failing_gates)

    def wilson_ci(self, successes, total, confidence=0.95):
        """
        Wilson score confidence interval
        More accurate than normal approximation for small samples
        """
        z = 1.96  # 95% confidence
        phat = successes / total

        denominator = 1 + z**2 / total
        centre = (phat + z**2 / (2*total)) / denominator
        spread = z * np.sqrt((phat*(1-phat) + z**2/(4*total)) / total) / denominator

        return (centre - spread, centre + spread)
```

**Action:** Implement release gates in CI/CD pipeline

---

## Part 5: Practical Improvements (Do These First)

### 1. Partitioning Strategy
```sql
-- Range partition raw_facts and structured_facts by month
CREATE TABLE raw_facts (
    id UUID,
    scraped_at TIMESTAMP NOT NULL,
    -- ... other columns
) PARTITION BY RANGE (scraped_at);

-- Pre-create partitions 2 months out
CREATE TABLE raw_facts_2025_10 PARTITION OF raw_facts
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

CREATE TABLE raw_facts_2025_11 PARTITION OF raw_facts
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

-- Set aggressive autovacuum for big GIN/ANN indexes
ALTER TABLE raw_facts SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

-- Drop partitions older than 2 years
-- (Archive to S3 first via pg_dump)
```

### 2. Materialized tsvector for FTS
```sql
-- Add generated tsvector column with weights
ALTER TABLE raw_facts
ADD COLUMN search_vector tsvector
GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(raw_content->>'title', '')), 'A') ||
    setweight(to_tsvector('english', coalesce(raw_content->>'content', '')), 'B') ||
    setweight(to_tsvector('english', coalesce(raw_content->>'tags', '')), 'C')
) STORED;

-- GIN index on generated column
CREATE INDEX idx_raw_facts_fts ON raw_facts USING GIN(search_vector);

-- Add synonyms for local place names
CREATE TEXT SEARCH DICTIONARY local_synonyms (
    TEMPLATE = synonym,
    SYNONYMS = gainesville_synonyms
);

-- gainesville_synonyms.txt:
-- downtown, city center, central district
-- UF, university of florida, uf campus
```

### 3. Robust LLM Cache Key
```sql
CREATE TABLE llm_cache (
    id UUID PRIMARY KEY,

    -- Complete cache key (all must match)
    model_id TEXT NOT NULL,           -- 'gemini-2.0-flash'
    model_version TEXT NOT NULL,      -- '20250115'
    prompt_template_version TEXT NOT NULL,  -- 'entity_extract_v3'
    temperature FLOAT NOT NULL,       -- Even if usually 0.0
    top_p FLOAT NOT NULL,
    retrieval_recipe_hash TEXT NOT NULL,  -- Hash of facts used

    -- Response
    response JSONB NOT NULL,
    cost_cents INTEGER,

    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,

    UNIQUE(model_id, model_version, prompt_template_version,
           temperature, top_p, retrieval_recipe_hash)
);
```

### 4. Composite Content Hash
```python
def compute_content_hash(scraped_data):
    """
    Don't just hash content blob
    Use composite: normalized_content + source_url + time_bucket + selector
    """
    # Normalize HTML (remove whitespace, comments, etc.)
    normalized = normalize_html(scraped_data.content)

    # Round timestamp to nearest hour (avoid false positives)
    time_bucket = scraped_data.retrieved_at.replace(minute=0, second=0)

    # Include selector used (if page structure changes)
    selector = scraped_data.css_selector

    composite = f"{normalized}|{scraped_data.source_url}|{time_bucket}|{selector}"

    return hashlib.sha256(composite.encode()).hexdigest()
```

### 5. Deterministic Entity Resolution Keys
```python
from libpostal.parser import parse_address

class EntityNormalizer:
    """
    Normalize before fuzzy matching
    Deterministic keys catch 80% of matches without ML
    """

    def normalize_entity(self, entity):
        """Generate deterministic keys"""
        keys = []

        # Key 1: Registered agent (LLC formations)
        if entity.registered_agent:
            keys.append(('registered_agent', self.normalize_agent(entity.registered_agent)))

        # Key 2: Tax ID (if available)
        if entity.tax_id:
            keys.append(('tax_id', entity.tax_id.strip()))

        # Key 3: Normalized address
        if entity.address:
            parsed = parse_address(entity.address)
            normalized_address = self.build_normalized_address(parsed)
            keys.append(('address', normalized_address))

        # Key 4: Normalized phone (E.164)
        if entity.phone:
            normalized_phone = self.normalize_phone_e164(entity.phone)
            keys.append(('phone', normalized_phone))

        # Key 5: Domain from email/website
        if entity.email:
            domain = entity.email.split('@')[1].lower()
            keys.append(('email_domain', domain))

        return keys

    def normalize_agent(self, agent_name):
        """
        Registered agents are highly distinctive
        'Smith & Associates Inc' → 'smith associates'
        """
        # Remove legal suffixes
        clean = re.sub(r'\b(inc|llc|corp|ltd|pa)\b', '', agent_name.lower())
        # Remove punctuation
        clean = re.sub(r'[^\w\s]', '', clean)
        # Remove extra whitespace
        clean = ' '.join(clean.split())
        return clean
```

---

## Part 6: MVP Implementation Plan (4 Weeks)

### Week 1: Foundation + Data Labeling
**Goal:** Get infrastructure ready, start labeling data

```
Days 1-2: Database Setup
├─ Install PostgreSQL 15+ with PostGIS + pgvector
├─ Run schema.sql (your existing schema)
├─ Implement partitioning (raw_facts, structured_facts)
├─ Add materialized tsvector columns
└─ Set up monitoring (connection pool, query latency)

Days 3-5: Labeling Sprint
├─ Export 2,000 potential entity matches for labeling
│  ├─ 1,000 from fuzzy matching (trigram > 0.7)
│  ├─ 500 from same registered agent
│  └─ 500 random negatives
├─ Label interface: "Same entity? Yes/No/Uncertain"
├─ Export 500 relationships per edge type (owns, developed, partnered)
└─ Label: "Correct relationship? Yes/No"

Days 6-7: Train Initial Scorers
├─ Train GradientBoostingClassifier per edge type
├─ Calibrate with IsotonicRegression
├─ Validate: Check Wilson CI on held-out set
└─ Store model versions in database
```

### Week 2: Ingestion Pipeline + Quality Gates
**Goal:** Scrapers → Database with validation

```
Days 8-10: Scraper Integration
├─ Update scrapers to write to raw_facts
├─ Implement composite content hashing
├─ Gate 1: Schema validation
├─ Gate 2: Deduplication check
└─ Gate 3: Store immutable raw_fact

Days 11-12: Extraction Layer
├─ Background worker: Process raw_facts
├─ LLM extraction (Gemini 2.0 Flash)
├─ Robust cache key implementation
├─ Gate 4: Extraction confidence check
└─ Gate 5: Store structured_fact with provenance

Days 13-14: Entity Resolution
├─ Deterministic key matching (80% of cases)
├─ Fuzzy matching with pg_trgm (15% of cases)
├─ ML scorer for edge cases (5% of cases)
├─ Gate 6: Three-band thresholding
└─ Human review queue setup
```

### Week 3: Relationship Validation + Review System
**Goal:** High-quality relationships only

```
Days 15-16: Relationship Extraction
├─ Extract relationships from structured_facts
├─ Apply learned scorer per edge type
├─ Gate 7: Cross-source validation
├─ Gate 8: Contradiction detection
└─ Gate 9: Three-band thresholding

Days 17-18: Human Review Interface
├─ Build review queue UI (priority-sorted)
├─ Show evidence/context for each decision
├─ Track reviewer decisions (build gold set)
├─ Measure Cohen's κ between reviewers
└─ Active learning: Sample uncertain cases

Days 19-21: Reversibility + Audit
├─ Event-sourced merge history
├─ 10-20% random sampling of auto-accepts
├─ Blind audit interface
├─ Merge reversal mechanism
└─ Alert on quality degradation
```

### Week 4: Release Gates + Scale Test
**Goal:** Validate ready for production

```
Days 22-24: Release Gates Implementation
├─ Compute Wilson CIs for all metrics
├─ Set up automated quality checks
├─ Block deploy if gates fail
└─ Dashboard: Quality metrics over time

Days 25-27: Scale Test
├─ Load 100k raw_facts
├─ Load 10k entities
├─ Load 1M vectors (synthetic if needed)
├─ Measure: p95 query latency, throughput
├─ Test: 3-hop relationship queries
└─ Validate: p95 < 300ms for graph, < 100ms for simple

Day 28: Production Readiness Review
├─ All release gates passing?
├─ Scale test SLOs met?
├─ Monitoring/alerting in place?
├─ Rollback plan documented?
└─ GO/NO-GO decision
```

---

## Part 7: Service Level Objectives (SLOs)

Define success criteria upfront - these determine off-ramps:

```yaml
# SLOs that must be met for MVP launch
quality_slos:
  entity_resolution_precision:
    target: 0.99
    ci_lower_bound: 0.99
    sample_size: 500

  relationship_precision:
    target: 0.95
    ci_lower_bound: 0.95
    sample_size: 200

  false_positive_rate:
    target: 0.01
    max_acceptable: 0.02

performance_slos:
  simple_query_latency:
    p50: 50ms
    p95: 100ms
    p99: 200ms

  api_response_latency:
    p50: 200ms
    p95: 500ms
    p99: 1000ms

  graph_query_latency:  # If we add Apache AGE
    p95: 300ms
    p99: 1000ms

  vector_search_latency:  # On 1M vectors
    p95: 100ms
    p99: 500ms

reviewer_slos:
  review_queue_latency:
    p95: 24h  # 95% reviewed within 24h
    p99: 72h

  queue_size:
    max: 500  # Never more than 500 pending

cost_slos:
  monthly_ai_spend:
    target: 50
    max_acceptable: 100  # Twice budget = investigate

  cost_per_analysis:
    target: 5
    max_acceptable: 15
```

**Off-Ramps (When to Add Specialized Systems):**

```python
# Decision tree for adding complexity
if graph_query_p95 > 300ms and tried_indexing_optimization:
    consider_apache_age()

if vector_search_p95 > 100ms and tried_pgvectorscale:
    consider_qdrant()

if review_queue_size > 500 consistently:
    improve_automatic_scoring()  # Don't just hire more reviewers

if false_positive_rate > 0.02:
    stop_new_features()
    focus_on_quality()
```

---

## Part 8: Security & Operations

```sql
-- Enable Row-Level Security on PII
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;

CREATE POLICY entity_user_isolation ON entities
    FOR ALL
    TO authenticated_users
    USING (
        -- Users can only see entities in their subscribed markets
        market_id IN (SELECT market_id FROM user_subscriptions WHERE user_id = current_user_id())
    );

-- Audit triggers for sensitive operations
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    old_data JSONB,
    new_data JSONB,
    changed_by UUID REFERENCES users(id),
    changed_at TIMESTAMP DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT
);

CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, operation, old_data, new_data, changed_by)
        VALUES (TG_TABLE_NAME, 'UPDATE', row_to_json(OLD), row_to_json(NEW), current_user_id());
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, operation, old_data, changed_by)
        VALUES (TG_TABLE_NAME, 'DELETE', row_to_json(OLD), current_user_id());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to sensitive tables
CREATE TRIGGER audit_entity_merges
    AFTER UPDATE OR DELETE ON entity_merge_history
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

-- WAL archiving for Point-in-Time Recovery
-- postgresql.conf:
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://dominion-wal-archive/%f'
archive_timeout = 300  # Force segment every 5 minutes

-- Backup strategy
# Daily: Full backup to S3 (pg_dump)
# Continuous: WAL archiving for PITR
# Retention: 90 days full backups, 7 days WAL
```

---

## Part 9: Monitoring & Observability

```python
# Emit metrics per phase (not tied to Prometheus internals)
from dataclasses import dataclass
from typing import Dict

@dataclass
class PhaseMetrics:
    """Metrics per ingestion phase"""
    phase_name: str
    items_processed: int
    items_failed: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    error_rate: float
    timestamp: datetime

class MetricsCollector:
    """
    Emit metrics that any backend can consume
    Default: Write to PostgreSQL metrics table
    Optional: Export to Prometheus, CloudWatch, etc.
    """

    async def record_phase_metrics(self, phase: str, duration_ms: float, success: bool):
        """Record ingestion phase metrics"""
        await self.db.execute("""
            INSERT INTO ingestion_metrics
            (phase, duration_ms, success, timestamp)
            VALUES ($1, $2, $3, NOW())
        """, phase, duration_ms, success)

    async def get_phase_health(self, phase: str, window_minutes: int = 60) -> PhaseMetrics:
        """Get phase health over time window"""
        stats = await self.db.fetchrow("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95,
                percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99
            FROM ingestion_metrics
            WHERE phase = $1
              AND timestamp > NOW() - INTERVAL '$2 minutes'
        """, phase, window_minutes)

        return PhaseMetrics(
            phase_name=phase,
            items_processed=stats['total'],
            items_failed=stats['total'] - stats['successful'],
            latency_p50_ms=stats['p50'],
            latency_p95_ms=stats['p95'],
            latency_p99_ms=stats['p99'],
            error_rate=(stats['total'] - stats['successful']) / stats['total'],
            timestamp=datetime.now()
        )

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Comprehensive health check
    Returns 200 if all systems healthy
    Returns 503 if any critical system down
    """
    checks = {
        'postgres': await db_health_check(),
        'redis': await redis_health_check(),
        'scraper_phase': await check_phase_health('scraping'),
        'extraction_phase': await check_phase_health('extraction'),
        'review_queue_size': await get_review_queue_size(),
        'quality_gates': await check_quality_gates()
    }

    all_healthy = all(check['healthy'] for check in checks.values())

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            'status': 'healthy' if all_healthy else 'degraded',
            'checks': checks,
            'timestamp': datetime.now().isoformat()
        }
    )
```

---

## Part 10: What NOT To Do (At Least for MVP)

### ❌ Don't Add These Yet:
1. **Apache AGE** - Start with recursive CTEs. Add AGE only if graph queries > 300ms p95
2. **ProvSQL** - JSONB provenance sufficient. Add only if you need provenance algebra
3. **Neo4j** - Too much operational complexity for MVP
4. **Qdrant/Pinecone** - pgvectorscale is sufficient for 115GB target
5. **Elasticsearch** - PostgreSQL FTS with materialized tsvector is enough
6. **Kafka** - Redis queue sufficient for MVP scale
7. **Airflow** - Custom scheduler with RQ workers is simpler
8. **dbt** - SQLAlchemy + Alembic sufficient for transformations

### ✅ Feature Flags for Future:
```python
FEATURE_FLAGS = {
    'use_apache_age': False,  # Enable if graph queries too slow
    'use_pgvectorscale': False,  # Enable after validating with 100k vectors
    'use_provsql': False,  # Enable if need provenance queries
    'enable_llm_caching': True,  # This is baseline
    'enable_active_learning': True,  # This is baseline
}
```

---

## Part 11: Final Checklist (Before Go-Live)

```markdown
## Database Foundation
- [ ] PostgreSQL 15+ installed with PostGIS + pgvector
- [ ] schema.sql executed successfully
- [ ] Partitioning configured (monthly range on raw_facts/structured_facts)
- [ ] Materialized tsvector columns with GIN indexes
- [ ] Autovacuum tuned for large indexes
- [ ] Connection pooling configured (asyncpg + SQLAlchemy)

## Quality System
- [ ] 2,000 entity pairs labeled (train/val split)
- [ ] 500 relationships per top 3 edge types labeled
- [ ] Gradient Boosting scorers trained + calibrated
- [ ] Three-band thresholds tuned (Wilson CI ≥ 0.99 for auto-accepts)
- [ ] Human review queue operational
- [ ] Audit sampling (10-20% of auto-accepts)
- [ ] Source reliability tracking implemented

## Ingestion Pipeline
- [ ] 10-gate validation pipeline implemented
- [ ] Composite content hashing (normalized + url + time + selector)
- [ ] Robust LLM cache keys (model + version + temp + recipe)
- [ ] Deterministic entity resolution (registered agent, tax ID, address)
- [ ] Fuzzy matching as fallback (pg_trgm)
- [ ] ML scorer for edge cases
- [ ] Provenance tracking (JSONB sources + evidence_ids)

## Release Gates
- [ ] Entity resolution precision CI ≥ 0.99
- [ ] Relationship precision CI ≥ 0.95
- [ ] False positive rate ≤ 0.01
- [ ] Review queue p95 latency ≤ 24h
- [ ] Automated quality check in CI/CD

## Performance
- [ ] Scale test completed (100k facts, 10k entities, 1M vectors)
- [ ] Simple query p95 < 100ms
- [ ] API response p95 < 500ms
- [ ] Graph query p95 < 300ms (or decision to add AGE)
- [ ] Vector search p95 < 100ms (or decision to add pgvectorscale)

## Security & Operations
- [ ] Row-level security enabled on PII tables
- [ ] Audit triggers on sensitive operations
- [ ] WAL archiving to S3 for PITR
- [ ] Daily full backups (pg_dump)
- [ ] Monitoring: Phase metrics, health checks, SLO dashboards
- [ ] Alerting: Quality degradation, performance SLO violations
- [ ] Rollback plan documented

## Documentation
- [ ] Architecture decision records (why PostgreSQL, why not Neo4j, etc.)
- [ ] SLO definitions and off-ramps
- [ ] Labeling guidelines for reviewers
- [ ] Incident response playbook
- [ ] Cost breakdown and optimization strategies
```

---

## Summary: The Final Plan

**FOUNDATION:** PostgreSQL + PostGIS + pgvector (what you have is good)

**CRITICAL ADDITIONS:**
1. **Learned confidence scorers** (not heuristics) - calibrated GBDT per edge type
2. **Three-band thresholding** - auto-accept (≥99% precision), review, auto-reject
3. **Release gates** - statistical quality checks block bad deploys
4. **Partitioning + materialized tsvector** - performance at scale
5. **Reversible operations** - event-sourced merges, audit sampling
6. **Human-in-the-loop** - for uncertain cases only (not everything)

**ADVANCED FEATURES (OPTIONAL):**
- Apache AGE: Only if graph queries > 300ms p95
- pgvectorscale: Only after validating with 100k vectors
- ProvSQL: Only if need provenance algebra queries

**TIMELINE:**
- Week 1: Foundation + label 2.5k examples
- Week 2: Ingestion pipeline + quality gates
- Week 3: Review system + reversibility
- Week 4: Release gates + scale test + GO/NO-GO

**SUCCESS CRITERIA:**
- Entity resolution: 99% precision (CI lower ≥ 0.99)
- Relationship extraction: 95% precision (CI lower ≥ 0.95)
- False positive rate: ≤ 1%
- Query latency: p95 < 500ms for API calls

**This plan is production-ready. Ship when gates pass.**
