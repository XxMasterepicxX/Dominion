"""
Intelligence Lambda Function Handler

Handles 7 tools:
1. search_properties - Search properties by criteria
2. find_entities - Find property owners/entities
3. analyze_market_trends - Market analysis
4. cluster_properties - Geographic clustering
5. find_assemblage_opportunities - Multi-parcel assemblage
6. analyze_location_intelligence - Location-based analysis
7. check_permit_history - Permit history lookup

Uses RDS Data API for serverless database access (no VPC needed).
Self-contained - no external module dependencies.
"""

import json
import os
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
rds_data = boto3.client('rds-data')

# Environment variables
CLUSTER_ARN = os.environ['CLUSTER_ARN']
SECRET_ARN = os.environ['SECRET_ARN']
DATABASE_NAME = os.environ['DATABASE_NAME']


def execute_sql(sql: str, parameters: List[Dict] = None) -> Dict:
    """Execute SQL via RDS Data API"""
    try:
        params = {
            'resourceArn': CLUSTER_ARN,
            'secretArn': SECRET_ARN,
            'database': DATABASE_NAME,
            'sql': sql,
            'includeResultMetadata': True,
        }
        if parameters:
            params['parameters'] = parameters

        response = rds_data.execute_statement(**params)
        return response
    except ClientError as e:
        print(f"RDS Data API error: {e}")
        raise


def format_rds_response(response: Dict) -> List[Dict]:
    """Convert RDS Data API response to list of dictionaries"""
    if 'records' not in response or not response['records']:
        return []

    column_names = [col['name'] for col in response.get('columnMetadata', [])]
    results = []

    for record in response['records']:
        row = {}
        for i, col_name in enumerate(column_names):
            if i < len(record):
                # Extract value from RDS Data API format
                value_dict = record[i]
                if 'stringValue' in value_dict:
                    row[col_name] = value_dict['stringValue']
                elif 'longValue' in value_dict:
                    row[col_name] = value_dict['longValue']
                elif 'doubleValue' in value_dict:
                    row[col_name] = value_dict['doubleValue']
                elif 'booleanValue' in value_dict:
                    row[col_name] = value_dict['booleanValue']
                elif 'isNull' in value_dict and value_dict['isNull']:
                    row[col_name] = None
                else:
                    row[col_name] = None
        results.append(row)

    return results


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def search_properties(params: Dict) -> Dict:
    """
    Search properties by criteria.

    Parameters:
    - city: str (optional)
    - property_type: str (optional)
    - min_price: float (optional)
    - max_price: float (optional)
    - limit: int (default: 20)
    """
    city = params.get('city')
    property_type = params.get('property_type')
    min_price = params.get('min_price')
    max_price = params.get('max_price')
    limit = params.get('limit', 20)

    # Build dynamic WHERE clause
    where_clauses = []
    sql_params = []

    if city:
        where_clauses.append("city = :city")
        sql_params.append({'name': 'city', 'value': {'stringValue': city}})

    if property_type:
        where_clauses.append("property_type = :property_type")
        sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

    if min_price is not None:
        where_clauses.append("market_value >= :min_price")
        sql_params.append({'name': 'min_price', 'value': {'doubleValue': float(min_price)}})

    if max_price is not None:
        where_clauses.append("market_value <= :max_price")
        sql_params.append({'name': 'max_price', 'value': {'doubleValue': float(max_price)}})

    # Construct SQL
    sql = """
        SELECT property_id, parcel_id, address, city, state, zip_code,
               property_type, zoning, land_use, lot_size, building_area,
               year_built, bedrooms, bathrooms, assessed_value, market_value,
               owner_name, owner_type, latitude, longitude
        FROM properties
    """

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += f" ORDER BY market_value DESC LIMIT {limit}"

    response = execute_sql(sql, sql_params if sql_params else None)
    properties = format_rds_response(response)

    return {
        'success': True,
        'count': len(properties),
        'properties': properties
    }


