"""
Property Search Analyzer

Enables searching/filtering properties by various criteria.
This fills the critical gap where agent can analyze but not search.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, and_, or_
import structlog

logger = structlog.get_logger(__name__)


class PropertySearchAnalyzer:
    """Search and filter properties by criteria"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        property_type: Optional[str] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        min_lot_size: Optional[float] = None,
        max_lot_size: Optional[float] = None,
        zoning: Optional[List[str]] = None,
        city: Optional[str] = None,
        area: Optional[str] = None,
        owner_type: Optional[str] = None,  # "individual", "company", "llc"
        has_permits: Optional[bool] = None,
        recent_sale: Optional[bool] = None,  # Sold in last 180 days
        exclude_owner: Optional[str] = None,
        near_lat: Optional[float] = None,
        near_lng: Optional[float] = None,
        radius_miles: Optional[float] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search properties by multiple criteria

        Args:
            property_type: Property type filter (e.g., "VACANT", "SINGLE FAMILY")
            max_price: Maximum market value
            min_price: Minimum market value
            min_lot_size: Minimum lot size in acres
            max_lot_size: Maximum lot size in acres
            zoning: List of acceptable zoning types
            city: City filter
            area: Geographic area (e.g., "SW Gainesville")
            owner_type: Filter by owner type
            has_permits: Filter properties with/without permits
            recent_sale: Filter recently sold properties
            exclude_owner: Exclude properties owned by this entity
            near_lat: Latitude for geographic search
            near_lng: Longitude for geographic search
            radius_miles: Radius for geographic search
            limit: Maximum results to return

        Returns:
            Dictionary with search results and metadata
        """
        logger.info("property_search_started",
                   property_type=property_type,
                   max_price=max_price,
                   min_lot_size=min_lot_size,
                   zoning=zoning,
                   limit=limit)

        # Build WHERE clauses dynamically
        where_clauses = []
        params = {}

        # Property type filter
        if property_type:
            where_clauses.append("property_type ILIKE :property_type")
            params['property_type'] = f'%{property_type}%'

        # Price filters
        if max_price:
            where_clauses.append("market_value <= :max_price")
            params['max_price'] = max_price

        if min_price:
            where_clauses.append("market_value >= :min_price")
            params['min_price'] = min_price

        # Lot size filters
        if min_lot_size:
            where_clauses.append("lot_size_acres >= :min_lot_size")
            params['min_lot_size'] = min_lot_size

        if max_lot_size:
            where_clauses.append("lot_size_acres <= :max_lot_size")
            params['max_lot_size'] = max_lot_size

        # Zoning filter
        if zoning:
            zoning_conditions = []
            for i, zone in enumerate(zoning):
                param_name = f'zoning_{i}'
                zoning_conditions.append(f"land_zoning_desc ILIKE :{param_name}")
                params[param_name] = f'%{zone}%'
            where_clauses.append(f"({' OR '.join(zoning_conditions)})")

        # City filter
        if city:
            where_clauses.append("city ILIKE :city")
            params['city'] = f'%{city}%'

        # Area filter (address-based)
        if area:
            where_clauses.append("site_address ILIKE :area")
            params['area'] = f'%{area}%'

        # Owner type filter
        if owner_type == "individual":
            where_clauses.append("owner_name NOT ILIKE '%LLC%'")
            where_clauses.append("owner_name NOT ILIKE '%INC%'")
            where_clauses.append("owner_name NOT ILIKE '%CORP%'")
            where_clauses.append("owner_name NOT ILIKE '%LP%'")
        elif owner_type == "company":
            where_clauses.append("(owner_name ILIKE '%LLC%' OR owner_name ILIKE '%INC%' OR owner_name ILIKE '%CORP%')")
        elif owner_type == "llc":
            where_clauses.append("owner_name ILIKE '%LLC%'")

        # Permit filter
        if has_permits is not None:
            if has_permits:
                where_clauses.append("total_permits > 0")
            else:
                where_clauses.append("(total_permits = 0 OR total_permits IS NULL)")

        # Recent sale filter
        if recent_sale:
            where_clauses.append("last_sale_date >= CURRENT_DATE - INTERVAL '180 days'")

        # Exclude owner
        if exclude_owner:
            where_clauses.append("owner_name NOT ILIKE :exclude_owner")
            params['exclude_owner'] = f'%{exclude_owner}%'

        # Geographic filter
        if near_lat and near_lng and radius_miles:
            # Approximate miles to degrees (1 degree ≈ 69 miles)
            lat_range = radius_miles / 69.0
            lng_range = radius_miles / 69.0
            where_clauses.append("""
                latitude::float BETWEEN :min_lat AND :max_lat
                AND longitude::float BETWEEN :min_lng AND :max_lng
            """)
            params['min_lat'] = near_lat - lat_range
            params['max_lat'] = near_lat + lat_range
            params['min_lng'] = near_lng - lng_range
            params['max_lng'] = near_lng + lng_range

        # Base filters
        where_clauses.append("site_address IS NOT NULL")
        where_clauses.append("market_value IS NOT NULL")
        where_clauses.append("market_value > 0")

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Build and execute query
        query = text(f"""
            SELECT
                parcel_id,
                site_address,
                owner_name,
                property_type,
                market_value,
                lot_size_acres,
                year_built,
                land_zoning_desc,
                land_use_desc,
                latitude,
                longitude,
                city,
                last_sale_date,
                last_sale_price,
                total_permits,
                building_details
            FROM bulk_property_records
            WHERE {where_clause}
            ORDER BY market_value / NULLIF(lot_size_acres, 0)
            LIMIT :limit
        """)

        params['limit'] = limit
        result = await self.session.execute(query, params)
        rows = result.fetchall()

        # Format results
        properties = []
        for row in rows:
            properties.append({
                'parcel_id': row[0],
                'address': row[1],
                'owner': row[2],
                'property_type': row[3],
                'market_value': float(row[4]) if row[4] else None,
                'lot_size_acres': float(row[5]) if row[5] else None,
                'price_per_acre': float(row[4] / row[5]) if (row[4] and row[5]) else None,
                'year_built': row[6],
                'zoning': row[7],
                'land_use': row[8],
                'coordinates': {
                    'lat': float(row[9]) if row[9] else None,
                    'lng': float(row[10]) if row[10] else None
                },
                'city': row[11],
                'last_sale_date': row[12].isoformat() if row[12] else None,
                'last_sale_price': float(row[13]) if row[13] else None,
                'total_permits': row[14],
                'building_details': row[15]
            })

        logger.info("property_search_completed",
                   results_found=len(properties),
                   filters_applied=len(where_clauses))

        return {
            'properties': properties,
            'count': len(properties),
            'search_criteria': {
                'property_type': property_type,
                'max_price': max_price,
                'min_lot_size': min_lot_size,
                'zoning': zoning,
                'city': city,
                'area': area,
                'limit': limit
            }
        }

    async def get_entity_properties(
        self,
        entity_name: str,
        property_type: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get actual property list for an entity (not just stats)

        Args:
            entity_name: Owner name
            property_type: Optional filter by property type
            limit: Maximum results

        Returns:
            Dictionary with property list and summary
        """
        logger.info("getting_entity_properties",
                   entity_name=entity_name,
                   property_type=property_type)

        where_clauses = ["owner_name ILIKE :entity_name"]
        params = {'entity_name': f'%{entity_name}%', 'limit': limit}

        if property_type:
            where_clauses.append("property_type ILIKE :property_type")
            params['property_type'] = f'%{property_type}%'

        where_clause = " AND ".join(where_clauses)

        query = text(f"""
            SELECT
                parcel_id,
                site_address,
                property_type,
                market_value,
                lot_size_acres,
                land_zoning_desc,
                latitude,
                longitude,
                last_sale_date,
                last_sale_price,
                year_built,
                total_permits
            FROM bulk_property_records
            WHERE {where_clause}
            ORDER BY last_sale_date DESC NULLS LAST
            LIMIT :limit
        """)

        result = await self.session.execute(query, params)
        rows = result.fetchall()

        properties = []
        for row in rows:
            properties.append({
                'parcel_id': row[0],
                'address': row[1],
                'property_type': row[2],
                'market_value': float(row[3]) if row[3] else None,
                'lot_size_acres': float(row[4]) if row[4] else None,
                'zoning': row[5],
                'coordinates': {
                    'lat': float(row[6]) if row[6] else None,
                    'lng': float(row[7]) if row[7] else None
                },
                'purchase_date': row[8].isoformat() if row[8] else None,
                'purchase_price': float(row[9]) if row[9] else None,
                'year_built': row[10],
                'total_permits': row[11]
            })

        # Calculate summary stats
        total_value = sum(p['market_value'] for p in properties if p['market_value'])
        total_acres = sum(p['lot_size_acres'] for p in properties if p['lot_size_acres'])

        logger.info("entity_properties_retrieved",
                   entity_name=entity_name,
                   properties_found=len(properties))

        return {
            'entity_name': entity_name,
            'properties': properties,
            'count': len(properties),
            'summary': {
                'total_properties': len(properties),
                'total_value': total_value,
                'total_acres': total_acres,
                'avg_value': total_value / len(properties) if properties else 0
            }
        }
