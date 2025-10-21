"""
Intelligence Lambda Function Handler

Handles 9 tools:
1. search_properties - Search properties by criteria (enhanced with 40+ filters)
2. find_entities - Find property owners/entities (uses entities table)
3. analyze_market_trends - Market analysis with absorption rates
4. cluster_properties - Geographic clustering
5. find_assemblage_opportunities - Multi-parcel assemblage detection
6. analyze_location_intelligence - Location-based analysis
7. check_permit_history - Permit history lookup (joins permits + entities)
8. find_comparable_properties - Find comps (actual sale prices)
9. get_property_details - Get ALL property data (80+ fields)

Uses RDS Data API for serverless database access (no VPC needed).
Self-contained - no external module dependencies.
"""

import json
import os
from typing import Dict, Any, List, Tuple
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
                elif 'arrayValue' in value_dict:
                    # Handle arrays (ARRAY_AGG returns arrayValue)
                    array_val = value_dict['arrayValue']
                    if 'stringValues' in array_val:
                        row[col_name] = array_val['stringValues']
                    elif 'longValues' in array_val:
                        row[col_name] = array_val['longValues']
                    elif 'doubleValues' in array_val:
                        row[col_name] = array_val['doubleValues']
                    else:
                        row[col_name] = []
                elif 'isNull' in value_dict and value_dict['isNull']:
                    row[col_name] = None
                else:
                    row[col_name] = None
        results.append(row)

    return results


def _normalize_owner_name(owner_name: Any) -> str:
    """Return an uppercase alphanumeric signature for the owner name."""
    if not owner_name or not isinstance(owner_name, str):
        return ''
    return ''.join(ch for ch in owner_name.upper() if ch.isalnum())


