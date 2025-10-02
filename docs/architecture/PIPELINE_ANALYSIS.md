# Data Pipeline Analysis: Sunbiz Enrichment Integration

## Current Pipeline Flow (INCOMPLETE)

```
1. Scraper (sunbiz.py) → Raw SFTP data
   └─ Downloads 1440-char fixed-width records
   └─ Basic parsing inline

2. DataIngestionService.ingest()
   └─ Creates immutable RawFact
   └─ Calls parser by fact_type

3. _parse_llc_formation() [LINE 371-408]
   └─ Creates Entity (canonical_name from raw data)
   └─ Creates LLCFormation (registered_agent from raw data)
   └─ ❌ NO ENRICHMENT - just uses SFTP data!

4. EntityResolver (in _find_or_create_entity)
   └─ Uses name matching only
   └─ ❌ MISSING: Should use registered agent as key!
```

## PROBLEM: Enrichment Not in Pipeline

**What's Missing:**
- LLCs from SFTP have **80% empty registered agent data**
- Website enrichment happens **AFTER** entity creation
- Entity resolution doesn't use registered agent (most distinctive field!)
- Contractor entities never get enriched automatically

## CORRECT Pipeline Flow (Per DATABASE_ARCHITECTURE_FINAL.md)

According to the architecture doc, enrichment should happen BEFORE entity resolution:

```
CORRECT FLOW:
┌─────────────────────────────────────────────────────────────┐
│ 1. SCRAPE                                                    │
│    Sunbiz SFTP → Raw 1440-char records                      │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 2. STORE IMMUTABLE                                           │
│    Create RawFact (event sourcing)                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 3. ENRICH (NEW STEP - BEFORE ENTITY CREATION)               │
│    ✓ Search Sunbiz website by document number              │
│    ✓ Get full data: registered agent, officers, status     │
│    ✓ 100% success rate (doc# is unique key)                │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 4. PARSE TO DOMAIN MODEL                                    │
│    Create Entity with ENRICHED data                         │
│    Create LLCFormation with ENRICHED data                   │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 5. ENTITY RESOLUTION (Uses enriched data!)                  │
│    ✓ Deterministic key: registered_agent (highly unique)   │
│    ✓ Deterministic key: document_number                    │
│    ✓ Deterministic key: tax_id (if available)              │
│    ✓ Fuzzy fallback: name matching                         │
└─────────────────────────────────────────────────────────────┘
```

## Why Enrichment Must Come BEFORE Entity Resolution

**From DATABASE_ARCHITECTURE_FINAL.md (Line 754):**
> "Registered agents are highly distinctive"
> "'Smith & Associates Inc' → 'smith associates'"

