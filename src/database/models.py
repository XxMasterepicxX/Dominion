"""
SQLAlchemy ORM models for Dominion database

Architecture:
- RawFact: Immutable provenance layer (ALL data starts here)
- Domain tables: Queryable entities (Property, Entity, Permit, etc.)
- Relationships: Graph connections with confidence scores
- AIInference: AI-generated insights with provenance

All models link back to raw_facts via raw_fact_id for full provenance tracking.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean, Column, Float, Integer, String, Text, TIMESTAMP,
    ForeignKey, CheckConstraint, Index, UniqueConstraint, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ============================================================================
# CORE PROVENANCE LAYER
# ============================================================================

class ContentSnapshot(Base):
    """Change detection using content hashing"""
    __tablename__ = 'content_snapshots'

    id = Column(UUID, primary_key=True, default=uuid4)
    content_hash = Column(Text, nullable=False, index=True)
    url = Column(Text, nullable=False, index=True)
    timestamp = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, index=True)
    size = Column(Integer, nullable=False)
    snapshot_metadata = Column('metadata', JSONB, default={})  # Renamed to avoid SQLAlchemy reserved word
    content_type = Column(Text)
    response_code = Column(Integer)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_content_snapshots_url_timestamp', 'url', 'timestamp'),
    )


class RawFact(Base):
    """
    Immutable facts with full provenance
    EVERY piece of data starts here - never modified, only added
    """
    __tablename__ = 'raw_facts_partitioned'  # Using partitioned table

    id = Column(UUID, primary_key=True, default=uuid4)
    fact_type = Column(Text, nullable=False, index=True)
    # Types: 'city_permit', 'county_permit', 'property_record', 'llc_formation',
    #        'news_article', 'council_meeting', 'crime_report', 'census_demographics',
    #        'gis_layer'

    source_url = Column(Text, nullable=False)
    scraped_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, index=True)
    parser_version = Column(Text, nullable=False)
    raw_content = Column(JSONB, nullable=False)
    content_hash = Column(Text, nullable=False, unique=True, index=True)
    processed_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships to domain tables (using primaryjoin since no FK constraints on partitioned tables)
    permits = relationship("Permit", primaryjoin="RawFact.id==foreign(Permit.raw_fact_id)", back_populates="raw_fact")
    properties = relationship("Property", primaryjoin="RawFact.id==foreign(Property.raw_fact_id)", back_populates="raw_fact")
    llc_formations = relationship("LLCFormation", primaryjoin="RawFact.id==foreign(LLCFormation.raw_fact_id)", back_populates="raw_fact")
    news_articles = relationship("NewsArticle", primaryjoin="RawFact.id==foreign(NewsArticle.raw_fact_id)", back_populates="raw_fact")
    council_meetings = relationship("CouncilMeeting", primaryjoin="RawFact.id==foreign(CouncilMeeting.raw_fact_id)", back_populates="raw_fact")
    crime_reports = relationship("CrimeReport", primaryjoin="RawFact.id==foreign(CrimeReport.raw_fact_id)", back_populates="raw_fact")


class StructuredFact(Base):
    """
    Extracted structured data from raw facts
    Confidence-scored extraction, may need validation
    """
    __tablename__ = 'structured_facts_partitioned'  # Using partitioned table

    id = Column(UUID, primary_key=True, default=uuid4)
    # Note: raw_fact_id references partitioned table - no FK constraint due to partitioning
    raw_fact_id = Column(UUID, nullable=False, index=True)
    entity_type = Column(Text, nullable=False, index=True)
    # Types: 'property', 'person', 'company', 'permit', 'sale', 'llc', 'event'

    structured_data = Column(JSONB, nullable=False)
    extraction_confidence = Column(Float, nullable=False)
    validation_status = Column(
        Text,
        default='unvalidated',
        server_default='unvalidated'
    )
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            'extraction_confidence >= 0 AND extraction_confidence <= 1',
            name='ck_extraction_confidence_range'
        ),
        CheckConstraint(
            "validation_status IN ('unvalidated', 'validated', 'flagged', 'rejected')",
            name='ck_validation_status_values'
        ),
    )


class FactEvent(Base):
    """Event sourcing for all data changes"""
    __tablename__ = 'fact_events'

    id = Column(UUID, primary_key=True, default=uuid4)
    event_type = Column(Text, nullable=False)
    # Note: fact_id references partitioned table - no FK constraint due to partitioning
    fact_id = Column(UUID)
    event_data = Column(JSONB, nullable=False)
    correlation_id = Column(UUID)  # Links related operations
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('fact_added', 'fact_updated', 'fact_invalidated')",
            name='ck_event_type_values'
        ),
    )


# ============================================================================
# DOMAIN ENTITIES (Queryable Layer)
# ============================================================================

class Property(Base):
    """
    Properties - core entity for real estate intelligence
    Links to: Permits, Sales, Owners, Crime, Zoning
    """
    __tablename__ = 'properties'

    id = Column(UUID, primary_key=True, default=uuid4)
    # Note: raw_fact_id references partitioned table - no FK constraint due to partitioning
    raw_fact_id = Column(UUID, index=True)

    # Core identifiers
    address = Column(Text, nullable=False)
    parcel_id = Column(Text, unique=True, index=True)
    coordinates = Column(Geometry('POINT', srid=4326))  # Index created via GIST in __table_args__

    # Data layers (JSONB for flexibility)
    factual_data = Column(JSONB, default={})
    # Contains: land_value, building_value, year_built, sqft, beds, baths, etc.

    inferred_data = Column(JSONB, default={})
    # Contains: market_value_estimate, risk_score, assemblage_potential, etc.

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    raw_fact = relationship("RawFact", primaryjoin="foreign(Property.raw_fact_id)==RawFact.id", back_populates="properties")
    permits = relationship("Permit", primaryjoin="Property.id==foreign(Permit.property_id)", back_populates="property")
    sales = relationship("PropertySale", primaryjoin="Property.id==foreign(PropertySale.property_id)", back_populates="property")
    crime_reports = relationship("CrimeReport", primaryjoin="Property.id==foreign(CrimeReport.property_id)", back_populates="property")


class Entity(Base):
    """
    Entities - people, companies, organizations
    Resolved across data sources with confidence scoring
    """
    __tablename__ = 'entities'

    id = Column(UUID, primary_key=True, default=uuid4)
    entity_type = Column(Text, nullable=False, index=True)
    # Types: 'person', 'company', 'llc', 'trust', 'government', 'organization'

    canonical_name = Column(Text, nullable=False, index=True)
    aliases = Column(ARRAY(Text), default=[])

    fact_based_attributes = Column(JSONB, default={})
    # Contains: registered_agent, tax_id, addresses, phone, email, filing_date, etc.

    inferred_attributes = Column(JSONB, default={})
    # Contains: investor_type, activity_level, network_centrality, risk_flags, etc.

    resolution_confidence = Column(Float)  # Confidence this is a unique entity
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owned_properties = relationship(
        "PropertySale",
        foreign_keys="PropertySale.buyer_entity_id",
        back_populates="buyer"
    )
    llc_formations = relationship("LLCFormation", primaryjoin="Entity.id==foreign(LLCFormation.entity_id)", back_populates="entity")
    permits_as_applicant = relationship(
        "Permit",
        foreign_keys="Permit.applicant_entity_id",
        back_populates="applicant"
    )
    permits_as_contractor = relationship(
        "Permit",
        foreign_keys="Permit.contractor_entity_id",
        back_populates="contractor"
    )

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('person', 'company', 'llc', 'trust', 'government', 'organization')",
            name='ck_entity_type_values'
        ),
    )


class EntityRelationship(Base):
    """
    Relationships between entities with confidence scores
    The graph layer - powers assemblage detection, network analysis
    """
    __tablename__ = 'entity_relationships'

    id = Column(UUID, primary_key=True, default=uuid4)
    from_entity_id = Column(UUID, ForeignKey('entities.id'), nullable=False, index=True)
    to_entity_id = Column(UUID, ForeignKey('entities.id'), nullable=False, index=True)

    relationship_type = Column(Text, nullable=False, index=True)
    # Types: 'owns', 'developed', 'hired_contractor', 'partnered', 'officer_of',
    #        'registered_agent_for', 'potentially_affiliated'

    confidence = Column(Float, nullable=False)
    supporting_fact_ids = Column(ARRAY(UUID), default=[])
    relationship_metadata = Column('metadata', JSONB, default={})  # Renamed to avoid SQLAlchemy reserved word

    first_observed = Column(TIMESTAMP, index=True)
    last_observed = Column(TIMESTAMP)
    is_active = Column(Boolean, default=True, index=True)

    # Validation tracking
    validation_status = Column(
        Text,
        default='auto_accepted',
        server_default='auto_accepted'
    )
    validated_by = Column(UUID, ForeignKey('users.id'))
    validated_at = Column(TIMESTAMP)

    # Reversibility
    superseded_by = Column(UUID, ForeignKey('entity_relationships.id'))
    supersedes = Column(UUID, ForeignKey('entity_relationships.id'))

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            'confidence >= 0 AND confidence <= 1',
            name='ck_relationship_confidence_range'
        ),
        CheckConstraint(
            "validation_status IN ('auto_accepted', 'under_review', 'human_validated', 'rejected')",
            name='ck_relationship_validation_status'
        ),
        Index('idx_entity_rel_from_to', 'from_entity_id', 'to_entity_id'),
        UniqueConstraint('from_entity_id', 'to_entity_id', 'relationship_type', name='uq_entity_relationship'),
    )


# ============================================================================
# DOMAIN TABLES (Specific Fact Types)
# ============================================================================

class Permit(Base):
    """Building permits - leading indicator of development"""
    __tablename__ = 'permits'

    id = Column(UUID, primary_key=True, default=uuid4)
    # Note: raw_fact_id references partitioned table - no FK constraint due to partitioning
    raw_fact_id = Column(UUID, index=True)

    permit_number = Column(Text, nullable=False, index=True)
    jurisdiction = Column(Text, nullable=False, index=True)  # e.g., 'Gainesville', 'Alachua County'
    permit_type = Column(Text, nullable=False, index=True)
    subtype = Column(Text)
    status = Column(Text, index=True)

    __table_args__ = (
        Index('ix_permits_number_jurisdiction', 'permit_number', 'jurisdiction', unique=True),
    )

    # Linkages
    property_id = Column(UUID, ForeignKey('properties.id'), index=True)
    applicant_entity_id = Column(UUID, ForeignKey('entities.id'), index=True)
    contractor_entity_id = Column(UUID, ForeignKey('entities.id'), index=True)

    # Details
    application_date = Column(TIMESTAMP)
    issue_date = Column(TIMESTAMP, index=True)
    expiration_date = Column(TIMESTAMP)
    close_date = Column(TIMESTAMP)
    valuation = Column(Float)
    description = Column(Text)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    raw_fact = relationship("RawFact", primaryjoin="foreign(Permit.raw_fact_id)==RawFact.id", back_populates="permits")
    property = relationship("Property", primaryjoin="foreign(Permit.property_id)==Property.id", back_populates="permits")
    applicant = relationship("Entity", foreign_keys=[applicant_entity_id], primaryjoin="foreign(Permit.applicant_entity_id)==Entity.id", back_populates="permits_as_applicant")
    contractor = relationship("Entity", foreign_keys=[contractor_entity_id], primaryjoin="foreign(Permit.contractor_entity_id)==Entity.id", back_populates="permits_as_contractor")


class PropertySale(Base):
    """Property sales transactions"""
    __tablename__ = 'property_sales'

    id = Column(UUID, primary_key=True, default=uuid4)
    property_id = Column(UUID, ForeignKey('properties.id'), nullable=False, index=True)
    # Note: raw_fact_id references partitioned table - no FK constraint due to partitioning
    raw_fact_id = Column(UUID, index=True)

    sale_date = Column(TIMESTAMP, nullable=False, index=True)
    sale_price = Column(Float, nullable=False)

    buyer_entity_id = Column(UUID, ForeignKey('entities.id'), index=True)
    seller_entity_id = Column(UUID, ForeignKey('entities.id'), index=True)

    deed_book = Column(Text)
    deed_page = Column(Text)
    instrument_number = Column(Text)

    sale_type = Column(Text)  # 'arms_length', 'foreclosure', 'quitclaim', etc.
    financing = Column(JSONB)  # Loan amount, lender, etc.

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", primaryjoin="foreign(PropertySale.property_id)==Property.id", back_populates="sales")
    buyer = relationship("Entity", foreign_keys=[buyer_entity_id], primaryjoin="foreign(PropertySale.buyer_entity_id)==Entity.id", back_populates="owned_properties")


class LLCFormation(Base):
    """LLC/Corporation formations from Sunbiz"""
    __tablename__ = 'llc_formations'

    id = Column(UUID, primary_key=True, default=uuid4)
    entity_id = Column(UUID, ForeignKey('entities.id'), nullable=False, index=True)
    # Note: raw_fact_id references partitioned table - no FK constraint due to partitioning
    raw_fact_id = Column(UUID, index=True)

    document_number = Column(Text, unique=True, nullable=False, index=True)
    filing_date = Column(TIMESTAMP, nullable=False, index=True)

    registered_agent = Column(Text, index=True)
    principal_address = Column(Text)

    is_property_related = Column(Boolean, default=False, index=True)
    # Detected from name keywords: "properties", "development", "realty", etc.

    status = Column(Text)  # 'active', 'inactive', 'dissolved'
    officers = Column(JSONB)  # Parsed officer data

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    entity = relationship("Entity", primaryjoin="foreign(LLCFormation.entity_id)==Entity.id", back_populates="llc_formations")
    raw_fact = relationship("RawFact", primaryjoin="foreign(LLCFormation.raw_fact_id)==RawFact.id", back_populates="llc_formations")


class NewsArticle(Base):
    """News articles - early signals"""
    __tablename__ = 'news_articles'

    id = Column(UUID, primary_key=True, default=uuid4)
    # Note: raw_fact_id references partitioned table - no FK constraint due to partitioning
    raw_fact_id = Column(UUID, nullable=False, index=True)

    title = Column(Text, nullable=False)
    published_date = Column(TIMESTAMP, nullable=False, index=True)
    source_publication = Column(Text, nullable=False, index=True)
    author = Column(Text)

    content = Column(Text)
    summary = Column(Text)
    url = Column(Text, unique=True, nullable=False)

    # Extracted entities (via LLM)
    mentioned_entities = Column(ARRAY(UUID))  # Entity IDs
    mentioned_properties = Column(ARRAY(UUID))  # Property IDs

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    raw_fact = relationship("RawFact", primaryjoin="foreign(NewsArticle.raw_fact_id)==RawFact.id", back_populates="news_articles")


class CouncilMeeting(Base):
    """City council meetings - policy changes"""
    __tablename__ = 'council_meetings'

    id = Column(UUID, primary_key=True, default=uuid4)
    # Note: raw_fact_id references partitioned table - no FK constraint due to partitioning
    raw_fact_id = Column(UUID, nullable=False, index=True)

    meeting_date = Column(TIMESTAMP, nullable=False, index=True)
    meeting_type = Column(Text, nullable=False)

    agenda_url = Column(Text)
    minutes_url = Column(Text)
    video_url = Column(Text)

    agenda_items = Column(JSONB)  # Structured agenda data
    extracted_text = Column(Text)  # Full PDF extraction

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    raw_fact = relationship("RawFact", primaryjoin="foreign(CouncilMeeting.raw_fact_id)==RawFact.id", back_populates="council_meetings")


class CrimeReport(Base):
    """Crime reports - risk assessment"""
    __tablename__ = 'crime_reports'

    id = Column(UUID, primary_key=True, default=uuid4)
    # Note: raw_fact_id references partitioned table - no FK constraint due to partitioning
    raw_fact_id = Column(UUID, nullable=False, index=True)
    property_id = Column(UUID, ForeignKey('properties.id'), index=True)

    incident_number = Column(Text, unique=True, nullable=False, index=True)
    offense_type = Column(Text, nullable=False, index=True)
    offense_date = Column(TIMESTAMP, nullable=False, index=True)

    address = Column(Text)
    location_geometry = Column(Geometry('POINT', srid=4326), index=True)

    disposition = Column(Text)
    details = Column(JSONB)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    raw_fact = relationship("RawFact", primaryjoin="foreign(CrimeReport.raw_fact_id)==RawFact.id", back_populates="crime_reports")
    property = relationship("Property", primaryjoin="foreign(CrimeReport.property_id)==Property.id", back_populates="crime_reports")

    __table_args__ = (
        Index('idx_crime_location', 'location_geometry', postgresql_using='gist'),
    )


# ============================================================================
# AI-DERIVED INSIGHTS
# ============================================================================

class AIInference(Base):
    """
    AI-generated insights with provenance and confidence
    Examples: assemblage_detected, market_analysis, relationship_prediction
    """
    __tablename__ = 'ai_inferences'

    id = Column(UUID, primary_key=True, default=uuid4)

    inference_type = Column(Text, nullable=False, index=True)
    # Types: 'assemblage_detected', 'relationship_prediction', 'market_analysis',
    #        'risk_assessment', 'property_valuation', 'owner_motivation'

    model_version = Column(Text, nullable=False)
    model_temperature = Column(Float)
    prompt_hash = Column(Text)

    # Confidence and thresholds
    confidence_score = Column(Float, nullable=False, index=True)
    threshold_met = Column(Boolean, nullable=False)

    # Content and reasoning
    inference_content = Column(JSONB, nullable=False)
    reasoning = Column(Text)
    known_uncertainties = Column(ARRAY(Text))

    # Provenance tracking
    source_fact_ids = Column(ARRAY(UUID), nullable=False)
    expires_at = Column(TIMESTAMP, index=True)

    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint(
            'confidence_score >= 0 AND confidence_score <= 1',
            name='ck_inference_confidence_range'
        ),
        Index('idx_ai_inference_type_confidence', 'inference_type', 'confidence_score'),
    )


class InferenceRelationship(Base):
    """Links between inferences (e.g., assemblage → multiple property valuations)"""
    __tablename__ = 'inference_relationships'

    id = Column(UUID, primary_key=True, default=uuid4)
    parent_inference_id = Column(UUID, ForeignKey('ai_inferences.id'), nullable=False, index=True)
    child_inference_id = Column(UUID, ForeignKey('ai_inferences.id'), nullable=False, index=True)
    relationship_type = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)


class InferenceOutcome(Base):
    """Track actual outcomes vs predictions"""
    __tablename__ = 'inference_outcomes'

    id = Column(UUID, primary_key=True, default=uuid4)
    inference_id = Column(UUID, ForeignKey('ai_inferences.id'), nullable=False, index=True)

    predicted_outcome = Column(JSONB, nullable=False)
    actual_outcome = Column(JSONB)
    outcome_date = Column(TIMESTAMP)

    was_correct = Column(Boolean)
    error_analysis = Column(JSONB)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)


# ============================================================================
# CACHING & OPTIMIZATION
# ============================================================================

class LLMCache(Base):
    """Cache LLM responses for cost optimization"""
    __tablename__ = 'llm_cache'

    id = Column(UUID, primary_key=True, default=uuid4)

    # Complete cache key
    model_id = Column(Text, nullable=False)
    model_version = Column(Text, nullable=False)
    prompt_template_version = Column(Text, nullable=False)
    temperature = Column(Float, nullable=False)
    top_p = Column(Float, nullable=False)
    retrieval_recipe_hash = Column(Text, nullable=False)

    # Response
    response = Column(JSONB, nullable=False)
    cost_cents = Column(Integer)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    expires_at = Column(TIMESTAMP, index=True)
    last_accessed_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            'model_id', 'model_version', 'prompt_template_version',
            'temperature', 'top_p', 'retrieval_recipe_hash',
            name='uq_llm_cache_key'
        ),
        Index('idx_llm_cache_expires', 'expires_at'),
    )


# ============================================================================
# OPERATIONAL TABLES
# ============================================================================

class ScraperRun(Base):
    """Track scraper executions"""
    __tablename__ = 'scraper_runs'

    id = Column(UUID, primary_key=True, default=uuid4)
    scraper_name = Column(Text, nullable=False, index=True)
    started_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, index=True)
    completed_at = Column(TIMESTAMP)

    status = Column(Text, nullable=False)  # 'running', 'completed', 'failed'
    records_scraped = Column(Integer, default=0)
    errors_encountered = Column(Integer, default=0)

    error_log = Column(JSONB)
    run_metadata = Column('metadata', JSONB)  # Renamed to avoid SQLAlchemy reserved word

    __table_args__ = (
        Index('idx_scraper_runs_name_date', 'scraper_name', 'started_at'),
    )


class DataQualityCheck(Base):
    """Data quality validation results"""
    __tablename__ = 'data_quality_checks'

    id = Column(UUID, primary_key=True, default=uuid4)
    check_name = Column(Text, nullable=False, index=True)
    table_name = Column(Text, nullable=False, index=True)
    executed_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, index=True)

    passed = Column(Boolean, nullable=False, index=True)
    issues_found = Column(Integer, default=0)
    issue_details = Column(JSONB)

    threshold = Column(Float)
    actual_value = Column(Float)


class IntelligenceAlert(Base):
    """User-facing alerts for high-confidence insights"""
    __tablename__ = 'intelligence_alerts'

    id = Column(UUID, primary_key=True, default=uuid4)

    alert_type = Column(Text, nullable=False, index=True)
    # Types: 'assemblage_detected', 'new_development', 'ownership_change',
    #        'zoning_change', 'market_shift'

    priority = Column(Text, nullable=False, index=True)  # 'low', 'medium', 'high', 'critical'
    title = Column(Text, nullable=False)
    description = Column(Text)

    related_properties = Column(ARRAY(UUID))
    related_entities = Column(ARRAY(UUID))
    inference_id = Column(UUID, ForeignKey('ai_inferences.id'))

    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(TIMESTAMP)
    resolved_by = Column(UUID, ForeignKey('users.id'))

    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_intelligence_alerts_unresolved', 'resolved'),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name='ck_alert_priority_values'
        ),
    )


class User(Base):
    """User accounts"""
    __tablename__ = 'users'

    id = Column(UUID, primary_key=True, default=uuid4)
    email = Column(Text, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)

    full_name = Column(Text)
    role = Column(Text, default='user')  # 'user', 'admin', 'analyst'

    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    last_login = Column(TIMESTAMP)

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'admin', 'analyst')",
            name='ck_user_role_values'
        ),
    )


class APIKey(Base):
    """API keys for external access"""
    __tablename__ = 'api_keys'

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False, index=True)

    key_hash = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)

    permissions = Column(ARRAY(Text), default=[])
    rate_limit = Column(Integer, default=1000)

    is_active = Column(Boolean, default=True, index=True)
    expires_at = Column(TIMESTAMP)
    last_used_at = Column(TIMESTAMP)

    created_at = Column(TIMESTAMP, default=datetime.utcnow)