def _apply_owner_limit(properties: List[Dict], per_owner_limit: int, limit: int) -> Tuple[List[Dict], Dict[str, Any]]:
    """Restrict the number of properties per owner and dedupe parcels/coordinates."""
    per_owner_limit = max(1, int(per_owner_limit or 1))
    limit = max(1, int(limit or 1))

    owner_counts: Dict[str, int] = {}
    parcel_seen: set[str] = set()
    coord_seen: set[tuple[float, float]] = set()
    filtered: List[Dict] = []
    removed = 0

    for prop in properties or []:
        if not isinstance(prop, dict):
            continue

        parcel_raw = (prop.get('parcel_id') or '').strip()
        parcel_key = parcel_raw.upper()
        if parcel_key and parcel_key in parcel_seen:
            removed += 1
            continue

        lat = prop.get('latitude')
        lon = prop.get('longitude')
        try:
            coord_key = (round(float(lat), 6), round(float(lon), 6))
        except (TypeError, ValueError):
            coord_key = None

        if coord_key and coord_key in coord_seen:
            removed += 1
            continue

        owner_key = _normalize_owner_name(prop.get('owner_name'))
        if owner_key:
            count = owner_counts.get(owner_key, 0)
            if count >= per_owner_limit:
                removed += 1
                continue
            owner_counts[owner_key] = count + 1

        if parcel_key:
            parcel_seen.add(parcel_key)
        if coord_key:
            coord_seen.add(coord_key)

        filtered.append(prop)
        if len(filtered) >= limit:
            break

    metrics = {
        'removed': removed,
        'unique_owners': len(owner_counts),
    }

    return filtered, metrics


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def search_properties(params: Dict) -> Dict:
    """
    Search properties by criteria with COMPREHENSIVE FILTERS.

    Now uses 40+ database fields for precise filtering.

    Parameters:
    -- Location & Basic
    - city: str
    - property_type: str
    - neighborhood_desc: str (neighborhood name)
    - subdivision_desc: str (subdivision name)

    -- Price & Value
    - min_price: float (market_value)
    - max_price: float (market_value)
    - min_assessed: float (assessed_value)
    - max_assessed: float (assessed_value)

    -- Physical
    - min_sqft: int (square_feet)
    - max_sqft: int (square_feet)
    - min_lot_acres: float
    - max_lot_acres: float
    - bedrooms: int (exact match)
    - min_bedrooms: int
    - bathrooms: float (exact match)
    - min_bathrooms: float
    - min_year_built: int
    - max_year_built: int
    - min_stories: int
    - max_stories: int

    -- Building Features (boolean filters)
    - has_pool: bool
    - has_garage: bool
    - has_porch: bool
    - has_fence: bool
    - has_shed: bool

    -- Building Quality
    - building_condition: str (e.g., "Good", "Fair", "Excellent")
    - building_quality: str
    - roof_type: str
    - heat_type: str
    - ac_type: str

    -- Owner Intelligence
    - owner_state: str (e.g., "FL" for in-state, "!FL" for out-of-state)
    - owner_name: str (partial match)

    -- Tax & Exemptions
    - has_homestead: bool (checks exemption_types)
    - exemption_types: str (partial match on exemption_types_list)

    -- Sale History
    - min_last_sale_price: float
    - max_last_sale_price: float
    - min_last_sale_date: str (YYYY-MM-DD)
    - max_last_sale_date: str (YYYY-MM-DD)
    - sale_qualified: str (e.g., "Q" for qualified)

    -- Other
    - limit: int (default: 20)
    - per_owner_limit: int (default: 2) - maximum properties returned per owner entity
    - order_by: str (default: "market_value_recent", options: "market_value", "market_value_recent", "last_sale_date", "last_sale_recent", "year_built", "year_built_recent", "lot_size_acres", "acreage_then_value", "random")
    """
    # Extract all parameters
    city = params.get('city')
    property_type = params.get('property_type')
    neighborhood_desc = params.get('neighborhood_desc')
    subdivision_desc = params.get('subdivision_desc')

    min_price = params.get('min_price')
    max_price = params.get('max_price')
    min_assessed = params.get('min_assessed')
    max_assessed = params.get('max_assessed')

    min_sqft = params.get('min_sqft')
    max_sqft = params.get('max_sqft')
    min_lot_acres = params.get('min_lot_acres')
    max_lot_acres = params.get('max_lot_acres')

    bedrooms = params.get('bedrooms')
    min_bedrooms = params.get('min_bedrooms')
    bathrooms = params.get('bathrooms')
    min_bathrooms = params.get('min_bathrooms')

    min_year_built = params.get('min_year_built')
    max_year_built = params.get('max_year_built')
    min_stories = params.get('min_stories')
    max_stories = params.get('max_stories')

    has_pool = params.get('has_pool')
    has_garage = params.get('has_garage')
    has_porch = params.get('has_porch')
    has_fence = params.get('has_fence')
    has_shed = params.get('has_shed')

    building_condition = params.get('building_condition')
    building_quality = params.get('building_quality')
    roof_type = params.get('roof_type')
    heat_type = params.get('heat_type')
    ac_type = params.get('ac_type')

    owner_state = params.get('owner_state')
    owner_name = params.get('owner_name')

    has_homestead = params.get('has_homestead')
    exemption_types = params.get('exemption_types')

    min_last_sale_price = params.get('min_last_sale_price')
    max_last_sale_price = params.get('max_last_sale_price')
    min_last_sale_date = params.get('min_last_sale_date')
    max_last_sale_date = params.get('max_last_sale_date')
    sale_qualified = params.get('sale_qualified')

    try:
        limit = int(params.get('limit', 20) or 20)
    except (TypeError, ValueError):
        limit = 20

    try:
        per_owner_limit = int(params.get('per_owner_limit', 2) or 2)
    except (TypeError, ValueError):
        per_owner_limit = 2

    order_by_raw = params.get('order_by') or 'market_value_recent'
    order_by = str(order_by_raw).strip().lower()

    # Build dynamic WHERE clause
    where_clauses = []
    sql_params = []

    # CRITICAL: Validate city parameter (Issue #1 fix)
    if city and city.strip() in ['', '~/', 'null', 'undefined', '*']:
        return {
            'success': False,
            'error': 'Invalid city parameter',
            'message': 'city must be a valid city name (e.g., "Gainesville"), not a wildcard or empty string',
            'received': city
        }

    # Location filters
    if city:
        where_clauses.append("UPPER(city) = UPPER(:city)")
        sql_params.append({'name': 'city', 'value': {'stringValue': city}})

    if property_type:
        where_clauses.append("UPPER(property_type) = UPPER(:property_type)")
        sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

    if neighborhood_desc:
        where_clauses.append("UPPER(neighborhood_desc) LIKE UPPER(:neighborhood)")
        sql_params.append({'name': 'neighborhood', 'value': {'stringValue': f'%{neighborhood_desc}%'}})

    if subdivision_desc:
        where_clauses.append("UPPER(subdivision_desc) LIKE UPPER(:subdivision)")
        sql_params.append({'name': 'subdivision', 'value': {'stringValue': f'%{subdivision_desc}%'}})

    # Price filters (Issue #3 fix: ensure numeric comparison and NULL handling)
    if min_price is not None:
        where_clauses.append("market_value >= :min_price AND market_value IS NOT NULL")
        sql_params.append({'name': 'min_price', 'value': {'doubleValue': float(min_price)}})

    if max_price is not None:
        where_clauses.append("market_value <= :max_price AND market_value IS NOT NULL")
        sql_params.append({'name': 'max_price', 'value': {'doubleValue': float(max_price)}})

    if min_assessed is not None:
        where_clauses.append("assessed_value >= :min_assessed AND assessed_value IS NOT NULL")
        sql_params.append({'name': 'min_assessed', 'value': {'doubleValue': float(min_assessed)}})

    if max_assessed is not None:
        where_clauses.append("assessed_value <= :max_assessed AND assessed_value IS NOT NULL")
        sql_params.append({'name': 'max_assessed', 'value': {'doubleValue': float(max_assessed)}})

    # Physical filters
    if min_sqft is not None:
        where_clauses.append("square_feet >= :min_sqft")
        sql_params.append({'name': 'min_sqft', 'value': {'longValue': int(min_sqft)}})

    if max_sqft is not None:
        where_clauses.append("square_feet <= :max_sqft")
        sql_params.append({'name': 'max_sqft', 'value': {'longValue': int(max_sqft)}})

    if min_lot_acres is not None:
        where_clauses.append("lot_size_acres >= :min_lot")
        sql_params.append({'name': 'min_lot', 'value': {'doubleValue': float(min_lot_acres)}})

    if max_lot_acres is not None:
        where_clauses.append("lot_size_acres <= :max_lot")
        sql_params.append({'name': 'max_lot', 'value': {'doubleValue': float(max_lot_acres)}})

    if bedrooms is not None:
        where_clauses.append("bedrooms = :bedrooms")
        sql_params.append({'name': 'bedrooms', 'value': {'longValue': int(bedrooms)}})

    if min_bedrooms is not None:
        where_clauses.append("bedrooms >= :min_bedrooms")
        sql_params.append({'name': 'min_bedrooms', 'value': {'longValue': int(min_bedrooms)}})

    if bathrooms is not None:
        where_clauses.append("bathrooms = :bathrooms")
        sql_params.append({'name': 'bathrooms', 'value': {'doubleValue': float(bathrooms)}})

    if min_bathrooms is not None:
        where_clauses.append("bathrooms >= :min_bathrooms")
        sql_params.append({'name': 'min_bathrooms', 'value': {'doubleValue': float(min_bathrooms)}})

    if min_year_built is not None:
        where_clauses.append("year_built >= :min_year")
        sql_params.append({'name': 'min_year', 'value': {'longValue': int(min_year_built)}})

    if max_year_built is not None:
        where_clauses.append("year_built <= :max_year")
        sql_params.append({'name': 'max_year', 'value': {'longValue': int(max_year_built)}})

    if min_stories is not None:
        where_clauses.append("stories >= :min_stories")
        sql_params.append({'name': 'min_stories', 'value': {'longValue': int(min_stories)}})

    if max_stories is not None:
        where_clauses.append("stories <= :max_stories")
        sql_params.append({'name': 'max_stories', 'value': {'longValue': int(max_stories)}})

    # Building feature filters (booleans)
    if has_pool is not None:
        where_clauses.append("has_pool = :has_pool")
        sql_params.append({'name': 'has_pool', 'value': {'booleanValue': bool(has_pool)}})

    if has_garage is not None:
        where_clauses.append("has_garage = :has_garage")
        sql_params.append({'name': 'has_garage', 'value': {'booleanValue': bool(has_garage)}})

    if has_porch is not None:
        where_clauses.append("has_porch = :has_porch")
        sql_params.append({'name': 'has_porch', 'value': {'booleanValue': bool(has_porch)}})

    if has_fence is not None:
        where_clauses.append("has_fence = :has_fence")
        sql_params.append({'name': 'has_fence', 'value': {'booleanValue': bool(has_fence)}})

    if has_shed is not None:
        where_clauses.append("has_shed = :has_shed")
        sql_params.append({'name': 'has_shed', 'value': {'booleanValue': bool(has_shed)}})

    # Quality filters
    if building_condition:
        where_clauses.append("UPPER(building_condition) = UPPER(:condition)")
        sql_params.append({'name': 'condition', 'value': {'stringValue': building_condition}})

    if building_quality:
        where_clauses.append("UPPER(building_quality) = UPPER(:quality)")
        sql_params.append({'name': 'quality', 'value': {'stringValue': building_quality}})

    if roof_type:
        where_clauses.append("UPPER(roof_type) LIKE UPPER(:roof)")
        sql_params.append({'name': 'roof', 'value': {'stringValue': f'%{roof_type}%'}})

    if heat_type:
        where_clauses.append("UPPER(heat_type) LIKE UPPER(:heat)")
        sql_params.append({'name': 'heat', 'value': {'stringValue': f'%{heat_type}%'}})

    if ac_type:
        where_clauses.append("UPPER(ac_type) LIKE UPPER(:ac)")
        sql_params.append({'name': 'ac', 'value': {'stringValue': f'%{ac_type}%'}})

    # Owner filters
    if owner_state:
        if owner_state.startswith('!'):
            # Exclude state (e.g., !FL = out-of-state)
            state = owner_state[1:]
            where_clauses.append("UPPER(owner_state) != UPPER(:owner_state)")
            sql_params.append({'name': 'owner_state', 'value': {'stringValue': state}})
        else:
            where_clauses.append("UPPER(owner_state) = UPPER(:owner_state)")
            sql_params.append({'name': 'owner_state', 'value': {'stringValue': owner_state}})

    if owner_name:
        where_clauses.append("UPPER(owner_name) LIKE UPPER(:owner_name)")
        sql_params.append({'name': 'owner_name', 'value': {'stringValue': f'%{owner_name}%'}})

    # Tax/Exemption filters
    if has_homestead is not None:
        if has_homestead:
            where_clauses.append("exemption_types_list LIKE '%HOMESTEAD%'")
        else:
            where_clauses.append("(exemption_types_list NOT LIKE '%HOMESTEAD%' OR exemption_types_list IS NULL)")

    if exemption_types:
        where_clauses.append("UPPER(exemption_types_list) LIKE UPPER(:exemption)")
        sql_params.append({'name': 'exemption', 'value': {'stringValue': f'%{exemption_types}%'}})

    # Sale history filters (NULL-safe: properties without sales excluded when filtering by price)
    if min_last_sale_price is not None:
        where_clauses.append("last_sale_price >= :min_sale_price AND last_sale_price IS NOT NULL")
        sql_params.append({'name': 'min_sale_price', 'value': {'doubleValue': float(min_last_sale_price)}})

    if max_last_sale_price is not None:
        where_clauses.append("last_sale_price <= :max_sale_price AND last_sale_price IS NOT NULL")
        sql_params.append({'name': 'max_sale_price', 'value': {'doubleValue': float(max_last_sale_price)}})

    if min_last_sale_date:
        where_clauses.append("last_sale_date >= :min_sale_date::date")
        sql_params.append({'name': 'min_sale_date', 'value': {'stringValue': min_last_sale_date}})

    if max_last_sale_date:
        where_clauses.append("last_sale_date <= :max_sale_date::date")
        sql_params.append({'name': 'max_sale_date', 'value': {'stringValue': max_last_sale_date}})

    if sale_qualified:
        where_clauses.append("sale_qualified = :sale_qualified")
        sql_params.append({'name': 'sale_qualified', 'value': {'stringValue': sale_qualified}})

    # Construct SQL with expanded field list
    sql = """
        SELECT property_id, parcel_id, site_address as address, city,
               property_type, land_zoning_desc as zoning, land_use_desc as land_use,
               lot_size_acres as lot_size, square_feet as building_area,
               year_built, bedrooms, bathrooms, stories,
               assessed_value, market_value, taxable_value,
               land_value, improvement_value,
               owner_name, owner_state, owner_city,
               latitude, longitude,
               last_sale_date, last_sale_price, sale_qualified,
               has_pool, has_garage, has_porch, has_fence, has_shed,
               building_condition, building_quality,
               neighborhood_desc, subdivision_desc,
               exemption_types_list, total_exemption_amount
        FROM bulk_property_records
    """

    # CRITICAL: Exclude properties with NULL or empty parcel_id (prevents get_property_details failures)
    where_clauses.append("parcel_id IS NOT NULL AND TRIM(parcel_id) != ''")

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    # Order by
    valid_orders = {
        'market_value': 'market_value DESC NULLS LAST',
        'market_value_recent': 'market_value DESC NULLS LAST, last_sale_date DESC NULLS LAST',
        'last_sale_date': 'last_sale_date DESC NULLS LAST',
        'last_sale_recent': 'last_sale_date DESC NULLS LAST, market_value DESC NULLS LAST',
        'year_built': 'year_built DESC NULLS LAST',
        'year_built_recent': 'year_built DESC NULLS LAST, last_sale_date DESC NULLS LAST',
        'lot_size_acres': 'lot_size_acres DESC NULLS LAST',
        'acreage_then_value': 'lot_size_acres DESC NULLS LAST, market_value DESC NULLS LAST',
        'random': 'RANDOM()'
    }

    order_clause = valid_orders.get(order_by, valid_orders['market_value_recent'])
    fetch_limit = min(max(limit, 1) * 3, 500)
    sql += f" ORDER BY {order_clause} LIMIT {fetch_limit}"

    response = execute_sql(sql, sql_params if sql_params else None)
    properties = format_rds_response(response)
    filtered_properties, owner_metrics = _apply_owner_limit(properties, per_owner_limit, limit)

    if owner_metrics.get('removed'):
        print(
            "[search_properties] Applied per-owner cap",
            {
                'removed': owner_metrics['removed'],
                'per_owner_limit': per_owner_limit,
                'returned': len(filtered_properties),
                'total_before_cap': len(properties)
            }
        )

    return {
        'success': True,
        'count': len(filtered_properties),
        'properties': filtered_properties,
        'filters_applied': len(where_clauses),
        'owner_cap_removed': owner_metrics.get('removed', 0),
        'total_before_owner_cap': len(properties),
        'note': 'Enhanced search with 40+ filters plus per-owner diversification and recency-aware ordering'
    }


