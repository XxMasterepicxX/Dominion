"""
Property Specialist Agent - Spatial Analysis & Clustering Expert
Loads prompt from property_specialist_prompt.md
"""

import json
import os
import uuid
from copy import deepcopy
from datetime import datetime
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from strands import Agent, tool
import structlog

logger = structlog.get_logger()

# AWS Lambda client
lambda_client = boto3.client('lambda', region_name='us-east-1')

# Lambda function ARNs
INTELLIGENCE_FUNCTION_ARN = os.environ.get('INTELLIGENCE_FUNCTION_ARN', 'Dominion-Tools-IntelligenceFunctionF3B7706E-MqwpnWGzHDyP')

# Load prompt from markdown file
PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', 'property_specialist_prompt.md')

def load_prompt():
    """Load prompt from markdown file"""
    try:
        with open(PROMPT_FILE, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt from {PROMPT_FILE}: {e}")
        raise

SYSTEM_PROMPT = load_prompt()


# Analysis tracking (captures total properties inspected per session)
_analysis_tracker = {
    'mode': None,
    'total_count': 0,
    'counts_by_type': {},
    'searches': [],
    'last_updated_at': None,
}


def _reset_analysis_tracker():
    """Reset per-session analysis tracker state."""
    _analysis_tracker['mode'] = None
    _analysis_tracker['total_count'] = 0
    _analysis_tracker['counts_by_type'] = {}
    _analysis_tracker['searches'] = []
    _analysis_tracker['last_updated_at'] = None


def _record_search_result(tool_name: str, counts_by_type: dict, criteria: dict | None = None):
    """Record aggregated property counts for the current analysis session."""
    counts_by_type = {str(key or 'UNKNOWN'): int(value or 0) for key, value in counts_by_type.items()}
    total = sum(counts_by_type.values())

    if tool_name == 'search_all_property_types':
        _analysis_tracker['mode'] = 'search_all_property_types'
        _analysis_tracker['counts_by_type'] = counts_by_type.copy()
        _analysis_tracker['total_count'] = total
    else:
        if _analysis_tracker['mode'] != 'search_all_property_types':
            _analysis_tracker['mode'] = _analysis_tracker['mode'] or 'search_properties'
            for key, value in counts_by_type.items():
                existing = _analysis_tracker['counts_by_type'].get(key, 0)
                _analysis_tracker['counts_by_type'][key] = max(existing, value)
            _analysis_tracker['total_count'] = sum(_analysis_tracker['counts_by_type'].values())

    _analysis_tracker['searches'].append({
        'tool': tool_name,
        'counts_by_type': counts_by_type,
        'criteria': criteria or {},
        'total': total,
        'recorded_at': datetime.utcnow().isoformat(),
    })
    _analysis_tracker['last_updated_at'] = datetime.utcnow().isoformat()


def get_latest_analysis_summary() -> dict:
    """Return a snapshot of the most recent property analysis tracking data."""
    return deepcopy(_analysis_tracker)


def _normalize_owner_name(owner_name: str | None) -> str:
    """Return an uppercase alphanumeric signature for the owner."""
    if not owner_name or not isinstance(owner_name, str):
        return ''
    return ''.join(ch for ch in owner_name.upper() if ch.isalnum())


def _apply_owner_cap(properties: list, per_owner_limit: int, max_results: int | None = None) -> tuple[list, dict]:
    """Limit number of properties per owner and dedupe by parcel and coordinates."""
    per_owner_limit = max(1, int(per_owner_limit or 1))
    max_results = max_results or len(properties or [])

    owner_counts: dict[str, int] = {}
    parcel_seen: set[str] = set()
    coord_seen: set[tuple[float, float]] = set()
    trimmed: list = []
    filtered_stats = {'removed': 0}

    for prop in properties or []:
        if not isinstance(prop, dict):
            continue

        parcel_raw = (prop.get('parcel_id') or '').strip()
        parcel_key = parcel_raw.upper()
        if parcel_key and parcel_key in parcel_seen:
            filtered_stats['removed'] += 1
            continue

        lat = prop.get('latitude')
        lon = prop.get('longitude')
        try:
            coord_key = (round(float(lat), 6), round(float(lon), 6))
        except (TypeError, ValueError):
            coord_key = None

        if coord_key and coord_key in coord_seen:
            filtered_stats['removed'] += 1
            continue

        owner_key = _normalize_owner_name(prop.get('owner_name'))
        if owner_key:
            owner_limit = owner_counts.get(owner_key, 0)
            if owner_limit >= per_owner_limit:
                filtered_stats['removed'] += 1
                continue
            owner_counts[owner_key] = owner_limit + 1

        if parcel_key:
            parcel_seen.add(parcel_key)
        if coord_key:
            coord_seen.add(coord_key)

        trimmed.append(prop)
        if len(trimmed) >= max_results:
            break

    return trimmed, filtered_stats


def _determine_default_order(property_type: str | None, requested_order: str | None = None) -> str | None:
    """Pick a diversified ordering strategy when caller does not specify one."""
    if requested_order:
        return requested_order

    type_key = (property_type or 'OTHER').strip().upper()
    order_map = {
        'CONDO': 'last_sale_recent',
        'TOWNHOME': 'last_sale_recent',
        'SINGLE FAMILY': 'market_value_recent',
        'MOBILE HOME': 'year_built_recent',
        'VACANT': 'acreage_then_value',
        'OTHER': 'market_value_recent'
    }
    return order_map.get(type_key, 'market_value_recent')


# Tool definitions for Property Specialist
@tool
def search_properties(
    city: str = None,
    min_price: float = None,
    max_price: float = None,
    property_type: str = None,
    min_sqft: int = None,
    max_sqft: int = None,
    min_lot_acres: float = None,
    max_lot_acres: float = None,
    bedrooms: int = None,
    bathrooms: float = None,
    min_bedrooms: int = None,
    min_bathrooms: float = None,
    min_year_built: int = None,
    max_year_built: int = None,
    min_stories: int = None,
    max_stories: int = None,
    has_pool: bool = None,
    has_garage: bool = None,
    has_porch: bool = None,
    has_fence: bool = None,
    has_shed: bool = None,
    building_condition: str = None,
    building_quality: str = None,
    roof_type: str = None,
    heat_type: str = None,
    ac_type: str = None,
    owner_state: str = None,
    owner_name: str = None,
    has_homestead: bool = None,
    exemption_types: str = None,
    min_last_sale_price: float = None,
    max_last_sale_price: float = None,
    min_last_sale_date: str = None,
    max_last_sale_date: str = None,
    sale_qualified: str = None,
    neighborhood_desc: str = None,
    subdivision_desc: str = None,
    min_assessed: float = None,
    max_assessed: float = None,
    limit: int = 100,
    order_by: str = None
) -> dict:
    """
    Search properties with 42 advanced filters.

    Supports: location, price, size, physical features, building quality,
    owner intelligence, tax/exemptions, sales history filters.
    """
    parameters = {
        k: v for k, v in locals().items()
        if v is not None and k not in ['payload', 'response', 'result', 'parameters', 'data', 'trimmed', 'stats']
    }

    if 'per_owner_limit' not in parameters:
        parameters['per_owner_limit'] = 2

    order_choice = _determine_default_order(parameters.get('property_type'), parameters.get('order_by'))
    if order_choice:
        parameters['order_by'] = order_choice

    payload = {
        'tool': 'search_properties',
        'parameters': parameters
    }

    response = lambda_client.invoke(
        FunctionName=INTELLIGENCE_FUNCTION_ARN,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    result = json.loads(response['Payload'].read())
    data = json.loads(result['body'])

    properties = data.get('properties', [])
    limit_value = parameters.get('limit') or 100
    try:
        per_owner_limit = int(parameters.get('per_owner_limit', 2))
    except (TypeError, ValueError):
        per_owner_limit = 2

    trimmed, stats = _apply_owner_cap(properties, per_owner_limit, max_results=int(limit_value))

    if stats.get('removed'):
        logger.info(
            "Applied per-owner cap to property search results",
            removed=stats['removed'],
            per_owner_limit=per_owner_limit,
            returned=len(trimmed),
        )

    data['properties'] = trimmed
    data['count'] = len(trimmed)

    try:
        property_type_label = parameters.get('property_type') or 'ALL'
        _record_search_result(
            'search_properties',
            {property_type_label: data.get('count', 0)},
            {k: v for k, v in parameters.items() if v is not None},
        )
    except Exception as tracking_error:  # pragma: no cover - tracking must not block core flow
        logger.warning("Failed to record search_properties tracking data", error=str(tracking_error))

    return data


@tool
def search_all_property_types(
    city: str = None,
    min_price: float = None,
    max_price: float = None,
    min_sqft: int = None,
    max_sqft: int = None,
    min_lot_acres: float = None,
    max_lot_acres: float = None,
    limit: int = 100
) -> dict:
    """
    Search ALL 6 property types in PARALLEL (10x faster than 6 sequential calls).

    Makes 6 concurrent Lambda invocations for complete market coverage:
    - CONDO, SINGLE FAMILY, MOBILE HOME, VACANT, TOWNHOME, Other types (null)

    Returns combined results grouped by property type with total counts.

    **USE THIS TOOL FIRST** for property discovery instead of making 6 separate
    search_properties calls. Completes in ~2 minutes instead of ~12 minutes.
    """
    logger.info("search_all_property_types invoked", city=city, max_price=max_price)

    property_types = ["CONDO", "SINGLE FAMILY", "MOBILE HOME", "VACANT", "TOWNHOME", None]

    def search_single_type(prop_type):
        """Helper to search one property type"""
        try:
            parameters = {
                'city': city,
                'min_price': min_price,
                'max_price': max_price,
                'property_type': prop_type,
                'min_sqft': min_sqft,
                'max_sqft': max_sqft,
                'min_lot_acres': min_lot_acres,
                'max_lot_acres': max_lot_acres,
                'limit': limit
            }
            parameters = {k: v for k, v in parameters.items() if v is not None}

            order_choice = _determine_default_order(prop_type, parameters.get('order_by'))
            if order_choice:
                parameters['order_by'] = order_choice

            parameters.setdefault('per_owner_limit', 2)

            payload = {
                'tool': 'search_properties',
                'parameters': parameters
            }

            response = lambda_client.invoke(
                FunctionName=INTELLIGENCE_FUNCTION_ARN,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )

            result = json.loads(response['Payload'].read())
            data = json.loads(result['body'])

            properties = data.get('properties', [])
            per_owner_limit = parameters.get('per_owner_limit', 2)
            trimmed, stats = _apply_owner_cap(properties, per_owner_limit, max_results=limit)

            if stats.get('removed'):
                logger.info(
                    "Applied per-owner cap in search_all_property_types",
                    property_type=prop_type or 'OTHER',
                    removed=stats['removed'],
                    per_owner_limit=per_owner_limit,
                    returned=len(trimmed),
                )

            data['properties'] = trimmed
            data['count'] = len(trimmed)

            return {
                'property_type': prop_type or 'OTHER',
                'count': data.get('count', 0),
                'properties': data.get('properties', [])
            }
        except Exception as e:
            logger.error(f"Error searching {prop_type}: {e}")
            return {'property_type': prop_type or 'OTHER', 'count': 0, 'properties': [], 'error': str(e)}

    # Execute all 6 searches in PARALLEL
    results_by_type = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_type = {executor.submit(search_single_type, pt): pt for pt in property_types}

        for future in as_completed(future_to_type):
            try:
                results_by_type.append(future.result())
            except Exception as e:
                prop_type = future_to_type[future]
                logger.error(f"Failed {prop_type}: {e}")
                results_by_type.append({'property_type': prop_type or 'OTHER', 'count': 0, 'properties': []})

    # Sort by property type for consistent output
    results_by_type.sort(key=lambda x: x['property_type'])
    total_properties = sum(r['count'] for r in results_by_type)

    logger.info("search_all_property_types completed", total=total_properties)

    try:
        _record_search_result(
            'search_all_property_types',
            {entry['property_type']: entry['count'] for entry in results_by_type},
            {'city': city, 'min_price': min_price, 'max_price': max_price, 'min_sqft': min_sqft, 'max_sqft': max_sqft},
        )
    except Exception as tracking_error:  # pragma: no cover - tracking must not block core flow
        logger.warning("Failed to record search_all_property_types tracking data", error=str(tracking_error))

    return {
        'success': True,
        'total_properties': total_properties,
        'results_by_type': results_by_type,
        'search_criteria': {'city': city, 'min_price': min_price, 'max_price': max_price}
    }


@tool
def get_property_details(
    parcel_id: str = None,
    property_id: str = None,
    address: str = None
) -> dict:
    """
    Get complete property details with ALL 80+ database fields.

    Returns: building features, neighborhood, owner, tax, financial data,
    JSONB fields (sales_history, building_details, permit_history).
    """
    payload = {
        'tool': 'get_property_details',
        'parameters': {
            'parcel_id': parcel_id,
            'property_id': property_id,
            'address': address
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
def cluster_properties(
    city: str,
    radius_meters: float = 500,
    min_cluster_size: int = 3,
    property_type: str = None
) -> dict:
    """
    Find geographic clusters of properties using DBSCAN.

    Returns: clusters with centroids, property counts, purity scores.
    """
    payload = {
        'tool': 'cluster_properties',
        'parameters': {
            'city': city,
            'radius_meters': radius_meters,
            'min_cluster_size': min_cluster_size,
            'property_type': property_type
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
def find_assemblage_opportunities(
    city: str,
    max_distance_meters: float = 200,
    min_parcels: int = 2,
    max_parcels: int = 10
) -> dict:
    """
    Find land assemblage opportunities (adjacent parcels by same owner).

    Returns: assemblages with entity_type, total_assemblage_value,
    total_lot_size_acres, property_types breakdown.
    """
    payload = {
        'tool': 'find_assemblage_opportunities',
        'parameters': {
            'city': city,
            'max_distance_meters': max_distance_meters,
            'min_parcels': min_parcels,
            'max_parcels': max_parcels
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
def analyze_location_intelligence(
    parcel_id: str = None,
    address: str = None,
    lat: float = None,
    lon: float = None,
    radius_meters: float = 500,
    limit: int = 50
) -> dict:
    """
    Analyze nearby properties and spatial context.

    Returns: nearby properties with distances, property mix, spatial patterns.
    """
    payload = {
        'tool': 'analyze_location_intelligence',
        'parameters': {
            'parcel_id': parcel_id,
            'address': address,
            'lat': lat,
            'lon': lon,
            'radius_meters': radius_meters,
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


# Configure model for Property Specialist - shared across all sessions
from strands.models import BedrockModel
from botocore.config import Config

# Configure boto client with extended timeout for long-running LLM operations
# AWS recommends 3600 seconds (60 minutes) for LLM inference
boto_config = Config(
    read_timeout=3600,      # 60 minutes for comprehensive property analysis
    connect_timeout=60,     # 60 seconds to establish connection
    retries={"max_attempts": 3, "mode": "adaptive"}
)

property_model = BedrockModel(
    model_id="us.amazon.nova-premier-v1:0",  # Premier required - Lite and Pro both crash on 6-call planning
    max_tokens=10000,  # Using compact output format to stay within limit
    temperature=0.2,
    boto_client_config=boto_config
)


def invoke(task: str, session_id: str = None) -> str:
    """
    Invoke the Property Specialist agent with session isolation.

    Creates a fresh agent instance per session to prevent conversation bleed.

    Args:
        task: Task description from supervisor
        session_id: Unique session ID for isolation (generated if None)

    Returns:
        Property analysis results
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    logger.info("Property Specialist invoked", task=task[:100], session_id=session_id)

    # Reset tracking so counts do not bleed between sessions
    _reset_analysis_tracker()

    # Create fresh agent instance for this session
    property_agent = Agent(
        name=f"PropertySpecialist-{session_id[:8]}",
        model=property_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            search_all_property_types,  # NEW: Parallel search (10x faster than 6 sequential calls)
            search_properties,           # Keep for specific single-type searches
            get_property_details,
            cluster_properties,
            find_assemblage_opportunities,
            analyze_location_intelligence
        ]
    )

    result = property_agent(task)
    logger.info("Property Specialist completed", session_id=session_id)

    # Convert AgentResult to dict
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

    # Extract text from dict structure
    if 'content' in result_dict:
        content = result_dict['content']
        if isinstance(content, list) and len(content) > 0 and isinstance(content[0], dict) and 'text' in content[0]:
            return content[0]['text']
        return str(content)
    elif 'message' in result_dict:
        return result_dict['message']
    return str(result_dict)
