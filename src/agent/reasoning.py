"""
Reasoning Engine

Synthesizes insights from tool outputs and calculates opportunity scores.
Pattern detection, risk assessment, and recommendation logic.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class ReasoningEngine:
    """
    Connects patterns across property/entity/market data and scores opportunities
    """

    def calculate_opportunity_score(
        self,
        property_data: Optional[Dict[str, Any]] = None,
        entity_data: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate 0-100 opportunity score based on multiple factors

        Scoring breakdown:
        - Valuation (30%): Property price vs market
        - Owner Sophistication (20%): Professional vs amateur
        - Market Momentum (30%): Growth, demand, trends
        - Risk Factors (20%): Negative signals

        Returns:
            {
                'score': 0-100,
                'breakdown': {...},
                'factors': {...}
            }
        """
        score_breakdown = {
            'valuation': 0,
            'owner_sophistication': 0,
            'market_momentum': 0,
            'risk_adjustment': 0
        }

        factors = {}

        # 1. Valuation Score (30 points max)
        if property_data and property_data.get('property'):
            prop = property_data['property']
            valuation = prop.get('valuation', {})
            neighborhood = property_data.get('neighborhood')

            market_value = valuation.get('market_value', 0)

            if neighborhood and neighborhood.get('stats'):
                avg_market_value = neighborhood['stats'].get('avg_market_value', 0)

                if avg_market_value and market_value:
                    # Calculate relative value
                    value_ratio = market_value / avg_market_value

                    if value_ratio < 0.85:  # 15%+ undervalued
                        score_breakdown['valuation'] = 30
                        factors['valuation'] = 'Significantly undervalued (15%+ below market)'
                    elif value_ratio < 0.95:  # 5-15% undervalued
                        score_breakdown['valuation'] = 20
                        factors['valuation'] = 'Moderately undervalued (5-15% below market)'
                    elif value_ratio <= 1.05:  # Fair value
                        score_breakdown['valuation'] = 15
                        factors['valuation'] = 'Fair market value'
                    elif value_ratio <= 1.15:  # Slightly overvalued
                        score_breakdown['valuation'] = 10
                        factors['valuation'] = 'Slightly overvalued (5-15% above market)'
                    else:  # Overvalued
                        score_breakdown['valuation'] = 0
                        factors['valuation'] = 'Overvalued (15%+ above market)'

        # 2. Owner Sophistication Score (20 points max)
        # IMPORTANT: Portfolio size is PRIMARY indicator, entity type is SECONDARY
        # A person with 50 properties is more sophisticated than an LLC with 2 properties
        if entity_data and entity_data.get('portfolio'):
            portfolio = entity_data['portfolio']['summary']
            entity_type = entity_data['entity'].get('type', 'unknown')
            total_props = portfolio.get('total_properties', 0)

            # Score primarily by portfolio size (anyone with 20+ is sophisticated)
            if total_props >= 20:
                score_breakdown['owner_sophistication'] = 20
                factors['owner_sophistication'] = f'Highly sophisticated investor ({total_props} properties)'
            elif total_props >= 10:
                score_breakdown['owner_sophistication'] = 15
                factors['owner_sophistication'] = f'Experienced investor ({total_props} properties)'
            elif total_props >= 5:
                score_breakdown['owner_sophistication'] = 10
                factors['owner_sophistication'] = f'Active investor ({total_props} properties)'
            elif total_props >= 3:
                # Small portfolio - entity type matters here
                if entity_type in ['llc', 'corporation']:
                    score_breakdown['owner_sophistication'] = 7
                    factors['owner_sophistication'] = f'Small professional investor ({total_props} properties)'
                else:
                    score_breakdown['owner_sophistication'] = 5
                    factors['owner_sophistication'] = f'Individual with {total_props} properties'
            else:
                # 1-2 properties - likely owner-occupied or small landlord
                score_breakdown['owner_sophistication'] = 0
                factors['owner_sophistication'] = 'Owner-occupied or single rental (1-2 properties)'

        # 3. Market Momentum Score (30 points max)
        if market_data:
            momentum_score = 0
            momentum_factors = []

            # Recent demand
            if market_data.get('demand'):
                demand = market_data['demand']
                if demand.get('recent_sales', 0) > 0:
                    metrics = demand.get('metrics', {})
                    appreciation = metrics.get('avg_appreciation_pct')

                    if appreciation:
                        if appreciation > 10:
                            momentum_score += 15
                            momentum_factors.append(f'Strong appreciation ({appreciation:.1f}%)')
                        elif appreciation > 5:
                            momentum_score += 10
                            momentum_factors.append(f'Moderate appreciation ({appreciation:.1f}%)')
                        elif appreciation > 0:
                            momentum_score += 5
                            momentum_factors.append(f'Positive appreciation ({appreciation:.1f}%)')
                        else:
                            momentum_factors.append(f'Negative appreciation ({appreciation:.1f}%)')

            # Active competition
            if market_data.get('competition'):
                comp = market_data['competition']
                active_buyers = len(comp.get('active_buyers', []))

                if active_buyers >= 10:
                    momentum_score += 10
                    momentum_factors.append(f'{active_buyers} active buyers')
                elif active_buyers >= 5:
                    momentum_score += 5
                    momentum_factors.append(f'{active_buyers} active buyers')

                # Investor concentration
                if comp.get('investor_concentration'):
                    conc = comp['investor_concentration']
                    control_pct = conc.get('investor_control_pct', 0)

                    if control_pct and control_pct > 30:
                        momentum_score += 5
                        momentum_factors.append(f'High investor interest ({control_pct:.1f}% control)')

            score_breakdown['market_momentum'] = min(momentum_score, 30)
            factors['market_momentum'] = ' | '.join(momentum_factors) if momentum_factors else 'Neutral'

        # 4. Risk Adjustment (-20 to 0 points)
        risk_factors = self.identify_red_flags(property_data, entity_data, market_data)
        if risk_factors:
            # Deduct points for each risk
            risk_deduction = min(len(risk_factors) * 5, 20)
            score_breakdown['risk_adjustment'] = -risk_deduction
            factors['risks'] = f'{len(risk_factors)} risk factors identified'
        else:
            score_breakdown['risk_adjustment'] = 0
            factors['risks'] = 'No major risks detected'

        # Calculate total
        total_score = sum(score_breakdown.values())
        total_score = max(0, min(100, total_score))  # Clamp to 0-100

        return {
            'score': int(total_score),
            'breakdown': score_breakdown,
            'factors': factors
        }

    def identify_red_flags(
        self,
        property_data: Optional[Dict] = None,
        entity_data: Optional[Dict] = None,
        market_data: Optional[Dict] = None
    ) -> List[Dict[str, str]]:
        """
        Identify potential issues/risks

        Returns:
            List of {severity, issue, description}
        """
        red_flags = []

        # Property red flags
        if property_data and property_data.get('property'):
            prop = property_data['property']
            valuation = prop.get('valuation', {})

            # Extremely high value
            market_value = valuation.get('market_value', 0)
            if market_value > 10000000:  # $10M+
                red_flags.append({
                    'severity': 'Low',
                    'issue': 'Very high value property',
                    'description': f'${market_value:,.0f} requires significant capital'
                })

            # Very old property
            chars = prop.get('characteristics', {})
            year_built = chars.get('year_built')
            if year_built and year_built < 1960:
                red_flags.append({
                    'severity': 'Medium',
                    'issue': 'Older property',
                    'description': f'Built in {year_built}, may need significant repairs'
                })

        # Entity red flags
        if entity_data and entity_data.get('entity'):
            entity_type = entity_data['entity'].get('type')

            # Unknown entity type
            if entity_type == 'unknown':
                red_flags.append({
                    'severity': 'Low',
                    'issue': 'Unknown entity type',
                    'description': 'Cannot determine owner sophistication level'
                })

        # Market red flags
        if market_data:
            if market_data.get('demand'):
                demand = market_data['demand']
                if demand.get('metrics'):
                    appreciation = demand['metrics'].get('avg_appreciation_pct')

                    # Negative appreciation
                    if appreciation and appreciation < -5:
                        red_flags.append({
                            'severity': 'High',
                            'issue': 'Declining market',
                            'description': f'Market showing {appreciation:.1f}% depreciation'
                        })

        return red_flags

    def identify_green_flags(
        self,
        property_data: Optional[Dict] = None,
        entity_data: Optional[Dict] = None,
        market_data: Optional[Dict] = None
    ) -> List[Dict[str, str]]:
        """
        Identify positive signals/opportunities

        Returns:
            List of {category, opportunity, description}
        """
        green_flags = []

        # Property opportunities
        if property_data:
            prop = property_data.get('property', {})
            neighborhood = property_data.get('neighborhood')

            # Undervalued property
            if neighborhood and neighborhood.get('stats'):
                valuation = prop.get('valuation', {})
                market_value = valuation.get('market_value', 0)
                avg_market_value = neighborhood['stats'].get('avg_market_value', 0)

                if market_value and avg_market_value:
                    value_ratio = market_value / avg_market_value
                    if value_ratio < 0.90:
                        pct_under = (1 - value_ratio) * 100
                        green_flags.append({
                            'category': 'Valuation',
                            'opportunity': 'Undervalued property',
                            'description': f'{pct_under:.1f}% below neighborhood average'
                        })

        # Entity opportunities
        if entity_data:
            portfolio = entity_data.get('portfolio', {}).get('summary', {})
            entity_type = entity_data.get('entity', {}).get('type')

            # Assemblage potential
            if portfolio.get('total_properties', 0) >= 10 and entity_type in ['llc', 'corporation']:
                green_flags.append({
                    'category': 'Owner Intelligence',
                    'opportunity': 'Sophisticated investor',
                    'description': f'Owner has {portfolio["total_properties"]} properties, may be assembling'
                })

            # Recent activity
            if entity_data.get('activity_patterns'):
                patterns = entity_data['activity_patterns']
                if patterns.get('property_type_preferences'):
                    prefs = patterns['property_type_preferences']
                    if prefs and prefs[0].get('recent_acquisitions', 0) > 0:
                        green_flags.append({
                            'category': 'Activity',
                            'opportunity': 'Active buyer',
                            'description': f'Owner recently acquired {prefs[0]["recent_acquisitions"]} properties'
                        })

        # Market opportunities
        if market_data:
            if market_data.get('demand'):
                demand = market_data['demand']
                if demand.get('metrics'):
                    appreciation = demand['metrics'].get('avg_appreciation_pct')
                    if appreciation and appreciation > 10:
                        green_flags.append({
                            'category': 'Market Momentum',
                            'opportunity': 'Strong appreciation',
                            'description': f'Market showing {appreciation:.1f}% annual appreciation'
                        })

            if market_data.get('competition'):
                comp = market_data['competition']
                active_buyers = comp.get('active_buyers', [])
                if len(active_buyers) >= 5:
                    green_flags.append({
                        'category': 'Competition',
                        'opportunity': 'Active market',
                        'description': f'{len(active_buyers)} active investors competing'
                    })

        return green_flags

    def make_recommendation(
        self,
        opportunity_score: int,
        red_flags: List[Dict],
        green_flags: List[Dict],
        confidence: float = 0.8
    ) -> str:
        """
        Make BUY/PASS/INVESTIGATE recommendation

        Args:
            opportunity_score: 0-100 score
            red_flags: List of risks
            green_flags: List of opportunities
            confidence: 0-1 confidence level

        Returns:
            'BUY' | 'PASS' | 'INVESTIGATE'
        """
        high_severity_risks = sum(1 for r in red_flags if r.get('severity') == 'High')

        if high_severity_risks >= 2:
            # Multiple high risks = PASS
            return 'PASS'

        if opportunity_score >= 70 and confidence >= 0.75:
            # High score + confidence = BUY
            return 'BUY'
        elif opportunity_score >= 50 and confidence >= 0.6:
            # Medium score = INVESTIGATE
            return 'INVESTIGATE'
        elif opportunity_score < 40:
            # Low score = PASS
            return 'PASS'
        else:
            # Default to investigate
            return 'INVESTIGATE'