def find_entities(params: Dict) -> Dict:
    """
    Find property owners/entities with multiple properties (portfolio owners).

    NOW USES entities TABLE FOR ACCURATE DATA:
    - Eliminates duplicates (523 unique entities vs 620 raw owner names)
    - Includes entity_type (llc, corp, individual, government)
    - Joins via canonical_name for better matching

    This tool has TWO MODES:

    MODE 1: DISCOVERY (no entity_name provided)
    - Returns list of entities with property counts
    - Used for: Finding all developers/investors in market

    MODE 2: DEEP DIVE (entity_name provided)
    - Returns full portfolio for specific entity
    - Includes: all properties, acquisition timeline, type breakdown
    - Used for: Portfolio analysis, strategic intent detection

    Parameters:
    - entity_name: str (optional) - If provided, returns full portfolio for this entity
    - city: str (optional) - Filter by city
    - min_properties: int (default: 2) - Minimum properties to qualify (discovery mode)
    - property_type: str (optional) - Filter by property type
    - entity_type: str (optional) - Filter by entity type (llc, corp, individual, government)
    - limit: int (default: 20)

    Returns (Discovery Mode):
        {
            "mode": "discovery",
            "entities": [
                {
                    "entity_name": str,
                    "entity_type": str,  # NEW: llc, corp, individual, government
                    "entity_id": str,    # NEW: UUID for deep dive queries
                    "property_count": int,
                    "total_portfolio_value": float,
                    "avg_property_value": float,
                    "property_types": [str] - Top 3 property types
                }
            ]
        }

    Returns (Deep Dive Mode):
        {
            "mode": "deep_dive",
            "entity_name": str,
            "entity_type": str,      # NEW
            "entity_id": str,        # NEW
            "property_count": int,
            "total_value": float,
            "avg_property_value": float,
            "properties": [...],  # Full property list
            "acquisition_timeline": {...},
            "property_type_breakdown": {...},
            "geographic_concentration": {...}
        }
    """
    entity_name = params.get('entity_name')
    city = params.get('city')
    min_properties = params.get('min_properties', 2)
    property_type = params.get('property_type')
    entity_type_filter = params.get('entity_type')
    limit = params.get('limit', 20)

    # Type coercion: handle float inputs for min_properties
    try:
        min_properties = int(float(min_properties))
    except (ValueError, TypeError):
        min_properties = 2

    # =========================================================================
    # MODE 2: DEEP DIVE - Get specific entity's full portfolio
    # =========================================================================
    if entity_name:
        # First, find the entity in the entities table
        sql_lookup = """
            SELECT id, name, canonical_name, entity_type
            FROM entities
            WHERE UPPER(canonical_name) = UPPER(:entity_name)
               OR UPPER(name) = UPPER(:entity_name)
            LIMIT 1
        """
        lookup_params = [{'name': 'entity_name', 'value': {'stringValue': entity_name}}]

        lookup_response = execute_sql(sql_lookup, lookup_params)
        entity_records = format_rds_response(lookup_response)

        if not entity_records:
            return {
                'success': False,
                'error': f'Entity not found: {entity_name}',
                'note': 'Check spelling or try discovery mode to find entity names',
                'suggestion': 'Use find_entities without entity_name to see all available entities'
            }

        entity_record = entity_records[0]
        entity_id = entity_record.get('id')
        canonical_name = entity_record.get('canonical_name')
        entity_type_val = entity_record.get('entity_type')

        # Now get properties using canonical_name
        where_clauses = ["UPPER(bp.owner_name) = UPPER(:canonical_name)", "bp.market_value > 0"]
        sql_params = [{'name': 'canonical_name', 'value': {'stringValue': canonical_name}}]

        if city:
            where_clauses.append("UPPER(bp.city) = UPPER(:city)")
            sql_params.append({'name': 'city', 'value': {'stringValue': city}})

        if property_type:
            where_clauses.append("bp.property_type = :property_type")
            sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

        where_clause = " WHERE " + " AND ".join(where_clauses)

        sql = f"""
            SELECT
                bp.property_id,
                bp.parcel_id,
                bp.site_address as address,
                bp.city,
                bp.property_type,
                bp.market_value,
                bp.last_sale_date,
                bp.last_sale_price,
                bp.lot_size_acres,
                bp.square_feet as building_area,
                bp.year_built,
                bp.bedrooms,
                bp.bathrooms,
                bp.latitude,
                bp.longitude,
                bp.land_zoning_desc as zoning
            FROM bulk_property_records bp
            {where_clause}
            ORDER BY bp.last_sale_date DESC NULLS LAST
        """

        response = execute_sql(sql, sql_params)
        properties = format_rds_response(response)

        if not properties:
            return {
                'success': False,
                'error': f'No properties found for entity: {entity_name}',
                'note': 'Entity exists but has no properties matching your filters',
                'entity_type': entity_type_val
            }

        # Calculate portfolio analytics
        property_count = len(properties)
        total_value = sum(float(p.get('market_value', 0) or 0) for p in properties)

        # Property type breakdown
        type_breakdown = {}
        for p in properties:
            ptype = p.get('property_type', 'UNKNOWN')
            type_breakdown[ptype] = type_breakdown.get(ptype, 0) + 1

        # Acquisition timeline analysis
        acquisitions_by_year = {}
        acquisitions_by_month = {}
        first_acquisition = None
        last_acquisition = None
        properties_with_sale_dates = 0

        for p in properties:
            sale_date = p.get('last_sale_date')
            if sale_date:
                properties_with_sale_dates += 1
                date_str = str(sale_date)

                # Extract year and month
                if len(date_str) >= 10:  # YYYY-MM-DD format
                    year = date_str[:4]
                    month = date_str[:7]  # YYYY-MM
                    acquisitions_by_year[year] = acquisitions_by_year.get(year, 0) + 1
                    acquisitions_by_month[month] = acquisitions_by_month.get(month, 0) + 1

                    if not first_acquisition or sale_date < first_acquisition:
                        first_acquisition = sale_date
                    if not last_acquisition or sale_date > last_acquisition:
                        last_acquisition = sale_date

        # Geographic concentration
        geo_concentration = {}
        for p in properties:
            city_name = p.get('city', 'UNKNOWN')
            geo_concentration[city_name] = geo_concentration.get(city_name, 0) + 1

        # Zoning concentration
        zoning_concentration = {}
        for p in properties:
            zoning = p.get('zoning', 'UNKNOWN')
            if zoning:
                zoning_concentration[zoning] = zoning_concentration.get(zoning, 0) + 1

        # Price range analysis
        prices = [float(p.get('market_value', 0) or 0) for p in properties if p.get('market_value')]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0

        return {
            'success': True,
            'mode': 'deep_dive',
            'entity_id': entity_id,
            'entity_name': entity_record.get('name'),
            'canonical_name': canonical_name,
            'entity_type': entity_type_val,
            'property_count': property_count,
            'total_value': total_value,
            'avg_property_value': total_value / property_count if property_count > 0 else 0,
            'min_property_value': min_price,
            'max_property_value': max_price,
            'properties': properties,  # FULL property list
            'acquisition_timeline': {
                'first_acquisition': str(first_acquisition) if first_acquisition else None,
                'last_acquisition': str(last_acquisition) if last_acquisition else None,
                'properties_with_dates': properties_with_sale_dates,
                'acquisitions_by_year': dict(sorted(acquisitions_by_year.items())),
                'acquisitions_by_month': dict(sorted(acquisitions_by_month.items())[-12:])  # Last 12 months
            },
            'property_type_breakdown': dict(sorted(type_breakdown.items(), key=lambda x: x[1], reverse=True)),
            'geographic_concentration': dict(sorted(geo_concentration.items(), key=lambda x: x[1], reverse=True)),
            'zoning_concentration': dict(sorted(zoning_concentration.items(), key=lambda x: x[1], reverse=True)),
            'portfolio_pattern_summary': f"{property_count} properties, " +
                                         f"${total_value:,.0f} total value, " +
                                         f"dominant type: {max(type_breakdown, key=type_breakdown.get) if type_breakdown else 'N/A'}, " +
                                         f"price range: ${min_price:,.0f}-${max_price:,.0f}"
        }

    # =========================================================================
    # MODE 1: DISCOVERY - Find entities with multiple properties using entities table
    # =========================================================================

    # Build WHERE clause for property filtering
    property_where = []
    sql_params = []

    if city:
        property_where.append("UPPER(bp.city) = UPPER(:city)")
        sql_params.append({'name': 'city', 'value': {'stringValue': city}})

    if property_type:
        property_where.append("bp.property_type = :property_type")
        sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

    property_where_clause = " AND " + " AND ".join(property_where) if property_where else ""

    # Entity type filter
    entity_type_where = ""
    if entity_type_filter:
        entity_type_where = " AND LOWER(e.entity_type) = LOWER(:entity_type)"
        sql_params.append({'name': 'entity_type', 'value': {'stringValue': entity_type_filter}})

    # Use entities table for accurate, de-duplicated results
    # OPTIMIZED: Simplified query for fast discovery
    sql = f"""
        SELECT
            e.id as entity_id,
            e.name as entity_name,
            e.entity_type,
            COUNT(*) as property_count,
            SUM(bp.market_value) as total_portfolio_value,
            AVG(bp.market_value) as avg_property_value
        FROM entities e
        JOIN bulk_property_records bp ON UPPER(bp.owner_name) = UPPER(e.canonical_name)
        WHERE bp.market_value > 0
          {property_where_clause}
          {entity_type_where}
        GROUP BY e.id, e.name, e.entity_type
        HAVING COUNT(*) >= :min_properties
        ORDER BY COUNT(*) DESC, SUM(bp.market_value) DESC
        LIMIT :limit
    """

    sql_params.append({'name': 'min_properties', 'value': {'longValue': min_properties}})
    sql_params.append({'name': 'limit', 'value': {'longValue': limit}})

    response = execute_sql(sql, sql_params if sql_params else None)
    entities = format_rds_response(response)

    return {
        'success': True,
        'mode': 'discovery',
        'entity_count': len(entities),
        'entities': entities,
        'data_quality': 'Using entities table (523 unique entities, eliminates duplicates)',
        'note': 'Use entity_name from results for deep dive analysis with full property list and property_types breakdown'
    }


