"""
SQLAlchemy ORM Models for Dominion Multi-Market Database V2

Architecture: Multi-Market Hybrid Bridge Model
- Global Layer: Entities and relationships that span markets
- Market Layer: Events and properties partitioned by market_id
- Linking Layer: Cross-market portfolio tracking

All partitioned tables include market_id in their composite primary key.
"""

from datetime import datetime, date
from typing import Optional, List
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean, Column, Float, Integer, String, Text, TIMESTAMP, Date,
    ForeignKey, CheckConstraint, Index, UniqueConstraint, PrimaryKeyConstraint, ARRAY,
    text, Numeric
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()


# ============================================================================
# GLOBAL LAYER: Cross-Market Tables
# ============================================================================

class Market(Base):
    """Central registry of all markets Dominion operates in"""
    __tablename__ = 'markets'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    market_code = Column(Text, unique=True, nullable=False, index=True)
    market_name = Column(Text, nullable=False)

    # Geographic identifiers
    state = Column(Text, nullable=False)
    county = Column(Text)
    city = Column(Text)
    metro_area = Column(Text)

    # Market metadata
    is_active = Column(Boolean, default=True, index=True)
    activation_date = Column(TIMESTAMP, default=datetime.utcnow)
    deactivation_date = Column(TIMESTAMP)

    # Configuration (JSONB)
    config = Column(JSONB, default={})

    # Stats
    total_properties = Column(Integer, default=0)
    total_entities = Column(Integer, default=0)
    last_scrape_at = Column(TIMESTAMP)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


class Entity(Base):
    """
    People, LLCs, Companies - GLOBAL across markets
    An entity exists once, tracks active_markets[] array
    """
    __tablename__ = 'entities'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Identity
    entity_type = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    canonical_name = Column(Text, index=True)

    # Definitive identifiers
    sunbiz_document_number = Column(Text, unique=True, index=True)
    tax_id = Column(Text)
    other_identifiers = Column(JSONB, default={})

    # Contact information
    primary_address = Column(Text)
    phone = Column(Text)
    email = Column(Text)
    website = Column(Text)

    # LLC/Corporation-specific data
    registered_agent = Column(Text)
    registered_agent_address = Column(Text)
    officers = Column(JSONB, default=[])
    formation_date = Column(Date)
    status = Column(Text)

    # Multi-market tracking
    active_markets = Column(ARRAY(PG_UUID(as_uuid=True)), default=[])
    first_seen_market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'))

    # Metadata
    verified = Column(Boolean, default=False)
    verification_source = Column(Text)
    confidence_score = Column(Float)

    # Enrichment timestamps
    sunbiz_enriched_at = Column(TIMESTAMP)
    last_seen_at = Column(TIMESTAMP, default=datetime.utcnow)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('person', 'llc', 'corporation', 'partnership', 'government', 'unknown')",
            name='ck_entity_type'
        ),
        CheckConstraint(
            'confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)',
            name='ck_confidence_score_range'
        ),
        Index('idx_entities_name_trgm', 'name', postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'}),
    )


class EntityRelationship(Base):
    """Relationships between entities (e.g., LLC owns property, person owns LLC)"""
    __tablename__ = 'entity_relationships'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Relationship
    source_entity_id = Column(PG_UUID(as_uuid=True), ForeignKey('entities.id'), nullable=False, index=True)
    target_entity_id = Column(PG_UUID(as_uuid=True), ForeignKey('entities.id'), nullable=False, index=True)
    relationship_type = Column(Text, nullable=False, index=True)

    # Context
    supporting_markets = Column(ARRAY(PG_UUID(as_uuid=True)), default=[])
    confidence_score = Column(Float)

    # Evidence
    evidence_sources = Column(ARRAY(Text))
    derived_from = Column(Text)

    # Temporal
    relationship_start_date = Column(Date)
    relationship_end_date = Column(Date)
    is_active = Column(Boolean, default=True)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('source_entity_id != target_entity_id', name='ck_no_self_reference'),
        CheckConstraint(
            'confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)',
            name='ck_relationship_confidence_range'
        ),
    )


class User(Base):
    """User accounts with multi-market subscriptions"""
    __tablename__ = 'users'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(Text, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)

    # User info
    full_name = Column(Text)
    company = Column(Text)
    user_type = Column(Text)

    # Subscriptions
    subscribed_markets = Column(ARRAY(PG_UUID(as_uuid=True)), default=[])
    subscription_tier = Column(Text, default='free')
    subscription_status = Column(Text, default='active')

    # Usage tracking
    analyses_run = Column(Integer, default=0)
    last_login_at = Column(TIMESTAMP)

    # Security
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# MARKET LAYER: Partitioned Tables (by market_id)
# ============================================================================

