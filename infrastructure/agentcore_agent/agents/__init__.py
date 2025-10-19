"""
Multi-Agent Architecture for Dominion Real Estate Intelligence

Supervisor Agent + 4 Specialist Agents:
- Supervisor: Orchestration, cross-verification, validation, synthesis
- Property Specialist: Spatial analysis, clustering, assemblage
- Market Specialist: Trends, absorption, valuation, comps
- Developer Intelligence: Portfolio analysis, entity profiling, match scoring
- Regulatory & Risk: Zoning, permits, risk assessment, ordinance research

Each agent loads its prompt from markdown files in ../prompts/
"""

from . import property_specialist
from . import market_specialist
from . import developer_intelligence
from . import regulatory_risk
from . import supervisor

__all__ = [
    'property_specialist',
    'market_specialist',
    'developer_intelligence',
    'regulatory_risk',
    'supervisor'
]
