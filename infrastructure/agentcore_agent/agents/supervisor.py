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
        import re
        if isinstance(message, str):
            # Remove thinking blocks (including multiline)
            message = re.sub(r'<thinking>.*?</thinking>', '', message, flags=re.DOTALL)
            # Remove standalone thinking tags
            message = re.sub(r'</?thinking>', '', message)
            # Clean up extra whitespace
            message = re.sub(r'\n\n\n+', '\n\n', message).strip()
            logger.info("Cleaned thinking blocks from message", cleaned_length=len(message))

        # Extract structured data from specialist responses AND final message
        structured_data = extract_structured_data(_specialist_responses, final_message=message)

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
    import re
    import json
    
    # === STRATEGY 1: Extract JSON block from final message (PREFERRED) ===
    if final_message:
        # Look for ```json ... ``` block - use greedy match to capture entire JSON object
        # Pattern: ```json followed by { ... } followed by ```
        # Use [\s\S]* (greedy) to capture everything between last { and first ``` after it
        json_match = re.search(r'```json\s*(\{[\s\S]*\})\s*```', final_message, re.MULTILINE | re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(1).strip()
                data = json.loads(json_str)
                logger.info("✅ Extracted structured data from JSON block", 
                           properties=len(data.get('properties', [])),
                           developers=len(data.get('developers', [])),
                           specialists=len(data.get('specialist_breakdown', [])),
                           risks=len(data.get('risks', [])),
                           actions=len(data.get('actions', [])),
                           has_assemblage=bool(data.get('assemblage')))
                
                # Validate required fields
                if 'recommendation' not in data:
                    logger.warning("JSON block missing 'recommendation' field")
                if 'confidence' not in data:
                    logger.warning("JSON block missing 'confidence' field")
                if 'properties' not in data:
                    logger.warning("JSON block missing 'properties' field")
                    
                return data
            except json.JSONDecodeError as e:
                logger.warning("⚠️ JSON block found but invalid, falling back to regex", 
                              error=str(e), 
                              json_snippet=json_match.group(1)[:300])
        else:
            logger.warning("⚠️ No JSON block found in final message, using regex fallback")
    
    # === STRATEGY 2: Regex parsing from specialist responses (FALLBACK) ===
    logger.info("Using regex fallback to extract structured data from specialist responses")
    
    structured = {
        'properties': [],
        'developers': [],
        'recommendation': 'UNKNOWN',
        'confidence': 0.5,
        'specialist_breakdown': [],
        'risks': [],
        'actions': [],
        'expected_return': None,
        'assemblage': None
    }

    try:
        # Extract properties from Property Specialist response
        # Format from logs: "parcel_id=06432-074-000, address=Granada Blvd, lat=29.6856, lon=-82.3426"
        # Note: Prompt instructs "COORDINATES:" prefix but agent sometimes omits it
        if 'property' in specialist_responses:
            prop_text = specialist_responses['property']
            
            # Try WITH "COORDINATES:" prefix first (as instructed in prompt)
            property_pattern_with_prefix = r'COORDINATES:\s*parcel_id=([^,\s]+)[\s,]+address=([^,]+)[\s,]+lat=([\d\.\-]+)[\s,]+lon=([\d\.\-]+)'
            matches = re.findall(property_pattern_with_prefix, prop_text, re.IGNORECASE)
            
            # Fallback: Try WITHOUT prefix (actual format from some logs)
            if len(matches) == 0:
                property_pattern_no_prefix = r'parcel_id=([^,\s]+)[\s,]+address=([^,]+)[\s,]+lat=([\d\.\-]+)[\s,]+lon=([\d\.\-]+)'
                matches = re.findall(property_pattern_no_prefix, prop_text, re.IGNORECASE)
            
            logger.info(f"Extracted {len(matches)} properties with coordinates from Property Specialist")
            
            for match in matches[:20]:  # Increased limit to 20 properties
                try:
                    structured['properties'].append({
                        'parcel_id': match[0].strip(),
                        'address': match[1].strip(),
                        'latitude': float(match[2]),
                        'longitude': float(match[3])
                    })
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse property: {match}, error: {e}")
                    continue

        # Extract developers from Developer Intelligence response
        # Formats: "1. **UCG REALTY LLC**" or "UCG Realty (86 properties)" or "Top Developers: UCG Realty"
        if 'developer' in specialist_responses:
            dev_text = specialist_responses['developer']
            
            # Pattern 1: Numbered list with bold (markdown): "1. **UCG REALTY LLC**"
            dev_pattern1 = r'\d+\.\s+\*\*([A-Z][A-Z\s\&\.\,\-]+(?:LLC|INC|CORP|HOMES|REALTY|GROUP|PROPERTIES)?)\*\*'
            matches1 = re.findall(dev_pattern1, dev_text, re.IGNORECASE)
            
            # Pattern 2: Name with property count: "UCG Realty (86 properties)"
            dev_pattern2 = r'([A-Z][A-Z\s\&\.\,\-]+(?:LLC|INC|CORP|HOMES|REALTY|GROUP|PROPERTIES)?)\s*\(\d+\s+properties?\)'
            matches2 = re.findall(dev_pattern2, dev_text, re.IGNORECASE)
            
            # Pattern 3: After "Top Developers:" or "Developer:" labels
            dev_pattern3 = r'(?:Top\s+Developers?|Developer)[:\s]+([A-Z][A-Z\s\&\.\,\-]+(?:LLC|INC|CORP|HOMES|REALTY|GROUP|PROPERTIES)?)'
            matches3 = re.findall(dev_pattern3, dev_text, re.IGNORECASE)
            
            # Combine and deduplicate
            all_matches = matches1 + matches2 + matches3
            seen = set()
            
            for match in all_matches[:10]:  # Limit to top 10
                clean_name = match.strip().upper()
                if clean_name and clean_name not in seen and len(clean_name) > 3:
                    seen.add(clean_name)
                    structured['developers'].append({
                        'name': match.strip()  # Keep original capitalization
                    })
            
            logger.info(f"Extracted {len(structured['developers'])} developers from Developer Intelligence")

        # Extract recommendation from Supervisor's final response
        # Look for patterns like "CONDITIONAL BUY", "BUY", "PASS", etc.
        supervisor_text = specialist_responses.get('supervisor', '')
        if 'BUY' in supervisor_text.upper() and 'NOT' not in supervisor_text.upper():
            if 'CONDITIONAL' in supervisor_text.upper():
                structured['recommendation'] = 'CONDITIONAL BUY'
            else:
                structured['recommendation'] = 'BUY'
        elif 'PASS' in supervisor_text.upper():
            structured['recommendation'] = 'PASS'
        
        # Extract confidence score
        # Patterns: "Confidence: 60%", "60% confidence", "Overall Confidence: 60%"
        confidence_pattern = r'(?:confidence|conf)[:\s]+(\d+)%|(\d+)%\s+confidence'
        confidence_match = re.search(confidence_pattern, supervisor_text, re.IGNORECASE)
        if confidence_match:
            confidence_val = confidence_match.group(1) or confidence_match.group(2)
            structured['confidence'] = float(confidence_val) / 100
            logger.info(f"Extracted confidence: {structured['confidence']}")

    except Exception as e:
        logger.error("Could not extract structured data", error=str(e), exc_info=True)

    return structured
