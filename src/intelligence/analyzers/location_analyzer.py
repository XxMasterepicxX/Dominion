"""
Location Analyzer

Analyzes geographic and spatial aspects of real estate including:
- Proximity analysis (find properties near target locations)
- Growth hotspots (detect areas with high development activity)
- Neighborhood profiling (aggregate metrics for geographic areas)
- Distance calculations (between properties, to points of interest)

Designed to be:
- Configurable (no hardcoded values)
- Reusable (works for any market, any location)
- Testable (clear inputs/outputs)
- Platform-agnostic (works with any deployment)
"""

from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import math

logger = structlog.get_logger(__name__)


class LocationAnalyzer:
    """
    Comprehensive location and spatial analysis engine

    Usage:
        analyzer = LocationAnalyzer(session)

        # Find nearby properties
        nearby = await analyzer.find_nearby_properties(
            target_property_id="123e4567-...",
            radius_miles=1.0
        )

        # Detect growth hotspots
        hotspots = await analyzer.find_growth_hotspots(
            market_id="gainesville_fl",
            min_activity_score=0.7
        )

        # Analyze neighborhood
        neighborhood = await analyzer.analyze_neighborhood(
            latitude=29.6516,
            longitude=-82.3248,
            radius_miles=0.5
        )
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize analyzer with database session

        Args:
            session: Active SQLAlchemy async session
        """
        self.session = session

    @staticmethod
    def calculate_distance_miles(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance between two points using Haversine formula

        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point

        Returns:
            Distance in miles

        Example:
            distance = LocationAnalyzer.calculate_distance_miles(
                29.6516, -82.3248,  # Gainesville
                29.6519, -82.3251   # Nearby point
            )
        """
        # Earth's radius in miles
        earth_radius_miles = 3959.0

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        return earth_radius_miles * c

    async def find_nearby_properties(
        self,
        target_property_id: Optional[str] = None,
        target_latitude: Optional[float] = None,
        target_longitude: Optional[float] = None,
        radius_miles: float = 1.0,
        market_id: Optional[str] = None,
        property_type: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        exclude_property_ids: Optional[List[str]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Find properties within radius of target location

        Args:
            target_property_id: Property ID to search around (alternative to lat/lon)
            target_latitude: Target latitude (if no property_id)
            target_longitude: Target longitude (if no property_id)
            radius_miles: Search radius in miles
            market_id: Optional market filter
            property_type: Optional property type filter (e.g., 'VACANT')
            min_price: Optional minimum market value
            max_price: Optional maximum market value
            exclude_property_ids: Optional list of property IDs to exclude
            limit: Maximum number of properties to return

        Returns:
            Dict with:
            - target_location: Coordinates of search center
            - radius_miles: Search radius used
            - properties_found: Number of properties found
            - properties: List of nearby properties with distances
            - filters_applied: What filters were used

        Raises:
            ValueError: If neither target_property_id nor (target_latitude, target_longitude) provided
        """
        logger.info(
            "finding_nearby_properties",
            target_property_id=target_property_id,
            radius_miles=radius_miles,
            market_id=market_id,
            property_type=property_type
        )

        # Get target coordinates
        if target_property_id:
            target_coords = await self._get_property_coordinates(target_property_id)
            if not target_coords:
                return {
                    'error': 'Target property not found or has no coordinates',
                    'target_property_id': target_property_id
                }
            target_lat, target_lon = target_coords
        elif target_latitude is not None and target_longitude is not None:
            target_lat = target_latitude
            target_lon = target_longitude
        else:
            raise ValueError("Must provide either target_property_id or (target_latitude, target_longitude)")

        # Calculate bounding box for efficient spatial filtering
        # 1 degree latitude ≈ 69 miles (constant)
        # 1 degree longitude ≈ 69 miles * cos(latitude) (varies by latitude)
        lat_degrees_per_mile = 1.0 / 69.0
        lat_radians = math.radians(target_lat)
        lon_degrees_per_mile = 1.0 / (69.0 * math.cos(lat_radians))

        # Add buffer (1.2x) to ensure we don't miss properties at corners
        buffer = 1.2
        lat_delta = radius_miles * lat_degrees_per_mile * buffer
        lon_delta = radius_miles * lon_degrees_per_mile * buffer

        lat_min = target_lat - lat_delta
        lat_max = target_lat + lat_delta
        lon_min = target_lon - lon_delta
        lon_max = target_lon + lon_delta

        # Build query - using only columns that exist in bulk_property_records
        query_parts = ["""
            SELECT
                p.id,
                p.parcel_id,
                p.site_address,
                p.property_type,
                p.market_value,
                p.lot_size_acres,
                p.latitude,
                p.longitude,
                p.owner_name
            FROM bulk_property_records p
            WHERE p.latitude IS NOT NULL
              AND p.longitude IS NOT NULL
              AND p.latitude BETWEEN :lat_min AND :lat_max
              AND p.longitude BETWEEN :lon_min AND :lon_max
        """]

        params = {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lon_min': lon_min,
            'lon_max': lon_max
        }

        # Market filter
        if market_id:
            query_parts.append("AND p.market_id = :market_id")
            params['market_id'] = market_id

        # Property type filter
        if property_type:
            query_parts.append("AND p.property_type = :property_type")
            params['property_type'] = property_type

        # Price filters
        if min_price is not None:
            query_parts.append("AND p.market_value >= :min_price")
            params['min_price'] = min_price

        if max_price is not None:
            query_parts.append("AND p.market_value <= :max_price")
            params['max_price'] = max_price

        # Exclude properties
        if exclude_property_ids:
            placeholders = ','.join([f':exclude_{i}' for i in range(len(exclude_property_ids))])
            query_parts.append(f"AND p.id NOT IN ({placeholders})")
            for i, prop_id in enumerate(exclude_property_ids):
                params[f'exclude_{i}'] = prop_id

        # Limit results (bounding box pre-filters, so we don't need 3x buffer anymore)
        # Still fetch more than limit to account for edge cases outside exact radius
        query_parts.append(f"LIMIT {limit * 2}")

        query = text(' '.join(query_parts))

        # Execute query
        result = await self.session.execute(query, params)
        rows = result.fetchall()

        # Calculate distances and filter by radius
        properties = []
        for row in rows:
            if row[6] is None or row[7] is None:  # Skip if no coordinates
                continue

            distance = self.calculate_distance_miles(
                target_lat, target_lon,
                float(row[6]), float(row[7])
            )

            if distance <= radius_miles:
                properties.append({
                    'property_id': str(row[0]),
                    'parcel_id': row[1],
                    'site_address': row[2],
                    'property_type': row[3],
                    'market_value': float(row[4]) if row[4] else None,
                    'lot_size_acres': float(row[5]) if row[5] else None,
                    'latitude': float(row[6]),
                    'longitude': float(row[7]),
                    'owner_name': row[8],
                    'distance_miles': round(distance, 2)
                })

        # Sort by distance
        properties.sort(key=lambda x: x['distance_miles'])

        # Apply limit after distance filtering
        properties = properties[:limit]

        logger.info(
            "nearby_properties_found",
            count=len(properties),
            radius_miles=radius_miles
        )

        return {
            'target_location': {
                'latitude': target_lat,
                'longitude': target_lon
            },
            'radius_miles': radius_miles,
            'properties_found': len(properties),
            'properties': properties,
            'filters_applied': {
                'market_id': market_id,
                'property_type': property_type,
                'min_price': min_price,
                'max_price': max_price,
                'excluded_count': len(exclude_property_ids) if exclude_property_ids else 0
            }
        }

    async def find_growth_hotspots(
        self,
        market_id: str,
        min_activity_score: float = 0.7,
        lookback_days: int = 180,
        grid_size_miles: float = 0.5,
        min_properties_per_area: int = 3
    ) -> Dict[str, Any]:
        """
        Detect geographic areas with high development activity

        Analyzes:
        - Permit concentration (building permits in area)
        - Sales activity (recent transactions)
        - Investor concentration (multiple investors buying)
        - Property value trends

        Args:
            market_id: Market to analyze
            min_activity_score: Minimum score to qualify as hotspot (0-1)
            lookback_days: Days to look back for activity
            grid_size_miles: Size of geographic grid cells
            min_properties_per_area: Minimum properties needed to analyze area

        Returns:
            Dict with:
            - market_id: Market analyzed
            - analysis_period: Time period analyzed
            - hotspots_found: Number of hotspots detected
            - hotspots: List of hotspot areas with activity metrics
            - analysis_metadata: Parameters used

        Example hotspot:
            {
                'area_center': {'latitude': 29.6516, 'longitude': -82.3248},
                'radius_miles': 0.5,
                'activity_score': 0.85,
                'properties_count': 15,
                'permits_count': 23,
                'recent_sales_count': 8,
                'active_investors': ['Entity A', 'Entity B'],
                'avg_property_value': 180000,
                'activity_breakdown': {
                    'permit_score': 0.9,
                    'sales_score': 0.8,
                    'investor_score': 0.85
                }
            }
        """
        logger.info(
            "finding_growth_hotspots",
            market_id=market_id,
            lookback_days=lookback_days
        )

        cutoff_date = datetime.now() - timedelta(days=lookback_days)

        # Get properties with coordinates and recent activity
        query = text("""
            WITH recent_activity AS (
                SELECT
                    p.id as property_id,
                    p.latitude,
                    p.longitude,
                    p.site_address,
                    p.market_value,
                    p.property_type,
                    COUNT(DISTINCT perm.id) as permit_count,
                    COUNT(DISTINCT CASE
                        WHEN perm.issued_date >= :cutoff_date
                        THEN perm.id
                    END) as recent_permit_count,
                    p.last_sale_date,
                    p.last_sale_price
                FROM bulk_property_records p
                LEFT JOIN permits perm ON perm.property_id = p.id
                WHERE p.market_id = :market_id
                  AND p.latitude IS NOT NULL
                  AND p.longitude IS NOT NULL
                GROUP BY p.id, p.latitude, p.longitude, p.site_address,
                         p.market_value, p.property_type, p.last_sale_date, p.last_sale_price
            )
            SELECT * FROM recent_activity
            WHERE permit_count > 0
               OR last_sale_date >= :cutoff_date
            ORDER BY recent_permit_count DESC, permit_count DESC
        """)

        result = await self.session.execute(query, {
            'market_id': market_id,
            'cutoff_date': cutoff_date
        })
        active_properties = result.fetchall()

        if not active_properties:
            return {
                'market_id': market_id,
                'analysis_period': {
                    'lookback_days': lookback_days,
                    'start_date': cutoff_date.isoformat()
                },
                'hotspots_found': 0,
                'hotspots': [],
                'message': 'No properties with recent activity found'
            }

        # Cluster properties into geographic areas
        clusters = self._cluster_by_proximity(
            active_properties,
            grid_size_miles=grid_size_miles
        )

        # Analyze each cluster
        hotspots = []
        for cluster_center, cluster_properties in clusters.items():
            if len(cluster_properties) < min_properties_per_area:
                continue

            # Calculate activity metrics
            total_permits = sum(prop[6] for prop in cluster_properties)
            recent_permits = sum(prop[7] for prop in cluster_properties)

            recent_sales = sum(
                1 for prop in cluster_properties
                if prop[8] and prop[8] >= cutoff_date.date()
            )

            # Calculate activity score
            permit_score = min(recent_permits / max(len(cluster_properties), 1), 1.0)
            sales_score = min(recent_sales / max(len(cluster_properties) * 0.5, 1), 1.0)

            # Overall activity score (weighted average)
            activity_score = (permit_score * 0.6 + sales_score * 0.4)

            if activity_score >= min_activity_score:
                # Get active investors in area
                investor_query = text("""
                    SELECT DISTINCT e.entity_name, COUNT(*) as property_count
                    FROM bulk_property_records p
                    JOIN entities e ON p.owner_entity_id = e.id
                    WHERE p.market_id = :market_id
                      AND p.latitude IS NOT NULL
                      AND p.longitude IS NOT NULL
                    GROUP BY e.entity_name
                    HAVING COUNT(*) > 1
                    LIMIT 5
                """)

                investor_result = await self.session.execute(investor_query, {'market_id': market_id})
                active_investors = [row[0] for row in investor_result.fetchall()]

                avg_value = sum(
                    float(prop[4]) for prop in cluster_properties if prop[4]
                ) / len([p for p in cluster_properties if p[4]])

                hotspots.append({
                    'area_center': {
                        'latitude': cluster_center[0],
                        'longitude': cluster_center[1]
                    },
                    'radius_miles': grid_size_miles,
                    'activity_score': round(activity_score, 2),
                    'properties_count': len(cluster_properties),
                    'permits_count': total_permits,
                    'recent_permits_count': recent_permits,
                    'recent_sales_count': recent_sales,
                    'active_investors': active_investors,
                    'avg_property_value': round(avg_value, 2) if avg_value else None,
                    'activity_breakdown': {
                        'permit_score': round(permit_score, 2),
                        'sales_score': round(sales_score, 2)
                    },
                    'sample_addresses': [prop[3] for prop in cluster_properties[:3]]
                })

        # Sort by activity score
        hotspots.sort(key=lambda x: x['activity_score'], reverse=True)

        logger.info(
            "growth_hotspots_found",
            count=len(hotspots),
            market_id=market_id
        )

        return {
            'market_id': market_id,
            'analysis_period': {
                'lookback_days': lookback_days,
                'start_date': cutoff_date.isoformat(),
                'end_date': datetime.now().isoformat()
            },
            'hotspots_found': len(hotspots),
            'hotspots': hotspots,
            'analysis_metadata': {
                'min_activity_score': min_activity_score,
                'grid_size_miles': grid_size_miles,
                'min_properties_per_area': min_properties_per_area
            }
        }

    async def analyze_neighborhood(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = 0.5,
        market_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze neighborhood characteristics around a location

        Provides aggregate metrics for area:
        - Property count and types
        - Value statistics (avg, median, range)
        - Ownership patterns (owner-occupied vs investor-owned)
        - Recent activity (sales, permits)

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_miles: Neighborhood radius
            market_id: Optional market filter

        Returns:
            Dict with:
            - center: Location analyzed
            - radius_miles: Radius used
            - properties_analyzed: Count of properties
            - value_statistics: Price metrics
            - property_mix: Distribution by type
            - ownership_patterns: Owner vs investor distribution
            - recent_activity: Sales and permits
        """
        logger.info(
            "analyzing_neighborhood",
            latitude=latitude,
            longitude=longitude,
            radius_miles=radius_miles
        )

        # Find all properties in radius
        nearby_result = await self.find_nearby_properties(
            target_latitude=latitude,
            target_longitude=longitude,
            radius_miles=radius_miles,
            market_id=market_id,
            limit=500
        )

        properties = nearby_result.get('properties', [])

        if not properties:
            return {
                'center': {'latitude': latitude, 'longitude': longitude},
                'radius_miles': radius_miles,
                'properties_analyzed': 0,
                'message': 'No properties found in this neighborhood'
            }

        # Calculate statistics
        values = [p['market_value'] for p in properties if p.get('market_value')]

        value_statistics = None
        if values:
            values_sorted = sorted(values)
            value_statistics = {
                'average': round(sum(values) / len(values), 2),
                'median': values_sorted[len(values_sorted) // 2],
                'min': min(values),
                'max': max(values),
                'count': len(values)
            }

        # Property type distribution
        property_types = {}
        for p in properties:
            ptype = p.get('property_type', 'UNKNOWN')
            property_types[ptype] = property_types.get(ptype, 0) + 1

        # Ownership patterns
        owner_types = {}
        for p in properties:
            otype = p.get('owner_type', 'UNKNOWN')
            owner_types[otype] = owner_types.get(otype, 0) + 1

        # Get recent activity (sales and permits in last 180 days)
        cutoff_date = datetime.now() - timedelta(days=180)

        property_ids = [p['property_id'] for p in properties]
        placeholders = ','.join([f':prop_{i}' for i in range(len(property_ids))])
        params = {f'prop_{i}': pid for i, pid in enumerate(property_ids)}
        params['cutoff_date'] = cutoff_date

        activity_query = text(f"""
            SELECT
                COUNT(DISTINCT p.id) FILTER (WHERE p.last_sale_date >= :cutoff_date) as recent_sales,
                COUNT(DISTINCT perm.id) FILTER (WHERE perm.issued_date >= :cutoff_date) as recent_permits
            FROM bulk_property_records p
            LEFT JOIN permits perm ON perm.property_id = p.id
            WHERE p.id IN ({placeholders})
        """)

        activity_result = await self.session.execute(activity_query, params)
        activity_row = activity_result.fetchone()

        return {
            'center': {'latitude': latitude, 'longitude': longitude},
            'radius_miles': radius_miles,
            'properties_analyzed': len(properties),
            'value_statistics': value_statistics,
            'property_mix': property_types,
            'ownership_patterns': owner_types,
            'recent_activity': {
                'sales_last_180_days': activity_row[0] if activity_row else 0,
                'permits_last_180_days': activity_row[1] if activity_row else 0
            }
        }

    # Private helper methods

    async def _get_property_coordinates(self, property_id: str) -> Optional[Tuple[float, float]]:
        """Get latitude/longitude for a property"""
        query = text("""
            SELECT latitude, longitude
            FROM bulk_property_records
            WHERE id = :property_id
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
        """)

        result = await self.session.execute(query, {'property_id': property_id})
        row = result.fetchone()

        if row:
            return (float(row[0]), float(row[1]))
        return None

    def _cluster_by_proximity(
        self,
        properties: List,
        grid_size_miles: float
    ) -> Dict[Tuple[float, float], List]:
        """
        Cluster properties into geographic grid cells

        Args:
            properties: List of property rows with coordinates
            grid_size_miles: Size of grid cells in miles

        Returns:
            Dict mapping grid cell centers to properties in that cell
        """
        clusters = {}

        for prop in properties:
            lat = float(prop[1])
            lon = float(prop[2])

            # Convert to approximate grid coordinates
            # 1 degree latitude ≈ 69 miles
            # 1 degree longitude ≈ 69 * cos(latitude) miles
            lat_grid = round(lat / (grid_size_miles / 69.0)) * (grid_size_miles / 69.0)
            lon_grid = round(lon / (grid_size_miles / (69.0 * math.cos(math.radians(lat))))) * \
                       (grid_size_miles / (69.0 * math.cos(math.radians(lat))))

            grid_cell = (round(lat_grid, 4), round(lon_grid, 4))

            if grid_cell not in clusters:
                clusters[grid_cell] = []
            clusters[grid_cell].append(prop)

        return clusters
