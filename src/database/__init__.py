# Database package for Dominion Real Estate Intelligence

from .connection import DatabaseManager
from .models import (
    Base,
    # Core provenance
    ContentSnapshot,
    RawFact,
    StructuredFact,
    FactEvent,
    # Domain entities
    Property,
    Entity,
    EntityRelationship,
    # Domain tables
    Permit,
    PropertySale,
    LLCFormation,
    NewsArticle,
    CouncilMeeting,
    CrimeReport,
    # AI insights
    AIInference,
    InferenceRelationship,
    InferenceOutcome,
    # Caching
    LLMCache,
    # Operational
    ScraperRun,
    DataQualityCheck,
    IntelligenceAlert,
    User,
    APIKey,
)

__all__ = [
    'DatabaseManager',
    'Base',
    # Core
    'ContentSnapshot',
    'RawFact',
    'StructuredFact',
    'FactEvent',
    # Domain
    'Property',
    'Entity',
    'EntityRelationship',
    'Permit',
    'PropertySale',
    'LLCFormation',
    'NewsArticle',
    'CouncilMeeting',
    'CrimeReport',
    # AI
    'AIInference',
    'InferenceRelationship',
    'InferenceOutcome',
    # Other
    'LLMCache',
    'ScraperRun',
    'DataQualityCheck',
    'IntelligenceAlert',
    'User',
    'APIKey',
]