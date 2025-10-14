"""
Comparable Sales Analyzer

Analyzes comparable properties (comps) for market valuation:
- Find similar properties that recently sold
- Calculate market value estimates
- Validate asking prices
- Generate CMA-style reports

Designed to be:
- Configurable (no hardcoded values)
- Reusable (works for any property, any market)
- Testable (clear inputs/outputs)
- Platform-agnostic (works with any deployment)
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import statistics

from .location_analyzer import LocationAnalyzer

logger = structlog.get_logger(__name__)


class ComparableSalesAnalyzer:
    """
    Comparable sales analysis for property valuation

    Usage:
        analyzer = ComparableSalesAnalyzer(session)

        # Find comparable sales
        comps = await analyzer.find_comparable_sales(
            subject_property_id="123e4567-...",
            max_distance_miles=1.0,
            max_age_days=180
        )

        # Estimate market value
        estimate = await analyzer.estimate_market_value(
            subject_property_id="123e4567-...",
            comps=comps
        )

        # Full CMA report
        cma = await analyzer.analyze_comps(
            subject_property_id="123e4567-...",
            asking_price=85000
        )
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize analyzer with database session

        Args:
            session: Active SQLAlchemy async session
        """
        self.session = session
        self.location_analyzer = LocationAnalyzer(session)

    async def find_comparable_sales(
        self,
        subject_property_id: str,
        property_type: Optional[str] = None,
        max_distance_miles: float = 1.0,
        max_age_days: int = 180,
        min_comps: int = 3,
        max_comps: int = 10,
        size_tolerance: float = 0.3  # ±30%
    ) -> Dict[str, Any]:
        """
        Find comparable properties that recently sold

        Args:
            subject_property_id: Property to find comps for
            property_type: Filter by property type (or use subject's type)
            max_distance_miles: Maximum distance from subject
            max_age_days: Maximum age of sale (default: 180 days)
            min_comps: Minimum comps to find (may expand search if not met)
            max_comps: Maximum comps to return
            size_tolerance: Size tolerance (0.3 = ±30%)

        Returns:
            Dict with:
            - subject: Subject property details
            - comparable_sales: List of comp properties
            - search_parameters: What filters were used
            - comps_found: Count of comps found
        """
        logger.info(
            "finding_comparable_sales",
            subject_property_id=subject_property_id,
            max_distance_miles=max_distance_miles,
            max_age_days=max_age_days
        )

        # Get subject property details
        subject = await self._get_property_details(subject_property_id)
        if not subject:
            return {
                'error': 'Subject property not found',
                'subject_property_id': subject_property_id
            }

        # Use subject's property type if not specified
        if not property_type:
            property_type = subject.get('property_type')

        # Calculate size range (±30% by default)
        subject_size = subject.get('lot_size_acres')
        if subject_size:
            min_size = subject_size * (1 - size_tolerance)
            max_size = subject_size * (1 + size_tolerance)
        else:
            min_size = None
            max_size = None

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        # Get nearby properties with recent sales
        # Note: LocationAnalyzer fetches limit*3 properties before distance filtering
        # So limit=500 means it will fetch 1500 properties to filter from
        nearby = await self.location_analyzer.find_nearby_properties(
            target_property_id=subject_property_id,
            radius_miles=max_distance_miles,
            property_type=property_type,
            limit=500  # Get plenty to filter from (fetches 1500 before distance filtering)
        )

        if 'error' in nearby:
            return {
                'error': 'Could not find nearby properties',
                'details': nearby['error']
            }

        # Filter for recent sales and similar size
        comps = []
        for prop in nearby.get('properties', []):
            # Must have recent sale data
            if not prop.get('property_id'):
                continue

            # Get full details with sale data
            details_query = text("""
                SELECT
                    id, parcel_id, site_address, property_type,
                    market_value, lot_size_acres,
                    last_sale_date, last_sale_price,
                    latitude, longitude
                FROM bulk_property_records
                WHERE id = :property_id
                  AND last_sale_date IS NOT NULL
                  AND last_sale_date >= :cutoff_date
                  AND last_sale_price IS NOT NULL
                  AND last_sale_price > 0
            """)

            result = await self.session.execute(details_query, {
                'property_id': prop['property_id'],
                'cutoff_date': cutoff_date.date()
            })
            row = result.fetchone()

            if not row:
                continue

            # Check size similarity
            comp_size = float(row[5]) if row[5] else None
            if min_size and max_size and comp_size:
                if comp_size < min_size or comp_size > max_size:
                    continue  # Too different in size

            # Calculate sale age
            sale_date = row[6]
            days_since_sale = (datetime.now().date() - sale_date).days if sale_date else None

            # Calculate distance
            distance = prop.get('distance_miles', 0)

            comps.append({
                'property_id': str(row[0]),
                'parcel_id': row[1],
                'site_address': row[2],
                'property_type': row[3],
                'current_market_value': float(row[4]) if row[4] else None,
                'lot_size_acres': comp_size,
                'sale_date': sale_date.isoformat() if sale_date else None,
                'sale_price': float(row[7]) if row[7] else None,
                'days_since_sale': days_since_sale,
                'distance_miles': distance,
                'latitude': float(row[8]) if row[8] else None,
                'longitude': float(row[9]) if row[9] else None,
                'size_difference_pct': round(((comp_size - subject_size) / subject_size * 100), 1) if (subject_size and comp_size) else None,
                'price_per_acre': round(float(row[7]) / comp_size, 2) if (row[7] and comp_size and comp_size > 0) else None
            })

        # Sort by relevance: closer and more recent are better
        comps.sort(key=lambda x: (x['distance_miles'] * 0.6 + (x['days_since_sale'] / 365) * 0.4))

        # Limit to requested max
        comps = comps[:max_comps]

        logger.info(
            "comparable_sales_found",
            count=len(comps),
            subject_property_id=subject_property_id
        )

        # Calculate price per acre for subject (if available)
        subject_price_per_acre = None
        if subject_size and subject.get('market_value'):
            subject_price_per_acre = round(float(subject['market_value']) / subject_size, 2)

        return {
            'subject': {
                'property_id': subject_property_id,
                'parcel_id': subject.get('parcel_id'),
                'site_address': subject.get('site_address'),
                'property_type': subject.get('property_type'),
                'market_value': subject.get('market_value'),
                'lot_size_acres': subject_size,
                'price_per_acre': subject_price_per_acre,
                'latitude': subject.get('latitude'),
                'longitude': subject.get('longitude')
            },
            'comparable_sales': comps,
            'comps_found': len(comps),
            'search_parameters': {
                'max_distance_miles': max_distance_miles,
                'max_age_days': max_age_days,
                'size_tolerance': size_tolerance,
                'property_type_filter': property_type,
                'cutoff_date': cutoff_date.date().isoformat()
            },
            'meets_minimum': len(comps) >= min_comps
        }

    async def estimate_market_value(
        self,
        subject_property_id: str,
        comps: Optional[List[Dict]] = None,
        max_distance_miles: float = 1.0,
        max_age_days: int = 180
    ) -> Dict[str, Any]:
        """
        Estimate market value based on comparable sales

        Args:
            subject_property_id: Property to value
            comps: Pre-fetched comps (or will fetch if not provided)
            max_distance_miles: Max distance for comp search
            max_age_days: Max age for comp search

        Returns:
            Dict with:
            - estimated_value: Estimated market value
            - value_range: (min, max) range
            - confidence: Confidence score (0-1)
            - comps_used: Number of comps used
            - methodology: How value was calculated
        """
        logger.info(
            "estimating_market_value",
            subject_property_id=subject_property_id
        )

        # Get comps if not provided
        if not comps:
            comp_result = await self.find_comparable_sales(
                subject_property_id=subject_property_id,
                max_distance_miles=max_distance_miles,
                max_age_days=max_age_days
            )
            if 'error' in comp_result:
                return comp_result

            comps = comp_result['comparable_sales']
            subject = comp_result['subject']
        else:
            # Get subject details
            subject_result = await self._get_property_details(subject_property_id)
            if not subject_result:
                return {'error': 'Subject property not found'}
            subject = subject_result

        if not comps:
            return {
                'error': 'No comparable sales found',
                'estimated_value': None,
                'confidence': 0.0
            }

        # Extract sale prices
        sale_prices = [c['sale_price'] for c in comps if c.get('sale_price')]

        if not sale_prices:
            return {
                'error': 'No valid sale prices in comps',
                'estimated_value': None,
                'confidence': 0.0
            }

        # Calculate statistics
        avg_sale_price = statistics.mean(sale_prices)
        median_sale_price = statistics.median(sale_prices)
        min_sale_price = min(sale_prices)
        max_sale_price = max(sale_prices)

        # Use price per acre if available
        price_per_acre_values = [c['price_per_acre'] for c in comps if c.get('price_per_acre')]

        estimated_value = None
        methodology = "average_sale_price"

        if price_per_acre_values and subject.get('lot_size_acres'):
            # Price per acre method (more accurate for land)
            avg_price_per_acre = statistics.mean(price_per_acre_values)
            estimated_value = round(avg_price_per_acre * float(subject['lot_size_acres']), 2)
            methodology = "price_per_acre"
        else:
            # Simple average method
            estimated_value = round(avg_sale_price, 2)
            methodology = "average_sale_price"

        # Calculate confidence based on:
        # - Number of comps (more is better)
        # - Consistency of prices (less variance is better)
        # - Recency (more recent is better)
        # - Proximity (closer is better)

        confidence = 0.0

        # Factor 1: Number of comps (0-0.4)
        comp_count_score = min(len(comps) / 10, 0.4)  # Max at 10 comps

        # Factor 2: Price consistency (0-0.3)
        if len(sale_prices) > 1:
            price_std = statistics.stdev(sale_prices)
            price_cv = price_std / avg_sale_price if avg_sale_price > 0 else 1
            consistency_score = max(0, 0.3 * (1 - price_cv))  # Lower CV = higher score
        else:
            consistency_score = 0.15

        # Factor 3: Recency (0-0.15)
        avg_days_old = statistics.mean([c['days_since_sale'] for c in comps if c.get('days_since_sale')])
        recency_score = max(0, 0.15 * (1 - avg_days_old / 365))  # Fresher = better

        # Factor 4: Proximity (0-0.15)
        avg_distance = statistics.mean([c['distance_miles'] for c in comps])
        proximity_score = max(0, 0.15 * (1 - avg_distance / 5))  # Closer = better

        confidence = round(comp_count_score + consistency_score + recency_score + proximity_score, 2)

        return {
            'estimated_value': estimated_value,
            'value_range': {
                'min': round(min_sale_price, 2),
                'max': round(max_sale_price, 2)
            },
            'statistics': {
                'average': round(avg_sale_price, 2),
                'median': round(median_sale_price, 2),
                'price_per_acre_avg': round(statistics.mean(price_per_acre_values), 2) if price_per_acre_values else None
            },
            'confidence': confidence,
            'comps_used': len(comps),
            'methodology': methodology,
            'confidence_factors': {
                'comp_count': len(comps),
                'avg_days_since_sale': round(avg_days_old, 0) if comps else None,
                'avg_distance_miles': round(avg_distance, 2) if comps else None,
                'price_consistency': round(1 - (price_cv if len(sale_prices) > 1 else 0), 2)
            }
        }

    async def validate_asking_price(
        self,
        subject_property_id: str,
        asking_price: float,
        comps: Optional[List[Dict]] = None,
        max_distance_miles: float = 1.0,
        max_age_days: int = 180
    ) -> Dict[str, Any]:
        """
        Validate if asking price is reasonable

        Args:
            subject_property_id: Property to evaluate
            asking_price: Asking/offer price
            comps: Pre-fetched comps (or will fetch)
            max_distance_miles: Max distance for comp search
            max_age_days: Max age for comp search

        Returns:
            Dict with:
            - assessment: "Fair", "Overpriced", "Underpriced", "Insufficient_Data"
            - asking_price: Price being evaluated
            - estimated_value: Market value estimate
            - difference_pct: Percentage difference
            - difference_amount: Dollar difference
            - recommendation: Text recommendation
        """
        logger.info(
            "validating_asking_price",
            subject_property_id=subject_property_id,
            asking_price=asking_price
        )

        # Get market value estimate
        estimate = await self.estimate_market_value(
            subject_property_id=subject_property_id,
            comps=comps,
            max_distance_miles=max_distance_miles,
            max_age_days=max_age_days
        )

        if 'error' in estimate or not estimate.get('estimated_value'):
            return {
                'assessment': 'Insufficient_Data',
                'asking_price': asking_price,
                'estimated_value': None,
                'difference_pct': None,
                'difference_amount': None,
                'recommendation': 'Insufficient comparable sales data to validate price',
                'comps_used': 0
            }

        estimated_value = estimate['estimated_value']
        difference_amount = asking_price - estimated_value
        difference_pct = round((difference_amount / estimated_value * 100), 1) if estimated_value > 0 else 0

        # Determine assessment
        if abs(difference_pct) <= 5:
            assessment = "Fair"
            recommendation = f"Asking price is at market value (within 5%)"
        elif difference_pct > 5:
            assessment = "Overpriced"
            recommendation = f"Asking price is {abs(difference_pct)}% above market value (${abs(difference_amount):,.0f} over)"
        else:  # difference_pct < -5
            assessment = "Underpriced"
            recommendation = f"Asking price is {abs(difference_pct)}% below market value (${abs(difference_amount):,.0f} under market)"

        return {
            'assessment': assessment,
            'asking_price': asking_price,
            'estimated_value': estimated_value,
            'difference_amount': round(difference_amount, 2),
            'difference_pct': difference_pct,
            'value_range': estimate.get('value_range'),
            'confidence': estimate.get('confidence'),
            'comps_used': estimate.get('comps_used'),
            'recommendation': recommendation,
            'methodology': estimate.get('methodology')
        }

    async def analyze_comps(
        self,
        subject_property_id: str,
        asking_price: Optional[float] = None,
        max_distance_miles: float = 1.0,
        max_age_days: int = 180
    ) -> Dict[str, Any]:
        """
        Full comparable sales analysis (CMA-style report)

        Args:
            subject_property_id: Property to analyze
            asking_price: Optional asking price to validate
            max_distance_miles: Max distance for comps
            max_age_days: Max age for comps

        Returns:
            Complete CMA report with:
            - subject: Subject property details
            - comparable_sales: List of comps
            - market_value_estimate: Estimated value
            - price_validation: Assessment if asking_price provided
            - analysis_summary: Text summary
        """
        logger.info(
            "generating_cma_report",
            subject_property_id=subject_property_id,
            asking_price=asking_price
        )

        # Find comps
        comp_result = await self.find_comparable_sales(
            subject_property_id=subject_property_id,
            max_distance_miles=max_distance_miles,
            max_age_days=max_age_days
        )

        if 'error' in comp_result:
            return comp_result

        # Estimate value
        estimate = await self.estimate_market_value(
            subject_property_id=subject_property_id,
            comps=comp_result['comparable_sales']
        )

        # Validate price if provided
        price_validation = None
        if asking_price:
            price_validation = await self.validate_asking_price(
                subject_property_id=subject_property_id,
                asking_price=asking_price,
                comps=comp_result['comparable_sales']
            )

        return {
            'subject': comp_result['subject'],
            'comparable_sales': comp_result['comparable_sales'],
            'comps_found': comp_result['comps_found'],
            'market_value_estimate': estimate,
            'price_validation': price_validation,
            'search_parameters': comp_result['search_parameters'],
            'analysis_date': datetime.now().isoformat()
        }

    # Helper methods

    async def _get_property_details(self, property_id: str) -> Optional[Dict]:
        """Get property details"""
        query = text("""
            SELECT
                id, parcel_id, site_address, property_type,
                market_value, lot_size_acres,
                latitude, longitude
            FROM bulk_property_records
            WHERE id = :property_id
        """)

        result = await self.session.execute(query, {'property_id': property_id})
        row = result.fetchone()

        if not row:
            return None

        return {
            'property_id': str(row[0]),
            'parcel_id': row[1],
            'site_address': row[2],
            'property_type': row[3],
            'market_value': float(row[4]) if row[4] else None,
            'lot_size_acres': float(row[5]) if row[5] else None,
            'latitude': float(row[6]) if row[6] else None,
            'longitude': float(row[7]) if row[7] else None
        }