def analyze_market_trends(params: Dict) -> Dict:
    """
    Analyze market trends with absorption rates, supply/demand analysis, and actionable insights.

    Uses professional real estate metrics:
    - Absorption Rate: Properties sold / Total inventory (annualized)
    - Months of Inventory: How long to sell current stock at current pace
    - Market Classification: Buyer's (<15%), Neutral (15-20%), Seller's (>20%)
    - Trend Direction: Accelerating, Stable, or Decelerating sales

    Parameters:
    - city: str (required)
    - property_type: str (optional)
    - timeframe_days: int (default: 365) - Days to look back for trend analysis
    """
    city = params.get('city')
    property_type = params.get('property_type')
    timeframe_days = params.get('timeframe_days', 365)

    # Type coercion: handle string/float inputs
    try:
        timeframe_days = int(float(timeframe_days))
    except (ValueError, TypeError):
        timeframe_days = 365

    if not city:
        return {'success': False, 'error': 'city parameter is required'}

    # Validate timeframe
    if timeframe_days < 30:
        timeframe_days = 30  # Minimum 30 days
    elif timeframe_days > 730:
        timeframe_days = 730  # Maximum 2 years

    sql_params = [{'name': 'city', 'value': {'stringValue': city}}]

    where_clause = "WHERE UPPER(city) = UPPER(:city) AND market_value > 0"
    if property_type:
        where_clause += " AND property_type = :property_type"
        sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

    # Calculate half-period for comparison (for trend direction)
    half_period_days = timeframe_days // 2

    # Comprehensive query with absorption metrics
    sql = f"""
        SELECT
            property_type,
            COUNT(*) as inventory_count,

            -- Price metrics
            AVG(market_value) as avg_price,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY market_value) as median_price,
            MIN(market_value) as min_price,
            MAX(market_value) as max_price,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY market_value) as price_p25,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY market_value) as price_p75,

            -- Sales metrics for absorption rate (using timeframe_days parameter)
            COUNT(CASE WHEN last_sale_date >= CURRENT_DATE - INTERVAL '{half_period_days} days' THEN 1 END) as sales_half_period,
            COUNT(CASE WHEN last_sale_date >= CURRENT_DATE - INTERVAL '{timeframe_days} days' THEN 1 END) as sales_full_period,
            AVG(CASE WHEN last_sale_date >= CURRENT_DATE - INTERVAL '{timeframe_days} days' THEN last_sale_price END) as avg_sale_price_period,

            -- Other metrics
            AVG(lot_size_acres) as avg_lot_size,
            SUM(market_value) as total_market_value

        FROM bulk_property_records
        {where_clause}
        GROUP BY property_type
        ORDER BY inventory_count DESC
    """

    response = execute_sql(sql, sql_params)
    trends = format_rds_response(response)

    # Calculate market-level aggregates
    total_inventory = sum(int(t.get('inventory_count', 0) or 0) for t in trends)
    total_value = sum(float(t.get('total_market_value', 0) or 0) for t in trends)
    total_sales_period = sum(int(t.get('sales_full_period', 0) or 0) for t in trends)

    # Enhance each trend with absorption metrics
    for trend in trends:
        inventory = int(trend.get('inventory_count', 0) or 0)
        sales_half = int(trend.get('sales_half_period', 0) or 0)
        sales_full = int(trend.get('sales_full_period', 0) or 0)

        # Absorption rate (annualized percentage)
        # Full period rate (annualized if not already a year)
        annualization_factor = 365 / timeframe_days
        absorption_rate_full = (sales_full / inventory * 100 * annualization_factor) if inventory > 0 else 0

        # Half period rate (annualized)
        absorption_rate_half = (sales_half / inventory * 100 * annualization_factor * 2) if inventory > 0 else 0

        # Months of inventory (at current half-period pace)
        monthly_sales = sales_half / (half_period_days / 30) if sales_half > 0 else 0
        months_of_inventory = (inventory / monthly_sales) if monthly_sales > 0 else float('inf')

        # Market classification (using annualized full period rate)
        if absorption_rate_full < 15:
            market_type = "Buyer's Market"
        elif absorption_rate_full <= 20:
            market_type = "Neutral Market"
        else:
            market_type = "Seller's Market"

        # Trend direction (half period vs full period, both annualized)
        if abs(absorption_rate_half - absorption_rate_full) < 2:
            trend_direction = "Stable"
        elif absorption_rate_half > absorption_rate_full:
            trend_direction = "Accelerating"
        else:
            trend_direction = "Decelerating"

        # Add absorption metrics to trend
        trend['absorption_rate_full_period'] = round(absorption_rate_full, 1)
        trend['absorption_rate_half_period'] = round(absorption_rate_half, 1)
        trend['months_of_inventory'] = round(months_of_inventory, 1) if months_of_inventory != float('inf') else None
        trend['market_type'] = market_type
        trend['trend_direction'] = trend_direction
        trend['timeframe_days'] = timeframe_days

    # Generate professional insights
    insights = []
    recommendations = []

    if trends:
        # Market overview
        dominant = trends[0]
        dom_count = int(dominant.get('inventory_count', 0) or 0)
        pct = (dom_count / total_inventory * 100) if total_inventory > 0 else 0
        insights.append(f"Market Overview: {dominant.get('property_type')} dominates with {pct:.1f}% of {total_inventory:,} total properties")

        # Absorption insights per property type
        for trend in trends:
            pt = trend.get('property_type')
            abs_rate = trend.get('absorption_rate_full_period', 0)
            market_type = trend.get('market_type')
            trend_dir = trend.get('trend_direction')
            months_inv = trend.get('months_of_inventory')

            if abs_rate > 0:
                if months_inv:
                    insights.append(f"{pt}: {abs_rate}% absorption ({market_type}, {trend_dir}) - {months_inv:.1f} months of inventory")
                else:
                    insights.append(f"{pt}: {abs_rate}% absorption ({market_type}, {trend_dir})")

        # Price vs sale analysis
        for trend in trends:
            pt = trend.get('property_type')
            median = float(trend.get('median_price', 0) or 0)
            avg = float(trend.get('avg_price', 0) or 0)
            avg_sale = float(trend.get('avg_sale_price_12m', 0) or 0)

            # Price spread analysis
            if avg > 0 and median > 0:
                diff_pct = ((avg - median) / median) * 100
                if abs(diff_pct) > 15:
                    insights.append(f"{pt} Pricing: Median ${median:,.0f} vs Avg ${avg:,.0f} ({diff_pct:+.1f}%) indicates {'luxury segment' if diff_pct > 0 else 'distressed assets'}")

            # Sale price vs market value
            if avg_sale > 0 and avg > 0:
                sale_premium = ((avg_sale - avg) / avg) * 100
                if abs(sale_premium) > 10:
                    insights.append(f"{pt} Sales: Avg sale ${avg_sale:,.0f} vs market value ${avg:,.0f} ({sale_premium:+.1f}%)")

        # Strategic recommendations
        for trend in trends:
            pt = trend.get('property_type')
            market_type = trend.get('market_type')
            trend_dir = trend.get('trend_direction')
            abs_rate = float(trend.get('absorption_rate_full_period', 0) or 0)
            months_inv = trend.get('months_of_inventory')  # Already converted above

            if market_type == "Buyer's Market" and months_inv and months_inv > 10:
                recommendations.append(f"[BUYER OPPORTUNITY] {pt}: Strong buyer leverage (>10 months inventory). Negotiate aggressively, focus on distressed/motivated sellers")

            if market_type == "Seller's Market" and trend_dir == "Accelerating":
                recommendations.append(f"[HOT MARKET] {pt}: Accelerating ({abs_rate:.1f}% absorption). Act quickly on opportunities, expect competition")

            if trend_dir == "Decelerating" and abs_rate < 12:
                recommendations.append(f"[SLOWING] {pt}: Sales decelerating in buyer's market. Wait for further price corrections or focus on value-add plays")

            if market_type == "Neutral Market" and trend_dir == "Stable":
                recommendations.append(f"[BALANCED] {pt}: Balanced market. Focus on deal quality, fundamentals, and long-term hold strategy")

        # Cross-property opportunities
        if len(trends) >= 2:
            # Find value opportunities (low price, buyer's market)
            value_plays = [t for t in trends if t.get('market_type') == "Buyer's Market" and float(t.get('avg_price', 0) or 0) > 0]
            if value_plays:
                top_value = min(value_plays, key=lambda x: float(x.get('avg_price', 0) or 0))
                recommendations.append(f"💰 Value Play: {top_value.get('property_type')} at ${float(top_value.get('avg_price', 0) or 0):,.0f} avg in buyer's market")

    return {
        'success': True,
        'city': city,
        'property_type': property_type,
        'timeframe_days': timeframe_days,
        'market_overview': {
            'total_inventory': total_inventory,
            'total_market_value': total_value,
            'total_sales_period': total_sales_period,
            'property_types': len(trends)
        },
        'trends': trends,
        'insights': insights,
        'recommendations': recommendations,
        'methodology': f'Professional absorption rate analysis over {timeframe_days} days: <15% buyer\'s market, 15-20% neutral, >20% seller\'s market (annualized)'
    }