def find_entities(params: Dict) -> Dict:
    """
    Find entities (property owners, LLCs, corporations).

    Parameters:
    - entity_name: str (optional)
    - entity_type: str (optional)
    - limit: int (default: 20)
    """
    entity_name = params.get('entity_name')
    entity_type = params.get('entity_type')
    limit = params.get('limit', 20)

    where_clauses = []
    sql_params = []

    if entity_name:
        where_clauses.append("entity_name ILIKE :entity_name")
        sql_params.append({'name': 'entity_name', 'value': {'stringValue': f'%{entity_name}%'}})

    if entity_type:
        where_clauses.append("entity_type = :entity_type")
        sql_params.append({'name': 'entity_type', 'value': {'stringValue': entity_type}})

    sql = """
        SELECT entity_id, entity_name, entity_type, status,
               registered_agent, principal_address, business_activity
        FROM entities
    """

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += f" ORDER BY entity_name LIMIT {limit}"

    response = execute_sql(sql, sql_params if sql_params else None)
    entities = format_rds_response(response)

    return {
        'success': True,
        'count': len(entities),
        'entities': entities
    }


def analyze_market_trends(params: Dict) -> Dict:
    """
    Analyze market trends for a city/area.

    Parameters:
    - city: str (required)
    - property_type: str (optional)
    """
    city = params.get('city')
    property_type = params.get('property_type')

    if not city:
        return {'success': False, 'error': 'city parameter is required'}

    sql_params = [{'name': 'city', 'value': {'stringValue': city}}]

    where_clause = "WHERE city = :city"
    if property_type:
        where_clause += " AND property_type = :property_type"
        sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

    sql = f"""
        SELECT
            property_type,
            COUNT(*) as count,
            AVG(market_value) as avg_price,
            MIN(market_value) as min_price,
            MAX(market_value) as max_price,
            AVG(lot_size) as avg_lot_size
        FROM properties
        {where_clause}
        GROUP BY property_type
        ORDER BY count DESC
    """

    response = execute_sql(sql, sql_params)
    trends = format_rds_response(response)

    return {
        'success': True,
        'city': city,
        'property_type': property_type,
        'trends': trends
    }


def cluster_properties(params: Dict) -> Dict:
    """
    Get geographic clusters of properties.

    Parameters:
    - city: str (required)
    - limit: int (default: 50)
    """
    city = params.get('city')
    limit = params.get('limit', 50)

    if not city:
        return {'success': False, 'error': 'city parameter is required'}

    sql = """
        SELECT property_id, address, city, property_type,
               latitude, longitude, market_value
        FROM properties
        WHERE city = :city
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY market_value DESC
        LIMIT :limit
    """

    sql_params = [
        {'name': 'city', 'value': {'stringValue': city}},
        {'name': 'limit', 'value': {'longValue': limit}}
    ]

    response = execute_sql(sql, sql_params)
    properties = format_rds_response(response)

    return {
        'success': True,
        'city': city,
        'count': len(properties),
        'properties': properties
    }


def find_assemblage_opportunities(params: Dict) -> Dict:
    """
    Find properties suitable for assemblage (adjacent parcels).

    Parameters:
    - city: str (required)
    - min_lot_size: float (optional)
    - limit: int (default: 20)
    """
    city = params.get('city')
    min_lot_size = params.get('min_lot_size')
    limit = params.get('limit', 20)

    if not city:
        return {'success': False, 'error': 'city parameter is required'}

    sql_params = [{'name': 'city', 'value': {'stringValue': city}}]

    where_clause = "WHERE city = :city AND lot_size IS NOT NULL"
    if min_lot_size:
        where_clause += " AND lot_size >= :min_lot_size"
        sql_params.append({'name': 'min_lot_size', 'value': {'doubleValue': float(min_lot_size)}})

    sql = f"""
        SELECT property_id, parcel_id, address, lot_size, zoning,
               market_value, owner_name, owner_type, latitude, longitude
        FROM properties
        {where_clause}
        ORDER BY lot_size DESC
        LIMIT {limit}
    """

    response = execute_sql(sql, sql_params)
    properties = format_rds_response(response)

    return {
        'success': True,
        'city': city,
        'count': len(properties),
        'opportunities': properties
    }