class RawFact(Base):
    """
    Immutable event log - ALL data starts here
    Partitioned by market_id for scalability
    """
    __tablename__ = 'raw_facts'

    id = Column(PG_UUID(as_uuid=True), default=uuid4)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), nullable=False, index=True)

    # Source
    fact_type = Column(Text, nullable=False, index=True)
    source_url = Column(Text, nullable=False)
    scraped_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, index=True)

    # Content
    raw_content = Column(JSONB, nullable=False)
    content_hash = Column(Text, nullable=False, index=True)

    # Processing
    parser_version = Column(Text, nullable=False, default='v1')
    processed_at = Column(TIMESTAMP)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint('id', 'market_id'),
        {'schema': None},  # Will be set by partition
    )


class Property(Base):
    """Properties - partitioned by market"""
    __tablename__ = 'properties'

    id = Column(PG_UUID(as_uuid=True), default=uuid4)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), nullable=False, index=True)

    # Identifiers
    parcel_id = Column(Text, nullable=False, index=True)
    property_address = Column(Text)

    # Location
    # coordinates = Column(Geometry('POINT', srid=4326))  # Removed - requires PostGIS
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))

    # Property details
    property_type = Column(Text, index=True)
    year_built = Column(Integer)
    square_feet = Column(Integer)
    lot_size_acres = Column(Numeric(10, 4))
    bedrooms = Column(Integer)
    bathrooms = Column(Numeric(3, 1))

    # Ownership
    owner_entity_id = Column(PG_UUID(as_uuid=True), ForeignKey('entities.id'), index=True)
    owner_name = Column(Text)
    mailing_address = Column(Text)

    # Valuation
    assessed_value = Column(Numeric(12, 2))
    market_value = Column(Numeric(12, 2))
    last_sale_price = Column(Numeric(12, 2))
    last_sale_date = Column(Date)

    # Zoning
    zoning_code = Column(Text)
    zoning_description = Column(Text)

    # Enrichment tracking
    last_enriched_at = Column(TIMESTAMP)
    enrichment_source = Column(Text)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint('id', 'market_id'),
        UniqueConstraint('parcel_id', 'market_id', name='uq_property_parcel_market'),
        {'schema': None},
    )


class Permit(Base):
    """Building permits - partitioned by market"""
    __tablename__ = 'permits'

    id = Column(PG_UUID(as_uuid=True), default=uuid4)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), nullable=False, index=True)

    # Identifiers
    permit_number = Column(Text, nullable=False, index=True)
    permit_type = Column(Text)
    jurisdiction = Column(Text)

    # Project details
    project_name = Column(Text)
    project_description = Column(Text)
    work_type = Column(Text)

    # Location (FK to properties in same partition)
    property_id = Column(PG_UUID(as_uuid=True), index=True)
    site_address = Column(Text)
    parcel_id = Column(Text)

    # Parties (FKs to global entities)
    applicant_entity_id = Column(PG_UUID(as_uuid=True), ForeignKey('entities.id'))
    contractor_entity_id = Column(PG_UUID(as_uuid=True), ForeignKey('entities.id'), index=True)
    owner_entity_id = Column(PG_UUID(as_uuid=True), ForeignKey('entities.id'))

    # Valuation
    project_value = Column(Numeric(12, 2))
    permit_fee = Column(Numeric(10, 2))

    # Status
    status = Column(Text, index=True)
    application_date = Column(Date, index=True)
    issued_date = Column(Date)
    final_inspection_date = Column(Date)

    # Source
    source_url = Column(Text)
    raw_fact_id = Column(PG_UUID(as_uuid=True))

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint('id', 'market_id'),
        UniqueConstraint('permit_number', 'market_id', name='uq_permit_number_market'),
        {'schema': None},
    )


class LLCFormation(Base):
    """LLC formations from daily Sunbiz scraper - NOT partitioned (statewide)"""
    __tablename__ = 'llc_formations'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Sunbiz identifiers
    document_number = Column(Text, unique=True, nullable=False, index=True)
    filing_type = Column(Text)

    # Entity details
    entity_id = Column(PG_UUID(as_uuid=True), ForeignKey('entities.id'), index=True)
    name = Column(Text, nullable=False)
    status = Column(Text)

    # Dates
    filing_date = Column(Date, index=True)
    effective_date = Column(Date)

    # Registration
    registered_agent = Column(Text)
    registered_agent_address = Column(Text)
    principal_address = Column(Text)
    mailing_address = Column(Text)

    # Officers/Members
    officers = Column(JSONB, default=[])

    # Source
    raw_fact_id = Column(PG_UUID(as_uuid=True))
    scraped_at = Column(TIMESTAMP)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)