def cluster_properties(params: Dict) -> Dict:
    """
    Grid-based property clustering using ST_SnapToGrid (RDS Data API compatible).

    Instead of complex algorithms (DBSCAN, K-means), this uses efficient grid aggregation:
    - Snaps all properties to a grid (e.g., 500m cells)
    - Groups properties by grid cell
    - Aggregates statistics for each cell

    This approach:
    - No window functions (RDS Data API compatible)
    - No self-joins (fast on large datasets)
    - Efficient spatial aggregation
    - Easy to visualize (regular grid)

    Parameters:
    - city: str (required)
    - grid_size_meters: float (default: 500) - Grid cell size in meters
    - min_cluster_size: int (default: 3) - Minimum properties per cluster
    """
    city = params.get('city')
    grid_size_meters = params.get('grid_size_meters', params.get('cluster_distance_meters', 500))
    min_cluster_size = params.get('min_cluster_size', 3)

    if not city:
        return {'success': False, 'error': 'city parameter is required'}

    # Grid-based clustering:
    # 1. Convert meters to degrees (approximate at this latitude: ~111km per degree)
    # 2. Snap all points to grid
    # 3. Group by grid cell
    # 4. Aggregate properties in each cell

    # For latitude ~30° (Gainesville), 1 degree ≈ 111km = 111,000m
    grid_size_degrees = grid_size_meters / 111000.0

    sql = """
        WITH gridded_properties AS (
            SELECT
                parcel_id,
                property_type,
                market_value,
                ST_SnapToGrid(
                    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
                    :grid_size,
                    :grid_size
                ) as grid_cell,
                latitude,
                longitude
            FROM bulk_property_records
            WHERE UPPER(city) = UPPER(:city)
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND property_type IS NOT NULL
              AND market_value > 0
        ),
        property_type_counts AS (
            SELECT
                grid_cell,
                property_type,
                COUNT(*) as type_count,
                AVG(market_value) as type_avg_value
            FROM gridded_properties
            GROUP BY grid_cell, property_type
        ),
        dominant_types AS (
            SELECT DISTINCT ON (grid_cell)
                grid_cell,
                property_type as dominant_type,
                type_count as dominant_count,
                type_avg_value as dominant_avg_value
            FROM property_type_counts
            ORDER BY grid_cell, type_count DESC
        ),
        grid_clusters AS (
            SELECT
                gp.grid_cell,
                ST_X(gp.grid_cell) as grid_center_lon,
                ST_Y(gp.grid_cell) as grid_center_lat,
                COUNT(*) as property_count,
                ROUND(AVG(gp.market_value)::numeric, 2) as avg_market_value,
                SUM(gp.market_value) as total_value,
                MIN(gp.latitude) as min_lat,
                MAX(gp.latitude) as max_lat,
                MIN(gp.longitude) as min_lon,
                MAX(gp.longitude) as max_lon,
                -- Aggregate property IDs
                ARRAY_AGG(gp.parcel_id) as property_ids,
                -- Get top 3 property types with counts
                (
                    SELECT json_agg(json_build_object('type', property_type, 'count', type_count, 'avg_value', ROUND(type_avg_value::numeric, 2)))
                    FROM (
                        SELECT property_type, type_count, type_avg_value
                        FROM property_type_counts ptc
                        WHERE ptc.grid_cell = gp.grid_cell
                        ORDER BY type_count DESC
                        LIMIT 3
                    ) top_types
                ) as top_property_types,
                dt.dominant_type,
                dt.dominant_count,
                dt.dominant_avg_value
            FROM gridded_properties gp
            JOIN dominant_types dt ON gp.grid_cell = dt.grid_cell
            GROUP BY gp.grid_cell, dt.dominant_type, dt.dominant_count, dt.dominant_avg_value
            HAVING COUNT(*) >= :min_size
        ),
        cluster_analysis AS (
            SELECT
                grid_center_lon as center_lon,
                grid_center_lat as center_lat,
                property_count,
                avg_market_value,
                total_value,
                property_ids,
                top_property_types,
                dominant_type,
                -- Cluster purity: what % is the dominant type?
                ROUND((dominant_count::float / property_count * 100)::numeric, 1) as cluster_purity_pct,
                -- Cluster classification
                CASE
                    WHEN dominant_type IN ('SINGLE FAMILY', 'CONDOMINIUM', 'MOBILE HOME', 'MULTIFAMILY', 'MFR <10 UNITS')
                        AND (dominant_count::float / property_count) > 0.7 THEN 'Residential Neighborhood'
                    WHEN dominant_type IN ('OFFICE 1 STORY', 'PROF OFFICES', 'OFF MULTISTORY', 'STORES', 'WAREH/DIST TERM')
                        AND (dominant_count::float / property_count) > 0.6 THEN 'Commercial District'
                    WHEN dominant_type = 'VACANT' AND (dominant_count::float / property_count) > 0.5 THEN 'Development Opportunity Zone'
                    WHEN (dominant_count::float / property_count) < 0.4 THEN 'Mixed-Use Area'
                    ELSE 'Specialized Zone'
                END as cluster_type,
                -- Value density ($ per property)
                ROUND((total_value / property_count)::numeric, 2) as value_per_property,
                -- Calculate actual cluster diameter from bounds
                ROUND(
                    ST_Distance(
                        ST_SetSRID(ST_MakePoint(min_lon, min_lat), 4326)::geography,
                        ST_SetSRID(ST_MakePoint(max_lon, max_lat), 4326)::geography
                    )::numeric,
                    2
                ) as cluster_diameter_meters
            FROM grid_clusters
            ORDER BY property_count DESC, total_value DESC
            LIMIT 20
        )
        SELECT * FROM cluster_analysis
    """

    sql_params = [
        {'name': 'city', 'value': {'stringValue': city}},
        {'name': 'grid_size', 'value': {'doubleValue': grid_size_degrees}},
        {'name': 'min_size', 'value': {'longValue': min_cluster_size}}
    ]

    try:
        response = execute_sql(sql, sql_params)
        clusters = format_rds_response(response)

        return {
            'success': True,
            'city': city,
            'cluster_count': len(clusters),
            'clusters': clusters,
            'parameters': {
                'grid_size_meters': grid_size_meters,
                'min_cluster_size': min_cluster_size
            },
            'method': 'Grid_Based_Clustering',
            'description': f'Properties grouped into {grid_size_meters}m grid cells. Each cluster represents a dense area with {min_cluster_size}+ properties.',
            'use_cases': [
                'Identify high-density development areas',
                'Find hotspots for market analysis',
                'Detect concentrated investment zones',
                'Map property distribution patterns'
            ]
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'city': city,
            'note': 'Grid clustering failed. Try increasing grid_size_meters or reducing dataset size.'
        }


