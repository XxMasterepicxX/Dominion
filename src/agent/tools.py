"""
Agent Tool Definitions

Defines tools (functions) that the agent can call using Gemini's function calling.
Research shows limiting to 8-10 tools max for best performance. We have 3.
"""

from typing import Dict, Any, Callable
from sqlalchemy.ext.asyncio import AsyncSession

from src.intelligence.analyzers import PropertyAnalyzer, EntityAnalyzer, MarketAnalyzer, PropertySearchAnalyzer
from src.services.sunbiz_enrichment import SunbizEnrichmentService
from src.services.qpublic_enrichment import QPublicEnrichmentService


# Tool definitions for Gemini function calling
TOOL_DEFINITIONS = [
    {
        "name": "analyze_property",
        "description": """Get comprehensive property data for a specific address or parcel.

WHEN TO USE: User asks about a specific property (e.g., "Should I buy 123 Main St?")

RETURNS:
- property: Core details (address, market_value, lot_size_acres, property_type, zoning, year_built)
- owner: Current owner info (entity_name, entity_type, mailing_address)
- owner_portfolio: Portfolio stats (total_properties, total_value, recent_acquisitions count)
- sales_history: Full transaction history (dates, prices, buyer/seller names)
- permits: Building permits at property and in owner's portfolio (dates, types, statuses, values)
- crime: Crime incidents nearby (counts, types, dates)
- neighborhood: Comparable properties (market_value stats, property counts)
- news: Media mentions of property or area (titles, dates, sources)
- council: City council activity mentions (meeting dates, topics)
""",
        "parameters": {
            "type": "object",
            "properties": {
                "property_address": {
                    "type": "string",
                    "description": "Full property address (e.g., '123 Main St, City, State' or '123 Main St')"
                },
                "parcel_id": {
                    "type": "string",
                    "description": "Alternative: Parcel ID if address is unknown (e.g., '12345-678-90')"
                },
                "include_neighborhood": {
                    "type": "boolean",
                    "description": "Include neighborhood analysis showing nearby properties and market context (default: true)"
                },
                "neighborhood_radius_miles": {
                    "type": "number",
                    "description": "Radius in miles for neighborhood analysis (default: 0.5). Use 0.25 for dense urban, 1.0 for rural."
                }
            },
            "required": []  # None strictly required, but need one of property_address or parcel_id
        }
    },
    {
        "name": "analyze_entity",
        "description": """Get owner/investor portfolio data and activity patterns.

WHEN TO USE:
1. User asks "What is [ENTITY] buying?" or "Follow [DEVELOPER]"
2. After analyze_property shows owner with many properties
3. Researching developer patterns or assemblage plays

RETURNS:
- entity_id: Unique identifier
- entity_name: Normalized name
- entity_type: Classification (person, company, llc, institutional)
- portfolio: Total properties owned, total market value, average property value
- activity: Recent acquisitions (dates, property types, values) for last 180 days
- property_preferences: Property type counts (VACANT, SINGLE FAMILY, COMMERCIAL, etc.)
- markets: Cross-market presence (city names, property counts)
- geographic_clustering: Where properties are concentrated (addresses, coordinates)

TOOL CALLING STRATEGY:
1. Call analyze_entity() FIRST to get statistics
2. Then call get_entity_properties() to get actual property list for pattern analysis
3. DO NOT call analyze_property() for each property in portfolio (wasteful)
""",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Entity name exactly as it appears in property ownership records (e.g., 'ABC Development LLC', 'John Smith')"
                },
                "entity_id": {
                    "type": "string",
                    "description": "Alternative: Entity UUID if known from property data"
                },
                "include_portfolio": {
                    "type": "boolean",
                    "description": "Include portfolio summary with total properties and value (default: true)"
                },
                "include_activity_patterns": {
                    "type": "boolean",
                    "description": "Include acquisition timeline and property type preferences (default: true)"
                },
                "market_id": {
                    "type": "string",
                    "description": "Optional: Filter analysis to specific market UUID"
                }
            },
            "required": []  # None strictly required, but need one of entity_name or entity_id
        }
    },
    {
        "name": "analyze_market",
        "description": "Get market intelligence including supply/demand dynamics, price trends, active competition, and investor concentration. Use this to understand the broader market context.",
        "parameters": {
            "type": "object",
            "properties": {
                "market_code": {
                    "type": "string",
                    "description": "Market code (e.g., 'gainesville_fl', 'tampa_fl'). Extract from property location."
                },
                "market_id": {
                    "type": "string",
                    "description": "Alternative: Market UUID if known from property data"
                },
                "include_supply": {
                    "type": "boolean",
                    "description": "Include supply metrics (inventory by type, price distribution) (default: true)"
                },
                "include_demand": {
                    "type": "boolean",
                    "description": "Include demand signals (recent sales, appreciation rates) (default: true)"
                },
                "include_competition": {
                    "type": "boolean",
                    "description": "Include competition analysis (active buyers, investor concentration) (default: true)"
                },
                "recent_period_days": {
                    "type": "integer",
                    "description": "Days to consider as 'recent' activity (default: 180). Use 90 for short-term, 365 for annual."
                }
            },
            "required": []  # None strictly required, but need one of market_code or market_id
        }
    },
    {
        "name": "enrich_entity_sunbiz",
        "description": "**USE THIS TOOL** when you encounter an entity (owner) with unclear type or missing details. Searches Florida Sunbiz database to find LLC/corporation information, registered agents, filing status, and business structure. IMPORTANT: Call this when entity_type is 'person' but has many properties (10+), or when entity_type is 'unknown', or when you need to verify if an owner is actually a business entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Entity/owner name to search for (e.g., 'Smith Properties LLC', 'John Smith', 'ABC Development')"
                },
                "mailing_address": {
                    "type": "string",
                    "description": "Optional: Owner's mailing address for better matching"
                },
                "city": {
                    "type": "string",
                    "description": "Optional: City for better matching"
                }
            },
            "required": ["entity_name"]
        }
    },
    {
        "name": "enrich_property_qpublic",
        "description": "Get detailed property data from qPublic when CAMA data is incomplete. Use this when property data is missing key fields like improvements, detailed valuations, or additional building info. Useful for understanding property potential.",
        "parameters": {
            "type": "object",
            "properties": {
                "parcel_id": {
                    "type": "string",
                    "description": "Parcel ID to enrich (e.g., '12345-678-90')"
                }
            },
            "required": ["parcel_id"]
        }
    },
    {
        "name": "search_properties",
        "description": """Search and filter properties by multiple criteria to find investment opportunities.

WHEN TO USE:
- User asks "Where should I buy?" or "Find properties matching [criteria]"
- After analyze_entity() reveals what property types successful investors are buying
- To find specific property types based on market analysis

RETURNS: List of properties matching filters, each with:
- property_id: Unique identifier
- parcel_id: Parcel ID (use this for detailed analysis)
- site_address: Full address (use this to identify property to user)
- market_value: Current assessed value
- lot_size_acres: Lot size
- property_type: Classification (VACANT, SINGLE FAMILY, COMMERCIAL, MULTI-FAMILY, CONDOMINIUM, etc.)
- zoning: Zoning code
- owner_name: Current owner

CRITICAL: PROPERTY TYPE SELECTION
- DO NOT default to property_type='VACANT' unless:
  1. User explicitly asks for land/vacant property, OR
  2. analyze_entity() showed successful investors prefer VACANT (from property_preferences)
- Available property types: VACANT, SINGLE FAMILY, MULTI-FAMILY, CONDOMINIUM, COMMERCIAL, INDUSTRIAL, etc.
- Let the data and user intent drive property_type selection
- If searching for "something to buy", consider ALL types or match what smart money buys

FILTERS FOR VACANT LAND (only when searching for land):
- property_type='VACANT' - Specify when searching for land
- owner_type='individual' - Consider private owners (often more motivated sellers than corporations)
- EXCLUDE if not viable: Government ownership (COUNTY, STATE, DISTRICT), conservation land, extreme outliers

LOT SIZE GUIDANCE (use professional judgment):
- Consider user's intent and budget
- Don't arbitrarily limit lot size unless user specifies
- Tiny lots (<0.25 acres): May be unbuildable or have issues - investigate carefully
- Large lots (>100 acres): May be agricultural, timber, or institutional - verify viability
- Use min/max_lot_size filters ONLY if they make sense for the specific query
- Example: "$50k budget" doesn't automatically mean "limit to 10 acres" - could get 50 acres for that price

USAGE PATTERN:
1. Call search_properties() with filters appropriate to user's query
2. Get list of matching properties (adjust limit based on query complexity and data needs)
3. Call analyze_property() for most promising candidates only (don't analyze all results - focus on quality over quantity)
4. Return specific recommendations with addresses

EXAMPLES (illustrative only - adapt to user's actual query):
- User asks for vacant land: search_properties(property_type='VACANT', max_price=50000, owner_type='individual')
- User asks for single-family homes: search_properties(property_type='SINGLE FAMILY', max_price=200000)
- User asks for duplexes/multifamily: search_properties(property_type='MULTI-FAMILY', max_price=300000)
- User asks for commercial properties: search_properties(property_type='COMMERCIAL', max_price=500000)
- User asks for ANY property type: search_properties(max_price=100000)
  (When no property_type specified, results include all types - analyze to find best opportunities)
""",
        "parameters": {
            "type": "object",
            "properties": {
                "property_type": {
                    "type": "string",
                    "description": "Property type (e.g., 'VACANT', 'SINGLE FAMILY', 'CONDOMINIUM', 'COMMERCIAL')"
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum market value in dollars"
                },
                "min_price": {
                    "type": "number",
                    "description": "Minimum market value in dollars"
                },
                "min_lot_size": {
                    "type": "number",
                    "description": "Minimum lot size in acres"
                },
                "max_lot_size": {
                    "type": "number",
                    "description": "Maximum lot size in acres"
                },
                "zoning": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of acceptable zoning types (e.g., ['AGRICULTURE', 'RESIDENTIAL'])"
                },
                "city": {
                    "type": "string",
                    "description": "City name to filter by"
                },
                "area": {
                    "type": "string",
                    "description": "Geographic area from address (e.g., 'SW', 'NW 127th')"
                },
                "owner_type": {
                    "type": "string",
                    "description": "Filter by owner type: 'individual', 'company', or 'llc'"
                },
                "has_permits": {
                    "type": "boolean",
                    "description": "Filter properties with/without permits"
                },
                "recent_sale": {
                    "type": "boolean",
                    "description": "Filter recently sold properties (last 180 days)"
                },
                "exclude_owner": {
                    "type": "string",
                    "description": "Exclude properties owned by this entity (e.g., 'D R HORTON')"
                },
                "near_lat": {
                    "type": "number",
                    "description": "Latitude for geographic search"
                },
                "near_lng": {
                    "type": "number",
                    "description": "Longitude for geographic search"
                },
                "radius_miles": {
                    "type": "number",
                    "description": "Radius in miles for geographic search (use with near_lat/near_lng)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 50). Use 30-50 for general searches to ensure broad evaluation, smaller for targeted searches."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_entity_properties",
        "description": """Get the actual list of properties owned by an entity (addresses, not just stats).

WHEN TO USE:
1. After analyze_entity() shows this is a sophisticated investor (20+ properties)
2. User asks to "follow" a developer or identify assemblage patterns
3. Need to identify gap parcels or geographic clustering

RETURNS: List of properties owned by entity, each with:
- site_address: Full address (use for geographic pattern analysis)
- parcel_id: Parcel ID
- property_type: Type (VACANT land is key for development plays)
- market_value: Value
- purchase_date: When acquired (recent = active strategy)
- lot_size_acres: Size

DIFFERENCE FROM analyze_entity:
- analyze_entity: Statistics (total count, total value, activity trends)
- get_entity_properties: Actual property list with addresses

GEOGRAPHIC PATTERN ANALYSIS:
1. Extract street names from addresses
2. Look for clustering: Multiple properties on same street or block
3. Identify contiguous parcels (adjacent addresses, e.g., 101, 103, 105 Main St)
4. Find gaps: Missing addresses between owned parcels (assemblage opportunities)
5. Predict next acquisitions: Properties needed to complete the block

TOOL EFFICIENCY:
- Call analyze_entity() FIRST (get stats in 1 call)
- Call get_entity_properties() SECOND (get addresses for pattern analysis)
- Analyze patterns from the address data WITHOUT calling analyze_property() for each
- Call analyze_property() ONLY for the most promising gap parcels you want to recommend (focus on quality)
""",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Entity/owner name (e.g., 'D R HORTON INC', 'ABC Development LLC')"
                },
                "property_type": {
                    "type": "string",
                    "description": "Optional: Filter by property type (e.g., 'VACANT' to see only their land holdings)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum properties to return (default: 100)"
                }
            },
            "required": ["entity_name"]
        }
    }
]


