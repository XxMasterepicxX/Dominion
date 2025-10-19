"""
Supervisor Agent - Multi-Agent Orchestration & Cross-Verification
Loads prompt from supervisor_prompt.md
Coordinates 4 specialist agents: Property, Market, Developer Intelligence, Regulatory & Risk
"""

import json
import os
import uuid
from strands import Agent, tool
import structlog

# Import specialist agents
from . import property_specialist
from . import market_specialist
from . import developer_intelligence
from . import regulatory_risk

logger = structlog.get_logger()

# Load prompt from markdown file
PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', 'supervisor_prompt.md')

def load_prompt():
    """Load prompt from markdown file"""
    try:
        with open(PROMPT_FILE, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt from {PROMPT_FILE}: {e}")
        raise

SYSTEM_PROMPT = load_prompt()


# Tools for delegating to specialist agents
# These need to be defined before creating the agent, but they'll use session_id from closure
_current_session_id = None

@tool
def delegate_to_property_specialist(task: str) -> str:
    """
    Delegate a task to the Property Specialist agent.

    The Property Specialist handles:
    - Spatial analysis and clustering
    - Property search with 42 advanced filters
    - Assemblage opportunity identification
    - Location intelligence analysis
    - Complete property details retrieval

    Args:
        task: Detailed task description for the Property Specialist
            Example: "Search for ALL property types under $150K in Phoenix.
                     Identify spatial patterns and clusters. Return top 10
                     properties ranked by spatial opportunity."

    Returns:
        Analysis from Property Specialist with insights and confidence scores
    """
    logger.info("Supervisor delegating to Property Specialist", task=task, session_id=_current_session_id)
    try:
        result = property_specialist.invoke(task, session_id=_current_session_id)
        logger.info("Property Specialist completed task", session_id=_current_session_id)
        return result
    except Exception as e:
        logger.error("Property Specialist error", error=str(e), session_id=_current_session_id)
        return f"ERROR: Property Specialist failed - {str(e)}"


@tool
def delegate_to_market_specialist(task: str) -> str:
    """
    Delegate a task to the Market Specialist agent.

    The Market Specialist handles:
    - Multi-period trend analysis (12m, 6m, 3m, 1m)
    - Comparable property analysis with professional appraisal methodology
    - Absorption rate calculation and market classification
    - Price appreciation forecasting

    Args:
        task: Detailed task description for the Market Specialist
            Example: "Analyze market trends for residential properties under $200K
                     in Seattle. Provide 12m/6m/3m/1m trend analysis, absorption
                     rates, and price appreciation forecast."

    Returns:
        Market analysis with trends, insights, and confidence scores
    """
    logger.info("Supervisor delegating to Market Specialist", task=task, session_id=_current_session_id)
    try:
        result = market_specialist.invoke(task, session_id=_current_session_id)
        logger.info("Market Specialist completed task", session_id=_current_session_id)
        return result
    except Exception as e:
        logger.error("Market Specialist error", error=str(e), session_id=_current_session_id)
        return f"ERROR: Market Specialist failed - {str(e)}"


@tool
def delegate_to_developer_intelligence(task: str) -> str:
    """
    Delegate a task to the Developer Intelligence Specialist agent.

    The Developer Intelligence Specialist handles:
    - Entity discovery using funnel methodology (50+ → filter → 3-5 top prospects)
    - Portfolio analysis and pattern detection
    - Strategic intent identification (land banker, builder, flipper, etc.)
    - Match scoring between properties and developer profiles
    - SunBiz business entity verification

    Args:
        task: Detailed task description for the Developer Intelligence Specialist
            Example: "Find all developers with 5+ properties in Austin. Analyze their
                     portfolios to identify acquisition patterns, property types, and
                     strategic intent. Return top 5 most active developers with match
                     scores for a 2-acre vacant lot at $75K."

    Returns:
        Developer intelligence with portfolio analysis, match scores, and confidence
    """
    logger.info("Supervisor delegating to Developer Intelligence", task=task, session_id=_current_session_id)
    try:
        result = developer_intelligence.invoke(task, session_id=_current_session_id)
        logger.info("Developer Intelligence completed task", session_id=_current_session_id)
        return result
    except Exception as e:
        logger.error("Developer Intelligence error", error=str(e), session_id=_current_session_id)
        return f"ERROR: Developer Intelligence failed - {str(e)}"


@tool
def delegate_to_regulatory_risk(task: str) -> str:
    """
    Delegate a task to the Regulatory & Risk Specialist agent.

    The Regulatory & Risk Specialist handles:
    - Comprehensive checklist methodology (50-100 items)
    - Permit history analysis
    - Zoning compliance verification
    - Ordinance research (RAG-powered, 5,176 chunks, 9 jurisdictions)
    - Risk matrix scoring (severity × probability)
    - Regulatory opportunity identification

    Args:
        task: Detailed task description for the Regulatory & Risk Specialist
            Example: "Assess zoning compliance and risks for a 0.3-acre property
                     in Denver. User wants to build a duplex. Check current zoning,
                     permitted uses, recent rezoning precedents, permit history, and
                     provide risk assessment with mitigation strategies."

    Returns:
        Regulatory analysis with risk scores, compliance status, opportunities, and confidence
    """
    logger.info("Supervisor delegating to Regulatory & Risk", task=task, session_id=_current_session_id)
    try:
        result = regulatory_risk.invoke(task, session_id=_current_session_id)
        logger.info("Regulatory & Risk completed task", session_id=_current_session_id)
        return result
    except Exception as e:
        logger.error("Regulatory & Risk error", error=str(e), session_id=_current_session_id)
        return f"ERROR: Regulatory & Risk failed - {str(e)}"


# Configure model for Supervisor - shared across all sessions
from strands.models import BedrockModel
from botocore.config import Config

# Configure boto client with extended timeout for long-running LLM operations
# AWS recommends 3600 seconds (60 minutes) for LLM inference
boto_config = Config(
    read_timeout=3600,      # 60 minutes for long multi-agent orchestration
    connect_timeout=60,     # 60 seconds to establish connection
    retries={"max_attempts": 3, "mode": "adaptive"}
)

supervisor_model = BedrockModel(
    model_id="us.amazon.nova-premier-v1:0",
    max_tokens=10000,  # High limit for complex multi-agent synthesis
    temperature=0.3,
    boto_client_config=boto_config
)


def invoke(user_query: str, session_id: str = None) -> str:
    """
    Invoke the Supervisor agent with a user query.

    Creates a fresh agent instance per session to prevent conversation bleed.

    The Supervisor will:
    1. Plan the analysis (which specialists to engage)
    2. Delegate tasks to specialists (Stages 1-3: DISCOVER → RANK → ANALYZE)
    3. Synthesize specialist outputs (Stages 4-6: CROSS-VERIFY → VALIDATE → PRESENT)
    4. Apply validation methodologies (CoVe, Red Team, Pre-Mortem, Sensitivity)
    5. Calculate overall confidence with cross-verification
    6. Present comprehensive executive summary

    Args:
        user_query: The user's real estate analysis request
        session_id: Unique session ID for isolation (generated if None)

    Returns:
        Institutional-grade analysis with recommendation, confidence, and full cross-verification
    """
    global _current_session_id

    if session_id is None:
        session_id = str(uuid.uuid4())

    _current_session_id = session_id
    logger.info("Supervisor invoked with user query", query=user_query, session_id=session_id)

    try:
        # Create fresh agent instance for this session to prevent conversation bleed
        session_supervisor = Agent(
            name=f"Supervisor-{session_id[:8]}",
            model=supervisor_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[
                delegate_to_property_specialist,
                delegate_to_market_specialist,
                delegate_to_developer_intelligence,
                delegate_to_regulatory_risk
            ]
        )

        result = session_supervisor(user_query)
        logger.info("Supervisor completed analysis",
                   session_id=session_id,
                   tool_calls=len(result.tool_calls) if hasattr(result, 'tool_calls') else 0)

        return result.message if hasattr(result, 'message') else str(result)

    except Exception as e:
        logger.error("Supervisor error", error=str(e), session_id=session_id, exc_info=True)
        return f"ERROR: Supervisor failed - {str(e)}"
    finally:
        _current_session_id = None