def find_assemblage_opportunities(params: Dict) -> Dict:
    """
    Find REAL assemblage opportunities using professional methodology.

    ENHANCED: Now includes entity intelligence, financial metrics, and development potential.

    Detects ownership patterns where single entities own multiple adjacent parcels.
    This is how institutional developers (D.R. Horton, Lennar, etc.) assemble land.

    Parameters:
    - city: str (required)
    - max_distance_meters: float (default: 200) - Max distance between parcels to consider clustered
    - min_parcels: int (default: 2) - Minimum parcels entity must own to qualify

    Returns:
        {
            "assemblages": [
                {
                    "owner_name": str,
                    "entity_type": str,  # NEW: LLC, Corp, Individual, Government
                    "parcel_count": int,
                    "total_assemblage_value": float,  # NEW: Sum of all property values
                    "total_lot_size_acres": float,    # NEW: Total land area
                    "property_types": [...],          # NEW: Breakdown of property types
                    "cluster_diameter_meters": float,
                    "opportunity_score": int (0-100),
                    "gap_parcels": [...]
                }
            ]
        }
    """
    city = params.get('city')
    max_distance_meters = params.get('max_distance_meters', 200)
    min_parcels = params.get('min_parcels', 2)

    if not city:
        return {'success': False, 'error': 'city parameter is required'}

    # Step 1: Find entities with multiple properties in geographic clusters
    # ENHANCED: Now includes entity_type, financial metrics, and property type breakdown
    sql_entities = """
        WITH entity_portfolios AS (
            SELECT
                bp.owner_name,
                COUNT(*) as parcel_count,
                ARRAY_AGG(bp.parcel_id) as property_ids,
                ST_Collect(ST_SetSRID(ST_MakePoint(bp.longitude, bp.latitude), 4326)) as geom_collection,
                -- NEW: Financial and development metrics
                SUM(bp.market_value) as total_assemblage_value,
                SUM(bp.lot_size_acres) as total_lot_size_acres,
                -- NEW: Property type breakdown
                json_agg(json_build_object('type', bp.property_type, 'value', bp.market_value, 'acres', bp.lot_size_acres)) as properties_detail,
                -- NEW: Entity intelligence
                MAX(e.entity_type) as entity_type  -- Use MAX to pick any non-null value
            FROM bulk_property_records bp
            LEFT JOIN entities e ON e.canonical_name = UPPER(TRIM(bp.owner_name))
            WHERE UPPER(bp.city) = UPPER(:city)
              AND bp.latitude IS NOT NULL
              AND bp.longitude IS NOT NULL
              AND bp.owner_name IS NOT NULL
              AND bp.owner_name != 'UNKNOWN'
              AND bp.owner_name != ''
            GROUP BY bp.owner_name
            HAVING COUNT(*) >= :min_parcels
        ),
        assemblage_candidates AS (
            SELECT
                ep.owner_name,
                ep.parcel_count,
                ep.property_ids,
                ep.total_assemblage_value,
                ep.total_lot_size_acres,
                ep.properties_detail,
                ep.entity_type,
                -- Use ST_Length on ST_LongestLine for geometry collections (more compatible than ST_MaxDistance)
                ST_Length(ST_LongestLine(ep.geom_collection, ep.geom_collection)::geography) as cluster_diameter_meters
            FROM entity_portfolios ep
            WHERE ST_Length(ST_LongestLine(ep.geom_collection, ep.geom_collection)::geography) <= :max_distance
        ),
        property_type_summary AS (
            SELECT
                ac.owner_name,
                ac.parcel_count,
                ac.property_ids,
                ac.total_assemblage_value,
                ac.total_lot_size_acres,
                ac.entity_type,
                ac.cluster_diameter_meters,
                -- Aggregate property types with counts
                (
                    SELECT json_agg(json_build_object('property_type', property_type, 'count', count, 'total_value', total_value))
                    FROM (
                        SELECT
                            (pd->>'type')::text as property_type,
                            COUNT(*) as count,
                            SUM((pd->>'value')::numeric) as total_value
                        FROM assemblage_candidates ac2
                        CROSS JOIN json_array_elements(ac2.properties_detail) pd
                        WHERE ac2.owner_name = ac.owner_name
                        GROUP BY (pd->>'type')::text
                        ORDER BY count DESC
                    ) pt_summary
                ) as property_types
            FROM assemblage_candidates ac
        )
        SELECT
            owner_name,
            entity_type,
            parcel_count,
            total_assemblage_value,
            total_lot_size_acres,
            property_types,
            property_ids,
            cluster_diameter_meters,
            CASE
                WHEN parcel_count >= 5 AND cluster_diameter_meters < 100 THEN 95
                WHEN parcel_count >= 4 AND cluster_diameter_meters < 200 THEN 80
                WHEN parcel_count >= 3 AND cluster_diameter_meters < 300 THEN 65
                WHEN parcel_count >= 2 AND cluster_diameter_meters < 500 THEN 50
                ELSE 30
            END as opportunity_score
        FROM property_type_summary
        ORDER BY opportunity_score DESC, parcel_count DESC
        LIMIT 20
    """

    sql_params = [
        {'name': 'city', 'value': {'stringValue': city}},
        {'name': 'max_distance', 'value': {'doubleValue': float(max_distance_meters)}},
        {'name': 'min_parcels', 'value': {'longValue': min_parcels}}
    ]

    response = execute_sql(sql_entities, sql_params)
    assemblages = format_rds_response(response)

    # Step 2: For top assemblages, find gap parcels (properties between their holdings)
    for i, assemblage in enumerate(assemblages[:5]):  # Only top 5 to save time
        owner_name = assemblage.get('owner_name')

        sql_gaps = """
            WITH owned_properties AS (
                SELECT
                    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography as geom
                FROM bulk_property_records
                WHERE owner_name = :owner_name
                  AND city = :city
                  AND latitude IS NOT NULL
                  AND longitude IS NOT NULL
            ),
            owned_centroid AS (
                SELECT ST_Centroid(ST_Collect(geom)) as centroid
                FROM owned_properties
            )
            SELECT
                p.parcel_id,
                p.site_address as address,
                p.owner_name as gap_owner,
                p.market_value,
                p.lot_size_acres,
                ROUND(ST_Distance(
                    ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography,
                    oc.centroid
                )::numeric, 2) as distance_to_cluster_meters
            FROM bulk_property_records p
            CROSS JOIN owned_centroid oc
            WHERE UPPER(p.city) = UPPER(:city)
              AND p.owner_name != :owner_name
              AND p.latitude IS NOT NULL
              AND p.longitude IS NOT NULL
              AND ST_DWithin(
                  ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography,
                  oc.centroid,
                  :max_distance
              )
            ORDER BY distance_to_cluster_meters
            LIMIT 5
        """

        gap_params = [
            {'name': 'owner_name', 'value': {'stringValue': owner_name}},
            {'name': 'city', 'value': {'stringValue': city}},
            {'name': 'max_distance', 'value': {'doubleValue': float(max_distance_meters) * 1.5}}  # Slightly wider search for gaps
        ]

        try:
            gap_response = execute_sql(sql_gaps, gap_params)
            assemblages[i]['gap_parcels'] = format_rds_response(gap_response)
        except Exception as e:
            print(f"Gap parcel search failed for {owner_name}: {e}")
            assemblages[i]['gap_parcels'] = []

    return {
        'success': True,
        'city': city,
        'assemblages_found': len(assemblages),
        'assemblages': assemblages,
        'methodology': 'Professional assemblage detection: ownership patterns + geographic clustering + entity intelligence + financial metrics + gap identification',
        'scoring_criteria': {
            95: '5+ parcels within 100m (prime assemblage)',
            80: '4+ parcels within 200m (strong assemblage)',
            65: '3+ parcels within 300m (moderate assemblage)',
            50: '2+ parcels within 500m (emerging pattern)',
            30: 'Other configurations'
        },
        'enhancements': {
            'entity_type': 'Identifies LLC/Corp (institutional) vs Individual/Government',
            'total_assemblage_value': 'Sum of all property values (acquisition cost estimate)',
            'total_lot_size_acres': 'Total land area (development potential)',
            'property_types': 'Breakdown of property types in assemblage'
        },
        'use_cases': [
            'Identify institutional developers (D.R. Horton, Lennar, etc.) by entity_type',
            'Estimate total acquisition cost via total_assemblage_value',
            'Calculate development potential via total_lot_size_acres',
            'Distinguish developer assemblages (LLC/Corp) from inherited properties (Individual)',
            'Find gap parcels for acquisition strategy',
            'Detect land banking patterns',
            'Wholesale opportunities to large developers'
        ]
    }


def analyze_location_intelligence(params: Dict) -> Dict:
    """
    Analyze properties near a location.

    Parameters:
    - parcel_id: str (optional) - If provided, looks up coordinates for this property
    - latitude: float (optional) - Direct coordinates (required if no parcel_id)
    - longitude: float (optional) - Direct coordinates (required if no parcel_id)
    - radius_meters: int (default: 1000)
    - limit: int (default: 20)
    """
    parcel_id = params.get('parcel_id')
    latitude = params.get('latitude')
    longitude = params.get('longitude')
    radius_meters = params.get('radius_meters', 1000)
    limit = params.get('limit', 20)

    # If parcel_id provided, look up coordinates first
    if parcel_id and (latitude is None or longitude is None):
        sql_lookup = """
            SELECT latitude, longitude, site_address, city
            FROM bulk_property_records
            WHERE parcel_id = :parcel_id
            LIMIT 1
        """
        lookup_params = [{'name': 'parcel_id', 'value': {'stringValue': str(parcel_id)}}]

        try:
            response = execute_sql(sql_lookup, lookup_params)
            results = format_rds_response(response)

            if not results:
                return {
                    'success': False,
                    'error': f'Property not found: {parcel_id}',
                    'note': 'Check parcel_id spelling or provide coordinates directly'
                }

            prop = results[0]
            latitude = prop.get('latitude')
            longitude = prop.get('longitude')

            if latitude is None or longitude is None:
                return {
                    'success': False,
                    'error': f'Property missing coordinates: {parcel_id}',
                    'property_address': prop.get('site_address'),
                    'note': 'This property has no lat/lon data in database'
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to lookup property: {str(e)}'
            }

    if latitude is None or longitude is None:
        return {
            'success': False,
            'error': 'Must provide either parcel_id or (latitude + longitude)',
            'example': 'parcel_id="12345" OR latitude=29.6516 + longitude=-82.3248'
        }

    # Using ST_DWithin with geography for accurate distance
    sql = """
        SELECT property_id, site_address as address, city, property_type, market_value,
               latitude, longitude,
               ST_Distance(
                   ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                   ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
               ) as distance_meters
        FROM bulk_property_records
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

    OPTIMIZED: Queries permits directly via bulk_property_records (no dependency on properties table).

    Since permits.parcel_id matches bulk_property_records.parcel_id, we can query directly.
    This avoids dependency on the normalized properties table which may be incomplete.

    Parameters:
    - property_id: str (optional) - property_id from bulk_property_records
    - parcel_id: str (optional) - parcel_id to look up
    - limit: int (default: 20)

    Returns:
        {
            "success": bool,
            "parcel_id": str,
            "property_address": str,
            "count": int,
            "permits": [
                {
                    "permit_id": str,
                    "permit_number": str,
                    "permit_type": str,
                    "status": str,
                    "description": str,
                    "project_value": float,
                    "application_date": str,
                    "issued_date": str,
                    "contractor_name": str,    # Resolved from entities
                    "owner_name": str,         # Resolved from entities
                    "applicant_name": str      # Resolved from entities
                }
            ]
        }
    """
    property_id_input = params.get('property_id')
    parcel_id_input = params.get('parcel_id')
    limit = params.get('limit', 20)

    if not property_id_input and not parcel_id_input:
        return {
            'success': False,
            'error': 'Either property_id or parcel_id is required',
            'note': 'Use parcel_id from bulk_property_records.parcel_id'
        }

    # Step 1: Look up property from bulk_property_records
    if property_id_input:
        lookup_sql = """
            SELECT parcel_id, site_address as property_address
            FROM bulk_property_records
            WHERE property_id::text = :property_id
            LIMIT 1
        """
        lookup_params = [{'name': 'property_id', 'value': {'stringValue': str(property_id_input)}}]
    else:
        # Try by parcel_id
        lookup_sql = """
            SELECT parcel_id, site_address as property_address
            FROM bulk_property_records
            WHERE parcel_id = :parcel_id
            LIMIT 1
        """
        lookup_params = [{'name': 'parcel_id', 'value': {'stringValue': str(parcel_id_input)}}]

    try:
        lookup_response = execute_sql(lookup_sql, lookup_params)
        properties = format_rds_response(lookup_response)

        if not properties:
            return {
                'success': False,
                'error': f'Property not found: {property_id_input or parcel_id_input}',
                'note': 'Check parcel_id or property_id'
            }

        property_record = properties[0]
        parcel_id = property_record.get('parcel_id')
        property_address = property_record.get('property_address')

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to lookup property: {str(e)}',
            'note': 'Database query failed'
        }

    # Step 2: Query permits with entity name resolution
    # Match via parcel_id since permits.parcel_id == bulk_property_records.parcel_id
    sql = """
        SELECT
            p.id as permit_id,
            p.permit_number,
            p.permit_type,
            p.status,
            p.project_description as description,
            p.project_value,
            p.application_date,
            p.issued_date,
            p.final_inspection_date,
            p.work_type,
            p.jurisdiction,
            p.site_address as permit_address,
            -- Resolve entity names
            contractor.name as contractor_name,
            owner.name as owner_name,
            applicant.name as applicant_name
        FROM permits p
        LEFT JOIN entities contractor ON p.contractor_entity_id = contractor.id
        LEFT JOIN entities owner ON p.owner_entity_id = owner.id
        LEFT JOIN entities applicant ON p.applicant_entity_id = applicant.id
        WHERE p.parcel_id = :parcel_id
        ORDER BY p.application_date DESC NULLS LAST
        LIMIT :limit
    """

    sql_params = [
        {'name': 'parcel_id', 'value': {'stringValue': str(parcel_id)}},
        {'name': 'limit', 'value': {'longValue': limit}}
    ]

    response = execute_sql(sql, sql_params)
    permits = format_rds_response(response)

    # Calculate summary stats
    total_project_value = sum(float(p.get('project_value', 0) or 0) for p in permits)
    permit_types = {}
    for p in permits:
        ptype = p.get('permit_type', 'UNKNOWN')
        permit_types[ptype] = permit_types.get(ptype, 0) + 1

    return {
        'success': True,
        'parcel_id': parcel_id,
        'property_address': property_address,
        'count': len(permits),
        'permits': permits,
        'summary': {
            'total_permits': len(permits),
            'total_project_value': total_project_value,
            'permit_types': permit_types,
            'has_active_permits': any(p.get('status') in ['ISSUED', 'IN PROGRESS', 'PENDING'] for p in permits)
        },
        'note': 'Permit data queried via parcel_id with full entity name resolution',
        'data_source': 'permits table joined with bulk_property_records and entities'
    }


