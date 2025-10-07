"""
Property Analyzer

Analyzes individual properties with comprehensive intelligence including:
- Property details (parcel, zoning, value, characteristics)
- Ownership information (current owner, entity details, portfolio)
- Neighborhood context (nearby properties, recent sales, development activity)
- Historical data (sales history, value trends)

Designed to be:
- Configurable (no hardcoded values)
- Reusable (works for any market, any property)
- Testable (clear inputs/outputs)
- Platform-agnostic (works with any deployment)
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)


class PropertyAnalyzer:
    """
    Comprehensive property analysis engine

    Usage:
        analyzer = PropertyAnalyzer(session)
        result = await analyzer.analyze(property_id="123e4567-...")
        result = await analyzer.analyze(parcel_id="12345-678-90")
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
        property_id: Optional[str] = None,
        parcel_id: Optional[str] = None,
        include_ownership: bool = True,
        include_neighborhood: bool = True,
        include_history: bool = True,
        include_permits: bool = True,
        include_crime: bool = True,
        include_news: bool = True,
        neighborhood_radius_miles: float = 0.5,
        history_years: int = 5
    ) -> Dict[str, Any]:
        """
        Analyze a property comprehensively

        Args:
            property_id: UUID of property in bulk_property_records
            parcel_id: Parcel ID (alternative to property_id)
            include_ownership: Include ownership and entity analysis
            include_neighborhood: Include neighborhood context
            include_history: Include historical data
            neighborhood_radius_miles: Radius for neighborhood analysis
            history_years: Years of history to analyze

        Returns:
            Comprehensive property analysis dict with:
            - property: Core property details
            - ownership: Owner and entity information (if requested)
            - neighborhood: Nearby context (if requested)
            - history: Historical data (if requested)
            - analysis_metadata: When analyzed, what was included

        Raises:
            ValueError: If neither property_id nor parcel_id provided
            PropertyNotFoundError: If property doesn't exist
        """
        if not property_id and not parcel_id:
            raise ValueError("Must provide either property_id or parcel_id")

        logger.info(
            "property_analysis_started",
            property_id=property_id,
            parcel_id=parcel_id,
            include_ownership=include_ownership,
            include_neighborhood=include_neighborhood,
            include_history=include_history
        )

        # Get core property details
        property_data = await self._get_property_details(property_id, parcel_id)

        if not property_data:
            raise PropertyNotFoundError(
                f"Property not found: property_id={property_id}, parcel_id={parcel_id}"
            )

        result = {
            'property': property_data,
            'ownership': None,
            'neighborhood': None,
            'history': None,
            'permits': None,
            'crime_risk': None,
            'news_mentions': None,
            'tax_risk': None,
            'analysis_metadata': {
                'analyzed_at': datetime.now().isoformat(),
                'includes': {
                    'ownership': include_ownership,
                    'neighborhood': include_neighborhood,
                    'history': include_history,
                    'permits': include_permits,
                    'crime': include_crime,
                    'news': include_news
                },
                'parameters': {
                    'neighborhood_radius_miles': neighborhood_radius_miles,
                    'history_years': history_years
                }
            }
        }

        # Get ownership information
        if include_ownership:
            result['ownership'] = await self._get_ownership_info(property_data)

        # Get neighborhood context
        if include_neighborhood:
            result['neighborhood'] = await self._get_neighborhood_context(
                property_data,
                radius_miles=neighborhood_radius_miles
            )

        # Get historical data
        if include_history:
            result['history'] = await self._get_historical_data(
                property_data,
                years=history_years
            )

        # Get permit history
        if include_permits:
            result['permits'] = await self._get_permit_history(property_data)

        # Get crime risk score
        if include_crime:
            result['crime_risk'] = await self._get_crime_risk_score(property_data)

        # Get news mentions
        if include_news:
            result['news_mentions'] = await self._get_news_mentions(property_data)

        # Analyze tax risk (always run - critical for investment decisions)
        result['tax_risk'] = self._analyze_tax_risk(property_data)

        logger.info(
            "property_analysis_completed",
            property_id=property_data['id'],
            parcel_id=property_data['parcel_id'],
            permits_found=len(result.get('permits', {}).get('at_property', [])) if result.get('permits') else 0,
            crime_risk_level=result.get('crime_risk', {}).get('risk_level') if result.get('crime_risk') else None,
            news_mentions_count=len(result.get('news_mentions', [])) if result.get('news_mentions') else 0
        )

        return result

    async def _get_property_details(
        self,
        property_id: Optional[str],
        parcel_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Get core property details from database"""

        # Build query based on what identifier was provided
        if property_id:
            where_clause = "WHERE id = :identifier"
            identifier = property_id
        else:
            where_clause = "WHERE parcel_id = :identifier"
            identifier = parcel_id

        query = text(f"""
            SELECT
                id,
                parcel_id,
                market_id,
                site_address,
                city,
                latitude,
                longitude,
                owner_name,
                mailing_address,
                property_type,
                land_zoning_code,
                land_zoning_desc,
                land_use_code,
                land_use_desc,
                market_value,
                assessed_value,
                taxable_value,
                exemptions,
                land_value,
                improvement_value,
                lot_size_acres,
                square_feet,
                year_built,
                bedrooms,
                bathrooms,
                last_sale_date,
                last_sale_price,
                use_code,
                sales_history,
                building_details,
                trim_notice,
                created_at,
                updated_at
            FROM bulk_property_records
            {where_clause}
            LIMIT 1
        """)

        result = await self.session.execute(query, {'identifier': identifier})
        row = result.fetchone()

        if not row:
            return None

        return {
            'id': str(row[0]),
            'parcel_id': row[1],
            'market_id': str(row[2]),
            'location': {
                'address': row[3],
                'city': row[4],
                'coordinates': {
                    'latitude': float(row[5]) if row[5] else None,
                    'longitude': float(row[6]) if row[6] else None
                }
            },
            'ownership': {
                'owner_name': row[7],
                'mailing_address': row[8]
            },
            'classification': {
                'property_type': row[9],
                'zoning_code': row[10],
                'zoning_desc': row[11],
                'land_use_code': row[12],
                'land_use_desc': row[13],
                'use_code': row[27] if len(row) > 27 else None
            },
            'valuation': {
                'market_value': float(row[14]) if row[14] else None,
                'assessed_value': float(row[15]) if row[15] else None,
                'taxable_value': float(row[16]) if row[16] else None,
                'exemptions': row[17] if row[17] else [],
                'land_value': float(row[18]) if row[18] else None,
                'improvement_value': float(row[19]) if row[19] else None
            },
            'characteristics': {
                'lot_size_acres': float(row[20]) if row[20] else None,
                'building_sqft': int(row[21]) if row[21] else None,
                'year_built': int(row[22]) if row[22] else None,
                'bedrooms': int(row[23]) if row[23] else None,
                'bathrooms': float(row[24]) if row[24] else None,
                'building_details': row[29] if len(row) > 29 else None
            },
            'sales': {
                'last_sale_date': row[25].isoformat() if row[25] else None,
                'last_sale_price': float(row[26]) if row[26] else None,
                'sales_history': row[28] if len(row) > 28 else []
            },
            'tax_info': {
                'trim_notice': row[30] if len(row) > 30 else None
            },
            'metadata': {
                'created_at': row[31].isoformat() if len(row) > 31 and row[31] else None,
                'updated_at': row[32].isoformat() if len(row) > 32 and row[32] else None
            }
        }

    async def _get_ownership_info(
        self,
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get detailed ownership and entity information"""

        owner_name = property_data['ownership']['owner_name']

        if not owner_name:
            return {
                'entity': None,
                'portfolio': None
            }

        # Get entity information
        query = text("""
            SELECT
                e.id,
                e.entity_type,
                e.name,
                e.canonical_name,
                e.primary_address,
                e.confidence_score,
                e.verification_source,
                emp.total_properties,
                emp.total_value,
                emp.first_activity_date,
                emp.last_activity_date
            FROM entities e
            LEFT JOIN entity_market_properties emp ON emp.entity_id = e.id
                AND emp.market_id = :market_id
            WHERE e.name = :owner_name
            LIMIT 1
        """)

        result = await self.session.execute(
            query,
            {
                'owner_name': owner_name,
                'market_id': property_data['market_id']
            }
        )
        row = result.fetchone()

        if not row:
            return {
                'entity': None,
                'portfolio': None
            }

        entity_data = {
            'id': str(row[0]),
            'type': row[1],
            'name': row[2],
            'canonical_name': row[3],
            'primary_address': row[4],
            'confidence_score': float(row[5]) if row[5] else None,
            'verification_source': row[6]
        }

        portfolio_data = None
        if row[7]:  # Has portfolio data
            portfolio_data = {
                'total_properties': int(row[7]),
                'total_value': float(row[8]) if row[8] else None,
                'first_activity_date': row[9].isoformat() if row[9] else None,
                'last_activity_date': row[10].isoformat() if row[10] else None,
                'average_property_value': (
                    float(row[8]) / int(row[7])
                    if row[8] and row[7] and int(row[7]) > 0
                    else None
                )
            }

        return {
            'entity': entity_data,
            'portfolio': portfolio_data
        }

    async def _get_neighborhood_context(
        self,
        property_data: Dict[str, Any],
        radius_miles: float = 0.5
    ) -> Optional[Dict[str, Any]]:
        """Get neighborhood context (nearby properties, recent activity)"""

        coords = property_data['location']['coordinates']
        if not coords['latitude'] or not coords['longitude']:
            return None

        # Get nearby properties using Haversine formula
        # 1 degree latitude ≈ 69 miles
        # 1 degree longitude ≈ 69 miles * cos(latitude)
        # For simplicity, using a square bounding box
        lat_delta = radius_miles / 69.0
        lon_delta = radius_miles / 69.0

        # Get property type and zoning for filtering comps
        property_type = property_data['classification']['property_type']
        zoning_code = property_data['classification']['zoning_code']

        query = text("""
            SELECT
                COUNT(*) as total_properties,
                AVG(market_value) as avg_market_value,
                AVG(assessed_value) as avg_assessed_value,
                AVG(square_feet) as avg_sqft,
                COUNT(CASE WHEN last_sale_date >= :recent_date THEN 1 END) as recent_sales,
                AVG(CASE WHEN last_sale_date >= :recent_date THEN last_sale_price END) as avg_recent_price
            FROM bulk_property_records
            WHERE market_id = :market_id
              AND id != :property_id
              AND latitude BETWEEN :min_lat AND :max_lat
              AND longitude BETWEEN :min_lon AND :max_lon
              AND property_type = :property_type
              AND (land_zoning_code = :zoning_code OR land_zoning_code IS NULL)
        """)

        recent_date = datetime.now() - timedelta(days=180)

        result = await self.session.execute(
            query,
            {
                'market_id': property_data['market_id'],
                'property_id': property_data['id'],
                'min_lat': coords['latitude'] - lat_delta,
                'max_lat': coords['latitude'] + lat_delta,
                'min_lon': coords['longitude'] - lon_delta,
                'max_lon': coords['longitude'] + lon_delta,
                'recent_date': recent_date,
                'property_type': property_type,
                'zoning_code': zoning_code
            }
        )
        row = result.fetchone()

        if not row or row[0] == 0:
            return {
                'radius_miles': radius_miles,
                'total_properties': 0,
                'stats': None,
                'recent_activity': None
            }

        return {
            'radius_miles': radius_miles,
            'total_properties': int(row[0]),
            'stats': {
                'avg_market_value': float(row[1]) if row[1] else None,
                'avg_assessed_value': float(row[2]) if row[2] else None,
                'avg_building_sqft': float(row[3]) if row[3] else None
            },
            'recent_activity': {
                'recent_sales_count': int(row[4]) if row[4] else 0,
                'avg_recent_sale_price': float(row[5]) if row[5] else None,
                'period_days': 180
            }
        }

    async def _get_historical_data(
        self,
        property_data: Dict[str, Any],
        years: int = 5
    ) -> Dict[str, Any]:
        """Get historical data for this property"""

        # For now, we only have current snapshot data
        # This will be enhanced when we add historical tracking

        return {
            'years_requested': years,
            'available': False,
            'note': 'Historical tracking not yet implemented. Current snapshot only.',
            'current_snapshot': {
                'market_value': property_data['valuation']['market_value'],
                'assessed_value': property_data['valuation']['assessed_value'],
                'last_sale_date': property_data['sales']['last_sale_date'],
                'last_sale_price': property_data['sales']['last_sale_price']
            }
        }

    async def _get_permit_history(
        self,
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get permit history at property and nearby for construction activity analysis"""

        parcel_id = property_data['parcel_id']
        market_id = property_data['market_id']

        result = {
            'at_property': [],
            'nearby_activity': None
        }

        try:
            # Permits at this property
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
                  AND market_id = :market_id
                ORDER BY application_date DESC
                LIMIT 20
            """)

            result_at = await self.session.execute(
                query_at_property,
                {'parcel_id': parcel_id, 'market_id': market_id}
            )

            for row in result_at:
                result['at_property'].append({
                    'permit_number': row[0],
                    'permit_type': row[1],
                    'work_type': row[2],
                    'project_name': row[3],
                    'description': row[4],
                    'value': float(row[5]) if row[5] else None,
                    'status': row[6],
                    'application_date': row[7].isoformat() if row[7] else None,
                    'issued_date': row[8].isoformat() if row[8] else None,
                    'final_inspection_date': row[9].isoformat() if row[9] else None,
                    'jurisdiction': row[10],
                    'permit_fee': float(row[11]) if row[11] else None
                })

            # Nearby permit activity (for development context)
            coords = property_data['location']['coordinates']
            if coords['latitude'] and coords['longitude']:
                lat_delta = 0.5 / 69.0
                lon_delta = 0.5 / 69.0

                query_nearby = text("""
                    SELECT
                        COUNT(*) as total_permits,
                        COUNT(CASE WHEN work_type = 'New Construction' THEN 1 END) as new_construction,
                        COUNT(CASE WHEN status = 'Issued' THEN 1 END) as active_permits,
                        SUM(project_value) as total_value
                    FROM permits p
                    JOIN bulk_property_records bpr ON bpr.parcel_id = p.parcel_id AND bpr.market_id = p.market_id
                    WHERE p.market_id = :market_id
                      AND bpr.latitude BETWEEN :min_lat AND :max_lat
                      AND bpr.longitude BETWEEN :min_lon AND :max_lon
                      AND p.application_date >= CURRENT_DATE - INTERVAL '180 days'
                      AND bpr.parcel_id != :parcel_id
                """)

                result_nearby = await self.session.execute(
                    query_nearby,
                    {
                        'market_id': market_id,
                        'parcel_id': parcel_id,
                        'min_lat': coords['latitude'] - lat_delta,
                        'max_lat': coords['latitude'] + lat_delta,
                        'min_lon': coords['longitude'] - lon_delta,
                        'max_lon': coords['longitude'] + lon_delta
                    }
                )
                row = result_nearby.fetchone()

                if row and row[0]:
                    result['nearby_activity'] = {
                        'total_permits_180d': int(row[0]),
                        'new_construction_count': int(row[1]) if row[1] else 0,
                        'active_permits': int(row[2]) if row[2] else 0,
                        'total_project_value': float(row[3]) if row[3] else None,
                        'radius_miles': 0.5
                    }

        except Exception as e:
            logger.warning("permit_history_query_failed", error=str(e))

        return result

    async def _get_crime_risk_score(
        self,
        property_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Calculate crime risk score for neighborhood with trend analysis"""

        coords = property_data['location']['coordinates']
        if not coords['latitude'] or not coords['longitude']:
            return None

        market_id = property_data['market_id']
        lat_delta = 0.5 / 69.0
        lon_delta = 0.5 / 69.0

        try:
            query = text("""
                WITH current_period AS (
                    SELECT
                        COUNT(*) as incidents,
                        COUNT(CASE WHEN incident_type ILIKE '%violent%'
                                    OR incident_type ILIKE '%assault%'
                                    OR incident_type ILIKE '%robbery%' THEN 1 END) as violent_crimes
                    FROM crime_reports
                    WHERE market_id = :market_id
                      AND latitude BETWEEN :min_lat AND :max_lat
                      AND longitude BETWEEN :min_lon AND :max_lon
                      AND incident_date >= CURRENT_DATE - INTERVAL '180 days'
                ),
                prior_period AS (
                    SELECT COUNT(*) as incidents
                    FROM crime_reports
                    WHERE market_id = :market_id
                      AND latitude BETWEEN :min_lat AND :max_lat
                      AND longitude BETWEEN :min_lon AND :max_lon
                      AND incident_date >= CURRENT_DATE - INTERVAL '365 days'
                      AND incident_date < CURRENT_DATE - INTERVAL '180 days'
                )
                SELECT
                    current_period.incidents as current_incidents,
                    current_period.violent_crimes,
                    prior_period.incidents as prior_incidents,
                    CASE
                        WHEN prior_period.incidents > 0
                        THEN ((current_period.incidents - prior_period.incidents)::float / prior_period.incidents) * 100
                        ELSE 0
                    END as trend_pct
                FROM current_period, prior_period
            """)

            result = await self.session.execute(
                query,
                {
                    'market_id': market_id,
                    'min_lat': coords['latitude'] - lat_delta,
                    'max_lat': coords['latitude'] + lat_delta,
                    'min_lon': coords['longitude'] - lon_delta,
                    'max_lon': coords['longitude'] + lon_delta
                }
            )
            row = result.fetchone()

            if not row:
                return None

            current_incidents = int(row[0]) if row[0] else 0
            violent_crimes = int(row[1]) if row[1] else 0
            prior_incidents = int(row[2]) if row[2] else 0
            trend_pct = float(row[3]) if row[3] else 0

            # Calculate risk level
            if current_incidents == 0:
                risk_level = 'very_low'
            elif current_incidents < 5:
                risk_level = 'low'
            elif current_incidents < 15:
                risk_level = 'moderate'
            elif current_incidents < 30:
                risk_level = 'high'
            else:
                risk_level = 'very_high'

            return {
                'current_incidents_180d': current_incidents,
                'violent_crimes_180d': violent_crimes,
                'prior_period_incidents_180d': prior_incidents,
                'trend_pct': round(trend_pct, 1),
                'trend': 'increasing' if trend_pct > 10 else 'decreasing' if trend_pct < -10 else 'stable',
                'risk_level': risk_level,
                'radius_miles': 0.5
            }

        except Exception as e:
            logger.warning("crime_risk_query_failed", error=str(e))
            return None

    async def _get_news_mentions(
        self,
        property_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get news articles mentioning this property or address"""

        address = property_data['location']['address']
        market_id = property_data['market_id']

        if not address:
            return []

        try:
            # Extract key parts of address for search
            address_parts = address.split()
            search_terms = ' '.join(address_parts[:3]) if len(address_parts) >= 3 else address

            query = text("""
                SELECT
                    title,
                    url,
                    published_date,
                    source,
                    summary,
                    relevance_score
                FROM news_articles
                WHERE market_id = :market_id
                  AND (
                      title ILIKE :search_term
                      OR article_text ILIKE :search_term
                      OR summary ILIKE :search_term
                  )
                  AND published_date >= CURRENT_DATE - INTERVAL '365 days'
                ORDER BY published_date DESC
                LIMIT 5
            """)

            result = await self.session.execute(
                query,
                {
                    'market_id': market_id,
                    'search_term': f'%{search_terms}%'
                }
            )

            news_mentions = []
            for row in result:
                news_mentions.append({
                    'title': row[0],
                    'url': row[1],
                    'published_date': row[2].isoformat() if row[2] else None,
                    'source': row[3],
                    'summary': row[4],
                    'relevance_score': float(row[5]) if row[5] else None
                })

            return news_mentions

        except Exception as e:
            logger.warning("news_mentions_query_failed", error=str(e))
            return []

    def _analyze_tax_risk(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze tax-related risks from TRIM notice data

        Returns risk assessment including:
        - Tax delinquency status
        - Amount owed
        - Lien information
        - Risk score impact
        """
        trim_notice = property_data.get('tax_info', {}).get('trim_notice')

        result = {
            'has_trim_data': trim_notice is not None,
            'is_delinquent': False,
            'delinquent_amount': None,
            'lien_filed': False,
            'lien_date': None,
            'certificate_sold': False,
            'delinquent_years': [],
            'total_due': None,
            'risk_level': 'none',
            'risk_score_impact': 0
        }

        if not trim_notice:
            return result

        # Parse delinquency information
        delinquent_info = trim_notice.get('delinquent', {})

        if delinquent_info.get('is_delinquent'):
            result['is_delinquent'] = True
            result['delinquent_amount'] = delinquent_info.get('amount_owed')
            result['delinquent_years'] = delinquent_info.get('years', [])
            result['total_due'] = delinquent_info.get('total_due')

            # Check for tax lien
            if delinquent_info.get('lien_filed'):
                result['lien_filed'] = True
                result['lien_date'] = delinquent_info.get('lien_filed')
                result['risk_level'] = 'critical'
                result['risk_score_impact'] = -25  # Major red flag
            elif delinquent_info.get('certificate_sold'):
                result['certificate_sold'] = True
                result['risk_level'] = 'high'
                result['risk_score_impact'] = -20  # Tax certificate sold
            elif result['delinquent_amount'] and result['delinquent_amount'] > 10000:
                result['risk_level'] = 'high'
                result['risk_score_impact'] = -15  # Large delinquency
            elif len(result['delinquent_years']) > 1:
                result['risk_level'] = 'moderate'
                result['risk_score_impact'] = -10  # Multiple years delinquent
            else:
                result['risk_level'] = 'low'
                result['risk_score_impact'] = -5  # Current year only

        return result


class PropertyNotFoundError(Exception):
    """Raised when a property cannot be found"""
    pass
