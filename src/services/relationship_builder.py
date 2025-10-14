"""
RelationshipBuilder - Builds entity_relationships from domain objects

Creates relationships between entities and properties:
1. Entity OWNS Property (from permits, property appraiser data)
2. Entity CONTRACTED Property (from permits)
3. Entity MEMBER_OF Entity (from LLC officers)
4. Entity REGISTERED_WITH Entity (from LLC registered agent)
5. Property ADJACENT_TO Property (from GIS geometry - future)

Design principles:
- Confidence scores on all relationships
- Source attribution (which permit, which data source)
- Deduplication (don't create duplicate relationships)
- Bidirectional relationships stored once
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from ..database import (
    Entity,
    Property,
    Permit,
    EntityRelationship,
    LLCFormation
)

logger = logging.getLogger(__name__)


@dataclass
class RelationshipSource:
    """Provenance for a relationship"""
    source_type: str  # 'permit', 'property_appraiser', 'llc_formation'
    source_id: Optional[UUID]
    source_url: Optional[str]
    confidence: float


class RelationshipBuilder:
    """
    Builds entity_relationships from domain objects

    Automatically called after creating permits, entities, etc.
    """

    def __init__(self):
        pass

    async def build_relationships_from_permit(
        self,
        permit: Permit,
        db_session: AsyncSession
    ) -> List[EntityRelationship]:
        """
        Build relationships from a permit:
        1. Applicant OWNS Property (confidence based on permit type)
        2. Contractor CONTRACTED Property

        Args:
            permit: Permit object with property_id, applicant_entity_id, contractor_entity_id
            db_session: Database session

        Returns:
            List of created relationships
        """
        relationships = []

        # NOTE: Schema v2 change - entity_relationships is for entity->entity only
        # Property relationships are tracked via FKs (permit.property_id, permit.contractor_entity_id)
        # For portfolio tracking, use entity_market_properties table

        # Skip entity->property relationships (properties aren't entities)
        # The link already exists via permit.property_id and permit.contractor_entity_id

        logger.info(f"Permit {permit.permit_number}: property_id={permit.property_id}, contractor={permit.contractor_entity_id}, applicant={permit.applicant_entity_id}")
        logger.info(f"Property-entity relationships tracked via permit FKs (not entity_relationships table)")

        if relationships:
            logger.info(f"Created {len(relationships)} relationships from permit {permit.permit_number}")

        return relationships

    async def build_relationships_from_property_data(
        self,
        property: Property,
        db_session: AsyncSession
    ) -> List[EntityRelationship]:
        """
        Build ownership relationships from property enrichment data

        Checks property.factual_data for:
        - GIS owner name
        - Property Appraiser owner name

        Validates ownership with entity matching

        Args:
            property: Property object with factual_data
            db_session: Database session

        Returns:
            List of created relationships
        """
        relationships = []

        if not property.factual_data:
            return relationships

        # Extract owner names from enrichment data
        owners = []

        # From GIS data
        if 'gis' in property.factual_data:
            gis_owner = property.factual_data['gis'].get('owner')
            if gis_owner:
                owners.append(('gis', gis_owner, 0.75))

        # From Property Appraiser data (higher confidence)
        if 'property_appraiser' in property.factual_data:
            pa_owner = property.factual_data['property_appraiser'].get('owner_name')
            if pa_owner:
                owners.append(('property_appraiser', pa_owner, 0.90))

        # Try to match owner names to existing entities
        for source_type, owner_name, confidence in owners:
            entity = await self._find_entity_by_name(owner_name, db_session)
            if entity:
                relationship = await self._create_or_update_relationship(
                    from_entity_id=entity.id,
                    to_entity_id=property.id,
                    relationship_type='owns',
                    confidence=confidence,
                    source=RelationshipSource(
                        source_type=source_type,
                        source_id=None,
                        source_url=None,
                        confidence=confidence
                    ),
                    metadata={
                        'owner_name': owner_name,
                        'data_source': source_type
                    },
                    db_session=db_session
                )
                if relationship:
                    relationships.append(relationship)

        return relationships

    async def build_relationships_from_llc(
        self,
        entity: Entity,
        llc_formation: LLCFormation,
        db_session: AsyncSession
    ) -> List[EntityRelationship]:
        """
        Build relationships from LLC formation data:
        1. Officer MEMBER_OF LLC (from officers list)
        2. Registered Agent REGISTERED_WITH LLC

        Args:
            entity: The LLC entity
            llc_formation: LLCFormation record with officers data
            db_session: Database session

        Returns:
            List of created relationships
        """
        relationships = []

        # Parse officers from JSON (if available)
        logger.info(f"Building LLC relationships for {entity.name}, officers: {llc_formation.officers}")

        if llc_formation.officers:
            import json
            try:
                if isinstance(llc_formation.officers, str):
                    officers = json.loads(llc_formation.officers)
                elif isinstance(llc_formation.officers, list):
                    officers = llc_formation.officers
                else:
                    officers = []

                logger.info(f"Parsed {len(officers)} officers from LLC formation")

                # Create person entities for officers and link them
                for officer_data in officers:
                    if isinstance(officer_data, dict):
                        officer_name = officer_data.get('name') or officer_data.get('officerName')
                        if officer_name:
                            # Find or create officer entity
                            officer_entity = await self._find_or_create_person_entity(
                                officer_name,
                                officer_data,
                                db_session
                            )

                            if officer_entity:
                                # Create MEMBER_OF relationship
                                membership = await self._create_or_update_relationship(
                                    from_entity_id=officer_entity.id,
                                    to_entity_id=entity.id,
                                    relationship_type='member_of',
                                    confidence=0.95,  # High confidence from official records
                                    source=RelationshipSource(
                                        source_type='llc_formation',
                                        source_id=llc_formation.id,
                                        source_url=None,
                                        confidence=0.95
                                    ),
                                    metadata={
                                        'title': officer_data.get('title') or officer_data.get('officerTitle'),
                                        'document_number': llc_formation.document_number
                                    },
                                    db_session=db_session
                                )
                                if membership:
                                    relationships.append(membership)

            except Exception as e:
                logger.error(f"Failed to parse LLC officers: {e}", exc_info=True)

        # Registered agent relationship
        if llc_formation.registered_agent:
            # Try to find registered agent as entity
            agent_entity = await self._find_entity_by_name(
                llc_formation.registered_agent,
                db_session
            )
            if agent_entity:
                agent_rel = await self._create_or_update_relationship(
                    from_entity_id=entity.id,
                    to_entity_id=agent_entity.id,
                    relationship_type='registered_with',
                    confidence=0.90,
                    source=RelationshipSource(
                        source_type='llc_formation',
                        source_id=llc_formation.id,
                        source_url=None,
                        confidence=0.90
                    ),
                    metadata={
                        'agent_name': llc_formation.registered_agent,
                        'document_number': llc_formation.document_number
                    },
                    db_session=db_session
                )
                if agent_rel:
                    relationships.append(agent_rel)

        if relationships:
            logger.info(f"Created {len(relationships)} relationships from LLC {entity.canonical_name}")

        return relationships

    # ==================== HELPER METHODS ====================

    async def _create_or_update_relationship(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        relationship_type: str,
        confidence: float,
        source: RelationshipSource,
        metadata: Dict[str, Any],
        db_session: AsyncSession
    ) -> Optional[EntityRelationship]:
        """
        Create new relationship or update existing one

        Deduplicates: If relationship already exists, update confidence and metadata

        Schema v2: Uses source_entity_id and target_entity_id (not from/to)
        """
        # Check if relationship already exists
        result = await db_session.execute(
            select(EntityRelationship).where(
                EntityRelationship.source_entity_id == from_entity_id,
                EntityRelationship.target_entity_id == to_entity_id,
                EntityRelationship.relationship_type == relationship_type
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing relationship
            # Boost confidence if new source confirms it
            new_confidence = max(existing.confidence, confidence)

            # Add new source to metadata
            existing_metadata = existing.metadata or {}
            sources = existing_metadata.get('sources', [])
            sources.append({
                'source_type': source.source_type,
                'source_id': str(source.source_id) if source.source_id else None,
                'confidence': source.confidence,
                'added_at': datetime.utcnow().isoformat()
            })
            existing_metadata['sources'] = sources

            existing.confidence = new_confidence
            existing.metadata = existing_metadata
            existing.last_observed = datetime.utcnow()

            logger.debug(f"Updated relationship: {relationship_type} (confidence: {new_confidence:.2f})")
            return existing

        # Create new relationship
        # Store source information in metadata
        relationship_metadata = metadata.copy()
        relationship_metadata['sources'] = [{
            'source_type': source.source_type,
            'source_id': str(source.source_id) if source.source_id else None,
            'confidence': source.confidence,
            'added_at': datetime.utcnow().isoformat()
        }]

        # Schema v2 field names: source_entity_id, target_entity_id
        relationship = EntityRelationship(
            id=uuid4(),
            source_entity_id=from_entity_id,
            target_entity_id=to_entity_id,
            relationship_type=relationship_type,
            confidence_score=confidence,
            evidence_sources=[str(source.source_id)] if source.source_id else [],
            derived_from=source.source_type,
            supporting_markets=[],
            is_active=True,
            created_at=datetime.utcnow()
        )

        db_session.add(relationship)
        logger.debug(f"Created relationship: {relationship_type} (confidence: {confidence:.2f})")
        return relationship

    def _calculate_ownership_confidence(self, permit: Permit) -> float:
        """
        Calculate confidence that permit applicant owns the property

        Different permit types have different ownership likelihood:
        - Building permits: Usually owner (0.90)
        - Demolition: Very likely owner (0.95)
        - Sign/Fence: May be tenant (0.70)
        - Electrical/Plumbing: Could be contractor (0.60)
        """
        permit_type = (permit.permit_type or '').upper()

        # High confidence types
        if any(t in permit_type for t in ['DEMOLITION', 'NEW CONSTRUCTION', 'ADDITION']):
            return 0.95

        # Medium-high confidence
        if any(t in permit_type for t in ['BUILDING', 'RENOVATION', 'REMODEL']):
            return 0.85

        # Medium confidence
        if any(t in permit_type for t in ['SIGN', 'FENCE', 'POOL']):
            return 0.70

        # Lower confidence (could be contractor/tenant)
        if any(t in permit_type for t in ['ELECTRICAL', 'PLUMBING', 'HVAC', 'MECHANICAL']):
            return 0.60

        # Default medium confidence
        return 0.75

    async def _find_entity_by_name(
        self,
        name: str,
        db_session: AsyncSession
    ) -> Optional[Entity]:
        """Find entity by fuzzy name matching"""
        try:
            result = await db_session.execute(text("""
                SELECT id, canonical_name, entity_type
                FROM entities
                WHERE similarity(canonical_name, :name) > 0.80
                ORDER BY similarity(canonical_name, :name) DESC
                LIMIT 1
            """), {'name': name.strip().upper()})

            row = result.fetchone()
            if row:
                entity = await db_session.get(Entity, row.id)
                return entity
            return None

        except Exception as e:
            logger.error(f"Entity lookup failed for '{name}': {e}")
            return None

    async def _find_or_create_person_entity(
        self,
        name: str,
        officer_data: Dict[str, Any],
        db_session: AsyncSession
    ) -> Optional[Entity]:
        """Find or create a person entity for LLC officers"""
        # Try to find existing
        entity = await self._find_entity_by_name(name, db_session)
        if entity:
            return entity

        # Create new person entity (schema v2: no fact_based_attributes)
        entity = Entity(
            id=uuid4(),
            entity_type='person',
            name=name,
            canonical_name=name.strip().lower(),
            active_markets=[],
            primary_address=officer_data.get('address') if isinstance(officer_data, dict) else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db_session.add(entity)
        await db_session.flush()

        logger.info(f"Created person entity for LLC officer: {name}")
        return entity