def find_comparable_properties(params: Dict) -> Dict:
    """
    Find comparable properties (comps) using PROFESSIONAL APPRAISAL METHODOLOGY.

    MASSIVE ENHANCEMENT:
    - Building features matching (pool, garage, condition, quality)
    - Neighborhood matching with bonus scoring
    - Time-decay weighting (recent sales weighted higher)
    - Sale qualification filtering (qualified sales only)
    - Distance-based scoring (closer properties score higher)
    - Multi-factor similarity algorithm

    Strategy (in priority order):
    1. Try recent QUALIFIED sales (12 months) with full feature matching
    2. If insufficient, expand to 24 months
    3. If still insufficient, use market values as fallback

    Parameters:
    - parcel_id: str (optional) - Auto-looks up all property details
    - city: str (required if no parcel_id)
    - property_type: str (required if no parcel_id)
    - target_value: float (required if no parcel_id)
    - bedrooms: int (optional)
    - bathrooms: float (optional)
    - has_pool: bool (optional)
    - has_garage: bool (optional)
    - building_condition: str (optional)
    - neighborhood_desc: str (optional)
    - latitude: float (optional) - For distance scoring
    - longitude: float (optional) - For distance scoring
    - limit: int (default: 10)

    Returns:
        {
            "comparables": [
                {
                    "parcel_id": str,
                    "property_address": str,
                    "sale_price": float,
                    "last_sale_date": str,
                    "similarity_score": float (0-100),
                    "comp_type": "RECENT_SALE" | "MARKET_VALUE",
                    "feature_match": float (0-100),
                    "neighborhood_match": bool,
                    "time_weight": float (0-100),
                    "distance_meters": float (if coords provided)
                }
            ],
            "data_source": str,
            "criteria": {...}
        }
    """
    parcel_id = params.get('parcel_id')
    city = params.get('city')
    property_type = params.get('property_type')
    target_value = params.get('target_value')
    bedrooms = params.get('bedrooms')
    bathrooms = params.get('bathrooms')
    has_pool = params.get('has_pool')
    has_garage = params.get('has_garage')
    building_condition = params.get('building_condition')
    neighborhood_desc = params.get('neighborhood_desc')
    latitude = params.get('latitude')
    longitude = params.get('longitude')
    limit = params.get('limit', 10)

    # If parcel_id provided, look up ALL property details
    if parcel_id:
        sql_lookup = """
            SELECT city, property_type, market_value, bedrooms, bathrooms,
                   has_pool, has_garage, building_condition, building_quality,
                   neighborhood_desc, subdivision_desc,
                   latitude, longitude,
                   site_address
            FROM bulk_property_records
            WHERE parcel_id = :parcel_id
            LIMIT 1
        """
        lookup_params = [{'name': 'parcel_id', 'value': {'stringValue': str(parcel_id)}}]

        try:
            response = execute_sql(sql_lookup, lookup_params)
            results = format_rds_response(response)

            if not results:
                return {
                    'success': False,
                    'error': f'Property not found: {parcel_id}',
                    'note': 'Check parcel_id or provide property details manually'
                }

            prop = results[0]
            # Use looked-up values if not provided by caller
            city = city or prop.get('city')
            property_type = property_type or prop.get('property_type')
            target_value = target_value or prop.get('market_value')
            bedrooms = bedrooms or prop.get('bedrooms')
            bathrooms = bathrooms or prop.get('bathrooms')
            has_pool = has_pool if has_pool is not None else prop.get('has_pool')
            has_garage = has_garage if has_garage is not None else prop.get('has_garage')
            building_condition = building_condition or prop.get('building_condition')
            neighborhood_desc = neighborhood_desc or prop.get('neighborhood_desc')
            latitude = latitude or prop.get('latitude')
            longitude = longitude or prop.get('longitude')

        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to lookup property: {str(e)}'
            }

    if not city or not property_type or target_value is None:
        return {
            'success': False,
            'error': 'Must provide parcel_id OR (city + property_type + target_value)',
            'example': 'parcel_id="12345" OR city="Gainesville" + property_type="SINGLE FAMILY" + target_value=200000'
        }

    # Build comprehensive WHERE clause
    where_clauses = ["UPPER(city) = UPPER(:city)", "property_type = :property_type", "market_value > 0"]
    sql_params = [
        {'name': 'city', 'value': {'stringValue': city}},
        {'name': 'property_type', 'value': {'stringValue': property_type}},
        {'name': 'target_value', 'value': {'doubleValue': float(target_value)}},
        {'name': 'limit', 'value': {'longValue': limit}}
    ]

    # Basic filters
    if bedrooms:
        where_clauses.append("bedrooms = :bedrooms")
        sql_params.append({'name': 'bedrooms', 'value': {'longValue': int(bedrooms)}})

    if bathrooms:
        where_clauses.append("bathrooms >= :bathrooms - 0.5 AND bathrooms <= :bathrooms + 0.5")
        sql_params.append({'name': 'bathrooms', 'value': {'doubleValue': float(bathrooms)}})

    # Building feature matching components (for score calculation)
    pool_match = f"CASE WHEN has_pool = {bool(has_pool)} THEN 10 ELSE 0 END" if has_pool is not None else "0"
    garage_match = f"CASE WHEN has_garage = {bool(has_garage)} THEN 10 ELSE 0 END" if has_garage is not None else "0"
    condition_match = f"CASE WHEN UPPER(building_condition) = UPPER('{building_condition}') THEN 15 ELSE 0 END" if building_condition else "0"
    neighborhood_match = f"CASE WHEN UPPER(neighborhood_desc) = UPPER('{neighborhood_desc}') THEN 20 ELSE 0 END" if neighborhood_desc else "0"

    # Distance component (if coordinates provided)
    if latitude and longitude:
        sql_params.extend([
            {'name': 'lat', 'value': {'doubleValue': float(latitude)}},
            {'name': 'lon', 'value': {'doubleValue': float(longitude)}}
        ])
        distance_calc = """
            ST_Distance(
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            )
        """
        distance_score = f"CASE WHEN {distance_calc} < 1000 THEN 15 WHEN {distance_calc} < 3000 THEN 10 WHEN {distance_calc} < 5000 THEN 5 ELSE 0 END"
        distance_select = f"{distance_calc} as distance_meters,"
    else:
        distance_score = "0"
        distance_select = ""

    # Strategy 1: Try recent QUALIFIED sales (12 months)
    sql_sales = f"""
        SELECT
            parcel_id,
            site_address as property_address,
            last_sale_price as sale_price,
            last_sale_date,
            market_value as assessed_value,
            bedrooms,
            bathrooms,
            has_pool,
            has_garage,
            building_condition,
            neighborhood_desc,
            lot_size_acres,
            year_built,
            sale_qualified,
            {distance_select}
            'RECENT_SALE' as comp_type,
            -- Time-decay weight (more recent = higher score)
            CASE
                WHEN last_sale_date >= CURRENT_DATE - INTERVAL '6 months' THEN 100
                WHEN last_sale_date >= CURRENT_DATE - INTERVAL '9 months' THEN 95
                WHEN last_sale_date >= CURRENT_DATE - INTERVAL '12 months' THEN 90
                ELSE 80
            END as time_weight,
            -- Feature matching score (0-100)
            (
                {pool_match} +
                {garage_match} +
                {condition_match} +
                {neighborhood_match} +
                {distance_score}
            ) as feature_match,
            -- Overall similarity score (price match + feature match + time decay)
            (
                (100 - (ABS(last_sale_price - :target_value) / :target_value * 50)) * 0.4 +
                ({pool_match} + {garage_match} + {condition_match} + {neighborhood_match} + {distance_score}) * 0.4 +
                CASE
                    WHEN last_sale_date >= CURRENT_DATE - INTERVAL '6 months' THEN 100
                    WHEN last_sale_date >= CURRENT_DATE - INTERVAL '9 months' THEN 95
                    WHEN last_sale_date >= CURRENT_DATE - INTERVAL '12 months' THEN 90
                    ELSE 80
                END * 0.2 +
                {f"ABS(bedrooms - {bedrooms}) * -5" if bedrooms else "0"} +
                {f"ABS(bathrooms - {bathrooms}) * -10" if bathrooms else "0"}
            ) as similarity_score
        FROM bulk_property_records
        WHERE {' AND '.join(where_clauses)}
          AND last_sale_price > 0
          AND last_sale_date >= CURRENT_DATE - INTERVAL '12 months'
          AND last_sale_price BETWEEN :target_value * 0.7 AND :target_value * 1.3
          AND (sale_qualified = 'Q' OR sale_qualified IS NULL)  -- Qualified sales only
        ORDER BY similarity_score DESC, last_sale_date DESC
        LIMIT :limit
    """

    try:
        response = execute_sql(sql_sales, sql_params)
        comparables = format_rds_response(response)

        # If we got good results, return them
        if len(comparables) >= 3:
            return {
                'success': True,
                'count': len(comparables),
                'comparables': comparables,
                'data_source': 'recent_sales_12m',
                'note': 'Using qualified sale prices from last 12 months with feature matching',
                'methodology': {
                    'price_weight': '40%',
                    'feature_match': '40% (pool, garage, condition, neighborhood, distance)',
                    'time_decay': '20% (recent sales weighted higher)'
                },
                'criteria': {
                    'city': city,
                    'property_type': property_type,
                    'target_value': target_value,
                    'bedrooms': bedrooms,
                    'bathrooms': bathrooms,
                    'has_pool': has_pool,
                    'has_garage': has_garage,
                    'building_condition': building_condition,
                    'neighborhood': neighborhood_desc
                }
            }

        # Strategy 2: Expand to 24 months if needed
        if len(comparables) < 3:
            sql_sales_24m = sql_sales.replace("INTERVAL '12 months'", "INTERVAL '24 months'")
            # Adjust time weights for 24mo
            sql_sales_24m = sql_sales_24m.replace("WHEN last_sale_date >= CURRENT_DATE - INTERVAL '12 months' THEN 90", "WHEN last_sale_date >= CURRENT_DATE - INTERVAL '18 months' THEN 85")
            sql_sales_24m = sql_sales_24m.replace("ELSE 80", "ELSE 75")

            response = execute_sql(sql_sales_24m, sql_params)
            comparables_24m = format_rds_response(response)

            if len(comparables_24m) >= 3:
                return {
                    'success': True,
                    'count': len(comparables_24m),
                    'comparables': comparables_24m,
                    'data_source': 'recent_sales_24m',
                    'note': 'Using qualified sale prices from last 24 months (expanded search)',
                    'methodology': {
                        'price_weight': '40%',
                        'feature_match': '40%',
                        'time_decay': '20% (older sales, slightly lower weight)'
                    },
                    'criteria': {
                        'city': city,
                        'property_type': property_type,
                        'target_value': target_value
                    }
                }

        # Strategy 3: Fallback to market values (last resort)
        sql_market = f"""
            SELECT
                parcel_id,
                site_address as property_address,
                0 as sale_price,
                NULL as last_sale_date,
                market_value as assessed_value,
                bedrooms,
                bathrooms,
                has_pool,
                has_garage,
                building_condition,
                neighborhood_desc,
                lot_size_acres,
                year_built,
                {distance_select}
                'MARKET_VALUE' as comp_type,
                100 as time_weight,  -- Not time-sensitive for market values
                ({pool_match} + {garage_match} + {condition_match} + {neighborhood_match} + {distance_score}) as feature_match,
                (
                    (100 - (ABS(market_value - :target_value) / :target_value * 50)) * 0.6 +
                    ({pool_match} + {garage_match} + {condition_match} + {neighborhood_match} + {distance_score}) * 0.4
                ) as similarity_score
            FROM bulk_property_records
            WHERE {' AND '.join(where_clauses)}
              AND market_value BETWEEN :target_value * 0.7 AND :target_value * 1.3
            ORDER BY similarity_score DESC
            LIMIT :limit
        """

        response = execute_sql(sql_market, sql_params)
        comparables_market = format_rds_response(response)

        return {
            'success': True,
            'count': len(comparables_market),
            'comparables': comparables_market,
            'data_source': 'market_values',
            'note': 'Using assessed market values (insufficient recent sales data). These are directional only, not appraisal-grade.',
            'warning': 'For professional appraisals, actual sale prices required',
            'methodology': {
                'price_weight': '60%',
                'feature_match': '40%'
            },
            'criteria': {
                'city': city,
                'property_type': property_type,
                'target_value': target_value
            }
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'note': 'Comp search failed. Try adjusting criteria.'
        }
