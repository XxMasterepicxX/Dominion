"""
ContextBuilder - Build comprehensive 50k token context for Gemini

Instead of 1k token summary, build full context:
- Full property details (not summary)
- Complete owner portfolio (all properties, not just count)
- Neighborhood context (comps, trends)
- Permits, crime, council, news data

Research shows:
- 50k tokens = only 5% of Gemini's 1M capacity
- More context = better analysis
- Put query at END of context for best performance
"""

import json
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

logger = structlog.get_logger(__name__)


class ContextBuilder:
    """Build rich context from database for property analysis"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_full_context(
        self,
        property_address: str = None,
        parcel_id: str = None
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for property analysis.

        Args:
            property_address: Property address
            parcel_id: Alternative - parcel ID

        Returns:
            Full context dict with ~50k tokens of data
        """
        logger.info("building_full_context",
                   address=property_address,
                   parcel_id=parcel_id)

        context = {
            'property': None,
            'owner_portfolio': [],
            'owner_activity': [],
            'neighborhood': {},
            'permits': {},
            'crime': [],
            'council': [],
            'news': []
        }

        # 1. Find property
        property_data = await self._find_property(property_address, parcel_id)
        if not property_data:
            return context

        context['property'] = property_data

        # 2. Get complete owner portfolio (ALL properties, not summary)
        if property_data.get('owner_name'):
            context['owner_portfolio'] = await self._get_full_portfolio(
                property_data['owner_name']
            )

            # 3. Get owner activity (recent acquisitions/dispositions)
            context['owner_activity'] = await self._get_owner_activity(
                property_data['owner_name'],
                days=180
            )

        # 4. Get neighborhood context
        if property_data.get('latitude') and property_data.get('longitude'):
            context['neighborhood'] = await self._get_neighborhood_context(
                lat=property_data['latitude'],
                lon=property_data['longitude'],
                radius_miles=0.5
            )

        # 5. Get permit history
        context['permits'] = await self._get_permits(
            parcel_id=property_data['parcel_id'],
            address=property_data['site_address']
        )

        # 6. Get crime data
        if property_data.get('latitude') and property_data.get('longitude'):
            context['crime'] = await self._get_crime_data(
                lat=property_data['latitude'],
                lon=property_data['longitude'],
                radius_miles=0.5,
                days=365
            )

        # 7. Get council activity
        context['council'] = await self._get_council_activity(
            neighborhood_code=property_data.get('neighborhood_code'),
            owner_name=property_data.get('owner_name'),
            days=180
            )

        # 8. Get news coverage
        context['news'] = await self._get_news_coverage(
            owner_name=property_data.get('owner_name'),
            neighborhood_code=property_data.get('neighborhood_code'),
            days=180
        )

        # 9. Analyze geographic clustering if owner has multiple recent purchases
        if len(context['owner_activity']) >= 4:
            context['geographic_analysis'] = self._analyze_geographic_clustering(
                context['owner_portfolio']
            )
        else:
            context['geographic_analysis'] = None

        logger.info("context_built",
                   property_found=context['property'] is not None,
                   portfolio_size=len(context['owner_portfolio']),
                   recent_activity=len(context['owner_activity']),
                   permits=len(context['permits'].get('at_property', [])),
                   crime_incidents=len(context['crime']),
                   council_mentions=len(context['council']),
                   news_articles=len(context['news']),
                   geographic_clustering=context['geographic_analysis'] is not None)

        return context

    async def _find_property(
        self,
        address: str = None,
        parcel_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """Find property and return ALL fields"""

        if address:
            query = text("""
                SELECT
                    id,
                    parcel_id,
                    site_address,
                    owner_name,
                    mailing_address,
                    property_type,
                    land_zoning_code,
                    land_zoning_desc,
                    land_use_code,
                    land_use_desc,
                    year_built,
                    square_feet,
                    lot_size_acres,
                    assessed_value,
                    market_value,
                    taxable_value,
                    land_value,
                    improvement_value,
                    bedrooms,
                    bathrooms,
                    last_sale_date,
                    last_sale_price,
                    latitude,
                    longitude,
                    use_code,
                    city,
                    neighborhood_code,
                    exemptions,
                    sales_history,
                    building_details,
                    trim_notice,
                    total_permits
                FROM bulk_property_records
                WHERE LOWER(site_address) LIKE LOWER(:address)
                LIMIT 1
            """)
            result = await self.session.execute(query, {'address': f'%{address}%'})
        elif parcel_id:
            query = text("""
                SELECT
                    id,
                    parcel_id,
                    site_address,
                    owner_name,
                    mailing_address,
                    property_type,
                    land_zoning_code,
                    land_zoning_desc,
                    land_use_code,
                    land_use_desc,
                    year_built,
                    square_feet,
                    lot_size_acres,
                    assessed_value,
                    market_value,
                    taxable_value,
                    land_value,
                    improvement_value,
                    bedrooms,
                    bathrooms,
                    last_sale_date,
                    last_sale_price,
                    latitude,
                    longitude,
                    use_code,
                    city,
                    neighborhood_code,
                    exemptions,
                    sales_history,
                    building_details,
                    trim_notice,
                    total_permits
                FROM bulk_property_records
                WHERE parcel_id = :parcel_id
                LIMIT 1
            """)
            result = await self.session.execute(query, {'parcel_id': parcel_id})
        else:
            return None

        row = result.fetchone()
        if not row:
            return None

        return dict(row._mapping)

    async def _get_full_portfolio(self, owner_name: str) -> List[Dict[str, Any]]:
        """Get ALL properties owned by this owner (not summary)"""

        query = text("""
            SELECT
                parcel_id,
                site_address,
                property_type,
                market_value,
                last_sale_date,
                last_sale_price,
                year_built,
                square_feet,
                lot_size_acres,
                use_code
            FROM bulk_property_records
            WHERE owner_name = :owner_name
            ORDER BY last_sale_date DESC NULLS LAST
        """)

        result = await self.session.execute(query, {'owner_name': owner_name})
        return [dict(row._mapping) for row in result]

    async def _get_owner_activity(
        self,
        owner_name: str,
        days: int = 180
    ) -> List[Dict[str, Any]]:
        """Get recent acquisitions/dispositions"""

        query = text("""
            SELECT
                parcel_id,
                site_address,
                property_type,
                market_value,
                last_sale_date,
                last_sale_price,
                use_code
            FROM bulk_property_records
            WHERE owner_name = :owner_name
            AND last_sale_date >= CURRENT_DATE - INTERVAL '180 days'
            ORDER BY last_sale_date DESC
        """)

        result = await self.session.execute(query, {'owner_name': owner_name})
        return [dict(row._mapping) for row in result]

    async def _get_neighborhood_context(
        self,
        lat: float,
        lon: float,
        radius_miles: float = 0.5
    ) -> Dict[str, Any]:
        """Get neighborhood comps and trends"""

        # Convert miles to degrees (rough approximation)
        # 1 degree latitude ≈ 69 miles
        lat_range = radius_miles / 69.0
        lon_range = radius_miles / 69.0  # Simplified, varies by latitude

        # Convert to float to avoid Decimal math issues
        lat = float(lat)
        lon = float(lon)

        query = text("""
            SELECT
                COUNT(*) as total_properties,
                AVG(market_value) as avg_market_value,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY market_value) as median_value,
                AVG(square_feet) as avg_sqft,
                COUNT(CASE WHEN last_sale_date >= CURRENT_DATE - INTERVAL '180 days' THEN 1 END) as recent_sales
            FROM bulk_property_records
            WHERE latitude::float BETWEEN :min_lat AND :max_lat
            AND longitude::float BETWEEN :min_lon AND :max_lon
            AND market_value > 0
        """)

        result = await self.session.execute(query, {
            'min_lat': lat - lat_range,
            'max_lat': lat + lat_range,
            'min_lon': lon - lon_range,
            'max_lon': lon + lon_range
        })

        row = result.fetchone()
        return dict(row._mapping) if row else {}

    async def _get_permits(
        self,
        parcel_id: str,
        address: str
    ) -> Dict[str, Any]:
        """Get permits at property and nearby"""

        permits_data = {
            'at_property': [],
            'nearby': []
        }

        # Check if permits table exists
        try:
            # Permits at property
            query_at_property = text("""
                SELECT
                    permit_number,
                    permit_type,
                    work_type,
                    project_name,
                    project_description,
                    project_value,
                    status,
                    application_date,
                    issued_date,
                    final_inspection_date,
                    jurisdiction,
                    permit_fee
                FROM permits
                WHERE parcel_id = :parcel_id
                ORDER BY application_date DESC
                LIMIT 20
            """)

            result = await self.session.execute(query_at_property, {'parcel_id': parcel_id})
            permits_data['at_property'] = [dict(row._mapping) for row in result]

        except Exception as e:
            logger.warning("permits_query_failed", error=str(e))

        return permits_data

    async def _get_crime_data(
        self,
        lat: float,
        lon: float,
        radius_miles: float = 0.5,
        days: int = 365
    ) -> List[Dict[str, Any]]:
        """Get crime incidents nearby"""

        lat_range = radius_miles / 69.0
        lon_range = radius_miles / 69.0

        # Convert to float
        lat = float(lat)
        lon = float(lon)

        try:
            query = text("""
                SELECT
                    incident_type,
                    incident_description,
                    incident_date,
                    incident_address,
                    latitude,
                    longitude
                FROM crime_reports
                WHERE latitude::float BETWEEN :min_lat AND :max_lat
                AND longitude::float BETWEEN :min_lon AND :max_lon
                AND incident_date >= CURRENT_DATE - INTERVAL '365 days'
                ORDER BY incident_date DESC
                LIMIT 50
            """)

            result = await self.session.execute(query, {
                'min_lat': lat - lat_range,
                'max_lat': lat + lat_range,
                'min_lon': lon - lon_range,
                'max_lon': lon + lon_range
            })

            return [dict(row._mapping) for row in result]

        except Exception as e:
            logger.warning("crime_query_failed", error=str(e))
            return []

    async def _get_council_activity(
        self,
        neighborhood_code: str = None,
        owner_name: str = None,
        days: int = 180
    ) -> List[Dict[str, Any]]:
        """Search council meetings for mentions"""

        try:
            # Search for neighborhood or owner mentions
            search_terms = []
            if neighborhood_code:
                search_terms.append(neighborhood_code)
            if owner_name:
                search_terms.append(owner_name)

            if not search_terms:
                return []

            # Use string formatting for interval to avoid SQL parameter issues
            query = text(f"""
                SELECT
                    meeting_date,
                    meeting_type,
                    summary,
                    topics,
                    source_url
                FROM council_meetings
                WHERE meeting_date >= CURRENT_DATE - INTERVAL '{days} days'
                AND (
                    summary ILIKE :search_term
                    OR :search_term = ANY(topics)
                )
                ORDER BY meeting_date DESC
                LIMIT 10
            """)

            result = await self.session.execute(query, {
                'search_term': f'%{search_terms[0]}%'
            })

            return [dict(row._mapping) for row in result]

        except Exception as e:
            logger.warning("council_query_failed", error=str(e))
            return []

    async def _get_news_coverage(
        self,
        owner_name: str = None,
        neighborhood_code: str = None,
        days: int = 180
    ) -> List[Dict[str, Any]]:
        """Search news articles for mentions"""

        try:
            search_terms = []
            if owner_name:
                search_terms.append(owner_name)
            if neighborhood_code:
                search_terms.append(neighborhood_code)

            if not search_terms:
                return []

            # Use string formatting for interval to avoid SQL parameter issues
            query = text(f"""
                SELECT
                    title,
                    url,
                    published_date,
                    source,
                    summary,
                    topics,
                    relevance_score
                FROM news_articles
                WHERE published_date >= CURRENT_DATE - INTERVAL '{days} days'
                AND (
                    title ILIKE :search_term
                    OR summary ILIKE :search_term
                    OR :search_term = ANY(topics)
                )
                ORDER BY published_date DESC
                LIMIT 10
            """)

            result = await self.session.execute(query, {
                'search_term': f'%{search_terms[0]}%'
            })

            return [dict(row._mapping) for row in result]

        except Exception as e:
            logger.warning("news_query_failed", error=str(e))
            return []

    def _analyze_geographic_clustering(self, portfolio: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze geographic clustering in portfolio.

        Identifies:
        - Street-level clustering
        - Gaps in assemblage
        - Edge parcels
        """
        if not portfolio:
            return None

        # Group by street
        street_groups = {}
        for prop in portfolio:
            address = prop.get('site_address', '')
            if not address:
                continue

            # Extract street name (everything after house number)
            parts = address.split(' ', 1)
            if len(parts) < 2:
                continue

            street = parts[1].upper()  # "NW 21ST CT", etc.
            house_num = parts[0]

            if street not in street_groups:
                street_groups[street] = []

            try:
                # Try to parse house number
                num = int(''.join(filter(str.isdigit, house_num)))
                street_groups[street].append({
                    'address': address,
                    'house_number': num,
                    'parcel_id': prop.get('parcel_id'),
                    'property_type': prop.get('property_type')
                })
            except (ValueError, TypeError):
                # Skip addresses with non-numeric house numbers
                continue

        # Analyze each street
        clusters = []
        for street, properties in street_groups.items():
            if len(properties) < 2:
                continue

            # Sort by house number
            properties.sort(key=lambda x: x['house_number'])

            # Find gaps
            gaps = []
            for i in range(len(properties) - 1):
                current = properties[i]['house_number']
                next_num = properties[i + 1]['house_number']

                # Check for gaps (assuming even/odd pattern)
                expected_increment = 2 if current % 2 == next_num % 2 else 1

                if next_num - current > expected_increment * 2:
                    # Potential gap
                    gaps.append({
                        'between': f"{current} and {next_num}",
                        'missing_numbers': list(range(current + expected_increment, next_num, expected_increment))
                    })

            clusters.append({
                'street': street,
                'parcel_count': len(properties),
                'house_number_range': f"{properties[0]['house_number']}-{properties[-1]['house_number']}",
                'addresses': [p['address'] for p in properties],
                'gaps': gaps,
                'is_contiguous': len(gaps) == 0,
                'edge_parcels': {
                    'low_end': properties[0]['address'],
                    'high_end': properties[-1]['address']
                }
            })

        # Sort by parcel count (largest clusters first)
        clusters.sort(key=lambda x: x['parcel_count'], reverse=True)

        return {
            'total_streets': len(clusters),
            'largest_cluster': clusters[0] if clusters else None,
            'all_clusters': clusters[:5],  # Top 5
            'assembly_detected': any(c['parcel_count'] >= 4 for c in clusters)
        }