class CrimeReport(Base):
    """Crime incidents - partitioned by market"""
    __tablename__ = 'crime_reports'

    id = Column(PG_UUID(as_uuid=True), default=uuid4)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), nullable=False, index=True)

    # Incident details
    case_number = Column(Text)
    incident_type = Column(Text)
    incident_description = Column(Text)

    # Location
    incident_address = Column(Text)
    coordinates = Column(Geometry('POINT', srid=4326))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))

    # Temporal
    incident_date = Column(TIMESTAMP, index=True)
    reported_date = Column(TIMESTAMP)

    # Source
    source_url = Column(Text)
    raw_fact_id = Column(PG_UUID(as_uuid=True))

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint('id', 'market_id'),
        {'schema': None},
    )


class CouncilMeeting(Base):
    """Council meetings - partitioned by market"""
    __tablename__ = 'council_meetings'

    id = Column(PG_UUID(as_uuid=True), default=uuid4)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), nullable=False, index=True)

    # Meeting details
    meeting_date = Column(Date, index=True)
    meeting_type = Column(Text)
    agenda_items = Column(JSONB, default=[])

    # Content
    minutes_text = Column(Text)
    summary = Column(Text)

    # Extracted entities and topics
    mentioned_entities = Column(ARRAY(PG_UUID(as_uuid=True)))
    topics = Column(ARRAY(Text))

    # Source
    source_url = Column(Text)
    raw_fact_id = Column(PG_UUID(as_uuid=True))

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint('id', 'market_id'),
        {'schema': None},
    )


class NewsArticle(Base):
    """News articles - partitioned by market"""
    __tablename__ = 'news_articles'

    id = Column(PG_UUID(as_uuid=True), default=uuid4)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), nullable=False, index=True)

    # Article details
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    published_date = Column(TIMESTAMP, index=True)
    source = Column(Text)

    # Content
    article_text = Column(Text)
    summary = Column(Text)

    # Extracted entities and topics
    mentioned_entities = Column(ARRAY(PG_UUID(as_uuid=True)))
    topics = Column(ARRAY(Text))
    relevance_score = Column(Float, index=True)

    # Source
    raw_fact_id = Column(PG_UUID(as_uuid=True))

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint('id', 'market_id'),
        UniqueConstraint('url', 'market_id', name='uq_news_url_market'),
        {'schema': None},
    )


# ============================================================================
# BULK DATA LAYER
# ============================================================================

class BulkDataSnapshot(Base):
    """Version tracking for bulk data imports"""
    __tablename__ = 'bulk_data_snapshots'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), index=True)

    # Source
    data_source = Column(Text, nullable=False, index=True)
    source_url = Column(Text)

    # File info
    file_name = Column(Text)
    file_size_bytes = Column(Integer)
    file_hash = Column(Text, nullable=False)

    # Processing
    status = Column(Text, default='pending')
    records_total = Column(Integer)
    records_inserted = Column(Integer)
    records_updated = Column(Integer)
    records_skipped = Column(Integer)

    # Timing
    download_started_at = Column(TIMESTAMP)
    download_completed_at = Column(TIMESTAMP)
    processing_started_at = Column(TIMESTAMP)
    processing_completed_at = Column(TIMESTAMP)

    # Metadata
    snapshot_date = Column(Date)
    is_current = Column(Boolean, default=True, index=True)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)


class BulkPropertyRecord(Base):
    """CAMA property records enriched with qPublic - partitioned by market"""
    __tablename__ = 'bulk_property_records'

    id = Column(PG_UUID(as_uuid=True), default=uuid4)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), nullable=False, index=True)
    snapshot_id = Column(PG_UUID(as_uuid=True), ForeignKey('bulk_data_snapshots.id'), index=True)

    # Identifiers
    parcel_id = Column(Text, nullable=False, index=True)
    property_id = Column(PG_UUID(as_uuid=True))

    # CAMA fields
    owner_name = Column(Text)
    mailing_address = Column(Text)
    site_address = Column(Text)
    property_type = Column(Text)
    year_built = Column(Integer)
    square_feet = Column(Integer)
    lot_size_acres = Column(Numeric(10, 4))
    assessed_value = Column(Numeric(12, 2))
    market_value = Column(Numeric(12, 2))
    taxable_value = Column(Numeric(12, 2))
    exemptions = Column(ARRAY(Text))

    # qPublic enrichment fields
    coordinates = Column(Geometry('POINT', srid=4326))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    sales_history = Column(JSONB, default=[])
    permit_history = Column(JSONB, default=[])
    trim_notice = Column(JSONB)

    # Additional qPublic fields (from migration 007)
    bedrooms = Column(Integer)
    bathrooms = Column(Numeric(4, 1))
    last_sale_date = Column(Date)
    last_sale_price = Column(Numeric(12, 2))
    use_code = Column(Text)
    city = Column(Text)
    raw_data = Column(JSONB)  # Complete qPublic response
    building_details = Column(JSONB)  # Building characteristics

    # Enrichment tracking
    qpublic_enriched_at = Column(TIMESTAMP)
    qpublic_enrichment_status = Column(Text)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        PrimaryKeyConstraint('id', 'market_id'),
        UniqueConstraint('parcel_id', 'market_id', 'snapshot_id', name='uq_bulk_property_parcel_market_snapshot'),
        {'schema': None},
    )