def get_property_details(params: Dict) -> Dict:
    """
    Get COMPLETE property details including ALL database fields.

    This tool provides comprehensive property data for deep analysis.
    Returns 80+ fields including building features, neighborhood context,
    owner information, tax data, and JSONB fields with historical data.

    Parameters:
    - parcel_id: str (optional)
    - property_id: str (optional)
    - address: str (optional) - Partial match on site_address

    Returns: Complete property record with all fields
    """
    parcel_id = params.get('parcel_id')
    property_id = params.get('property_id')
    address = params.get('address')

    if not parcel_id and not property_id and not address:
        return {
            'success': False,
            'error': 'Must provide parcel_id, property_id, or address'
        }

    # Build WHERE clause
    where_clauses = []
    sql_params = []

    if parcel_id:
        # Trim whitespace for robust matching (fixes 70% failure rate issue)
        where_clauses.append("TRIM(parcel_id) = TRIM(:parcel_id)")
        sql_params.append({'name': 'parcel_id', 'value': {'stringValue': str(parcel_id).strip()}})

    if property_id:
        where_clauses.append("property_id::text = :property_id")
        sql_params.append({'name': 'property_id', 'value': {'stringValue': str(property_id)}})

    if address:
        where_clauses.append("UPPER(site_address) LIKE UPPER(:address)")
        sql_params.append({'name': 'address', 'value': {'stringValue': f'%{address}%'}})

    where_clause = " WHERE " + " AND ".join(where_clauses)

    # Return ALL fields (80+ columns)
    sql = f"""
        SELECT
            -- IDs
            parcel_id, property_id, market_id, snapshot_id,

            -- Basic info
            site_address, city, owner_name, mailing_address,
            property_type, use_code, land_use_desc, land_zoning_desc,

            -- Physical characteristics
            year_built, effective_year_built, square_feet, bedrooms, bathrooms, stories,
            lot_size_acres, land_sqft, land_type,

            -- Building details
            has_garage, has_porch, has_pool, has_fence, has_shed,
            roof_type, wall_type, exterior_type, heat_type, ac_type,
            building_quality, building_condition,
            improvement_type, improvement_desc,
            total_improvement_sqft, total_improvement_count, improvement_types_list,
            oldest_improvement_year, newest_improvement_year,

            -- Financial
            assessed_value, market_value, taxable_value,
            land_value, improvement_value,
            last_sale_price, last_sale_date,
            sale_qualified, sale_type_vac_imp, sale_book, sale_page,

            -- Tax/Exemptions
            exemptions, total_exemption_amount, exemption_types_list, exemption_count,
            most_recent_exemption_year,

            -- Location
            latitude, longitude,
            neighborhood_code, neighborhood_desc,
            subdivision_code, subdivision_desc,
            section, township, range_value,
            legal_description,

            -- Owner details
            owner_city, owner_state, owner_zip,

            -- Permit count (summary)
            total_permits,

            -- Valuation
            valuation_year,

            -- JSONB fields with historical data
            sales_history,
            building_details,
            permit_history,
            trim_notice,
            raw_data,

            -- Metadata
            qpublic_enriched_at, qpublic_enrichment_status,
            created_at, updated_at

        FROM bulk_property_records
        {where_clause}
        LIMIT 1
    """

    try:
        response = execute_sql(sql, sql_params)
        properties = format_rds_response(response)

        if not properties:
            return {
                'success': False,
                'error': 'Property not found',
                'note': 'No property matches the provided criteria'
            }

        property_data = properties[0]

        # Parse JSONB fields for better readability
        jsonb_fields = ['sales_history', 'building_details', 'permit_history', 'trim_notice', 'raw_data', 'exemptions']
        for field in jsonb_fields:
            if field in property_data and property_data[field]:
                try:
                    import json
                    if isinstance(property_data[field], str):
                        property_data[field] = json.loads(property_data[field])
                except:
                    pass  # Keep as string if parse fails

        return {
            'success': True,
            'property': property_data,
            'data_quality': {
                'total_fields': len(property_data),
                'populated_fields': sum(1 for v in property_data.values() if v is not None),
                'has_sales_history': bool(property_data.get('sales_history')),
                'has_building_details': bool(property_data.get('building_details')),
                'qpublic_enriched': bool(property_data.get('qpublic_enriched_at'))
            },
            'note': 'Complete property record with all 80+ database fields'
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'note': 'Failed to retrieve property details'
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
            'find_comparable_properties': find_comparable_properties,
            'get_property_details': get_property_details,  # NEW: Returns ALL property data (80+ fields)
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