def analyze_location_intelligence(params: Dict) -> Dict:
    """
    Analyze properties near a location.

    Parameters:
    - latitude: float (required)
    - longitude: float (required)
    - radius_meters: int (default: 1000)
    - limit: int (default: 20)
    """
    latitude = params.get('latitude')
    longitude = params.get('longitude')
    radius_meters = params.get('radius_meters', 1000)
    limit = params.get('limit', 20)

    if latitude is None or longitude is None:
        return {'success': False, 'error': 'latitude and longitude parameters are required'}

    # Using ST_DWithin with geography for accurate distance
    sql = """
        SELECT property_id, address, city, property_type, market_value,
               latitude, longitude,
               ST_Distance(
                   ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                   ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
               ) as distance_meters
        FROM properties
        WHERE ST_DWithin(
            ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
            ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
            :radius
        )
        ORDER BY distance_meters
        LIMIT :limit
    """

    sql_params = [
        {'name': 'latitude', 'value': {'doubleValue': float(latitude)}},
        {'name': 'longitude', 'value': {'doubleValue': float(longitude)}},
        {'name': 'radius', 'value': {'doubleValue': float(radius_meters)}},
        {'name': 'limit', 'value': {'longValue': limit}}
    ]

    response = execute_sql(sql, sql_params)
    properties = format_rds_response(response)

    return {
        'success': True,
        'latitude': latitude,
        'longitude': longitude,
        'radius_meters': radius_meters,
        'count': len(properties),
        'properties': properties
    }


def check_permit_history(params: Dict) -> Dict:
    """
    Check permit history for a property.

    Parameters:
    - property_id: str (required)
    - limit: int (default: 20)
    """
    property_id = params.get('property_id')
    limit = params.get('limit', 20)

    if not property_id:
        return {'success': False, 'error': 'property_id parameter is required'}

    sql = """
        SELECT permit_id, property_id, permit_type, permit_date,
               issue_date, status, description, contractor,
               estimated_cost, final_cost
        FROM permits
        WHERE property_id = :property_id
        ORDER BY permit_date DESC
        LIMIT :limit
    """

    sql_params = [
        {'name': 'property_id', 'value': {'stringValue': property_id}},
        {'name': 'limit', 'value': {'longValue': limit}}
    ]

    response = execute_sql(sql, sql_params)
    permits = format_rds_response(response)

    return {
        'success': True,
        'property_id': property_id,
        'count': len(permits),
        'permits': permits
    }


# =============================================================================
# LAMBDA HANDLER
# =============================================================================

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for intelligence tools.

    Event format:
    {
        "tool": "search_properties",
        "parameters": {...}
    }
    """
    try:
        print(f"Intelligence function invoked: {json.dumps(event)}")

        tool_name = event.get('tool')
        parameters = event.get('parameters', {})

        if not tool_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing tool name'})
            }

        # Route to appropriate tool function
        tool_functions = {
            'search_properties': search_properties,
            'find_entities': find_entities,
            'analyze_market_trends': analyze_market_trends,
            'cluster_properties': cluster_properties,
            'find_assemblage_opportunities': find_assemblage_opportunities,
            'analyze_location_intelligence': analyze_location_intelligence,
            'check_permit_history': check_permit_history,
        }

        if tool_name not in tool_functions:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown tool: {tool_name}'})
            }

        # Execute tool
        result = tool_functions[tool_name](parameters)

        print(f"Tool executed successfully: {tool_name}")

        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str)  # default=str handles datetime, etc.
        }

    except Exception as e:
        print(f"Intelligence function error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
