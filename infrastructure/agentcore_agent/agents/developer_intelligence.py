"""
Developer Intelligence Specialist Agent - Portfolio Analysis & Entity Profiling Expert
Loads prompt from developer_intelligence_prompt.md
"""

import json
import uuid
import os
import boto3
from strands import Agent, tool
import structlog

logger = structlog.get_logger()

# AWS Lambda client
lambda_client = boto3.client('lambda', region_name='us-east-1')

# Lambda function ARNs
INTELLIGENCE_FUNCTION_ARN = os.environ.get('INTELLIGENCE_FUNCTION_ARN', 'Dominion-Tools-IntelligenceFunctionF3B7706E-MqwpnWGzHDyP')
ENRICHMENT_FUNCTION_ARN = os.environ.get('ENRICHMENT_FUNCTION_ARN', 'Dominion-Tools-EnrichmentFunction65873741-Nu6t0OWMde2r')

# Load prompt from markdown file
PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', 'developer_intelligence_prompt.md')

def load_prompt():
    """Load prompt from markdown file"""
    try:
        with open(PROMPT_FILE, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt from {PROMPT_FILE}: {e}")
        raise

SYSTEM_PROMPT = load_prompt()


# Tool definitions for Developer Intelligence Specialist
@tool
def find_entities(
    entity_name: str = None,
    entity_type: str = None,
    min_property_count: int = 2,
    city: str = None,
    property_type: str = None,
    include_details: bool = True,
    limit: int = 50
) -> dict:
    """
    Find property owners and entities with portfolio analysis.

    Two modes:
    - Discovery mode (no entity_name): Returns all entities with min_property_count+
    - Deep dive mode (entity_name provided): Returns full portfolio for specific entity

    Enhanced with entity_type field ("llc", "corp", "individual", "government").
    60x faster performance using entities table (523 unique entities).
    """
    payload = {
        'tool': 'find_entities',
        'parameters': {
            'entity_name': entity_name,
            'entity_type': entity_type,
            'min_property_count': min_property_count,
            'city': city,
            'property_type': property_type,
            'include_details': include_details,
            'limit': limit
        }
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


@tool
def enrich_from_sunbiz(
    entity_name: str = None,
    document_number: str = None
) -> dict:
    """
    Enrich entity data from Florida SunBiz (business registry).

    Returns: entity status, registration date, principals, addresses, filing history.
    """
    payload = {
        'tool': 'enrich_from_sunbiz',
        'parameters': {
            'entity_name': entity_name,
            'document_number': document_number
        }
    }

    response = lambda_client.invoke(
        FunctionName=ENRICHMENT_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])


# Create Developer Intelligence Specialist Agent
from strands.models import BedrockModel
from botocore.config import Config

# Configure boto client with extended timeout for long-running LLM operations
# AWS recommends 3600 seconds (60 minutes) for LLM inference
boto_config = Config(
    read_timeout=3600,      # 60 minutes for comprehensive developer analysis
    connect_timeout=60,     # 60 seconds to establish connection
    retries={"max_attempts": 3, "mode": "adaptive"}
)

developer_model = BedrockModel(
    model_id="us.amazon.nova-lite-v1:0",
    max_tokens=10000,  # High limit for comprehensive developer analysis
    temperature=0.2,
    boto_client_config=boto_config
)

def invoke(task: str, session_id: str = None) -> str:
    """
    Invoke the Developer Intelligence agent with session isolation.

    Args:
        task: Task description from supervisor
        session_id: Unique session ID for isolation (generated if None)

    Returns:
        Developer intelligence results
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    logger.info("Developer Intelligence invoked", task=task[:100], session_id=session_id)

    # Create fresh agent instance for this session
    developer_agent = Agent(
        name=f"DeveloperIntelligence-{session_id[:8]}",
        model=developer_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            find_entities,
            enrich_from_sunbiz
        ]
    )

    result = developer_agent(task)
    logger.info("Developer Intelligence completed", session_id=session_id)
    return result.message if hasattr(result, 'message') else str(result)