class BulkLLCRecord(Base):
    """Sunbiz LLC records from monthly SFTP dump - NOT partitioned (statewide)"""
    __tablename__ = 'bulk_llc_records'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id = Column(PG_UUID(as_uuid=True), ForeignKey('bulk_data_snapshots.id'), index=True)

    # Sunbiz identifiers
    document_number = Column(Text, nullable=False, index=True)
    filing_type = Column(Text)

    # Entity info
    entity_id = Column(PG_UUID(as_uuid=True), ForeignKey('entities.id'), index=True)
    name = Column(Text, nullable=False)
    status = Column(Text)

    # Dates
    filing_date = Column(Date)
    last_event_date = Column(Date)

    # Address
    principal_address = Column(Text)
    mailing_address = Column(Text)

    # Officers
    registered_agent = Column(Text)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('document_number', 'snapshot_id', name='uq_bulk_llc_document_snapshot'),
    )


# ============================================================================
# LINKING LAYER: Cross-Market Relationships
# ============================================================================

class EntityMarketProperty(Base):
    """Portfolio tracking for entities across markets"""
    __tablename__ = 'entity_market_properties'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_id = Column(PG_UUID(as_uuid=True), ForeignKey('entities.id'), nullable=False, index=True)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), nullable=False, index=True)

    # Portfolio stats in this market
    total_properties = Column(Integer, default=0)
    total_value = Column(Numeric(15, 2), default=0)
    property_ids = Column(ARRAY(PG_UUID(as_uuid=True)), default=[])

    # Activity tracking
    first_activity_date = Column(Date)
    last_activity_date = Column(Date)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('entity_id', 'market_id', name='uq_entity_market'),
    )


# ============================================================================
# AI/ML LAYER: Placeholder Tables (MVP Week 3+)
# ============================================================================

class AIInference(Base):
    """AI-generated insights with confidence scores and provenance"""
    __tablename__ = 'ai_inferences'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    market_id = Column(PG_UUID(as_uuid=True), ForeignKey('markets.id'), index=True)

    # Inference details
    inference_type = Column(Text, nullable=False, index=True)
    model_version = Column(Text, nullable=False)
    confidence_score = Column(Float, index=True)

    # Content
    inference_content = Column(JSONB, nullable=False)
    reasoning = Column(Text)
    known_uncertainties = Column(ARRAY(Text))

    # Provenance
    source_fact_ids = Column(ARRAY(PG_UUID(as_uuid=True)))
    source_urls = Column(ARRAY(Text))

    # Validation
    validated = Column(Boolean, default=False)
    validation_outcome = Column(Text)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    expires_at = Column(TIMESTAMP)

    __table_args__ = (
        CheckConstraint(
            'confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)',
            name='ck_ai_confidence_range'
        ),
    )


class EmbeddingCache(Base):
    """Document vectors for semantic search"""
    __tablename__ = 'embeddings_cache'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    content_hash = Column(Text, unique=True, nullable=False, index=True)
    embedding = Column(Vector(1536))  # OpenAI ada-002 or similar
    model_version = Column(Text, nullable=False)
    content_preview = Column(Text)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)


class LLMCache(Base):
    """LLM response caching to reduce API costs"""
    __tablename__ = 'llm_cache'

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    prompt_hash = Column(Text, unique=True, nullable=False, index=True)
    prompt_preview = Column(Text)
    response_content = Column(Text, nullable=False)
    model_version = Column(Text, nullable=False)
    temperature = Column(Float)
    token_count = Column(Integer)
    cost_cents = Column(Integer)
    hit_count = Column(Integer, default=1)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    last_used_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