**The registered agent is the BEST matching key for LLCs:**
1. **More unique than company name** (many "ABC Development LLC")
2. **More stable than address** (companies move, agents don't change)
3. **Deterministic match** - catches 80% of matches without ML

**Current Problem:**
- SFTP data: 80% have NO registered agent
- Without enrichment: Can only match by fuzzy name (low confidence)
- With enrichment: Can match by registered agent (high confidence)

## Proposed Solution: Enrichment Layer

### Option 1: Eager Enrichment (RECOMMENDED)

Enrich IMMEDIATELY after RawFact creation, before parsing:

```python
async def ingest(self, fact_type, source_url, raw_content, ...):
    # ... existing code ...

    # 3. Create immutable RawFact
    raw_fact = RawFact(...)
    db_session.add(raw_fact)
    await db_session.flush()

    # 3.5 ENRICHMENT LAYER (NEW!)
    if fact_type == 'llc_formation':
        enriched_content = await self._enrich_llc(raw_content)
        raw_content = enriched_content  # Use enriched data for parsing

    # 4. Parse into domain models (now with enriched data!)
    domain_objects = []
    if fact_type in self.parsers:
        parsed = await parser(raw_fact, raw_content, db_session)
        ...
```

**Benefits:**
- ✅ Parser gets complete data
- ✅ Entity resolution has best keys
- ✅ Happens automatically for all LLCs
- ✅ No NULLs in database

**Drawbacks:**
- Adds 2-3 seconds per LLC during ingestion
- Could slow down bulk imports

### Option 2: Lazy Enrichment

Enrich on-demand when entity is accessed:

```python
async def _find_or_create_entity(self, name, entity_type, ...):
    # Try to find existing first
    result = await self.entity_resolver.resolve_entity(...)

    # If entity_type == 'llc' and missing data, try enrichment
    if entity_type == 'llc' and not result.entity:
        enriched = await self.sunbiz_enrichment.search_and_match(name)
        if enriched:
            # Create entity with enriched data
            ...
```

**Benefits:**
- ✅ Fast bulk imports
- ✅ Only enriches when needed

**Drawbacks:**
- ❌ Database has NULLs until accessed
- ❌ Entity resolution happens with incomplete data first time
- ❌ More complex logic

### Option 3: Background Enrichment Worker

Enrich asynchronously after import:

```python
# After RawFact created
await queue.enqueue('enrich_llc', raw_fact_id=raw_fact.id)

# Worker processes queue
async def enrich_llc_worker(raw_fact_id):
    raw_fact = await db.get(raw_fact_id)
    enriched = await sunbiz_enrichment.enrich(...)
    # Update Entity and LLCFormation with enriched data
```

**Benefits:**
- ✅ Fast ingestion
- ✅ Asynchronous processing

**Drawbacks:**
- ❌ Data incomplete until worker runs
- ❌ More infrastructure (queue, workers)
- ❌ Entity resolution can't use enriched data initially

## RECOMMENDATION: Hybrid Approach

**For SFTP bulk imports:** Background enrichment (Option 3)
- Import 100 LLCs quickly
- Enrich in background (parallel processing)
- Update entities when enriched

**For contractor linking:** Eager enrichment (Option 1)
- When creating entity from permit contractor
- Check if LLC exists in Sunbiz
- Create with full data immediately

## Implementation Plan

### 1. Update DataIngestionService

Add enrichment layer:

```python
from .sunbiz_enrichment import SunbizEnrichmentService

class DataIngestionService:
    def __init__(self, llm_client=None):
        self.parsers = {}
        self.entity_resolver = EntityResolver(llm_client=llm_client)
        self.sunbiz_enrichment = SunbizEnrichmentService(headless=True)  # NEW
        self._register_default_parsers()

    async def _enrich_llc(self, raw_content: Dict) -> Dict:
        """
        Enrich LLC data from Sunbiz website

        Args:
            raw_content: Raw SFTP data (may have missing fields)

        Returns:
            Enriched data with full registered agent, officers, etc.
        """
        doc_num = raw_content.get('document_number') or raw_content.get('DocumentNumber')

        if not doc_num:
            return raw_content  # Can't enrich without doc number

        # Fetch from website
        enriched = await self.sunbiz_enrichment.scraper.scrape_entity(doc_num)

        if not enriched:
            return raw_content  # Website unavailable, use SFTP data

        # Merge: website data takes precedence
        return {
            **raw_content,  # SFTP data as base
            'name': enriched.get('entityName') or raw_content.get('name'),
            'registered_agent': enriched.get('registeredAgent', {}).get('name'),
            'registered_agent_address': enriched.get('registeredAgent', {}).get('address'),
            'officers': enriched.get('officers'),
            'status': enriched.get('status'),
            'principal_address': enriched.get('principalAddress'),
            'mailing_address': enriched.get('mailingAddress'),
            # ... more fields
        }
```

### 2. Update _parse_llc_formation

Use enriched data:

```python
async def _parse_llc_formation(self, raw_fact, content, db_session):
    """Parse LLC formation from Sunbiz (now with enriched data!)"""

    # Enrich if not already done
    if not content.get('_enriched'):
        content = await self._enrich_llc(content)
        content['_enriched'] = True

    # Create entity with ENRICHED canonical name
    entity = Entity(
        id=uuid4(),
        entity_type='llc',
        canonical_name=content.get('name'),  # Now from website!
        fact_based_attributes=content
    )
    db_session.add(entity)
    await db_session.flush()

    # Create LLC formation with ENRICHED registered agent
    llc = LLCFormation(
        id=uuid4(),
        raw_fact_id=raw_fact.id,
        entity_id=entity.id,
        document_number=content.get('document_number'),
        filing_date=self._parse_datetime(content.get('filing_date')),
        registered_agent=content.get('registered_agent'),  # Now complete!
        principal_address=content.get('principal_address'),
        status=content.get('status', 'active'),
        officers=content.get('officers')  # Now populated!
    )

    db_session.add(llc)
    return [llc]
```

### 3. Update EntityResolver

Add registered agent as primary key:

```python
# In entity_resolution.py
async def resolve_entity(self, scraped_data, source_context, db_session):
    # ... existing code ...

    # NEW: Try registered agent match first (highest confidence)
    if scraped_data.get('registered_agent'):
        agent_normalized = self._normalize_agent(scraped_data['registered_agent'])
        existing = await self._find_by_registered_agent(agent_normalized, db_session)
        if existing:
            return ResolutionResult(
                entity=existing,
                confidence=0.98,  # Very high confidence
                method='registered_agent_match'
            )

    # Then try other keys (tax_id, address, name...)
    ...
```

## Answer to Your Questions

### 1. "Why delete parser instead of moving to utilities?"

**DELETED because it's unused:**
- `sunbiz_parser_v2.py` was a parser for 1440-char SFTP records
- `sunbiz.py` scraper has its own inline parsing
- Parser was never imported anywhere
- No point keeping dead code

**If we needed it:**
- Would move to `src/scrapers/utilities/` (for scraper-specific helpers)
- NOT `src/utilities/` (that's for general app utilities)

### 2. "Should enrichment be in pipeline before connections?"

**YES - 100% correct intuition!**

**Per DATABASE_ARCHITECTURE_FINAL.md:**
- "Deterministic entity resolution keys" (Line 739-791)
- Registered agent is "highly distinctive" matching key
- Should happen BEFORE entity resolution

**Current problem:**
- Enrichment happens AFTER entity creation (manually, separate scripts)
- Entity resolution can't use registered agent (80% missing from SFTP)
- Contractors never get enriched automatically

**Fix:**
- Add enrichment layer in DataIngestionService
- Enrich BEFORE calling _parse_llc_formation
- Entity resolver gets complete data for matching

## Next Steps

1. **Integrate enrichment into DataIngestionService**
   - Add `_enrich_llc()` method
   - Call before parsing LLC formations
   - Update `_parse_llc_formation` to use enriched data

2. **Update EntityResolver**
   - Add registered_agent as primary matching key
   - Add document_number as deterministic key
   - Use fuzzy name matching as fallback only

3. **Test end-to-end**
   - Import 10 LLCs from SFTP
   - Verify enrichment happens automatically
   - Verify entity resolution uses registered agent
   - Check for NULLs (should be 0%)

4. **Add background enrichment for bulk imports**
   - Queue enrichment tasks
   - Process in parallel
   - Update entities when complete

This is the "full picture" architecture!