class AgentTools:
    """
    Tool executor that connects agent function calls to analyzers
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize tools with database session

        Args:
            session: Active SQLAlchemy async session
        """
        self.session = session
        self.property_analyzer = PropertyAnalyzer(session)
        self.entity_analyzer = EntityAnalyzer(session)
        self.market_analyzer = MarketAnalyzer(session)
        self.property_search_analyzer = PropertySearchAnalyzer(session)

        # Enrichment services (initialized lazily)
        self._sunbiz_service = None
        self._qpublic_service = None

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name with given parameters

        Args:
            tool_name: Name of tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool name is unknown
        """
        if tool_name == "analyze_property":
            return await self._analyze_property(**parameters)
        elif tool_name == "analyze_entity":
            return await self._analyze_entity(**parameters)
        elif tool_name == "analyze_market":
            return await self._analyze_market(**parameters)
        elif tool_name == "search_properties":
            return await self._search_properties(**parameters)
        elif tool_name == "get_entity_properties":
            return await self._get_entity_properties(**parameters)
        elif tool_name == "enrich_entity_sunbiz":
            return await self._enrich_entity_sunbiz(**parameters)
        elif tool_name == "enrich_property_qpublic":
            return await self._enrich_property_qpublic(**parameters)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _analyze_property(
        self,
        property_address: str = None,
        parcel_id: str = None,
        include_neighborhood: bool = True,
        neighborhood_radius_miles: float = 0.5
    ) -> Dict[str, Any]:
        """Execute PropertyAnalyzer"""

        # First, find the property by address if provided
        if property_address and not parcel_id:
            # Search for property by address
            from sqlalchemy import text
            query = text("""
                SELECT id, parcel_id
                FROM bulk_property_records
                WHERE LOWER(site_address) LIKE LOWER(:address)
                LIMIT 1
            """)
            result = await self.session.execute(
                query,
                {'address': f'%{property_address}%'}
            )
            row = result.fetchone()

            if not row:
                return {
                    'error': f'Property not found: {property_address}',
                    'suggestion': 'Try different address format or use parcel_id'
                }

            property_id = str(row[0])
            parcel_id = row[1]

        elif parcel_id:
            # Find by parcel_id
            from sqlalchemy import text
            query = text("""
                SELECT id FROM bulk_property_records
                WHERE parcel_id = :parcel_id
                LIMIT 1
            """)
            result = await self.session.execute(
                query,
                {'parcel_id': parcel_id}
            )
            row = result.fetchone()

            if not row:
                return {
                    'error': f'Property not found: {parcel_id}',
                    'suggestion': 'Verify parcel_id is correct'
                }

            property_id = str(row[0])

        else:
            return {
                'error': 'Must provide either property_address or parcel_id'
            }

        # Analyze the property
        result = await self.property_analyzer.analyze(
            property_id=property_id,
            include_ownership=True,
            include_neighborhood=include_neighborhood,
            include_history=True,  # Include full sales history for ownership verification and trend analysis
            neighborhood_radius_miles=neighborhood_radius_miles
        )

        return result

    async def _analyze_entity(
        self,
        entity_name: str = None,
        entity_id: str = None,
        include_portfolio: bool = True,
        include_activity_patterns: bool = True,
        market_id: str = None
    ) -> Dict[str, Any]:
        """Execute EntityAnalyzer"""

        if not entity_name and not entity_id:
            return {
                'error': 'Must provide either entity_name or entity_id'
            }

        result = await self.entity_analyzer.analyze(
            entity_id=entity_id,
            entity_name=entity_name,
            market_id=market_id,
            include_portfolio=include_portfolio,
            include_activity_patterns=include_activity_patterns,
            include_cross_market=True
        )

        return result

    async def _analyze_market(
        self,
        market_code: str = None,
        market_id: str = None,
        include_supply: bool = True,
        include_demand: bool = True,
        include_competition: bool = True,
        recent_period_days: int = 180
    ) -> Dict[str, Any]:
        """Execute MarketAnalyzer"""

        if not market_code and not market_id:
            # No market specified - return error
            return {
                'error': 'Market code or market_id required for market analysis',
                'suggestion': 'Provide market_code (e.g., "city_state") or market_id'
            }

        result = await self.market_analyzer.analyze(
            market_id=market_id,
            market_code=market_code,
            include_supply=include_supply,
            include_demand=include_demand,
            include_competition=include_competition,
            include_trends=True,
            recent_period_days=recent_period_days
        )

        return result

    async def _enrich_entity_sunbiz(
        self,
        entity_name: str,
        mailing_address: str = None,
        city: str = None
    ) -> Dict[str, Any]:
        """Search Sunbiz for LLC/corporation information"""

        # Lazy init
        if self._sunbiz_service is None:
            self._sunbiz_service = SunbizEnrichmentService(headless=True)

        # Build context for better matching
        context = {}
        if mailing_address:
            context['address'] = mailing_address
        if city:
            context['city'] = city

        try:
            result = await self._sunbiz_service.search_and_match(
                entity_name,
                additional_context=context if context else None
            )

            if result:
                return {
                    'found': True,
                    'entity_name': result.get('entityName'),
                    'document_number': result.get('documentNumber'),
                    'status': result.get('status'),
                    'filing_type': result.get('filingType'),
                    'registered_agent': result.get('registeredAgent', {}).get('name'),
                    'officers': result.get('officers', []),
                    'date_filed': result.get('dateFiled'),
                    'principal_address': result.get('principalAddress'),
                    'mailing_address': result.get('mailingAddress')
                }
            else:
                return {
                    'found': False,
                    'message': f'No Sunbiz record found for {entity_name}'
                }

        except Exception as e:
            return {
                'error': f'Sunbiz enrichment failed: {str(e)}'
            }

    async def _enrich_property_qpublic(
        self,
        parcel_id: str
    ) -> Dict[str, Any]:
        """Get detailed property data from qPublic"""

        # Lazy init
        if self._qpublic_service is None:
            from src.database.connection import db_manager
            self._qpublic_service = QPublicEnrichmentService(db_manager, headless=True)

        try:
            # This would call the qPublic scraper
            # For now, return a placeholder
            return {
                'message': 'qPublic enrichment not yet implemented in this version',
                'suggestion': 'Property data from CAMA should be sufficient for initial analysis'
            }

        except Exception as e:
            return {
                'error': f'qPublic enrichment failed: {str(e)}'
            }

    async def _search_properties(
        self,
        property_type: str = None,
        max_price: float = None,
        min_price: float = None,
        min_lot_size: float = None,
        max_lot_size: float = None,
        zoning: list = None,
        city: str = None,
        area: str = None,
        owner_type: str = None,
        has_permits: bool = None,
        recent_sale: bool = None,
        exclude_owner: str = None,
        near_lat: float = None,
        near_lng: float = None,
        radius_miles: float = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Execute PropertySearchAnalyzer.search()"""
        return await self.property_search_analyzer.search(
            property_type=property_type,
            max_price=max_price,
            min_price=min_price,
            min_lot_size=min_lot_size,
            max_lot_size=max_lot_size,
            zoning=zoning,
            city=city,
            area=area,
            owner_type=owner_type,
            has_permits=has_permits,
            recent_sale=recent_sale,
            exclude_owner=exclude_owner,
            near_lat=near_lat,
            near_lng=near_lng,
            radius_miles=radius_miles,
            limit=limit
        )

    async def _get_entity_properties(
        self,
        entity_name: str,
        property_type: str = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Execute PropertySearchAnalyzer.get_entity_properties()"""
        return await self.property_search_analyzer.get_entity_properties(
            entity_name=entity_name,
            property_type=property_type,
            limit=limit
        )

    def get_tool_definitions(self) -> list:
        """Get tool definitions for Gemini function calling"""
        return TOOL_DEFINITIONS
