"""
Supervisor Agent - Multi-Agent Orchestration & Cross-Verification
Loads prompt from supervisor_prompt.md
Coordinates 4 specialist agents: Property, Market, Developer Intelligence, Regulatory & Risk
"""

import json
import os
import uuid
import re
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

# Capture specialist responses for structured data extraction
_specialist_responses = {}


def _strip_non_ascii(text: str) -> str:
    """Remove non-ASCII characters (emoji, styling glyphs) from supervisor output."""
    if not isinstance(text, str):
        return text
    return ''.join(ch for ch in text if ord(ch) < 128)

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
        # Store for structured data extraction
        _specialist_responses['property'] = result
        try:
            summary = property_specialist.get_latest_analysis_summary()
            if summary:
                _specialist_responses['property_metadata'] = summary
        except Exception as tracking_error:  # pragma: no cover - metadata retrieval optional
            logger.warning("Failed to capture property analysis summary", error=str(tracking_error))
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
        # Store for structured data extraction
        _specialist_responses['developer'] = result
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


def invoke(user_query: str, session_id: str = None):
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
        Dict with 'message' (text analysis) and 'structured_data' (properties, developers, etc.)
    """
    global _current_session_id, _specialist_responses

    if session_id is None:
        session_id = str(uuid.uuid4())

    _current_session_id = session_id
    _specialist_responses = {}  # Reset for this session
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

        # Extract text from Strands Agent result structure
        # AgentResult needs to be converted to dict first
        logger.info("Processing result", result_type=type(result).__name__)

        # Convert AgentResult to dict if needed
        if hasattr(result, 'model_dump'):
            result_dict = result.model_dump()
        elif hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
        elif hasattr(result, 'dict'):
            result_dict = result.dict()
        elif isinstance(result, dict):
            result_dict = result
        else:
            result_dict = dict(result) if hasattr(result, '__iter__') else {'message': str(result)}

        logger.info("Converted to dict", has_content=('content' in result_dict), dict_keys=list(result_dict.keys())[:5])

        # Extract message text from dict structure
        # Format: {'role': 'assistant', 'content': [{'text': 'actual message'}]}
        if 'content' in result_dict:
            content = result_dict['content']
            if isinstance(content, list) and len(content) > 0 and isinstance(content[0], dict) and 'text' in content[0]:
                message = content[0]['text']
            else:
                message = str(content)
        elif 'message' in result_dict:
            message = result_dict['message']
        else:
            message = str(result_dict)

        logger.info("Extracted message from result",
                   message_length=len(message),
                   message_type=type(message).__name__,
                   is_string=isinstance(message, str))

        # Strip internal agent thinking blocks from message before sending to frontend
        # Agents may include <thinking>...</thinking> blocks that should not be visible to users
        if isinstance(message, str):
            # Remove thinking blocks (including multiline)
            message = re.sub(r'<thinking>.*?</thinking>', '', message, flags=re.DOTALL)
            # Remove standalone thinking tags
            message = re.sub(r'</?thinking>', '', message)
            # Clean up extra whitespace
            message = re.sub(r'\n\n\n+', '\n\n', message).strip()
            # Remove emoji and other non-ASCII glyphs to enforce neutral presentation
            sanitized_message = _strip_non_ascii(message)
            if sanitized_message != message:
                logger.info("Removed non-ASCII characters from Supervisor message",
                            original_length=len(message), sanitized_length=len(sanitized_message))
            message = sanitized_message
            logger.info("Cleaned thinking blocks from message", cleaned_length=len(message))

        # Extract structured data from specialist responses AND final message
        structured_data = extract_structured_data(_specialist_responses, final_message=message)
        structured_data = validate_structured_data(structured_data, final_message=message)

        # Ensure final message always carries a JSON payload for the frontend parser
        message = ensure_structured_json_block(message, structured_data)

        return {
            'message': message,
            'structured_data': structured_data
        }

    except Exception as e:
        logger.error("Supervisor error", error=str(e), session_id=session_id, exc_info=True)
        return {
            'message': f"ERROR: Supervisor failed - {str(e)}",
            'structured_data': {}
        }
    finally:
        _current_session_id = None
        _specialist_responses = {}


def extract_structured_data(specialist_responses: dict, final_message: str = None) -> dict:
    """
    Extract structured data from agent response for frontend dashboard integration.
    
    Strategy 1 (PREFERRED): Parse JSON block from final message
    Strategy 2 (FALLBACK): Regex parsing from specialist responses
    
    The frontend needs structured data to populate:
    - Report tab: Confidence, risks, actions
    - Opportunities tab: Property cards, assemblage details
    - Activity tab: Specialist breakdown with confidence and durations
    - Globe/Map: Property markers at exact coordinates
    """
    if not final_message:
        logger.error("Supervisor final message missing; cannot extract structured data")
        raise ValueError("Supervisor final message missing; structured JSON block required")

    json_match = re.search(r'```json\s*(\{[\s\S]*\})\s*```', final_message, re.MULTILINE | re.DOTALL)
    if not json_match:
        logger.error("Supervisor response missing structured JSON block")
        raise ValueError("Supervisor response must include structured JSON block")

    json_str = json_match.group(1).strip()
    try:
        structured = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("Structured JSON block invalid", error=str(exc), snippet=json_str[:200])
        raise ValueError("Supervisor structured JSON block invalid") from exc

    logger.info(
        "Extracted structured data from JSON block",
        properties=len(structured.get('properties', []) or []),
        developers=len(structured.get('developers', []) or []),
        specialists=len(structured.get('specialist_breakdown', []) or []),
        risks=len(structured.get('risks', []) or []),
        actions=len(structured.get('actions', []) or []),
        has_assemblage=bool(structured.get('assemblage')),
    )

    # Validate required fields and surface clear diagnostics for the Supervisor prompt author.
    missing_fields = [
        field for field in ('recommendation', 'confidence', 'properties', 'developers', 'actions')
        if field not in structured
    ]
    if missing_fields:
        logger.warning("Structured JSON block missing required fields", missing=missing_fields)

    # Enrich structured data with metadata captured from tool execution (property counts, etc.).
    property_metadata = specialist_responses.get('property_metadata')
    if isinstance(property_metadata, dict):
        total = property_metadata.get('total_count') or property_metadata.get('total_properties')
        if isinstance(total, (int, float)) and total > 0 and 'properties_analyzed_total' not in structured:
            structured['properties_analyzed_total'] = int(total)
        counts_by_type = property_metadata.get('counts_by_type')
        if isinstance(counts_by_type, dict) and 'properties_analyzed_by_type' not in structured:
            structured['properties_analyzed_by_type'] = {
                str(key): int(value) for key, value in counts_by_type.items() if isinstance(value, (int, float))
            }
        searches = property_metadata.get('searches')
        if isinstance(searches, list) and 'property_searches' not in structured:
            structured['property_searches'] = searches

    return structured


def validate_structured_data(structured: dict, final_message: str) -> dict:
    """
    Ensure structured data contains the minimum fields the frontend expects.
    Fills sensible defaults and normalises confidence values.
    """
    structured = structured or {}

    # Recommendation
    recommendation = structured.get('recommendation') or 'UNKNOWN'
    structured['recommendation'] = recommendation

    # Confidence normalisation
    confidence = structured.get('confidence')
    if isinstance(confidence, (int, float)):
        confidence = float(confidence)
        if confidence > 1:
            confidence /= 100.0
        confidence = max(0.0, min(1.0, confidence))
    else:
        match = re.search(r'(?:confidence|conf)[\s:]+(\d+)%', final_message or '', re.IGNORECASE)
        confidence = float(match.group(1)) / 100.0 if match else 0.5
    structured['confidence'] = confidence

    # Collections required by dashboard
    collections = ['properties', 'developers', 'specialist_breakdown', 'risks', 'actions']
    for key in collections:
        value = structured.get(key)
        if not isinstance(value, list):
            structured[key] = []

    # Remove duplicate properties (parcel_id or coordinate collisions) to avoid dashboard bias
    properties = structured.get('properties', [])
    if isinstance(properties, list) and properties:
        seen_parcels = set()
        seen_coords = set()
        seen_addresses = set()
        unique_properties = []
        duplicates = 0

        for prop in properties:
            if not isinstance(prop, dict):
                continue

            parcel_raw = prop.get('parcel_id') or ''
            parcel_id = parcel_raw.strip().upper() if isinstance(parcel_raw, str) else None

            lat = prop.get('latitude')
            lon = prop.get('longitude')
            try:
                coords = (round(float(lat), 6), round(float(lon), 6))
            except (TypeError, ValueError):
                coords = None

            address_raw = prop.get('address') or ''
            address_key = address_raw.strip().upper() if isinstance(address_raw, str) else None

            duplicate = False
            if parcel_id:
                if parcel_id in seen_parcels:
                    duplicate = True
                else:
                    seen_parcels.add(parcel_id)

            if coords:
                if coords in seen_coords:
                    duplicate = True
                else:
                    seen_coords.add(coords)

            if not parcel_id and not coords and address_key:
                if address_key in seen_addresses:
                    duplicate = True
                else:
                    seen_addresses.add(address_key)

            if duplicate:
                duplicates += 1
                continue

            unique_properties.append(prop)

        if duplicates:
            logger.info(
                "Removed duplicate properties from structured payload",
                before=len(properties),
                after=len(unique_properties),
                duplicates=duplicates,
            )

        # Cap to reasonable number to avoid overwhelming downstream consumers
        structured['properties'] = unique_properties[:15]

    # Properties analyzed totals/by type
    total_analyzed = structured.get('properties_analyzed_total')
    if isinstance(total_analyzed, (int, float)):
        structured['properties_analyzed_total'] = int(total_analyzed)
    else:
        structured['properties_analyzed_total'] = len(structured.get('properties', []))

    counts_by_type = structured.get('properties_analyzed_by_type')
    if isinstance(counts_by_type, dict):
        normalised = {}
        for key, value in counts_by_type.items():
            if isinstance(value, (int, float)):
                normalised[str(key)] = int(value)
        structured['properties_analyzed_by_type'] = normalised
    else:
        structured['properties_analyzed_by_type'] = {}

    searches = structured.get('property_searches')
    if isinstance(searches, list):
        normalised_searches = []
        for entry in searches:
            if isinstance(entry, dict):
                normalised_entry = dict(entry)
                if 'counts_by_type' in normalised_entry and isinstance(normalised_entry['counts_by_type'], dict):
                    normalised_entry['counts_by_type'] = {
                        str(k): int(v) for k, v in normalised_entry['counts_by_type'].items() if isinstance(v, (int, float))
                    }
                if 'total' in normalised_entry and isinstance(normalised_entry['total'], (int, float)):
                    normalised_entry['total'] = int(normalised_entry['total'])
                normalised_searches.append(normalised_entry)
        structured['property_searches'] = normalised_searches
    else:
        structured['property_searches'] = []

    # Assemblage optional: ensure dict type when present
    assemblage = structured.get('assemblage')
    if assemblage is not None and not isinstance(assemblage, dict):
        structured['assemblage'] = None

    # Normalise property coordinates if available
    normalised_properties = []
    for prop in structured.get('properties', []):
        if not isinstance(prop, dict):
            continue
        try:
            lat = float(prop.get('latitude'))
            lon = float(prop.get('longitude'))
            prop['latitude'] = lat
            prop['longitude'] = lon
        except (TypeError, ValueError):
            # Skip properties without numeric coordinates
            continue
        parcel_id = prop.get('parcel_id')
        address = prop.get('address')
        if parcel_id and address:
            normalised_properties.append(prop)
    if normalised_properties:
        structured['properties'] = normalised_properties

    return structured


def ensure_structured_json_block(message: str, structured: dict) -> str:
    """
    Append (or replace) the structured JSON block required by the frontend.
    """
    if not isinstance(message, str):
        message = str(message)

    json_block = json.dumps(structured, ensure_ascii=False, indent=2, sort_keys=True)

    message = re.sub(r'```json[\s\S]*?```', '', message).rstrip()

    return f"{message}\n\n```json\n{json_block}\n```"
