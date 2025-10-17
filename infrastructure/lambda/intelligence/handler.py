"""
Intelligence Lambda Function Handler

Handles 9 tools:
1. search_properties - Search properties by criteria
2. find_entities - Find property owners/entities
3. analyze_market_trends - Market analysis
4. cluster_properties - Geographic clustering
5. find_assemblage_opportunities - Multi-parcel assemblage
6. analyze_location_intelligence - Location-based analysis
7. check_permit_history - Permit history lookup
8. find_comparable_properties - Find comps (actual sale prices)
9. identify_investment_opportunities - Deal finding with clear criteria

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
        where_clauses.append("UPPER(city) = UPPER(:city)")
        sql_params.append({'name': 'city', 'value': {'stringValue': city}})

    if property_type:
        where_clauses.append("UPPER(property_type) = UPPER(:property_type)")
        sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

    if min_price is not None:
        where_clauses.append("market_value >= :min_price")
        sql_params.append({'name': 'min_price', 'value': {'doubleValue': float(min_price)}})

    if max_price is not None:
        where_clauses.append("market_value <= :max_price")
        sql_params.append({'name': 'max_price', 'value': {'doubleValue': float(max_price)}})

    # Construct SQL
    sql = """
        SELECT property_id, parcel_id, site_address as address, city,
               property_type, land_zoning_desc as zoning, land_use_desc as land_use,
               lot_size_acres as lot_size, square_feet as building_area,
               year_built, bedrooms, bathrooms, assessed_value, market_value,
               owner_name, latitude, longitude
        FROM bulk_property_records
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
    Find property owners/entities with multiple properties (portfolio owners).

    This is critical for:
    - Institutional investors: Track competitor acquisitions
    - Developers: Monitor institutional activity
    - Wholesalers: Build buyer lists

    Parameters:
    - city: str (optional) - Filter by city
    - min_properties: int (default: 2) - Minimum properties to qualify
    - property_type: str (optional) - Filter by property type
    - limit: int (default: 20)

    Returns:
        {
            "entities": [
                {
                    "entity_name": str,
                    "property_count": int,
                    "total_portfolio_value": float,
                    "avg_property_value": float,
                    "property_types": [str] - Top 3 property types
                }
            ]
        }
    """
    city = params.get('city')
    min_properties = params.get('min_properties', 2)
    property_type = params.get('property_type')
    limit = params.get('limit', 20)

    where_clauses = []
    sql_params = []

    if city:
        where_clauses.append("UPPER(city) = UPPER(:city)")
        sql_params.append({'name': 'city', 'value': {'stringValue': city}})

    if property_type:
        where_clauses.append("property_type = :property_type")
        sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

    where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Find owners with multiple properties
    sql = f"""
        WITH owner_portfolios AS (
            SELECT
                owner_name,
                COUNT(*) as property_count,
                SUM(market_value) as total_portfolio_value,
                AVG(market_value) as avg_property_value,
                -- Get top 3 property types
                (
                    SELECT json_agg(json_build_object('type', property_type, 'count', type_count))
                    FROM (
                        SELECT property_type, COUNT(*) as type_count
                        FROM bulk_property_records bp2
                        WHERE bp2.owner_name = bp.owner_name
                          {("AND UPPER(bp2.city) = UPPER(:city)" if city else "")}
                        GROUP BY property_type
                        ORDER BY type_count DESC
                        LIMIT 3
                    ) top_types
                ) as property_types
            FROM bulk_property_records bp
            {where_clause}
              AND owner_name IS NOT NULL
              AND owner_name != 'UNKNOWN'
              AND owner_name != ''
              AND market_value > 0
            GROUP BY owner_name
            HAVING COUNT(*) >= :min_properties
        )
        SELECT
            owner_name as entity_name,
            property_count,
            total_portfolio_value,
            avg_property_value,
            property_types
        FROM owner_portfolios
        ORDER BY property_count DESC, total_portfolio_value DESC
        LIMIT :limit
    """

    sql_params.append({'name': 'min_properties', 'value': {'longValue': min_properties}})
    sql_params.append({'name': 'limit', 'value': {'longValue': limit}})

    response = execute_sql(sql, sql_params if sql_params else None)
    entities = format_rds_response(response)

    return {
        'success': True,
        'count': len(entities),
        'entities': entities
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
    """
    city = params.get('city')
    property_type = params.get('property_type')

    if not city:
        return {'success': False, 'error': 'city parameter is required'}

    sql_params = [{'name': 'city', 'value': {'stringValue': city}}]

    where_clause = "WHERE UPPER(city) = UPPER(:city) AND market_value > 0"
    if property_type:
        where_clause += " AND property_type = :property_type"
        sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

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

            -- Sales metrics for absorption rate
            COUNT(CASE WHEN last_sale_date >= CURRENT_DATE - INTERVAL '6 months' THEN 1 END) as sales_6m,
            COUNT(CASE WHEN last_sale_date >= CURRENT_DATE - INTERVAL '12 months' THEN 1 END) as sales_12m,
            AVG(CASE WHEN last_sale_date >= CURRENT_DATE - INTERVAL '12 months' THEN last_sale_price END) as avg_sale_price_12m,

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
    total_sales_12m = sum(int(t.get('sales_12m', 0) or 0) for t in trends)

    # Enhance each trend with absorption metrics
    for trend in trends:
        inventory = int(trend.get('inventory_count', 0) or 0)
        sales_6m = int(trend.get('sales_6m', 0) or 0)
        sales_12m = int(trend.get('sales_12m', 0) or 0)

        # Absorption rate (annualized percentage)
        absorption_rate_6m = (sales_6m * 2 / inventory * 100) if inventory > 0 else 0
        absorption_rate_12m = (sales_12m / inventory * 100) if inventory > 0 else 0

        # Months of inventory (at current 6-month pace)
        monthly_sales = sales_6m / 6 if sales_6m > 0 else 0
        months_of_inventory = (inventory / monthly_sales) if monthly_sales > 0 else float('inf')

        # Market classification
        if absorption_rate_12m < 15:
            market_type = "Buyer's Market"
        elif absorption_rate_12m <= 20:
            market_type = "Neutral Market"
        else:
            market_type = "Seller's Market"

        # Trend direction (6m vs 12m annualized)
        if abs(absorption_rate_6m - absorption_rate_12m) < 2:
            trend_direction = "Stable"
        elif absorption_rate_6m > absorption_rate_12m:
            trend_direction = "Accelerating"
        else:
            trend_direction = "Decelerating"

        # Add absorption metrics to trend
        trend['absorption_rate_12m'] = round(absorption_rate_12m, 1)
        trend['absorption_rate_6m'] = round(absorption_rate_6m, 1)
        trend['months_of_inventory'] = round(months_of_inventory, 1) if months_of_inventory != float('inf') else None
        trend['market_type'] = market_type
        trend['trend_direction'] = trend_direction

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
            abs_rate = trend.get('absorption_rate_12m', 0)
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
            abs_rate = float(trend.get('absorption_rate_12m', 0) or 0)
            months_inv = trend.get('months_of_inventory')  # Already converted above

            # Buyer's market opportunities
            if market_type == "Buyer's Market" and months_inv and months_inv > 10:
                recommendations.append(f"🎯 {pt}: Strong buyer leverage (>10 months inventory). Negotiate aggressively, focus on distressed/motivated sellers")

            # Seller's market - act fast
            if market_type == "Seller's Market" and trend_dir == "Accelerating":
                recommendations.append(f"⚡ {pt}: Hot market accelerating ({abs_rate:.1f}% absorption). Act quickly on opportunities, expect competition")

            # Trend reversals
            if trend_dir == "Decelerating" and abs_rate < 12:
                recommendations.append(f"📉 {pt}: Sales decelerating in buyer's market. Wait for further price corrections or focus on value-add plays")

            # Stable neutral markets
            if market_type == "Neutral Market" and trend_dir == "Stable":
                recommendations.append(f"⚖️ {pt}: Balanced market. Focus on deal quality, fundamentals, and long-term hold strategy")

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
        'market_overview': {
            'total_inventory': total_inventory,
            'total_market_value': total_value,
            'total_sales_12m': total_sales_12m,
            'property_types': len(trends)
        },
        'trends': trends,
        'insights': insights,
        'recommendations': recommendations,
        'methodology': 'Professional absorption rate analysis: <15% buyer\'s market, 15-20% neutral, >20% seller\'s market'
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
                    "parcel_count": int,
                    "cluster_diameter_meters": float,
                    "opportunity_score": int (0-100),
                    "gap_parcels": [...]  # Available parcels between owned properties
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
    # Note: Use geometry for ST_Collect/ST_MaxDistance, then filter by geography distance
    sql_entities = """
        WITH entity_portfolios AS (
            SELECT
                owner_name,
                COUNT(*) as parcel_count,
                ARRAY_AGG(parcel_id) as property_ids,
                ST_Collect(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) as geom_collection
            FROM bulk_property_records
            WHERE UPPER(city) = UPPER(:city)
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND owner_name IS NOT NULL
              AND owner_name != 'UNKNOWN'
              AND owner_name != ''
            GROUP BY owner_name
            HAVING COUNT(*) >= :min_parcels
        ),
        assemblage_candidates AS (
            SELECT
                ep.owner_name,
                ep.parcel_count,
                ep.property_ids,
                -- Use ST_Length on ST_LongestLine for geometry collections (more compatible than ST_MaxDistance)
                ST_Length(ST_LongestLine(ep.geom_collection, ep.geom_collection)::geography) as cluster_diameter_meters
            FROM entity_portfolios ep
            WHERE ST_Length(ST_LongestLine(ep.geom_collection, ep.geom_collection)::geography) <= :max_distance
        )
        SELECT
            ac.owner_name,
            ac.parcel_count,
            ac.cluster_diameter_meters,
            CASE
                WHEN ac.parcel_count >= 5 AND ac.cluster_diameter_meters < 100 THEN 95
                WHEN ac.parcel_count >= 4 AND ac.cluster_diameter_meters < 200 THEN 80
                WHEN ac.parcel_count >= 3 AND ac.cluster_diameter_meters < 300 THEN 65
                WHEN ac.parcel_count >= 2 AND ac.cluster_diameter_meters < 500 THEN 50
                ELSE 30
            END as opportunity_score
        FROM assemblage_candidates ac
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
        'methodology': 'Professional assemblage detection: ownership patterns + geographic clustering + gap identification',
        'scoring_criteria': {
            95: '5+ parcels within 100m (prime assemblage)',
            80: '4+ parcels within 200m (strong assemblage)',
            65: '3+ parcels within 300m (moderate assemblage)',
            50: '2+ parcels within 500m (emerging pattern)',
            30: 'Other configurations'
        },
        'use_cases': [
            'Identify institutional developers (D.R. Horton, Lennar, etc.)',
            'Find gap parcels for acquisition strategy',
            'Detect land banking patterns',
            'Wholesale opportunities to large developers'
        ]
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

    Parameters:
    - property_id: str (required)
    - limit: int (default: 20)
    """
    property_id = params.get('property_id')
    limit = params.get('limit', 20)

    if not property_id:
        return {'success': False, 'error': 'property_id parameter is required'}

    sql = """
        SELECT id as permit_id, permit_number, property_id, permit_type,
               application_date as permit_date, issued_date as issue_date,
               status, project_description as description,
               contractor_entity_id as contractor, project_value as estimated_cost
        FROM permits
        WHERE property_id::text = :property_id
        ORDER BY application_date DESC
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


def find_comparable_properties(params: Dict) -> Dict:
    """
    Find comparable properties (comps) for appraisal/pricing.
    
    AGENT-READY: Always returns useful results with fallback logic
    
    Strategy:
    1. Try recent sales (12 months) with actual sale prices
    2. If insufficient, expand to 24 months
    3. If still insufficient, use market values as fallback
    
    Parameters:
    - city: str (required)
    - property_type: str (required)
    - target_value: float (required)
    - bedrooms: int (optional)
    - bathrooms: float (optional)
    - limit: int (default: 10)
    """
    city = params.get('city')
    property_type = params.get('property_type')
    target_value = params.get('target_value')
    bedrooms = params.get('bedrooms')
    bathrooms = params.get('bathrooms')
    limit = params.get('limit', 10)

    if not city or not property_type or target_value is None:
        return {'success': False, 'error': 'city, property_type, and target_value are required'}

    # Try strategy 1: Recent sales (12 months)
    where_clauses = ["UPPER(city) = UPPER(:city)", "property_type = :property_type", "market_value > 0"]
    sql_params = [
        {'name': 'city', 'value': {'stringValue': city}},
        {'name': 'property_type', 'value': {'stringValue': property_type}},
        {'name': 'target_value', 'value': {'doubleValue': float(target_value)}},
        {'name': 'limit', 'value': {'longValue': limit}}
    ]

    if bedrooms:
        where_clauses.append("bedrooms = :bedrooms")
        sql_params.append({'name': 'bedrooms', 'value': {'longValue': int(bedrooms)}})

    if bathrooms:
        where_clauses.append("bathrooms >= :bathrooms - 0.5 AND bathrooms <= :bathrooms + 0.5")
        sql_params.append({'name': 'bathrooms', 'value': {'doubleValue': float(bathrooms)}})

    # Strategy 1: Try recent sales first
    sql_sales = f"""
        SELECT
            parcel_id,
            site_address as property_address,
            last_sale_price as sale_price,
            last_sale_date,
            market_value as assessed_value,
            bedrooms,
            bathrooms,
            lot_size_acres,
            year_built,
            'RECENT_SALE' as comp_type,
            (100 - (
                ABS(last_sale_price - :target_value) / :target_value * 50 +
                {f"ABS(bedrooms - {bedrooms}) * 5" if bedrooms else "0"} +
                {f"ABS(bathrooms - {bathrooms}) * 10" if bathrooms else "0"}
            )) as similarity_score
        FROM bulk_property_records
        WHERE {' AND '.join(where_clauses)}
          AND last_sale_price > 0
          AND last_sale_date >= CURRENT_DATE - INTERVAL '12 months'
          AND last_sale_price BETWEEN :target_value * 0.7 AND :target_value * 1.3
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
                'note': 'Using actual sale prices from last 12 months',
                'criteria': {
                    'city': city,
                    'property_type': property_type,
                    'target_value': target_value
                }
            }

        # Strategy 2: Expand to 24 months if needed
        if len(comparables) < 3:
            sql_sales_24m = sql_sales.replace("INTERVAL '12 months'", "INTERVAL '24 months'")
            response = execute_sql(sql_sales_24m, sql_params)
            comparables_24m = format_rds_response(response)

            if len(comparables_24m) >= 3:
                return {
                    'success': True,
                    'count': len(comparables_24m),
                    'comparables': comparables_24m,
                    'data_source': 'recent_sales_24m',
                    'note': 'Using actual sale prices from last 24 months (limited 12m data)',
                    'criteria': {
                        'city': city,
                        'property_type': property_type,
                        'target_value': target_value
                    }
                }

        # Strategy 3: Fallback to market values
        sql_market = f"""
            SELECT
                parcel_id,
                site_address as property_address,
                0 as sale_price,
                NULL as last_sale_date,
                market_value as assessed_value,
                bedrooms,
                bathrooms,
                lot_size_acres,
                year_built,
                'MARKET_VALUE' as comp_type,
                (100 - (
                    ABS(market_value - :target_value) / :target_value * 50 +
                    {f"ABS(bedrooms - {bedrooms}) * 5" if bedrooms else "0"} +
                    {f"ABS(bathrooms - {bathrooms}) * 10" if bathrooms else "0"}
                )) as similarity_score
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

def identify_investment_opportunities(params: Dict) -> Dict:
    """
    Identify investment opportunities with CLEAR CRITERIA.
    
    AGENT-READY: Always returns structured results
    
    Opportunity types:
    1. UNDERVALUED: Market value < 80% of type average
    2. HIGH_EQUITY: 30%+ appreciation since purchase
    3. DEVELOPMENT: Vacant land
    4. LONG_HOLD: 20+ years ownership (potential motivation)
    """
    city = params.get('city')
    property_type = params.get('property_type')
    min_value = params.get('min_value')
    max_value = params.get('max_value')
    limit = params.get('limit', 20)

    if not city:
        return {'success': False, 'error': 'city parameter is required'}

    where_clauses = ["UPPER(city) = UPPER(:city)", "market_value > 0"]
    sql_params = [
        {'name': 'city', 'value': {'stringValue': city}},
        {'name': 'limit', 'value': {'longValue': limit}}
    ]

    if property_type:
        where_clauses.append("property_type = :property_type")
        sql_params.append({'name': 'property_type', 'value': {'stringValue': property_type}})

    if min_value:
        where_clauses.append("market_value >= :min_value")
        sql_params.append({'name': 'min_value', 'value': {'doubleValue': float(min_value)}})

    if max_value:
        where_clauses.append("market_value <= :max_value")
        sql_params.append({'name': 'max_value', 'value': {'doubleValue': float(max_value)}})

    where_clause = " WHERE " + " AND ".join(where_clauses)

    sql = f"""
        WITH property_averages AS (
            SELECT
                property_type,
                AVG(market_value) as avg_market_value,
                COUNT(*) as type_count
            FROM bulk_property_records
            WHERE UPPER(city) = UPPER(:city)
              AND market_value > 0
            GROUP BY property_type
        ),
        opportunities AS (
            SELECT
                bp.parcel_id,
                bp.site_address as property_address,
                bp.property_type,
                bp.market_value,
                bp.last_sale_price,
                bp.last_sale_date,
                COALESCE(pa.avg_market_value, bp.market_value) as type_avg_value,
                -- Value ratio
                (bp.market_value / NULLIF(pa.avg_market_value, bp.market_value)) as value_ratio,
                -- Equity percentage
                CASE
                    WHEN bp.last_sale_price > 0 AND bp.last_sale_date IS NOT NULL THEN
                        ((bp.market_value - bp.last_sale_price) / NULLIF(bp.last_sale_price, 1) * 100)
                    ELSE NULL
                END as equity_pct,
                -- Opportunity classification
                CASE
                    WHEN bp.market_value < COALESCE(pa.avg_market_value, bp.market_value) * 0.8 THEN 'UNDERVALUED'
                    WHEN bp.property_type IN ('VACANT', 'VACANT COMM', 'COUNTY VACANT/XFEATURES') THEN 'DEVELOPMENT'
                    WHEN bp.last_sale_price > 0 AND bp.market_value > bp.last_sale_price * 1.3 THEN 'HIGH_EQUITY'
                    WHEN bp.last_sale_date < CURRENT_DATE - INTERVAL '20 years' AND bp.last_sale_date IS NOT NULL THEN 'LONG_HOLD'
                    ELSE 'STANDARD'
                END as opportunity_type,
                -- Investment score
                (
                    CASE WHEN bp.market_value < COALESCE(pa.avg_market_value, bp.market_value) * 0.8 THEN 40 ELSE 0 END +
                    CASE
                        WHEN bp.last_sale_price > 0 AND bp.market_value > bp.last_sale_price * 1.5 THEN 30
                        WHEN bp.last_sale_price > 0 AND bp.market_value > bp.last_sale_price * 1.3 THEN 20
                        ELSE 0
                    END +
                    CASE WHEN bp.property_type IN ('VACANT', 'VACANT COMM') THEN 30 ELSE 0 END +
                    CASE WHEN bp.last_sale_date < CURRENT_DATE - INTERVAL '20 years' AND bp.last_sale_date IS NOT NULL THEN 10 ELSE 0 END
                ) as investment_score
            FROM bulk_property_records bp
            LEFT JOIN property_averages pa ON bp.property_type = pa.property_type
            {where_clause}
        )
        SELECT *
        FROM opportunities
        WHERE investment_score >= 20 OR opportunity_type != 'STANDARD'
        ORDER BY investment_score DESC, market_value ASC
        LIMIT :limit
    """

    try:
        response = execute_sql(sql, sql_params)
        opportunities = format_rds_response(response)

        # Categorize opportunities
        by_type = {}
        for opp in opportunities:
            opp_type = opp.get('opportunity_type', 'STANDARD')
            if opp_type not in by_type:
                by_type[opp_type] = []
            by_type[opp_type].append(opp)

        return {
            'success': True,
            'count': len(opportunities),
            'opportunities': opportunities,
            'summary': {
                'by_type': {k: len(v) for k, v in by_type.items()},
                'avg_score': sum(float(o.get('investment_score', 0) or 0) for o in opportunities) / len(opportunities) if opportunities else 0
            },
            'criteria': {
                'city': city,
                'property_type': property_type,
                'value_range': f"${min_value:,.0f} - ${max_value:,.0f}" if min_value and max_value else "All"
            },
            'opportunity_definitions': {
                'UNDERVALUED': 'Market value < 80% of property type average',
                'HIGH_EQUITY': '30%+ appreciation since last sale',
                'DEVELOPMENT': 'Vacant land - development potential',
                'LONG_HOLD': '20+ years ownership - potential motivated seller'
            }
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'note': 'Investment opportunity search failed'
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
            'identify_investment_opportunities': identify_investment_opportunities,
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
