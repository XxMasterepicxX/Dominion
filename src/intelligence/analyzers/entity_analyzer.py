"""
Entity Analyzer

Analyzes entities (property owners, LLCs, corporations, individuals) including:
- Entity profile (type, name, address, confidence)
- Property portfolio (total properties, value, locations)
- Activity patterns (acquisition timeline, market preferences)
- Cross-market presence (if entity owns in multiple markets)

Designed to be:
- Configurable (no hardcoded values)
- Reusable (works for any entity, any market)
- Testable (clear inputs/outputs)
- Platform-agnostic (works with any deployment)
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)


class EntityAnalyzer:
    """
    Comprehensive entity analysis engine

    Usage:
        analyzer = EntityAnalyzer(session)
        result = await analyzer.analyze(entity_id="123e4567-...")
        result = await analyzer.analyze(entity_name="ABC Development LLC")
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
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        market_id: Optional[str] = None,
        include_portfolio: bool = True,
        include_activity_patterns: bool = True,
        include_cross_market: bool = True,
        include_contractor_performance: bool = True,
        include_sentiment: bool = True,
        include_network: bool = True,
        include_sunbiz: bool = True,
        recent_activity_days: int = 180
    ) -> Dict[str, Any]:
        """
        Analyze an entity comprehensively

        Args:
            entity_id: UUID of entity
            entity_name: Name of entity (alternative to entity_id)
            market_id: Specific market to analyze (optional, analyzes all if not provided)
            include_portfolio: Include portfolio details
            include_activity_patterns: Include activity pattern analysis
            include_cross_market: Include cross-market analysis
            recent_activity_days: Days to consider as "recent" activity

        Returns:
            Comprehensive entity analysis dict with:
            - entity: Core entity details
            - portfolio: Portfolio summary and details (if requested)
            - activity_patterns: Activity analysis (if requested)
            - cross_market: Multi-market presence (if requested)
            - analysis_metadata: When analyzed, what was included

        Raises:
            ValueError: If neither entity_id nor entity_name provided
            EntityNotFoundError: If entity doesn't exist
        """
        if not entity_id and not entity_name:
            raise ValueError("Must provide either entity_id or entity_name")

        logger.info(
            "entity_analysis_started",
            entity_id=entity_id,
            entity_name=entity_name,
            market_id=market_id
        )

        # Get core entity details
        entity_data = await self._get_entity_details(entity_id, entity_name)

        if not entity_data:
            raise EntityNotFoundError(
                f"Entity not found: entity_id={entity_id}, entity_name={entity_name}"
            )

        result = {
            'entity': entity_data,
            'portfolio': None,
            'activity_patterns': None,
            'cross_market': None,
            'contractor_performance': None,
            'permit_applicant_activity': None,
            'permit_owner_activity': None,
            'sentiment': None,
            'network': None,
            'sunbiz_history': None,
            'analysis_metadata': {
                'analyzed_at': datetime.now().isoformat(),
                'market_id': market_id,
                'includes': {
                    'portfolio': include_portfolio,
                    'activity_patterns': include_activity_patterns,
                    'cross_market': include_cross_market,
                    'contractor_performance': include_contractor_performance,
                    'sentiment': include_sentiment,
                    'network': include_network,
                    'sunbiz': include_sunbiz
                },
                'parameters': {
                    'recent_activity_days': recent_activity_days
                }
            }
        }

        # Get portfolio information
        if include_portfolio:
            result['portfolio'] = await self._get_portfolio_details(
                entity_data['id'],
                market_id
            )

        # Get activity patterns
        if include_activity_patterns:
            result['activity_patterns'] = await self._get_activity_patterns(
                entity_data['id'],
                market_id,
                recent_days=recent_activity_days
            )

        # Get cross-market presence
        if include_cross_market:
            result['cross_market'] = await self._get_cross_market_presence(
                entity_data['id']
            )

        # Get contractor performance
        if include_contractor_performance:
            result['contractor_performance'] = await self._get_contractor_performance(
                entity_data['id'],
                market_id
            )

        # Get permit applicant activity (who's filing permits)
        result['permit_applicant_activity'] = await self._get_permit_applicant_activity(
            entity_data['id'],
            market_id
        )

        # Get permit owner activity (development on owned properties)
        result['permit_owner_activity'] = await self._get_permit_owner_activity(
            entity_data['id'],
            market_id
        )

        # Get entity sentiment
        if include_sentiment:
            result['sentiment'] = await self._get_entity_sentiment(
                entity_data['id'],
                entity_data['name'],
                market_id
            )

        # Get entity network
        if include_network:
            result['network'] = await self._get_entity_network(entity_data['id'])

        # Get Sunbiz history
        if include_sunbiz:
            result['sunbiz_history'] = await self._get_sunbiz_history(entity_data['id'])

        # Safely extract logging values
        news_mentions = 0
        if result.get('sentiment') and result['sentiment'].get('news_mentions'):
            news_mentions = result['sentiment']['news_mentions'].get('mention_count_365d', 0)

        network_size = 0
        if result.get('network'):
            network_size = result['network'].get('network_size', 0)

        logger.info(
            "entity_analysis_completed",
            entity_id=entity_data['id'],
            entity_name=entity_data['name'],
            is_contractor=result.get('contractor_performance') is not None,
            news_mentions=news_mentions,
            network_size=network_size
        )

        return result

    async def _get_entity_details(
        self,
        entity_id: Optional[str],
        entity_name: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Get core entity details from database"""

        # Build query based on what identifier was provided
        if entity_id:
            where_clause = "WHERE id = :identifier"
            identifier = entity_id
        else:
            where_clause = "WHERE name = :identifier"
            identifier = entity_name

        query = text(f"""
            SELECT
                id,
                entity_type,
                name,
                canonical_name,
                primary_address,
                confidence_score,
                verification_source,
                officers,
                active_markets,
                phone,
                email,
                website,
                formation_date,
                registered_agent,
                created_at,
                updated_at
            FROM entities
            {where_clause}
            LIMIT 1
        """)

        result = await self.session.execute(query, {'identifier': identifier})
        row = result.fetchone()

        if not row:
            return None

        return {
            'id': str(row[0]),
            'type': row[1],
            'name': row[2],
            'canonical_name': row[3],
            'primary_address': row[4],
            'confidence_score': float(row[5]) if row[5] else None,
            'verification_source': row[6],
            'officers': row[7] if row[7] else [],
            'active_markets': [str(m) for m in row[8]] if row[8] else [],
            'contact': {
                'phone': row[9],
                'email': row[10],
                'website': row[11]
            },
            'formation_date': row[12].isoformat() if row[12] else None,
            'registered_agent': row[13],
            'created_at': row[14].isoformat() if row[14] else None,
            'updated_at': row[15].isoformat() if row[15] else None
        }

    async def _get_portfolio_details(
        self,
        entity_id: str,
        market_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get portfolio details for entity"""

        # Build market filter
        market_filter = ""
        params = {'entity_id': entity_id}
        if market_id:
            market_filter = "AND emp.market_id = :market_id"
            params['market_id'] = market_id

        # Get portfolio summary
        query = text(f"""
            SELECT
                COUNT(DISTINCT emp.market_id) as markets_count,
                SUM(emp.total_properties) as total_properties,
                SUM(emp.total_value) as total_value,
                MIN(emp.first_activity_date) as first_activity,
                MAX(emp.last_activity_date) as last_activity
            FROM entity_market_properties emp
            WHERE emp.entity_id = :entity_id
            {market_filter}
        """)

        result = await self.session.execute(query, params)
        row = result.fetchone()

        if not row or not row[1]:
            return {
                'summary': {
                    'markets_count': 0,
                    'total_properties': 0,
                    'total_value': None,
                    'first_activity': None,
                    'last_activity': None
                },
                'by_market': []
            }

        summary = {
            'markets_count': int(row[0]) if row[0] else 0,
            'total_properties': int(row[1]) if row[1] else 0,
            'total_value': float(row[2]) if row[2] else None,
            'first_activity': row[3].isoformat() if row[3] else None,
            'last_activity': row[4].isoformat() if row[4] else None,
            'average_property_value': (
                float(row[2]) / int(row[1])
                if row[2] and row[1] and int(row[1]) > 0
                else None
            )
        }

        # Get breakdown by market
        query = text(f"""
            SELECT
                m.market_code,
                m.market_name,
                emp.total_properties,
                emp.total_value,
                emp.first_activity_date,
                emp.last_activity_date
            FROM entity_market_properties emp
            JOIN markets m ON m.id = emp.market_id
            WHERE emp.entity_id = :entity_id
            {market_filter}
            ORDER BY emp.total_properties DESC
        """)

        result = await self.session.execute(query, params)
        by_market = []
        for row in result:
            by_market.append({
                'market_code': row[0],
                'market_name': row[1],
                'total_properties': int(row[2]),
                'total_value': float(row[3]) if row[3] else None,
                'first_activity': row[4].isoformat() if row[4] else None,
                'last_activity': row[5].isoformat() if row[5] else None
            })

        return {
            'summary': summary,
            'by_market': by_market
        }

    async def _get_activity_patterns(
        self,
        entity_id: str,
        market_id: Optional[str] = None,
        recent_days: int = 180
    ) -> Dict[str, Any]:
        """Analyze entity activity patterns"""

        # Build market filter
        market_filter = ""
        params = {
            'entity_id': entity_id,
            'recent_date': datetime.now() - timedelta(days=recent_days)
        }
        if market_id:
            market_filter = "AND bp.market_id = :market_id"
            params['market_id'] = market_id

        # Get property type preferences
        query = text(f"""
            SELECT
                bp.property_type,
                COUNT(*) as count,
                AVG(bp.market_value) as avg_value,
                COUNT(CASE WHEN bp.last_sale_date >= :recent_date THEN 1 END) as recent_count
            FROM bulk_property_records bp
            JOIN entities e ON e.name = bp.owner_name
            WHERE e.id = :entity_id
            {market_filter}
            GROUP BY bp.property_type
            ORDER BY count DESC
        """)

        result = await self.session.execute(query, params)
        property_types = []
        for row in result:
            property_types.append({
                'property_type': row[0],
                'total_count': int(row[1]),
                'avg_value': float(row[2]) if row[2] else None,
                'recent_acquisitions': int(row[3]) if row[3] else 0
            })

        # Get acquisition timeline
        query = text(f"""
            SELECT
                DATE_TRUNC('year', bp.last_sale_date) as year,
                COUNT(*) as acquisitions,
                SUM(bp.last_sale_price) as total_invested
            FROM bulk_property_records bp
            JOIN entities e ON e.name = bp.owner_name
            WHERE e.id = :entity_id
              AND bp.last_sale_date IS NOT NULL
            {market_filter}
            GROUP BY DATE_TRUNC('year', bp.last_sale_date)
            ORDER BY year DESC
            LIMIT 10
        """)

        result = await self.session.execute(query, params)
        timeline = []
        for row in result:
            timeline.append({
                'year': row[0].year if row[0] else None,
                'acquisitions': int(row[1]),
                'total_invested': float(row[2]) if row[2] else None
            })

        return {
            'property_type_preferences': property_types,
            'acquisition_timeline': timeline,
            'recent_activity_period_days': recent_days
        }

    async def _get_cross_market_presence(
        self,
        entity_id: str
    ) -> Dict[str, Any]:
        """Analyze entity's presence across multiple markets"""

        query = text("""
            SELECT
                COUNT(DISTINCT emp.market_id) as total_markets,
                BOOL_OR(emp.total_properties >= 2) as has_assemblages,
                MAX(emp.total_properties) as max_properties_single_market,
                MIN(emp.first_activity_date) as earliest_activity,
                MAX(emp.last_activity_date) as latest_activity
            FROM entity_market_properties emp
            WHERE emp.entity_id = :entity_id
        """)

        result = await self.session.execute(query, {'entity_id': entity_id})
        row = result.fetchone()

        if not row or row[0] == 0:
            return {
                'active_in_multiple_markets': False,
                'total_markets': 0,
                'insights': None
            }

        total_markets = int(row[0])
        is_multi_market = total_markets > 1

        insights = None
        if is_multi_market:
            insights = {
                'expansion_strategy': 'Geographic diversification',
                'largest_market_holdings': int(row[2]) if row[2] else 0,
                'potential_assemblages': bool(row[1]),
                'activity_span_years': (
                    (row[4].year - row[3].year)
                    if row[3] and row[4]
                    else None
                )
            }

        return {
            'active_in_multiple_markets': is_multi_market,
            'total_markets': total_markets,
            'insights': insights
        }

    async def _get_contractor_performance(
        self,
        entity_id: str,
        market_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Analyze entity as contractor - project completion rates, specialization, performance"""

        market_filter = ""
        params = {'entity_id': entity_id}
        if market_id:
            market_filter = "AND market_id = :market_id"
            params['market_id'] = market_id

        try:
            query = text(f"""
                SELECT
                    COUNT(*) as total_projects,
                    COUNT(CASE WHEN status = 'Closed' OR status = 'Finaled' THEN 1 END) as completed_projects,
                    COUNT(CASE WHEN status = 'Issued' OR status = 'Active' THEN 1 END) as active_projects,
                    AVG(project_value) as avg_project_value,
                    SUM(project_value) as total_project_value,
                    MIN(application_date) as first_project,
                    MAX(application_date) as last_project,
                    COUNT(DISTINCT permit_type) as permit_types_count,
                    mode() WITHIN GROUP (ORDER BY permit_type) as primary_permit_type,
                    AVG(
                        CASE WHEN final_inspection_date IS NOT NULL AND issued_date IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (final_inspection_date::timestamp - issued_date::timestamp)) / 86400
                        ELSE NULL
                        END
                    ) as avg_completion_days
                FROM permits
                WHERE contractor_entity_id = :entity_id
                {market_filter}
            """)

            result = await self.session.execute(query, params)
            row = result.fetchone()

            if not row or not row[0]:
                return None

            total_projects = int(row[0])
            completed_projects = int(row[1]) if row[1] else 0
            completion_rate = (completed_projects / total_projects * 100) if total_projects > 0 else 0

            # Determine experience level
            if total_projects >= 50:
                experience_level = 'highly_experienced'
            elif total_projects >= 20:
                experience_level = 'experienced'
            elif total_projects >= 5:
                experience_level = 'moderate'
            else:
                experience_level = 'limited'

            return {
                'total_projects': total_projects,
                'completed_projects': completed_projects,
                'active_projects': int(row[2]) if row[2] else 0,
                'completion_rate_pct': round(completion_rate, 1),
                'avg_project_value': float(row[3]) if row[3] else None,
                'total_project_value': float(row[4]) if row[4] else None,
                'first_project_date': row[5].isoformat() if row[5] else None,
                'last_project_date': row[6].isoformat() if row[6] else None,
                'permit_types_count': int(row[7]) if row[7] else 0,
                'primary_specialization': row[8],
                'avg_completion_days': round(float(row[9]), 1) if row[9] else None,
                'experience_level': experience_level
            }

        except Exception as e:
            logger.warning("contractor_performance_query_failed", error=str(e))
            return None

    async def _get_permit_applicant_activity(
        self,
        entity_id: str,
        market_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Analyze entity as permit applicant - who's filing for permits"""

        market_filter = ""
        params = {'entity_id': entity_id}
        if market_id:
            market_filter = "AND market_id = :market_id"
            params['market_id'] = market_id

        try:
            query = text(f"""
                SELECT
                    COUNT(*) as total_applications,
                    COUNT(DISTINCT permit_type) as permit_types_count,
                    SUM(project_value) as total_project_value,
                    AVG(project_value) as avg_project_value,
                    MIN(application_date) as first_application,
                    MAX(application_date) as last_application,
                    COUNT(CASE WHEN status = 'Issued' OR status = 'Active' THEN 1 END) as active_permits,
                    COUNT(CASE WHEN status = 'Closed' OR status = 'Finaled' THEN 1 END) as completed_permits,
                    mode() WITHIN GROUP (ORDER BY permit_type) as primary_permit_type
                FROM permits
                WHERE applicant_entity_id = :entity_id
                {market_filter}
            """)

            result = await self.session.execute(query, params)
            row = result.fetchone()

            if not row or not row[0]:
                return None

            total_applications = int(row[0])

            return {
                'total_applications': total_applications,
                'permit_types_count': int(row[1]) if row[1] else 0,
                'total_project_value': float(row[2]) if row[2] else None,
                'avg_project_value': float(row[3]) if row[3] else None,
                'first_application_date': row[4].isoformat() if row[4] else None,
                'last_application_date': row[5].isoformat() if row[5] else None,
                'active_permits': int(row[6]) if row[6] else 0,
                'completed_permits': int(row[7]) if row[7] else 0,
                'primary_permit_type': row[8],
                'role': 'applicant'
            }

        except Exception as e:
            logger.warning("permit_applicant_activity_query_failed", error=str(e))
            return None

    async def _get_permit_owner_activity(
        self,
        entity_id: str,
        market_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Analyze entity as property owner at time of permit - development on owned properties"""

        market_filter = ""
        params = {'entity_id': entity_id}
        if market_id:
            market_filter = "AND market_id = :market_id"
            params['market_id'] = market_id

        try:
            query = text(f"""
                SELECT
                    COUNT(*) as total_permits_on_owned,
                    SUM(project_value) as total_project_value,
                    AVG(project_value) as avg_project_value,
                    COUNT(DISTINCT permit_type) as permit_types,
                    COUNT(CASE WHEN work_type = 'New Construction' THEN 1 END) as new_construction,
                    COUNT(CASE WHEN work_type ILIKE '%renovation%' OR work_type ILIKE '%remodel%' THEN 1 END) as renovations,
                    MIN(application_date) as first_permit,
                    MAX(application_date) as last_permit,
                    mode() WITHIN GROUP (ORDER BY permit_type) as primary_permit_type
                FROM permits
                WHERE owner_entity_id = :entity_id
                {market_filter}
            """)

            result = await self.session.execute(query, params)
            row = result.fetchone()

            if not row or not row[0]:
                return None

            total_permits = int(row[0])

            return {
                'total_permits_on_owned_properties': total_permits,
                'total_project_value': float(row[1]) if row[1] else None,
                'avg_project_value': float(row[2]) if row[2] else None,
                'permit_types_count': int(row[3]) if row[3] else 0,
                'new_construction_count': int(row[4]) if row[4] else 0,
                'renovation_count': int(row[5]) if row[5] else 0,
                'first_permit_date': row[6].isoformat() if row[6] else None,
                'last_permit_date': row[7].isoformat() if row[7] else None,
                'primary_permit_type': row[8],
                'role': 'property_owner',
                'is_active_developer': total_permits >= 3  # Threshold for "active developer"
            }

        except Exception as e:
            logger.warning("permit_owner_activity_query_failed", error=str(e))
            return None

    async def _get_entity_sentiment(
        self,
        entity_id: str,
        entity_name: str,
        market_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze entity reputation from news and council mentions"""

        result = {
            'news_mentions': None,
            'council_activity': None,
            'reputation_indicators': []
        }

        market_filter = ""
        params = {'entity_id': entity_id, 'entity_name': entity_name}
        if market_id:
            market_filter = "AND market_id = :market_id"
            params['market_id'] = market_id

        try:
            # News mentions analysis
            news_query = text(f"""
                SELECT
                    COUNT(*) as mention_count,
                    AVG(relevance_score) as avg_relevance,
                    array_agg(title ORDER BY published_date DESC) FILTER (WHERE title IS NOT NULL) as recent_headlines,
                    MAX(published_date) as last_mention
                FROM news_articles
                WHERE (
                    mentioned_entities @> ARRAY[:entity_id]::uuid[]
                    OR title ILIKE :name_pattern
                    OR article_text ILIKE :name_pattern
                )
                {market_filter}
                AND published_date >= CURRENT_DATE - INTERVAL '365 days'
            """)

            news_result = await self.session.execute(
                news_query,
                {**params, 'name_pattern': f'%{entity_name}%'}
            )
            news_row = news_result.fetchone()

            if news_row and news_row[0]:
                result['news_mentions'] = {
                    'mention_count_365d': int(news_row[0]),
                    'avg_relevance': round(float(news_row[1]), 2) if news_row[1] else None,
                    'recent_headlines': news_row[2][:5] if news_row[2] else [],
                    'last_mention_date': news_row[3].isoformat() if news_row[3] else None
                }

            # Council meeting mentions
            council_query = text(f"""
                SELECT
                    COUNT(*) as mention_count,
                    array_agg(DISTINCT meeting_type) as meeting_types,
                    array_agg(topics) FILTER (WHERE topics IS NOT NULL) as all_topics,
                    MAX(meeting_date) as last_mention
                FROM council_meetings
                WHERE (
                    mentioned_entities @> ARRAY[:entity_id]::uuid[]
                    OR summary ILIKE :name_pattern
                    OR :entity_name = ANY(topics)
                )
                {market_filter}
                AND meeting_date >= CURRENT_DATE - INTERVAL '365 days'
            """)

            council_result = await self.session.execute(
                council_query,
                {**params, 'name_pattern': f'%{entity_name}%'}
            )
            council_row = council_result.fetchone()

            if council_row and council_row[0]:
                # Flatten topics array
                all_topics = []
                if council_row[2]:
                    for topic_list in council_row[2]:
                        if topic_list:
                            all_topics.extend(topic_list)

                result['council_activity'] = {
                    'mention_count_365d': int(council_row[0]),
                    'meeting_types': council_row[1] if council_row[1] else [],
                    'topics_mentioned': list(set(all_topics)),
                    'last_mention_date': council_row[3].isoformat() if council_row[3] else None
                }

            # Generate reputation indicators
            if result['news_mentions']:
                if result['news_mentions']['mention_count_365d'] > 10:
                    result['reputation_indicators'].append('high_visibility')
                if result['news_mentions']['avg_relevance'] and result['news_mentions']['avg_relevance'] > 0.7:
                    result['reputation_indicators'].append('significant_news_coverage')

            if result['council_activity']:
                if result['council_activity']['mention_count_365d'] > 5:
                    result['reputation_indicators'].append('active_political_engagement')
                if 'development' in result['council_activity']['topics_mentioned']:
                    result['reputation_indicators'].append('development_activity')

        except Exception as e:
            logger.warning("entity_sentiment_query_failed", error=str(e))

        return result

    async def _get_entity_network(
        self,
        entity_id: str
    ) -> Dict[str, Any]:
        """Map entity relationship network - officers, related entities, connections"""

        result = {
            'related_entities': [],
            'network_size': 0,
            'relationship_types': []
        }

        try:
            query = text("""
                SELECT
                    er.relationship_type,
                    e.id as related_entity_id,
                    e.name as related_entity_name,
                    e.entity_type as related_type,
                    er.confidence_score,
                    er.evidence_sources
                FROM entity_relationships er
                JOIN entities e ON e.id = er.target_entity_id
                WHERE er.source_entity_id = :entity_id
                  AND er.is_active = true
                ORDER BY er.confidence_score DESC NULLS LAST
                LIMIT 20
            """)

            result_query = await self.session.execute(query, {'entity_id': entity_id})

            relationship_types_set = set()
            for row in result_query:
                result['related_entities'].append({
                    'relationship_type': row[0],
                    'entity_id': str(row[1]),
                    'entity_name': row[2],
                    'entity_type': row[3],
                    'confidence_score': float(row[4]) if row[4] else None,
                    'evidence_sources': row[5] if row[5] else []
                })
                relationship_types_set.add(row[0])

            result['network_size'] = len(result['related_entities'])
            result['relationship_types'] = list(relationship_types_set)

        except Exception as e:
            logger.warning("entity_network_query_failed", error=str(e))

        return result

    async def _get_sunbiz_history(
        self,
        entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get LLC formation history and status from Sunbiz"""

        try:
            query = text("""
                SELECT
                    document_number,
                    filing_type,
                    name,
                    status,
                    filing_date,
                    registered_agent,
                    principal_address,
                    officers
                FROM llc_formations
                WHERE entity_id = :entity_id
                ORDER BY filing_date DESC
                LIMIT 1
            """)

            result = await self.session.execute(query, {'entity_id': entity_id})
            row = result.fetchone()

            if not row:
                return None

            return {
                'document_number': row[0],
                'filing_type': row[1],
                'legal_name': row[2],
                'status': row[3],
                'filing_date': row[4].isoformat() if row[4] else None,
                'registered_agent': row[5],
                'principal_address': row[6],
                'officers': row[7] if row[7] else [],
                'years_in_business': (
                    (datetime.now().year - row[4].year)
                    if row[4]
                    else None
                )
            }

        except Exception as e:
            logger.warning("sunbiz_history_query_failed", error=str(e))
            return None


class EntityNotFoundError(Exception):
    """Raised when an entity cannot be found"""
    pass
