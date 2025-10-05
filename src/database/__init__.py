# Database package for Dominion Real Estate Intelligence - Multi-Market V2

from .connection import DatabaseManager
from .models import (
    Base,
    # Global layer
    Market,
    Entity,
    EntityRelationship,
    User,
    # Event layer (partitioned)
    RawFact,
    Property,
    Permit,
    CrimeReport,
    CouncilMeeting,
    NewsArticle,
    # Business entities
    LLCFormation,
    # Bulk data layer
    BulkDataSnapshot,
    BulkPropertyRecord,
    BulkLLCRecord,
    # Linking layer
    EntityMarketProperty,
    # AI layer
    AIInference,
    EmbeddingCache,
    LLMCache,
)

__all__ = [
    'DatabaseManager',
    'Base',
    # Global
    'Market',
    'Entity',
    'EntityRelationship',
    'User',
    # Events
    'RawFact',
    'Property',
    'Permit',
    'CrimeReport',
    'CouncilMeeting',
    'NewsArticle',
    # Business
    'LLCFormation',
    # Bulk
    'BulkDataSnapshot',
    'BulkPropertyRecord',
    'BulkLLCRecord',
    # Linking
    'EntityMarketProperty',
    # AI
    'AIInference',
    'EmbeddingCache',
    'LLMCache',
]