"""
Market Analyzer

Analyzes real estate markets including:
- Market overview (total properties, values, distribution)
- Supply metrics (inventory by type, price ranges)
- Demand signals (recent sales, price trends)
- Competition (active buyers, investor activity)
- Market trends (appreciation, hotspots)

Designed to be:
- Configurable (no hardcoded values)
- Reusable (works for any market)
- Testable (clear inputs/outputs)
- Platform-agnostic (works with any deployment)
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)


class MarketAnalyzer:
    """
    Comprehensive market analysis engine

    Usage:
        analyzer = MarketAnalyzer(session)
        result = await analyzer.analyze(market_id="123e4567-...")
        result = await analyzer.analyze(market_code="gainesville_fl")
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize analyzer with database session

        Args:
            session: Active SQLAlchemy async session
        """
        self.session = session

    async def analyze(
        self,
        market_id: Optional[str] = None,
        market_code: Optional[str] = None,
        include_supply: bool = True,
        include_demand: bool = True,
        include_competition: bool = True,
        include_trends: bool = True,
        include_construction_pipeline: bool = True,
        include_crime_trends: bool = True,
        include_development_sentiment: bool = True,
        include_permit_velocity: bool = True,
        include_multi_developer_permits: bool = True,
        recent_period_days: int = 180,
        price_percentiles: List[int] = [25, 50, 75, 90],
        top_developers: int = 10
    ) -> Dict[str, Any]:
        """
        Analyze a real estate market comprehensively

        Args:
            market_id: UUID of market
            market_code: Market code (e.g., 'gainesville_fl')
            include_supply: Include supply metrics
            include_demand: Include demand signals
            include_competition: Include competition analysis
            include_trends: Include trend analysis
            recent_period_days: Days to consider as "recent" activity
            price_percentiles: Price percentiles to calculate

        Returns:
            Comprehensive market analysis dict with:
            - market: Core market details
            - overview: High-level market statistics
            - supply: Supply metrics (if requested)
            - demand: Demand signals (if requested)
            - competition: Competition analysis (if requested)
            - trends: Market trends (if requested)
            - analysis_metadata: When analyzed, what was included

        Raises:
            ValueError: If neither market_id nor market_code provided
            MarketNotFoundError: If market doesn't exist
        """
        if not market_id and not market_code:
            raise ValueError("Must provide either market_id or market_code")

        logger.info(
            "market_analysis_started",
            market_id=market_id,
            market_code=market_code
        )

        # Get market details
        market_data = await self._get_market_details(market_id, market_code)

        if not market_data:
            raise MarketNotFoundError(
                f"Market not found: market_id={market_id}, market_code={market_code}"
            )

        # Get overview statistics
        overview = await self._get_market_overview(market_data['id'])

        result = {
            'market': market_data,
            'overview': overview,
            'supply': None,
            'demand': None,
            'competition': None,
            'trends': None,
            'construction_pipeline': None,
            'crime_trends': None,
            'development_sentiment': None,
            'permit_velocity': None,
            'multi_developer_permits': None,
            'analysis_metadata': {
                'analyzed_at': datetime.now().isoformat(),
                'includes': {
                    'supply': include_supply,
                    'demand': include_demand,
                    'competition': include_competition,
                    'trends': include_trends,
                    'construction_pipeline': include_construction_pipeline,
                    'crime_trends': include_crime_trends,
                    'development_sentiment': include_development_sentiment,
                    'permit_velocity': include_permit_velocity,
                    'multi_developer_permits': include_multi_developer_permits
                },
                'parameters': {
                    'recent_period_days': recent_period_days,
                    'price_percentiles': price_percentiles,
                    'top_developers': top_developers
                }
            }
        }

        # Get supply metrics
        if include_supply:
            result['supply'] = await self._get_supply_metrics(
                market_data['id'],
                percentiles=price_percentiles
            )

        # Get demand signals
        if include_demand:
            result['demand'] = await self._get_demand_signals(
                market_data['id'],
                recent_days=recent_period_days
            )

        # Get competition analysis
        if include_competition:
            result['competition'] = await self._get_competition_analysis(
                market_data['id'],
                recent_days=recent_period_days
            )

        # Get market trends
        if include_trends:
            result['trends'] = await self._get_market_trends(
                market_data['id'],
                recent_days=recent_period_days
            )

        # Get construction pipeline
        if include_construction_pipeline:
            result['construction_pipeline'] = await self._get_construction_pipeline(
                market_data['id'],
                recent_days=recent_period_days
            )

        # Get crime trends
        if include_crime_trends:
            result['crime_trends'] = await self._get_crime_trends(
                market_data['id'],
                recent_days=recent_period_days
            )

        # Get development sentiment
        if include_development_sentiment:
            result['development_sentiment'] = await self._get_development_sentiment(
                market_data['id'],
                recent_days=recent_period_days
            )

        # Get permit velocity
        if include_permit_velocity:
            result['permit_velocity'] = await self._get_permit_velocity(
                market_data['id'],
                recent_days=recent_period_days
            )

        # Get multi-developer permits
        if include_multi_developer_permits:
            result['multi_developer_permits'] = await self._get_multi_developer_permits(
                market_data['id'],
                recent_days=recent_period_days,
                top_n=top_developers
            )

        # Get demographics (census data)
        result['demographics'] = await self._get_demographics(market_data['id'])

        logger.info(
            "market_analysis_completed",
            market_id=market_data['id'],
            market_code=market_data['market_code'],
            total_permits=result.get('construction_pipeline', {}).get('total_permits') if result.get('construction_pipeline') else None,
            crime_incidents=result.get('crime_trends', {}).get('total_incidents') if result.get('crime_trends') else None,
            council_meetings=result.get('development_sentiment', {}).get('council_activity', {}).get('total_meetings') if result.get('development_sentiment') else None,
            permit_count=result.get('permit_velocity', {}).get('total_permits') if result.get('permit_velocity') else None,
            developers_analyzed=result.get('multi_developer_permits', {}).get('developers_found') if result.get('multi_developer_permits') else None
        )

        return result

    async def _get_market_details(
        self,
        market_id: Optional[str],
        market_code: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Get market details from database"""

        # Build query based on what identifier was provided
        if market_id:
            where_clause = "WHERE id = :identifier"
            identifier = market_id
        else:
            where_clause = "WHERE market_code = :identifier"
            identifier = market_code

        query = text(f"""
            SELECT
                id,
                market_code,
                market_name,
                state,
                county,
                created_at
            FROM markets
            {where_clause}
            LIMIT 1
        """)

        result = await self.session.execute(query, {'identifier': identifier})
        row = result.fetchone()

        if not row:
            return None

        return {
            'id': str(row[0]),
            'market_code': row[1],
            'market_name': row[2],
            'state': row[3],
            'county': row[4],
            'created_at': row[5].isoformat() if row[5] else None
        }

    async def _get_market_overview(
        self,
        market_id: str
    ) -> Dict[str, Any]:
        """Get high-level market overview statistics"""

        query = text("""
            SELECT
                COUNT(*) as total_properties,
                COUNT(DISTINCT owner_name) as total_owners,
                SUM(market_value) as total_market_value,
                AVG(market_value) as avg_market_value,
                SUM(square_feet) as total_sqft,
                AVG(square_feet) as avg_sqft,
                COUNT(CASE WHEN last_sale_date >= NOW() - INTERVAL '365 days' THEN 1 END) as sales_last_year
            FROM bulk_property_records
            WHERE market_id = :market_id
        """)

        result = await self.session.execute(query, {'market_id': market_id})
        row = result.fetchone()

        if not row:
            return {}

        return {
            'total_properties': int(row[0]) if row[0] else 0,
            'total_owners': int(row[1]) if row[1] else 0,
            'total_market_value': float(row[2]) if row[2] else None,
            'avg_property_value': float(row[3]) if row[3] else None,
            'total_building_sqft': float(row[4]) if row[4] else None,
            'avg_building_sqft': float(row[5]) if row[5] else None,
            'sales_last_year': int(row[6]) if row[6] else 0
        }

    async def _get_supply_metrics(
        self,
        market_id: str,
        percentiles: List[int] = [25, 50, 75, 90]
    ) -> Dict[str, Any]:
        """Get supply-side market metrics"""

        # Get property type distribution
        query = text("""
            SELECT
                property_type,
                COUNT(*) as count,
                AVG(market_value) as avg_value,
                SUM(market_value) as total_value
            FROM bulk_property_records
            WHERE market_id = :market_id
              AND property_type IS NOT NULL
            GROUP BY property_type
            ORDER BY count DESC
        """)

        result = await self.session.execute(query, {'market_id': market_id})
        by_type = []
        for row in result:
            by_type.append({
                'property_type': row[0],
                'count': int(row[1]),
                'avg_value': float(row[2]) if row[2] else None,
                'total_value': float(row[3]) if row[3] else None
            })

        # Get price distribution (percentiles)
        percentile_queries = []
        for p in percentiles:
            percentile_queries.append(
                f"PERCENTILE_CONT({p/100.0}) WITHIN GROUP (ORDER BY market_value) as p{p}"
            )

        query = text(f"""
            SELECT
                {', '.join(percentile_queries)}
            FROM bulk_property_records
            WHERE market_id = :market_id
              AND market_value IS NOT NULL
              AND market_value > 0
        """)

        result = await self.session.execute(query, {'market_id': market_id})
        row = result.fetchone()

        price_distribution = {}
        if row:
            for i, p in enumerate(percentiles):
                price_distribution[f'p{p}'] = float(row[i]) if row[i] else None

        return {
            'by_property_type': by_type,
            'price_distribution': price_distribution
        }

    async def _get_demand_signals(
        self,
        market_id: str,
        recent_days: int = 180
    ) -> Dict[str, Any]:
        """Get demand-side market signals"""

        recent_date = datetime.now() - timedelta(days=recent_days)

        query = text("""
            SELECT
                COUNT(*) as recent_sales,
                AVG(last_sale_price) as avg_sale_price,
                SUM(last_sale_price) as total_volume,
                AVG(market_value) as avg_current_value
            FROM bulk_property_records
            WHERE market_id = :market_id
              AND last_sale_date >= :recent_date
              AND last_sale_price IS NOT NULL
              AND last_sale_price > 0
        """)

        result = await self.session.execute(
            query,
            {'market_id': market_id, 'recent_date': recent_date}
        )
        row = result.fetchone()

        if not row or row[0] == 0:
            return {
                'period_days': recent_days,
                'recent_sales': 0,
                'metrics': None
            }

        # Calculate appreciation (current value vs sale price)
        avg_appreciation = None
        if row[1] and row[3]:
            avg_appreciation = ((row[3] - row[1]) / row[1]) * 100

        return {
            'period_days': recent_days,
            'recent_sales': int(row[0]),
            'metrics': {
                'avg_sale_price': float(row[1]) if row[1] else None,
                'total_volume': float(row[2]) if row[2] else None,
                'avg_current_value': float(row[3]) if row[3] else None,
                'avg_appreciation_pct': avg_appreciation
            }
        }

    async def _get_competition_analysis(
        self,
        market_id: str,
        recent_days: int = 180
    ) -> Dict[str, Any]:
        """Analyze competitive landscape (active buyers/investors)"""

        recent_date = datetime.now() - timedelta(days=recent_days)

        # Get most active buyers
        query = text("""
            SELECT
                e.id,
                e.name,
                e.entity_type,
                emp.total_properties,
                COUNT(CASE WHEN bp.last_sale_date >= :recent_date THEN 1 END) as recent_acquisitions
            FROM entities e
            JOIN entity_market_properties emp ON emp.entity_id = e.id
            JOIN bulk_property_records bp ON bp.owner_name = e.name
            WHERE emp.market_id = :market_id
              AND emp.total_properties >= 2
            GROUP BY e.id, e.name, e.entity_type, emp.total_properties
            HAVING COUNT(CASE WHEN bp.last_sale_date >= :recent_date THEN 1 END) > 0
            ORDER BY recent_acquisitions DESC, emp.total_properties DESC
            LIMIT 10
        """)

        result = await self.session.execute(
            query,
            {'market_id': market_id, 'recent_date': recent_date}
        )

        active_buyers = []
        for row in result:
            active_buyers.append({
                'entity_id': str(row[0]),
                'entity_name': row[1],
                'entity_type': row[2],
                'total_properties': int(row[3]),
                'recent_acquisitions': int(row[4])
            })

        # Get investor concentration
        query = text("""
            SELECT
                COUNT(DISTINCT e.id) as total_investors,
                SUM(emp.total_properties) as properties_by_investors,
                (SELECT COUNT(*) FROM bulk_property_records WHERE market_id = :market_id) as total_properties
            FROM entities e
            JOIN entity_market_properties emp ON emp.entity_id = e.id
            WHERE emp.market_id = :market_id
              AND emp.total_properties >= 2
        """)

        result = await self.session.execute(query, {'market_id': market_id})
        row = result.fetchone()

        concentration = None
        if row and row[0]:
            concentration = {
                'total_investors': int(row[0]),
                'properties_controlled': int(row[1]) if row[1] else 0,
                'total_market_properties': int(row[2]) if row[2] else 0,
                'investor_control_pct': (
                    (int(row[1]) / int(row[2]) * 100)
                    if row[1] and row[2] and row[2] > 0
                    else None
                )
            }

        # Add geographic clustering for each buyer
        for buyer in active_buyers:
            clustering = await self._analyze_buyer_geographic_focus(
                entity_id=buyer['entity_id'],
                entity_name=buyer['entity_name'],
                market_id=market_id,
                recent_days=recent_days
            )
            buyer['geographic_concentration'] = clustering

        return {
            'active_buyers': active_buyers,
            'investor_concentration': concentration,
            'period_days': recent_days
        }

    async def _analyze_buyer_geographic_focus(
        self,
        entity_id: str,
        entity_name: str,
        market_id: str,
        recent_days: int = 180
    ) -> Dict[str, Any]:
        """
        Analyze where a buyer concentrates their acquisitions geographically.

        Returns geographic clustering data showing which areas of the market
        this buyer is most active in.
        """
        from collections import defaultdict

        recent_date = datetime.now() - timedelta(days=recent_days)

        # Get buyer's recent properties with locations
        query = text("""
            SELECT
                bp.site_address,
                bp.latitude,
                bp.longitude,
                bp.last_sale_date
            FROM bulk_property_records bp
            WHERE bp.market_id = :market_id
              AND bp.owner_name = :entity_name
              AND bp.last_sale_date >= :recent_date
              AND bp.latitude IS NOT NULL
              AND bp.longitude IS NOT NULL
        """)

        result = await self.session.execute(
            query,
            {
                'market_id': market_id,
                'entity_name': entity_name,
                'recent_date': recent_date
            }
        )

        properties = []
        for row in result:
            properties.append({
                'address': row[0],
                'lat': float(row[1]) if row[1] else None,
                'lng': float(row[2]) if row[2] else None,
                'date': row[3]
            })

        if not properties:
            return {
                'has_geographic_data': False,
                'property_count': 0
            }

        # Analyze geographic clustering by extracting area patterns from addresses
        area_counts = defaultdict(int)
        street_patterns = defaultdict(int)

        for prop in properties:
            address = prop['address']
            if not address:
                continue

            # Extract directional area (SW, NE, etc.)
            address_upper = address.upper()
            if 'SW' in address_upper:
                area_counts['SW'] += 1
            elif 'SE' in address_upper:
                area_counts['SE'] += 1
            elif 'NW' in address_upper:
                area_counts['NW'] += 1
            elif 'NE' in address_upper:
                area_counts['NE'] += 1
            elif 'NORTH' in address_upper:
                area_counts['N'] += 1
            elif 'SOUTH' in address_upper:
                area_counts['S'] += 1
            elif 'EAST' in address_upper:
                area_counts['E'] += 1
            elif 'WEST' in address_upper:
                area_counts['W'] += 1

            # Extract street name patterns (for more granular clustering)
            parts = address.split(',')[0].strip().split()
            if len(parts) >= 2:
                # Get street name (last 1-2 words before comma)
                street = ' '.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
                street_patterns[street] += 1

        # Calculate concentration
        total = len(properties)

        # Find primary area
        sorted_areas = sorted(area_counts.items(), key=lambda x: x[1], reverse=True)

        clustered_areas = []
        for area, count in sorted_areas[:3]:  # Top 3 areas
            clustered_areas.append({
                'area': area,
                'property_count': count,
                'percentage': round((count / total) * 100, 1)
            })

        # Calculate concentration score (what % in top area)
        concentration_score = (sorted_areas[0][1] / total) if sorted_areas else 0

        # Identify top streets (shows even more granular clustering)
        top_streets = sorted(street_patterns.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            'has_geographic_data': True,
            'property_count': total,
            'clustered_areas': clustered_areas,
            'concentration_score': round(concentration_score, 2),
            'top_streets': [
                {'street': street, 'count': count}
                for street, count in top_streets
            ] if top_streets else []
        }

    async def _get_market_trends(
        self,
        market_id: str,
        recent_days: int = 180
    ) -> Dict[str, Any]:
        """Analyze market trends and patterns"""

        recent_date = datetime.now() - timedelta(days=recent_days)

        # Get sales velocity (sales per month)
        query = text("""
            SELECT
                DATE_TRUNC('month', last_sale_date) as month,
                COUNT(*) as sales_count,
                AVG(last_sale_price) as avg_price
            FROM bulk_property_records
            WHERE market_id = :market_id
              AND last_sale_date >= :recent_date
              AND last_sale_price IS NOT NULL
            GROUP BY DATE_TRUNC('month', last_sale_date)
            ORDER BY month DESC
        """)

        result = await self.session.execute(
            query,
            {'market_id': market_id, 'recent_date': recent_date}
        )

        sales_velocity = []
        for row in result:
            sales_velocity.append({
                'month': row[0].isoformat() if row[0] else None,
                'sales_count': int(row[1]),
                'avg_price': float(row[2]) if row[2] else None
            })

        # Identify geographic hotspots (areas with high activity)
        query = text("""
            SELECT
                city,
                COUNT(*) as total_properties,
                COUNT(CASE WHEN last_sale_date >= :recent_date THEN 1 END) as recent_sales,
                AVG(market_value) as avg_value
            FROM bulk_property_records
            WHERE market_id = :market_id
              AND city IS NOT NULL
            GROUP BY city
            HAVING COUNT(CASE WHEN last_sale_date >= :recent_date THEN 1 END) > 0
            ORDER BY recent_sales DESC
            LIMIT 10
        """)

        result = await self.session.execute(
            query,
            {'market_id': market_id, 'recent_date': recent_date}
        )

        hotspots = []
        for row in result:
            hotspots.append({
                'city': row[0],
                'total_properties': int(row[1]),
                'recent_sales': int(row[2]),
                'avg_value': float(row[3]) if row[3] else None
            })

        return {
            'sales_velocity': sales_velocity,
            'geographic_hotspots': hotspots,
            'period_days': recent_days
        }

    async def _get_construction_pipeline(
        self,
        market_id: str,
        recent_days: int = 180
    ) -> Dict[str, Any]:
        """Analyze new construction pipeline for oversupply risk detection"""

        try:
            query = text(f"""
                SELECT
                    permit_type,
                    COUNT(*) as permit_count,
                    SUM(project_value) as total_value,
                    COUNT(CASE WHEN status = 'Issued' OR status = 'Active' THEN 1 END) as active_projects,
                    COUNT(CASE WHEN status = 'Applied' OR status = 'Pending' THEN 1 END) as pending_projects
                FROM permits
                WHERE market_id = :market_id
                  AND application_date >= CURRENT_DATE - INTERVAL '{recent_days} days'
                GROUP BY permit_type
                ORDER BY permit_count DESC
            """)

            result = await self.session.execute(
                query,
                {'market_id': market_id}
            )

            pipeline = []
            total_units = 0
            for row in result:
                pipeline.append({
                    'permit_type': row[0],
                    'permit_count': int(row[1]),
                    'total_value': float(row[2]) if row[2] else None,
                    'active_projects': int(row[3]) if row[3] else 0,
                    'pending_projects': int(row[4]) if row[4] else 0
                })
                total_units += int(row[1])

            return {
                'pipeline': pipeline,
                'total_permits': total_units,
                'total_project_value': sum(p.get('total_value', 0) or 0 for p in pipeline),
                'period_days': recent_days
            }

        except Exception as e:
            logger.warning("construction_pipeline_query_failed", error=str(e))
            return {
                'pipeline': [],
                'total_permits': 0,
                'total_project_value': 0,
                'period_days': recent_days
            }

    async def _get_crime_trends(
        self,
        market_id: str,
        recent_days: int = 180
    ) -> Dict[str, Any]:
        """Analyze market-wide crime trends and safety scores"""

        try:
            query = text(f"""
                WITH current_period AS (
                    SELECT
                        COUNT(*) as total_incidents,
                        COUNT(CASE WHEN incident_type ILIKE '%violent%'
                                    OR incident_type ILIKE '%assault%'
                                    OR incident_type ILIKE '%robbery%' THEN 1 END) as violent_crimes
                    FROM crime_reports
                    WHERE market_id = :market_id
                      AND incident_date >= CURRENT_DATE - INTERVAL '{recent_days} days'
                ),
                prior_period AS (
                    SELECT COUNT(*) as total_incidents
                    FROM crime_reports
                    WHERE market_id = :market_id
                      AND incident_date >= CURRENT_DATE - INTERVAL '{recent_days * 2} days'
                      AND incident_date < CURRENT_DATE - INTERVAL '{recent_days} days'
                ),
                by_type AS (
                    SELECT
                        incident_type,
                        COUNT(*) as count
                    FROM crime_reports
                    WHERE market_id = :market_id
                      AND incident_date >= CURRENT_DATE - INTERVAL '{recent_days} days'
                    GROUP BY incident_type
                    ORDER BY count DESC
                    LIMIT 5
                )
                SELECT
                    current_period.total_incidents,
                    current_period.violent_crimes,
                    prior_period.total_incidents,
                    CASE
                        WHEN prior_period.total_incidents > 0
                        THEN ((current_period.total_incidents - prior_period.total_incidents)::float / prior_period.total_incidents) * 100
                        ELSE 0
                    END as trend_pct,
                    array_agg(by_type.incident_type) as top_incident_types,
                    array_agg(by_type.count) as top_incident_counts
                FROM current_period, prior_period, by_type
                GROUP BY current_period.total_incidents, current_period.violent_crimes, prior_period.total_incidents
            """)

            result = await self.session.execute(
                query,
                {'market_id': market_id}
            )
            row = result.fetchone()

            if not row:
                return {
                    'total_incidents': 0,
                    'violent_crimes': 0,
                    'prior_period_incidents': 0,
                    'trend_pct': 0,
                    'top_incident_types': [],
                    'period_days': recent_days
                }

            current_incidents = int(row[0]) if row[0] else 0
            violent_crimes = int(row[1]) if row[1] else 0
            prior_incidents = int(row[2]) if row[2] else 0
            trend_pct = float(row[3]) if row[3] else 0

            top_types = []
            if row[4] and row[5]:
                for i in range(min(len(row[4]), len(row[5]))):
                    top_types.append({
                        'incident_type': row[4][i],
                        'count': int(row[5][i])
                    })

            return {
                'total_incidents': current_incidents,
                'violent_crimes': violent_crimes,
                'prior_period_incidents': prior_incidents,
                'trend_pct': round(trend_pct, 1),
                'top_incident_types': top_types,
                'period_days': recent_days
            }

        except Exception as e:
            logger.warning("crime_trends_query_failed", error=str(e))
            return {
                'total_incidents': 0,
                'violent_crimes': 0,
                'prior_period_incidents': 0,
                'trend_pct': 0,
                'top_incident_types': [],
                'period_days': recent_days
            }

    async def _get_development_sentiment(
        self,
        market_id: str,
        recent_days: int = 180
    ) -> Dict[str, Any]:
        """Analyze development sentiment from council and news for political climate"""

        result = {
            'council_activity': None,
            'news_coverage': None
        }

        try:
            # Council development activity
            council_query = text(f"""
                SELECT
                    COUNT(*) as meeting_count,
                    COUNT(CASE WHEN 'development' = ANY(topics)
                               OR 'zoning' = ANY(topics)
                               OR 'rezoning' = ANY(topics) THEN 1 END) as development_meetings,
                    array_agg(meeting_type) FILTER (WHERE meeting_type IS NOT NULL) as meeting_types
                FROM council_meetings
                WHERE market_id = :market_id
                  AND meeting_date >= CURRENT_DATE - INTERVAL '{recent_days} days'
            """)

            council_result = await self.session.execute(
                council_query,
                {'market_id': market_id}
            )
            council_row = council_result.fetchone()

            if council_row and council_row[0]:
                result['council_activity'] = {
                    'total_meetings': int(council_row[0]),
                    'development_related': int(council_row[1]) if council_row[1] else 0,
                    'meeting_types': list(set(council_row[2])) if council_row[2] else []
                }

            # News development coverage
            news_query = text(f"""
                SELECT
                    COUNT(*) as article_count,
                    COUNT(CASE WHEN 'development' = ANY(topics)
                               OR 'real estate' = ANY(topics)
                               OR 'construction' = ANY(topics) THEN 1 END) as development_articles,
                    AVG(relevance_score) as avg_relevance
                FROM news_articles
                WHERE market_id = :market_id
                  AND published_date >= CURRENT_DATE - INTERVAL '{recent_days} days'
            """)

            news_result = await self.session.execute(
                news_query,
                {'market_id': market_id}
            )
            news_row = news_result.fetchone()

            if news_row and news_row[0]:
                result['news_coverage'] = {
                    'total_articles': int(news_row[0]),
                    'development_related': int(news_row[1]) if news_row[1] else 0,
                    'avg_relevance': round(float(news_row[2]), 2) if news_row[2] else None
                }

        except Exception as e:
            logger.warning("development_sentiment_query_failed", error=str(e))

        return result

    async def _get_permit_velocity(
        self,
        market_id: str,
        recent_days: int = 180
    ) -> Dict[str, Any]:
        """Analyze permit volume trends and market activity"""

        try:
            query = text(f"""
                SELECT
                    COUNT(*) as total_permits,
                    COUNT(DISTINCT contractor_entity_id) as unique_contractors,
                    AVG(project_value) as avg_project_value,
                    SUM(project_value) as total_project_value,
                    mode() WITHIN GROUP (ORDER BY permit_type) as most_common_type
                FROM permits
                WHERE market_id = :market_id
                  AND application_date >= CURRENT_DATE - INTERVAL '{recent_days} days'
            """)

            result = await self.session.execute(
                query,
                {'market_id': market_id}
            )
            row = result.fetchone()

            if not row or not row[0]:
                return {
                    'total_permits': 0,
                    'unique_contractors': 0,
                    'avg_project_value': None,
                    'total_project_value': None,
                    'most_common_permit_type': None,
                    'period_days': recent_days
                }

            return {
                'total_permits': int(row[0]),
                'unique_contractors': int(row[1]) if row[1] else 0,
                'avg_project_value': float(row[2]) if row[2] else None,
                'total_project_value': float(row[3]) if row[3] else None,
                'most_common_permit_type': row[4],
                'period_days': recent_days
            }

        except Exception as e:
            logger.warning("permit_velocity_query_failed", error=str(e))
            return {
                'total_permits': 0,
                'unique_contractors': 0,
                'avg_project_value': None,
                'total_project_value': None,
                'most_common_permit_type': None,
                'period_days': recent_days
            }


    async def _get_multi_developer_permits(
        self,
        market_id: str,
        recent_days: int = 180,
        top_n: int = 10
    ) -> Dict[str, Any]:
        """
        Get permit activity for top developers in market - pure data, no interpretations.
        Returns permits grouped by developer with full details.
        """
        try:
            query = text(f"""
                WITH developer_permits AS (
                    SELECT
                        e.name as entity_name,
                        e.id as entity_id,
                        COUNT(*) as total_permits,
                        jsonb_agg(
                            jsonb_build_object(
                                'permit_number', p.permit_number,
                                'permit_type', p.permit_type,
                                'work_type', p.work_type,
                                'status', p.status,
                                'application_date', p.application_date,
                                'project_value', p.project_value
                            ) ORDER BY p.application_date DESC
                        ) as permits
                    FROM permits p
                    JOIN entities e ON p.contractor_entity_id = e.id
                    WHERE p.market_id = :market_id
                      AND p.application_date >= CURRENT_DATE - INTERVAL '{recent_days} days'
                    GROUP BY e.name, e.id
                    HAVING COUNT(*) > 0
                    ORDER BY COUNT(*) DESC
                    LIMIT :top_n
                )
                SELECT * FROM developer_permits
            """)

            result = await self.session.execute(
                query,
                {'market_id': market_id, 'top_n': top_n}
            )

            developers = []
            for row in result:
                developers.append({
                    'entity_name': row[0],
                    'entity_id': str(row[1]),
                    'total_permits': int(row[2]),
                    'permits': row[3] if row[3] else []
                })

            return {
                'developers': developers,
                'period_days': recent_days,
                'top_n_requested': top_n,
                'developers_found': len(developers)
            }

        except Exception as e:
            logger.warning("multi_developer_permits_query_failed", error=str(e))
            return {
                'developers': [],
                'period_days': recent_days,
                'top_n_requested': top_n,
                'developers_found': 0
            }


    async def _get_demographics(self, market_id: str) -> Dict[str, Any]:
        """
        Get census demographic data for market - pure data, no interpretations.
        """
        try:
            query = text("""
                SELECT
                    total_population,
                    median_household_income,
                    median_home_value,
                    data_year,
                    scraped_at
                FROM market_demographics
                WHERE market_id = :market_id
                ORDER BY data_year DESC
                LIMIT 1
            """)

            result = await self.session.execute(query, {'market_id': market_id})
            row = result.fetchone()

            if not row:
                return {
                    'available': False,
                    'message': 'No demographic data available for this market'
                }

            return {
                'available': True,
                'total_population': int(row[0]) if row[0] else None,
                'median_household_income': int(row[1]) if row[1] else None,
                'median_home_value': int(row[2]) if row[2] else None,
                'data_year': int(row[3]),
                'last_updated': row[4].isoformat() if row[4] else None
            }

        except Exception as e:
            logger.warning("demographics_query_failed", error=str(e))
            return {
                'available': False,
                'error': str(e)
            }


class MarketNotFoundError(Exception):
    """Raised when a market cannot be found"""
    pass
