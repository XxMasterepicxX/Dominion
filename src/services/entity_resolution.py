"""
EntityResolver - Context-aware entity matching with LLM fallback

Strategy:
1. Tier 1: Definitive keys (document #, tax ID) - 99.9% confidence
2. Tier 2: Multi-signal scoring with context awareness - 70-95% confidence
3. Tier 3: LLM zero-shot for uncertain cases - human-level reasoning
4. All decisions logged -> training data for Week 3 ML model

Design principles:
- No hardcoded abbreviation lists
- Use ALL available data fields
- Context-aware (news vs sunbiz vs permit)
- Collect training data for future ML
"""
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from ..database import Entity

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Individual matching signal"""
    name: str
    value: float  # 0.0 to 1.0
    weight: float
    explanation: str = ""


@dataclass
class MatchScore:
    """Scoring result for a candidate match"""
    confidence: float
    signals: List[Signal]
    method: str  # 'definitive', 'multi_signal', 'llm', 'needs_review'
    explanation: str = ""


@dataclass
class MatchResult:
    """Final entity resolution result"""
    entity: Optional[Entity]
    confidence: float
    matched_on: str
    method: str
    created_new: bool = False
    needs_review: bool = False


class EntityResolver:
    """
    Context-aware entity resolution
    Combines deterministic matching, multi-signal scoring, and LLM fallback
    """

    # Confidence thresholds (three-band)
    # Tuned for real-world data (Week 1 baseline)
    AUTO_ACCEPT_THRESHOLD = 0.85  # Lowered from 0.95 - too strict for initial matching
    REVIEW_THRESHOLD = 0.60  # Lowered from 0.70

    # Source type reliability (for name matching weight)
    SOURCE_WEIGHTS = {
        'sunbiz': 0.50,          # Official registration - trust name heavily
        'property_deed': 0.40,   # Legal document - high trust
        'property_appraiser': 0.40,
        'city_permit': 0.35,     # Official but can have typos
        'county_permit': 0.35,
        'news_article': 0.15,    # Informal references - low trust
        'social_media': 0.10,
        'manual_entry': 0.20,
    }

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: Optional LLM client (Gemini) for uncertain matches
        """
        self.llm_client = llm_client

    async def resolve_entity(
        self,
        scraped_data: Dict[str, Any],
        source_context: Dict[str, Any],
        db_session: AsyncSession
    ) -> MatchResult:
        """
        Main entry point: Find or create entity

        Args:
            scraped_data: Raw data about the entity (name, address, phone, etc.)
            source_context: Context about the source (type, url, date, etc.)
            db_session: Database session

        Returns:
            MatchResult with entity and confidence
        """

        # Extract all available features
        features = self.extract_all_features(scraped_data)

        logger.info(f"Resolving entity: {features.get('official_name', 'unknown')}")

        # ========================================
        # TIER 1: DEFINITIVE KEYS
        # ========================================

        definitive_match = await self._try_definitive_keys(features, db_session)
        if definitive_match:
            logger.info(f"Definitive match found: {definitive_match.matched_on}")
            return definitive_match

        # ========================================
        # TIER 2: MULTI-SIGNAL MATCHING
        # ========================================

        # Find candidates
        candidates = await self._find_candidates(features, db_session)

        if not candidates:
            # No candidates - create new entity
            logger.info("No candidates found - creating new entity")
            new_entity = await self._create_new_entity(scraped_data, features, db_session)
            return MatchResult(
                entity=new_entity,
                confidence=1.0,
                matched_on='new_entity',
                method='creation',
                created_new=True
            )

        # Score all candidates
        scored_candidates = []
        for candidate in candidates:
            score = await self._score_match(
                features=features,
                source_context=source_context,
                candidate=candidate,
                db_session=db_session
            )
            scored_candidates.append((candidate, score))

        # Sort by confidence
        scored_candidates.sort(key=lambda x: x[1].confidence, reverse=True)
        best_candidate, best_score = scored_candidates[0]

        logger.info(
            f"Best match: {best_candidate['canonical_name']} "
            f"(confidence: {best_score.confidence:.3f}, method: {best_score.method})"
        )

        # ========================================
        # DECISION: Auto-accept, Review, or Reject
        # ========================================

        if best_score.confidence >= self.AUTO_ACCEPT_THRESHOLD:
            # High confidence - auto-accept
            entity = await db_session.get(Entity, best_candidate['id'])

            # Log decision for training data
            await self._log_resolution_decision(
                features=features,
                matched_entity_id=entity.id,
                confidence=best_score.confidence,
                signals=best_score.signals,
                method=best_score.method,
                auto_accepted=True,
                db_session=db_session
            )

            return MatchResult(
                entity=entity,
                confidence=best_score.confidence,
                matched_on=', '.join(s.name for s in best_score.signals if s.value > 0),
                method=best_score.method
            )

        elif best_score.confidence >= self.REVIEW_THRESHOLD:
            # Medium confidence - try LLM if available, else queue review

            if self.llm_client:
                # ========================================
                # TIER 3: LLM ZERO-SHOT REASONING
                # ========================================
                llm_score = await self._llm_score_match(
                    features=features,
                    source_context=source_context,
                    candidate=best_candidate,
                    deterministic_score=best_score
                )

                if llm_score.confidence >= self.AUTO_ACCEPT_THRESHOLD:
                    # LLM confident - accept
                    entity = await db_session.get(Entity, best_candidate['id'])

                    await self._log_resolution_decision(
                        features=features,
                        matched_entity_id=entity.id,
                        confidence=llm_score.confidence,
                        signals=llm_score.signals,
                        method='llm',
                        auto_accepted=True,
                        db_session=db_session
                    )

                    return MatchResult(
                        entity=entity,
                        confidence=llm_score.confidence,
                        matched_on='llm_reasoning',
                        method='llm'
                    )

            # LLM not confident or not available - queue for human review
            await self._queue_for_review(
                features=features,
                candidate=best_candidate,
                score=best_score,
                db_session=db_session
            )

            return MatchResult(
                entity=None,
                confidence=best_score.confidence,
                matched_on='needs_review',
                method='needs_review',
                needs_review=True
            )

        else:
            # Low confidence - create new with verification flag
            logger.info(f"Low confidence ({best_score.confidence:.3f}) - creating new entity")
            new_entity = await self._create_new_entity(
                scraped_data,
                features,
                db_session,
                needs_verification=True
            )
            return MatchResult(
                entity=new_entity,
                confidence=best_score.confidence,
                matched_on='low_confidence_new',
                method='creation',
                created_new=True,
                needs_review=True
            )

    def extract_all_features(self, scraped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract ALL available features from scraped data
        Don't filter - get everything we have
        """
        return {
            # Legal identifiers
            'document_number': scraped_data.get('document_number') or scraped_data.get('DocumentNumber'),
            'tax_id': scraped_data.get('tax_id') or scraped_data.get('ein') or scraped_data.get('EIN'),

            # Names (all variations)
            'official_name': (
                scraped_data.get('entity_name') or
                scraped_data.get('EntityName') or
                scraped_data.get('name') or
                scraped_data.get('company_name') or
                scraped_data.get('applicant') or
                scraped_data.get('Applicant') or
                scraped_data.get('contractor') or
                scraped_data.get('Contractor') or
                scraped_data.get('buyer')
            ),
            'legal_designator': scraped_data.get('entity_type') or self._extract_designator(
                scraped_data.get('entity_name') or scraped_data.get('name', '')
            ),

            # People
            'owner': scraped_data.get('owner'),
            'owners': scraped_data.get('owners', []),
            'principals': scraped_data.get('principals', []),
            'officers': scraped_data.get('officers', []),
            'registered_agent': scraped_data.get('registered_agent') or scraped_data.get('RegisteredAgent'),

            # Contact info
            'principal_address': (
                scraped_data.get('principal_address') or
                scraped_data.get('PrincipalAddress') or
                scraped_data.get('address') or
                scraped_data.get('Address')
            ),
            'mailing_address': scraped_data.get('mailing_address') or scraped_data.get('MailingAddress'),
            'phone': scraped_data.get('phone') or scraped_data.get('Phone'),
            'email': scraped_data.get('email') or scraped_data.get('Email'),
            'website': scraped_data.get('website') or scraped_data.get('Website'),

            # Context identifiers
            'parcel_id': scraped_data.get('parcel_id'),
            'permit_number': scraped_data.get('permit_number'),
        }

    def _extract_designator(self, name: str) -> str:
        """Extract legal designator from name"""
        if not name:
            return ''

        name_upper = name.upper()

        # Check for LLC
        if re.search(r'\bL\.?L\.?C\.?\b', name_upper):
            return 'LLC'

        # Check for Inc
        if re.search(r'\bINC\.?\b|\bINCORPORATED\b', name_upper):
            return 'INC'

        # Check for Corp
        if re.search(r'\bCORP\.?\b|\bCORPORATION\b', name_upper):
            return 'CORP'

        # Check for Ltd
        if re.search(r'\bLTD\.?\b|\bLIMITED\b', name_upper):
            return 'LTD'

        return ''

    async def _try_definitive_keys(
        self,
        features: Dict[str, Any],
        db_session: AsyncSession
    ) -> Optional[MatchResult]:
        """Try matching on definitive identifiers"""

        # Try document number (Florida L12345678, P12345678, etc.)
        if features['document_number']:
            result = await db_session.execute(
                select(Entity).where(
                    Entity.fact_based_attributes['document_number'].astext == features['document_number']
                )
            )
            entity = result.scalar_one_or_none()
            if entity:
                return MatchResult(
                    entity=entity,
                    confidence=0.999,
                    matched_on='document_number',
                    method='definitive'
                )

        # Try tax ID / EIN
        if features['tax_id']:
            result = await db_session.execute(
                select(Entity).where(
                    Entity.fact_based_attributes['tax_id'].astext == features['tax_id']
                )
            )
            entity = result.scalar_one_or_none()
            if entity:
                return MatchResult(
                    entity=entity,
                    confidence=0.999,
                    matched_on='tax_id',
                    method='definitive'
                )

        # Try parcel ID (property parcels are unique identifiers)
        if features['parcel_id']:
            result = await db_session.execute(
                select(Entity).where(
                    Entity.fact_based_attributes['parcel_id'].astext == features['parcel_id']
                )
            )
            entity = result.scalar_one_or_none()
            if entity:
                return MatchResult(
                    entity=entity,
                    confidence=0.999,
                    matched_on='parcel_id',
                    method='definitive'
                )

        return None

    async def _find_candidates(
        self,
        features: Dict[str, Any],
        db_session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Find candidate entities using ANY available field
        Cast wide net - we'll score them next
        """
        candidates = {}  # Use dict to deduplicate by ID

        # Search by name (fuzzy)
        if features['official_name']:
            name_norm = self.normalize_name(features['official_name'])
            result = await db_session.execute(
                select(Entity.id, Entity.canonical_name, Entity.fact_based_attributes)
                .where(func.similarity(Entity.canonical_name, name_norm) > 0.3)
                .order_by(func.similarity(Entity.canonical_name, name_norm).desc())
                .limit(20)
            )
            for row in result:
                candidates[str(row.id)] = {
                    'id': row.id,
                    'canonical_name': row.canonical_name,
                    'attributes': row.fact_based_attributes
                }

        # Search by address (check all possible field names)
        if features['principal_address']:
            addr_norm = self.normalize_address(features['principal_address'])
            result = await db_session.execute(
                text("""
                    SELECT id, canonical_name, fact_based_attributes
                    FROM entities
                    WHERE fact_based_attributes->>'principal_address' ILIKE :addr
                       OR fact_based_attributes->>'PrincipalAddress' ILIKE :addr
                       OR fact_based_attributes->>'address' ILIKE :addr
                       OR fact_based_attributes->>'Address' ILIKE :addr
                    LIMIT 20
                """),
                {'addr': f'%{addr_norm}%'}
            )
            for row in result:
                candidates[str(row.id)] = {
                    'id': row.id,
                    'canonical_name': row.canonical_name,
                    'attributes': row.fact_based_attributes
                }

        # Search by phone (check all possible field names)
        if features['phone']:
            phone_norm = self.normalize_phone(features['phone'])
            result = await db_session.execute(
                text("""
                    SELECT id, canonical_name, fact_based_attributes
                    FROM entities
                    WHERE fact_based_attributes->>'phone' = :phone
                       OR fact_based_attributes->>'Phone' = :phone
                    LIMIT 20
                """),
                {'phone': phone_norm}
            )
            for row in result:
                candidates[str(row.id)] = {
                    'id': row.id,
                    'canonical_name': row.canonical_name,
                    'attributes': row.fact_based_attributes
                }

        # Search by owner
        if features['owner']:
            result = await db_session.execute(
                text("""
                    SELECT id, canonical_name, fact_based_attributes
                    FROM entities
                    WHERE fact_based_attributes->>'owner' ILIKE :owner
                    LIMIT 20
                """),
                {'owner': f'%{features["owner"]}%'}
            )
            for row in result:
                candidates[str(row.id)] = {
                    'id': row.id,
                    'canonical_name': row.canonical_name,
                    'attributes': row.fact_based_attributes
                }

        return list(candidates.values())

    async def _score_match(
        self,
        features: Dict[str, Any],
        source_context: Dict[str, Any],
        candidate: Dict[str, Any],
        db_session: AsyncSession
    ) -> MatchScore:
        """
        Score how likely features refer to same entity as candidate
        Context-aware, multi-signal scoring
        """
        signals = []
        candidate_attrs = candidate['attributes']

        # =============================================
        # CONTRADICTION CHECK: Different Document Numbers
        # =============================================
        # If both have document numbers and they're different -> DIFFERENT entities
        # (e.g., dissolved company name reused)
        scraped_doc = features.get('document_number')
        candidate_doc = candidate_attrs.get('document_number')

        if scraped_doc and candidate_doc and scraped_doc != candidate_doc:
            # Different document numbers = definitely different entities
            return MatchScore(
                confidence=0.0,
                signals=[Signal(
                    name='document_number_mismatch',
                    value=0.0,
                    weight=1.0,
                    explanation=f"Different document numbers: {scraped_doc} vs {candidate_doc}"
                )],
                method='contradiction',
                explanation=f"Cannot be same entity: different document numbers ({scraped_doc} vs {candidate_doc})"
            )

        # =============================================
        # SIGNAL 1: Name Similarity (context-aware)
        # =============================================
        if features['official_name']:
            name_sim = self._calculate_name_similarity(
                features['official_name'],
                candidate['canonical_name'],
                source_context
            )

            # Weight based on source type
            source_type = source_context.get('source_type', 'unknown')
            name_weight = self.SOURCE_WEIGHTS.get(source_type, 0.30)

            signals.append(Signal(
                name='name_similarity',
                value=name_sim,
                weight=name_weight,
                explanation=f"Name similarity: {name_sim:.2f} (source: {source_type})"
            ))

        # =============================================
        # SIGNAL 2: Address Match
        # =============================================
        # Extract address from candidate (check multiple field names)
        candidate_address = (
            candidate_attrs.get('principal_address') or
            candidate_attrs.get('PrincipalAddress') or
            candidate_attrs.get('address') or
            candidate_attrs.get('Address')
        )

        if features['principal_address'] and candidate_address:
            addr_sim = self._calculate_address_similarity(
                features['principal_address'],
                candidate_address
            )
            signals.append(Signal(
                name='address_match',
                value=addr_sim,
                weight=0.35,
                explanation=f"Address similarity: {addr_sim:.2f}"
            ))

        # =============================================
        # SIGNAL 3: Phone Match
        # =============================================
        # Extract phone from candidate (check multiple field names)
        candidate_phone = candidate_attrs.get('phone') or candidate_attrs.get('Phone')

        if features['phone'] and candidate_phone:
            phone_match = (
                self.normalize_phone(features['phone']) ==
                self.normalize_phone(candidate_phone)
            )
            signals.append(Signal(
                name='phone_match',
                value=1.0 if phone_match else 0.0,
                weight=0.30,
                explanation=f"Phone {'matches' if phone_match else 'differs'}"
            ))

        # =============================================
        # SIGNAL 4: Owner/Principal Similarity
        # =============================================
        owner_sim = self._calculate_owner_similarity(features, candidate_attrs)
        if owner_sim > 0:
            signals.append(Signal(
                name='owner_similarity',
                value=owner_sim,
                weight=0.40,
                explanation=f"Owner similarity: {owner_sim:.2f}"
            ))

        # =============================================
        # SIGNAL 5: Email Domain Match
        # =============================================
        if features['email'] and candidate_attrs.get('email'):
            scraped_domain = features['email'].split('@')[1].lower() if '@' in features['email'] else None
            candidate_domain = candidate_attrs['email'].split('@')[1].lower() if '@' in candidate_attrs['email'] else None

            if scraped_domain and candidate_domain:
                domain_match = scraped_domain == candidate_domain
                signals.append(Signal(
                    name='email_domain_match',
                    value=1.0 if domain_match else 0.0,
                    weight=0.25,
                    explanation=f"Email domain {'matches' if domain_match else 'differs'}"
                ))

        # =============================================
        # SIGNAL 6: Registered Agent Match (with service detection)
        # =============================================
        scraped_agent = features.get('registered_agent')
        candidate_agent = (
            candidate_attrs.get('registered_agent') or
            candidate_attrs.get('RegisteredAgent')
        )

        if scraped_agent and candidate_agent:
            # Check if this is a known agent service (CT Corporation, etc.)
            agent_signal = await self._check_registered_agent_signal(
                scraped_agent,
                candidate_agent,
                db_session
            )
            if agent_signal:
                signals.append(agent_signal)

        # =============================================
        # Calculate weighted confidence
        # =============================================
        if not signals:
            return MatchScore(
                confidence=0.0,
                signals=[],
                method='no_signals',
                explanation="No matching signals found"
            )

        total_weight = sum(s.weight for s in signals)
        weighted_sum = sum(s.value * s.weight for s in signals)
        confidence = weighted_sum / total_weight if total_weight > 0 else 0.0

        # IMPORTANT: Penalize single-signal matches
        # Name-only matches (even if perfect) should never auto-accept
        # We need multiple confirming signals to be confident
        positive_signals = [s for s in signals if s.value > 0]
        if len(positive_signals) == 1:
            # Only one signal - cap confidence at 0.85 to force review
            # (Just below AUTO_ACCEPT_THRESHOLD)
            confidence = min(confidence, 0.84)
            explanation_suffix = "\n  [CAPPED: Single signal only]"
        else:
            explanation_suffix = ""

        # Build explanation
        explanation = f"Confidence: {confidence:.3f} based on:\n"
        for signal in signals:
            if signal.value > 0:
                explanation += f"  - {signal.explanation}\n"
        explanation += explanation_suffix

        return MatchScore(
            confidence=confidence,
            signals=positive_signals,
            method='multi_signal',
            explanation=explanation
        )

    def _calculate_name_similarity(
        self,
        name1: str,
        name2: str,
        source_context: Dict[str, Any]
    ) -> float:
        """
        Context-aware name similarity
        News articles get looser matching (informal names)
        Official sources get stricter matching
        """
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Trigram similarity (PostgreSQL pg_trgm equivalent)
        base_sim = self._trigram_similarity(norm1, norm2)

        # Adjust based on source context
        source_type = source_context.get('source_type', 'unknown')

        if source_type == 'news_article':
            # News often uses informal names
            # "ABC Dev" might be "ABC Development LLC"

            # Boost if one is substring of other
            if norm1 in norm2 or norm2 in norm1:
                base_sim = max(base_sim, 0.85)

            # Boost if significant words overlap
            words1 = set(w for w in norm1.split() if len(w) >= 3)
            words2 = set(w for w in norm2.split() if len(w) >= 3)
            if words1 and words2:
                word_overlap = len(words1 & words2) / len(words1 | words2)
                base_sim = max(base_sim, word_overlap)

        return base_sim

    def _calculate_address_similarity(self, addr1: str, addr2: str) -> float:
        """Calculate address similarity"""
        norm1 = self.normalize_address(addr1)
        norm2 = self.normalize_address(addr2)

        if norm1 == norm2:
            return 1.0

        # Check if one contains the other (123 Main St vs 123 Main Street)
        if norm1 in norm2 or norm2 in norm1:
            return 0.95

        return self._trigram_similarity(norm1, norm2)

    def _calculate_owner_similarity(
        self,
        features: Dict[str, Any],
        candidate_attrs: Dict[str, Any]
    ) -> float:
        """Compare owner/principal/officer information"""

        # Collect all people from features
        scraped_people = set()
        if features.get('owner'):
            scraped_people.add(self.normalize_person_name(features['owner']))
        for person_list in [features.get('owners', []), features.get('principals', []), features.get('officers', [])]:
            scraped_people.update(self.normalize_person_name(p) for p in person_list if p)

        # Collect all people from candidate
        candidate_people = set()
        if candidate_attrs.get('owner'):
            candidate_people.add(self.normalize_person_name(candidate_attrs['owner']))
        for person_list in [candidate_attrs.get('owners', []), candidate_attrs.get('principals', []), candidate_attrs.get('officers', [])]:
            if person_list:
                candidate_people.update(self.normalize_person_name(p) for p in person_list if p)

        if not scraped_people or not candidate_people:
            return 0.0

        # Overlap coefficient (intersection / min)
        # Better than Jaccard for entity resolution - if one owner matches, it's significant
        # even if one entity has more owners listed
        intersection = scraped_people & candidate_people
        min_size = min(len(scraped_people), len(candidate_people))

        return len(intersection) / min_size if min_size > 0 else 0.0

    async def _check_registered_agent_signal(
        self,
        scraped_agent: str,
        candidate_agent: str,
        db_session: AsyncSession
    ) -> Optional[Signal]:
        """
        Check if registered agent is a known service or unique agent

        CRITICAL NEGATIVE SIGNAL:
        - If both entities use CT Corporation System -> Different companies (not related)
        - If both use rare agent "John Smith Law Office" -> Might be same company

        Args:
            scraped_agent: Registered agent from scraped data
            candidate_agent: Registered agent from candidate entity
            db_session: Database session

        Returns:
            Signal with appropriate weight (0.0 for services, 0.30 for unique agents)
        """
        # Normalize both agent names
        scraped_norm = self.normalize_name(scraped_agent)
        candidate_norm = self.normalize_name(candidate_agent)

        # Check if they match
        if scraped_norm != candidate_norm:
            # Different agents - not a signal either way
            return None

        # Same agent - check if it's a known service
        result = await db_session.execute(
            text("""
                SELECT id FROM known_agent_services
                WHERE LOWER(service_name) = LOWER(:agent)
                LIMIT 1
            """),
            {'agent': scraped_agent}
        )

        is_service = result.scalar_one_or_none() is not None

        if is_service:
            # It's a service (CT Corp, etc.) - same agent means NOTHING
            # This is actually a NEGATIVE signal (different companies)
            # Don't add to scoring - just skip it
            return None
        else:
            # It's a real person/small firm - same agent is meaningful
            # Strong positive signal that these are the same company
            return Signal(
                name='registered_agent_match',
                value=1.0,
                weight=0.30,
                explanation=f"Same registered agent: {scraped_agent}"
            )

    async def _llm_score_match(
        self,
        features: Dict[str, Any],
        source_context: Dict[str, Any],
        candidate: Dict[str, Any],
        deterministic_score: MatchScore
    ) -> MatchScore:
        """
        Use LLM for uncertain matches
        Provides human-level reasoning
        """
        if not self.llm_client:
            return deterministic_score

        # Build prompt
        prompt = self._build_llm_prompt(features, source_context, candidate, deterministic_score)

        try:
            # Call LLM
            response = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.0,  # Deterministic
                response_format='json'
            )

            # Parse response
            result = response.json()

            return MatchScore(
                confidence=result.get('confidence', deterministic_score.confidence),
                signals=deterministic_score.signals + [
                    Signal(
                        name='llm_reasoning',
                        value=result.get('confidence', 0),
                        weight=1.0,
                        explanation=result.get('reasoning', '')
                    )
                ],
                method='llm',
                explanation=result.get('reasoning', '')
            )

        except Exception as e:
            logger.error(f"LLM scoring failed: {e}")
            return deterministic_score

    def _build_llm_prompt(
        self,
        features: Dict[str, Any],
        source_context: Dict[str, Any],
        candidate: Dict[str, Any],
        deterministic_score: MatchScore
    ) -> str:
        """Build prompt for LLM entity matching"""

        candidate_attrs = candidate['attributes']

        return f"""Are these two entity mentions referring to the same real-world company?

**Entity 1 (Newly Scraped):**
Source: {source_context.get('source_type', 'unknown')}
Name: {features.get('official_name', 'unknown')}
Address: {features.get('principal_address', 'unknown')}
Phone: {features.get('phone', 'unknown')}
Owner: {features.get('owner', 'unknown')}

**Entity 2 (Existing in Database):**
Official Name: {candidate['canonical_name']}
Document #: {candidate_attrs.get('document_number', 'unknown')}
Address: {candidate_attrs.get('principal_address', 'unknown')}
Phone: {candidate_attrs.get('phone', 'unknown')}
Owner: {candidate_attrs.get('owner', 'unknown')}

**Deterministic Scoring Result:**
Confidence: {deterministic_score.confidence:.3f}
Signals: {deterministic_score.explanation}

**Context to Consider:**
1. Name variations: Informal names in news vs official names in legal docs
2. Address normalization: "123 Main St" vs "123 Main Street"
3. Source reliability: {source_context.get('source_type')} data quality
4. Abbreviations: "ABC Dev" might be "ABC Development LLC"

Return JSON with:
{{
  "same_entity": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "Explain your decision in 1-2 sentences"
}}"""

    async def _create_new_entity(
        self,
        scraped_data: Dict[str, Any],
        features: Dict[str, Any],
        db_session: AsyncSession,
        needs_verification: bool = False
    ) -> Entity:
        """Create new entity from scraped data"""

        entity = Entity(
            id=uuid4(),
            entity_type=self._determine_entity_type(features),
            canonical_name=self.normalize_name(features['official_name']),
            fact_based_attributes=scraped_data,
            resolution_confidence=0.60 if needs_verification else 1.0
        )

        db_session.add(entity)
        await db_session.flush()

        logger.info(f"Created new entity: {entity.canonical_name} (verification: {needs_verification})")

        return entity

    def _determine_entity_type(self, features: Dict[str, Any]) -> str:
        """Determine entity type from features"""
        designator = features.get('legal_designator', '').upper()

        if designator == 'LLC':
            return 'llc'
        elif designator in ('INC', 'CORP'):
            return 'company'
        else:
            return 'organization'

    async def _log_resolution_decision(
        self,
        features: Dict[str, Any],
        matched_entity_id: uuid4,
        confidence: float,
        signals: List[Signal],
        method: str,
        auto_accepted: bool,
        db_session: AsyncSession
    ):
        """
        Log resolution decision for training data
        This builds dataset for Week 3 ML model
        """
        import json

        try:
            # Store in entity_resolution_log table for ML training
            await db_session.execute(
                text("""
                    INSERT INTO entity_resolution_log
                    (id, scraped_features, matched_entity_id, confidence, signals, method, auto_accepted, created_at)
                    VALUES (CAST(:id AS uuid), CAST(:features AS jsonb), CAST(:entity_id AS uuid), CAST(:confidence AS float), CAST(:signals AS jsonb), CAST(:method AS text), CAST(:auto_accepted AS boolean), NOW())
                """),
                {
                    'id': str(uuid4()),
                    'features': json.dumps(features),
                    'entity_id': str(matched_entity_id) if matched_entity_id else None,
                    'confidence': float(confidence),
                    'signals': json.dumps([{'name': s.name, 'value': s.value, 'weight': s.weight} for s in signals]),
                    'method': str(method),
                    'auto_accepted': bool(auto_accepted)
                }
            )
            logger.debug(f"Logged resolution decision: {method} (confidence: {confidence:.3f})")
        except Exception as e:
            logger.warning(f"Failed to log resolution decision: {e}")
            # Don't fail the resolution if logging fails  # Skip logging for now

    async def _queue_for_review(
        self,
        features: Dict[str, Any],
        candidate: Dict[str, Any],
        score: MatchScore,
        db_session: AsyncSession
    ):
        """Queue uncertain match for human review"""
        import json

        try:
            await db_session.execute(
                text("""
                    INSERT INTO entity_review_queue
                    (id, scraped_features, candidate_entity_id, confidence, signals, status, created_at)
                    VALUES (CAST(:id AS uuid), CAST(:features AS jsonb), CAST(:candidate_id AS uuid), CAST(:confidence AS float), CAST(:signals AS jsonb), 'pending', NOW())
                """),
                {
                    'id': str(uuid4()),
                    'features': json.dumps(features),
                    'candidate_id': str(candidate['id']),
                    'confidence': float(score.confidence),
                    'signals': json.dumps([{'name': s.name, 'value': s.value, 'weight': s.weight} for s in score.signals])
                }
            )
            logger.info(f"Queued for review: {features.get('official_name')} vs {candidate['canonical_name']}")
        except Exception as e:
            logger.warning(f"Failed to queue for review: {e}")
            # Don't fail the resolution if queueing fails

    # ==================== NORMALIZATION HELPERS ====================

    def normalize_name(self, name: str) -> str:
        """Normalize company name (Florida-style)"""
        if not name:
            return ''

        name = name.upper()

        # Remove articles
        name = re.sub(r'\b(THE|A|AN)\b\s*', '', name)

        # Remove punctuation
        name = re.sub(r'[^\w\s]', '', name)

        # Normalize whitespace
        name = ' '.join(name.split())

        return name

    def normalize_address(self, address: str) -> str:
        """
        Normalize address using usaddress library for better accuracy

        Handles:
        - Directional abbreviations (West -> W, North -> N)
        - Street type abbreviations (Avenue -> AVE, Street -> ST)
        - Unit numbers (Apt 5B -> #5B)
        - Fractional addresses (1234½ -> 1234 1/2)

        Returns normalized address string for matching
        """
        if not address:
            return ''

        try:
            import usaddress

            # Parse address into components
            try:
                parsed, address_type = usaddress.tag(address)
            except usaddress.RepeatedLabelError:
                # Handle addresses with repeated components (common with non-English text)
                raise ValueError("Address has repeated labels - falling back to regex")

            # Build normalized address from components
            # Order: house_number + street_direction + street_name + street_type + unit + city + state + zipcode
            components = []

            # House number (with fractions)
            if 'AddressNumber' in parsed:
                components.append(parsed['AddressNumber'].upper())

            # Street prefix direction (N, S, E, W, NW, etc.)
            if 'StreetNamePreDirectional' in parsed:
                direction = parsed['StreetNamePreDirectional'].upper()
                # Standardize to single-letter abbreviations
                dir_map = {
                    'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W',
                    'NORTHEAST': 'NE', 'NORTHWEST': 'NW',
                    'SOUTHEAST': 'SE', 'SOUTHWEST': 'SW'
                }
                direction = dir_map.get(direction, direction)
                components.append(direction)

            # Street name
            if 'StreetName' in parsed:
                components.append(parsed['StreetName'].upper())

            # Street type (ST, AVE, RD, etc.)
            if 'StreetNamePostType' in parsed:
                street_type = parsed['StreetNamePostType'].upper()
                # Standardize common abbreviations
                type_map = {
                    'STREET': 'ST', 'AVENUE': 'AVE', 'ROAD': 'RD',
                    'DRIVE': 'DR', 'BOULEVARD': 'BLVD', 'LANE': 'LN',
                    'COURT': 'CT', 'CIRCLE': 'CIR', 'PLACE': 'PL'
                }
                street_type = type_map.get(street_type, street_type)
                components.append(street_type)

            # Street suffix direction
            if 'StreetNamePostDirectional' in parsed:
                direction = parsed['StreetNamePostDirectional'].upper()
                # Standardize to single-letter abbreviations
                dir_map = {
                    'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W',
                    'NORTHEAST': 'NE', 'NORTHWEST': 'NW',
                    'SOUTHEAST': 'SE', 'SOUTHWEST': 'SW'
                }
                direction = dir_map.get(direction, direction)
                components.append(direction)

            # Unit/apartment number
            unit_parts = []
            if 'OccupancyType' in parsed:
                unit_parts.append(parsed['OccupancyType'].upper())
            if 'OccupancyIdentifier' in parsed:
                unit_parts.append(parsed['OccupancyIdentifier'].upper())
            if unit_parts:
                components.append('#' + ' '.join(unit_parts))

            # City
            if 'PlaceName' in parsed:
                components.append(parsed['PlaceName'].upper())

            # State
            if 'StateName' in parsed:
                components.append(parsed['StateName'].upper())

            # Zip code
            if 'ZipCode' in parsed:
                components.append(parsed['ZipCode'])

            normalized = ' '.join(components)

            # Clean up any extra whitespace
            normalized = ' '.join(normalized.split())

            return normalized

        except Exception as e:
            # Fallback to simple regex normalization if usaddress fails
            logger.debug(f"usaddress parsing failed for '{address}': {e}, using regex fallback")

            addr = address.upper()

            # Common abbreviations
            replacements = {
                r'\bWEST\b': 'W', r'\bEAST\b': 'E', r'\bNORTH\b': 'N', r'\bSOUTH\b': 'S',
                r'\bNORTHWEST\b': 'NW', r'\bNORTHEAST\b': 'NE',
                r'\bSOUTHWEST\b': 'SW', r'\bSOUTHEAST\b': 'SE',
                r'\bSTREET\b': 'ST', r'\bAVENUE\b': 'AVE', r'\bROAD\b': 'RD',
                r'\bDRIVE\b': 'DR', r'\bBOULEVARD\b': 'BLVD', r'\bLANE\b': 'LN',
                r'\bCOURT\b': 'CT', r'\bCIRCLE\b': 'CIR', r'\bPLACE\b': 'PL',
                r'\bAPARTMENT\b': 'APT', r'\bSUITE\b': 'STE', r'\bUNIT\b': 'UNIT',
            }

            for pattern, replacement in replacements.items():
                addr = re.sub(pattern, replacement, addr)

            # Remove punctuation except # for unit numbers
            addr = re.sub(r'[^\w\s#]', '', addr)

            # Normalize whitespace
            addr = ' '.join(addr.split())

            return addr

    def normalize_phone(self, phone: str) -> str:
        """Normalize phone to digits only"""
        if not phone:
            return ''

        # Extract only digits
        digits = re.sub(r'\D', '', phone)

        # Handle 10-digit US numbers
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+{digits}"

        return digits

    def normalize_person_name(self, name: str) -> str:
        """Normalize person name for comparison"""
        if not name:
            return ''

        # Remove titles
        name = re.sub(r'\b(MR|MRS|MS|DR|PROF)\.?\b', '', name.upper())

        # Remove extra whitespace
        name = ' '.join(name.split())

        return name

    def _trigram_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate trigram similarity (approximation of PostgreSQL pg_trgm)
        Simple implementation - can be replaced with actual pg_trgm query
        """
        if not str1 or not str2:
            return 0.0

        if str1 == str2:
            return 1.0

        # Generate trigrams
        def trigrams(s):
            s = f"  {s} "  # Pad with spaces
            return set(s[i:i+3] for i in range(len(s)-2))

        tri1 = trigrams(str1)
        tri2 = trigrams(str2)

        if not tri1 or not tri2:
            return 0.0

        # Jaccard similarity
        intersection = tri1 & tri2
        union = tri1 | tri2

        return len(intersection) / len(union) if union else 0.0
