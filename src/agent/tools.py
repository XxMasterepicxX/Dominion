"""
Agent Tool Definitions

Defines tools (functions) that the agent can call using Gemini's function calling.
Research shows limiting to 8-10 tools max for best performance. We have 10.
"""

from typing import Dict, Any, Callable
from sqlalchemy.ext.asyncio import AsyncSession

from src.intelligence.analyzers import (
    PropertyAnalyzer,
    EntityAnalyzer,
    MarketAnalyzer,
    PropertySearchAnalyzer,
    LocationAnalyzer,
    ComparableSalesAnalyzer
)
from src.services.sunbiz_enrichment import SunbizEnrichmentService
from src.services.qpublic_enrichment import QPublicEnrichmentService
from src.services.ordinance_rag import get_ordinance_rag


# Tool definitions for Gemini function calling
TOOL_DEFINITIONS = [
    {
        "name": "analyze_property",
        "description": """Get comprehensive property data for a specific address or parcel.

WHEN TO USE: User asks about a specific property (e.g., "Should I buy 123 Main St?")

IMPORTANT: If you have parcel_id from search_properties or get_entity_properties results,
USE parcel_id parameter (guaranteed match). Only use property_address when parcel_id unavailable
(e.g., user provided address without prior search).

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
                "parcel_id": {
                    "type": "string",
                    "description": "Parcel ID for guaranteed property match (e.g., '12345-678-90'). PREFERRED: Use this if available from search_properties or get_entity_properties results."
                },
                "property_address": {
                    "type": "string",
                    "description": "Property address (e.g., '123 Main St, City, State'). Use only when parcel_id not available (e.g., user-provided address)."
                },
                "include_neighborhood": {
                    "type": "boolean",
                    "description": "Include neighborhood analysis showing nearby properties and market context (default: true)"
                },
                "neighborhood_radius_miles": {
                    "type": "number",
                    "description": "Radius in miles for neighborhood analysis (default: 0.5 miles). Agent determines appropriate radius based on area density."
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
4. Comparing multiple buyers for exit strategy selection (analyze several to compare criteria)

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
3. Avoid calling analyze_property() for each property in portfolio (wasteful)
""",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Entity name as it appears in property ownership records (e.g., 'ABC Development LLC', 'John Smith')"
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
        "description": """Get market intelligence including supply/demand dynamics, price trends, active competition, and investor concentration.

WHAT IT RETURNS:
- Supply metrics: Inventory by property type, price distribution
- Demand signals: Recent sales, appreciation rates, market velocity
- Competition data: Active buyers list with:
  * Entity names, recent acquisition counts, total portfolios
  * Geographic concentration: WHERE each buyer focuses activity (SW, NE, NW, SE areas)
  * Concentration score: How focused buyer is in specific area
  * Top streets: Most active street corridors for each buyer
- Investor concentration: Market share by major players

USE FOR BUYER COMPARISON:
The competition data includes active_buyers list showing who's acquiring properties and WHERE.
Each buyer includes geographic_concentration showing which areas they focus on.
Use this to match properties to buyers actively acquiring in that specific area.
For wholesale/resale strategies, consider both acquisition volume AND geographic fit.
""",
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
                    "description": "Days to consider as 'recent' activity (default: 180 days). Agent determines appropriate timeframe based on analysis needs."
                }
            },
            "required": []  # None strictly required, but need one of market_code or market_id
        }
    },
    {
        "name": "enrich_entity_sunbiz",
        "description": "**Consider using this tool** when you encounter an entity (owner) with unclear type or missing details. Searches Florida Sunbiz database to find LLC/corporation information, registered agents, filing status, and business structure. Useful when entity_type is 'person' but has many properties (10+), or when entity_type is 'unknown', or when you need to verify if an owner is actually a business entity.",
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
- Avoid defaulting to property_type='VACANT' unless:
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
- Tiny lots (very small lots): May be unbuildable or have issues - investigate carefully
- Large lots (very large lots): May be agricultural, timber, or institutional - verify viability
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
                    "description": "Geographic area to filter by (e.g., 'SW', 'NW', 'NE', 'SE'). Use this to match properties to buyer's geographic_concentration from analyze_market results."
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
                    "description": "Maximum results to return (default: 50). Agent determines appropriate limit based on search scope."
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
    },
    {
        "name": "search_ordinances",
        "description": """Search municipal ordinances and zoning codes using semantic search over 2,588 ordinance chunks from 9 cities.

WHEN TO USE:

TYPICAL USE CASES:
- Vacant land analysis (verify zoning, lot size, setbacks, subdivision rules, development constraints)
- User asks "Can I...?" questions (build duplex, operate business, build ADU, subdivide lot)
- Development/construction feasibility questions
- Property has zoning code - verify allowed uses
- Parking requirements (multifamily, commercial)
- Environmental/historic constraints
- Permit process understanding

INDUSTRY CONTEXT:
Professional investors typically verify regulatory feasibility for vacant land to reduce risk of deal failure.

WHAT IT RETURNS:
- Ordinance text chunks (exact legal language from actual ordinances)
- Relevance scores (0.6-0.75+ typical for good matches)
- Source file and city for each result
- Top 3-5 most relevant sections

QUERY CONSTRUCTION:

EFFECTIVE PATTERNS:
- Specific queries with context: Include zoning code or use type
- Use-based queries: Focus on intended use or activity
- Requirement queries: Ask about specific dimensional or procedural requirements
- Process queries: Ask about approval or application processes

LESS EFFECTIVE:
- Single words without context
- Overly broad terms

CITY FILTERING (9 cities available):

WITH CITY FILTER:
- Property location known: Use city from property data
- User mentions specific city: Use that city parameter
- Comparing regulations: Multiple searches with different cities

NO FILTER:
- Comparing across jurisdictions
- Location not specified
- Retry if filtered search returns insufficient results

VACANT LAND CONSIDERATIONS:
Typical topics to research for vacant land:
- Zoning allowed uses and restrictions
- Dimensional requirements (lot size, setbacks, coverage)
- Subdivision and lot split regulations
- Development constraints and overlay districts
- Approval processes and permit requirements

INTERPRETING RESULTS:
- Relevance 0.70+: High confidence match (directly answers query)
- Relevance 0.60-0.69: Good match (related, may need interpretation)
- Relevance <0.60: Weak match (try rephrasing or broadening query)
- No results: Broaden query, remove city filter, or state "verification needed"

CITING IN RECOMMENDATIONS:
- Quote specific requirements from ordinance text
- Include relevance score for transparency on match quality
- Reference source city and file
- Note if professional verification recommended when results uncertain

NOTE: This searches ACTUAL ordinance text with citations, not AI summaries. Results are real legal requirements.""",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query about ordinances (specific queries with context work best)"
                },
                "city": {
                    "type": "string",
                    "description": "Optional: Filter to specific city (e.g., 'Gainesville', 'Alachua County'). Use this if user mentions a city or if searching for a specific property."
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5). Agent determines count based on query complexity."
                },
                "min_relevance": {
                    "type": "number",
                    "description": "Minimum relevance score 0-1 (default: 0.6 relevance threshold). Agent adjusts based on query specificity."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_location",
        "description": """Analyze geographic and spatial aspects of properties and markets.

CAPABILITIES:

1. FIND NEARBY PROPERTIES
   Find properties within radius of a location:
   - Search around specific property (use property_id)
   - Search around coordinates (use latitude/longitude)
   - Filter by property type, price range
   - Returns properties sorted by distance

   Use cases:
   - "Find vacant land near where D.R. Horton is building"
   - "Properties within 1 mile of [address]"
   - "Land near [investor's] other properties"

2. DETECT GROWTH HOTSPOTS
   Find areas with concentrated development activity:
   - High permit concentration
   - Active sales activity
   - Multiple investor presence
   - Returns hotspot areas with activity scores

   Use cases:
   - "Where is development happening?"
   - "Find emerging growth areas"
   - "Areas with high investor activity"

3. ANALYZE NEIGHBORHOOD
   Get aggregate metrics for geographic area:
   - Property values and distribution
   - Ownership patterns (owner vs investor)
   - Property type mix
   - Recent activity (sales and permits)

   Use cases:
   - "What's the neighborhood like around this property?"
   - "Property values in this area"
   - "Is this area mostly owner-occupied or investor-owned?"

PARAMETERS:

analysis_type (required): Type of analysis to perform
  - "nearby_properties": Find properties near location
  - "growth_hotspots": Detect areas with high activity
  - "neighborhood": Analyze area characteristics

For nearby_properties:
  - target_property_id OR (target_latitude + target_longitude): Center point
  - radius_miles: Search radius (suggest: 0.5-2.0 miles)
  - property_type: Optional filter (e.g., "VACANT")
  - min_price, max_price: Optional price filters

For growth_hotspots:
  - market_id: Market to analyze (e.g., "gainesville_fl")
  - min_activity_score: Threshold for hotspot (suggest: 0.6-0.8)
  - lookback_days: Days to analyze (suggest: 90-180)

For neighborhood:
  - latitude, longitude: Center point
  - radius_miles: Neighborhood radius (suggest: 0.3-0.5 miles)

LOCATION CONTEXT (INDUSTRY PRACTICE):

Real estate is local - "location, location, location":
- Proximity to active development increases value and exit probability
- Growth hotspots indicate market momentum and investor confidence
- Neighborhood characteristics affect investment viability
- Properties near successful investors often have better fundamentals

STRATEGIC APPLICATIONS:

Following Developer Strategy (TYPE 2 queries):
- Use nearby_properties to find available properties near developer's portfolio
- Use growth_hotspots to identify where developers are concentrating activity
- Match property location to buyer's geographic focus from analyze_entity

Exit Strategy Validation:
- Verify exit buyer is active NEAR the subject property
- Properties outside buyer's geographic focus have lower exit probability
- Proximity to buyer's other properties suggests acquisition interest

Market Opportunity Discovery:
- Growth hotspots reveal emerging submarkets before they're obvious
- Properties near hotspots may benefit from spillover development
- Areas with high investor activity indicate market validation""",
        "parameters": {
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "enum": ["nearby_properties", "growth_hotspots", "neighborhood"],
                    "description": "Type of location analysis to perform"
                },
                "target_property_id": {
                    "type": "string",
                    "description": "Property ID to search around (for nearby_properties)"
                },
                "target_latitude": {
                    "type": "number",
                    "description": "Target latitude (for nearby_properties or neighborhood)"
                },
                "target_longitude": {
                    "type": "number",
                    "description": "Target longitude (for nearby_properties or neighborhood)"
                },
                "radius_miles": {
                    "type": "number",
                    "description": "Search or analysis radius in miles (suggest: 0.5-2.0 for nearby, 0.3-0.5 for neighborhood)"
                },
                "market_id": {
                    "type": "string",
                    "description": "Market ID (for growth_hotspots)"
                },
                "property_type": {
                    "type": "string",
                    "description": "Filter by property type (e.g., 'VACANT', 'SINGLE FAMILY')"
                },
                "min_price": {
                    "type": "number",
                    "description": "Minimum market value filter"
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum market value filter"
                },
                "min_activity_score": {
                    "type": "number",
                    "description": "Minimum activity score for hotspots (0-1, suggest: 0.6-0.8)"
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Days to analyze for hotspots (suggest: 90-180)"
                }
            },
            "required": ["analysis_type"]
        }
    },
    {
        "name": "analyze_comparable_sales",
        "description": """Analyze comparable property sales to estimate market value and validate asking prices.

WHEN TO USE:
1. User asks "Is this price fair?" or "What's this property worth?"
2. Validating a deal (check if asking price aligns with market)
3. Supporting investment recommendation with market validation
4. Generating CMA-style reports for $200 deep analysis product

CAPABILITIES:

1. FIND COMPARABLE SALES
   Find similar properties that recently sold:
   - Same property type (e.g., SINGLE FAMILY, VACANT)
   - Similar size (±30% lot_size_acres by default)
   - Nearby location (within radius)
   - Recent sales (last 6-12 months typical)
   Returns list of comps with sale prices, dates, distances

2. ESTIMATE MARKET VALUE
   Calculate estimated market value from comparable sales:
   - Uses price per acre methodology for land
   - Averages sale prices for similar properties
   - Returns confidence score (0-1) based on:
     * Number of comps (more is better)
     * Price consistency (less variance is better)
     * Recency (newer sales weighted higher)
     * Proximity (closer comps weighted higher)

3. VALIDATE ASKING PRICE
   Determine if an asking price is fair, overpriced, or underpriced:
   - Compares asking price to estimated market value
   - "Fair" if within 5% of market
   - "Overpriced" if >5% above market
   - "Underpriced" if >5% below market
   - Provides recommendation text and percentage differences

4. FULL CMA REPORT
   Generate complete comparative market analysis:
   - All comparable sales found
   - Market value estimate with confidence
   - Price validation if asking price provided
   - Complete statistics and methodology

USAGE PATTERNS:

Price Validation:
- User has asking price → use validate_asking_price
- User wants to know value → use estimate_market_value
- Full report needed → use full_cma

Market Context:
- Combine with analyze_property for complete picture
- Use after location analysis to understand market dynamics
- Part of $200 deep analysis reports

RETURNS (varies by analysis_mode):
- comparable_sales: List of similar properties with sale data
- market_value_estimate: Estimated value, confidence, methodology
- price_validation: Assessment, difference from market, recommendation
- full_report: Complete CMA with all components""",
        "parameters": {
            "type": "object",
            "properties": {
                "subject_property_id": {
                    "type": "string",
                    "description": "Property ID to analyze (from search_properties or analyze_property)"
                },
                "analysis_mode": {
                    "type": "string",
                    "enum": ["find_comps", "estimate_value", "validate_price", "full_cma"],
                    "description": "Type of analysis: find_comps (just find comps), estimate_value (calculate market value), validate_price (check if asking price fair), full_cma (complete report)"
                },
                "asking_price": {
                    "type": "number",
                    "description": "Asking/offer price to validate (required for validate_price and full_cma modes)"
                },
                "max_distance_miles": {
                    "type": "number",
                    "description": "Maximum distance for comparable properties (default: 1.0 mile, can expand to 2-5 if few comps)"
                },
                "max_age_days": {
                    "type": "integer",
                    "description": "Maximum age of sales to consider (default: 180 days for 6 months, can use 365 for 1 year)"
                },
                "min_comps": {
                    "type": "integer",
                    "description": "Minimum comparable sales to find (default: 3, standard CMA needs 3-5)"
                },
                "max_comps": {
                    "type": "integer",
                    "description": "Maximum comparable sales to return (default: 10)"
                },
                "size_tolerance": {
                    "type": "number",
                    "description": "Size tolerance for comps (default: 0.3 for ±30%, can adjust for unique properties)"
                }
            },
            "required": ["subject_property_id", "analysis_mode"]
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
        self.location_analyzer = LocationAnalyzer(session)
        self.comparable_sales_analyzer = ComparableSalesAnalyzer(session)

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
        elif tool_name == "search_ordinances":
            return await self._search_ordinances(**parameters)
        elif tool_name == "analyze_location":
            return await self._analyze_location(**parameters)
        elif tool_name == "analyze_comparable_sales":
            return await self._analyze_comparable_sales(**parameters)
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
            # Use enhanced address matching
            from sqlalchemy import text
            from src.utils.address_matcher import get_address_matcher

            matcher = get_address_matcher()

            # Strategy 1: Try normalized exact match
            normalized = matcher.normalize_address(property_address)
            query = text("""
                SELECT id, parcel_id, site_address
                FROM bulk_property_records
                WHERE LOWER(site_address) = LOWER(:address)
                LIMIT 1
            """)
            result = await self.session.execute(query, {'address': normalized})
            row = result.fetchone()

            if row:
                property_id = str(row[0])
                parcel_id = row[1]
            else:
                # Strategy 2: Try progressive fuzzy matching
                search_queries = matcher.build_search_queries(property_address)
                candidates = []

                for search_query in search_queries:
                    query = text("""
                        SELECT id, parcel_id, site_address
                        FROM bulk_property_records
                        WHERE LOWER(site_address) LIKE :pattern
                        LIMIT 10
                    """)
                    result = await self.session.execute(
                        query,
                        {'pattern': f'%{search_query}%'}
                    )
                    rows = result.fetchall()

                    if rows:
                        # Collect candidates
                        for r in rows:
                            candidates.append((str(r[0]), r[1], r[2]))
                        break  # Stop at first successful query level

                if not candidates:
                    # No matches found at all
                    return {
                        'error': f'Property not found: {property_address}',
                        'suggestion': 'Try different address format, verify street name/number, or use parcel_id',
                        'normalized_query': normalized,
                        'note': 'Address normalization attempted: street abbreviations, ordinals, and directionals standardized'
                    }

                # Strategy 3: Rank candidates by similarity
                ranked = matcher.rank_matches(property_address, candidates)

                # Take best match if score is high enough (>0.7)
                best_match = ranked[0]
                property_id, parcel_id, matched_address, score = best_match

                if score < 0.7:
                    # Score too low - provide suggestions
                    top_suggestions = [
                        {'address': addr, 'similarity': f'{sc:.0%}'}
                        for _, _, addr, sc in ranked[:3]
                    ]
                    return {
                        'error': f'No exact match for: {property_address}',
                        'suggestion': 'Address may be misspelled or formatted differently. Did you mean one of these?',
                        'possible_matches': top_suggestions,
                        'note': 'Use exact address from suggestions or provide parcel_id for guaranteed match'
                    }

                # Good match found (score >= 0.7) - use it
                # The property_id and parcel_id are already set from best_match above

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

    async def _search_ordinances(
        self,
        query: str,
        city: str = None,
        top_k: int = 5,
        min_relevance: float = 0.6
    ) -> Dict[str, Any]:
        """Search municipal ordinances using RAG"""

        try:
            # Get RAG service
            rag = get_ordinance_rag()

            # Search ordinances
            results = await rag.search(
                session=self.session,
                query=query,
                city=city,
                top_k=top_k,
                min_relevance=min_relevance
            )

            # Format results for agent
            if not results:
                return {
                    'query': query,
                    'city_filter': city,
                    'results_found': 0,
                    'message': f'No ordinances found matching "{query}"' + (f' in {city}' if city else ''),
                    'suggestion': 'Try a broader query or remove city filter'
                }

            formatted_results = []
            for result in results:
                formatted_results.append({
                    'city': result['city'],
                    'relevance_score': result['relevance_score'],
                    'text': result['chunk_text'],
                    'source_file': result['ordinance_file'],
                    'chunk_number': result['chunk_number'],
                    'word_count': result['chunk_words']
                })

            return {
                'query': query,
                'city_filter': city,
                'results_found': len(results),
                'ordinances': formatted_results
            }

        except Exception as e:
            return {
                'error': f'Ordinance search failed: {str(e)}',
                'query': query
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

    async def _analyze_location(
        self,
        analysis_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute LocationAnalyzer methods based on analysis_type"""

        try:
            if analysis_type == "nearby_properties":
                # Extract relevant parameters
                result = await self.location_analyzer.find_nearby_properties(
                    target_property_id=kwargs.get('target_property_id'),
                    target_latitude=kwargs.get('target_latitude'),
                    target_longitude=kwargs.get('target_longitude'),
                    radius_miles=kwargs.get('radius_miles', 1.0),
                    market_id=kwargs.get('market_id'),
                    property_type=kwargs.get('property_type'),
                    min_price=kwargs.get('min_price'),
                    max_price=kwargs.get('max_price'),
                    limit=100
                )
                return result

            elif analysis_type == "growth_hotspots":
                market_id = kwargs.get('market_id')
                if not market_id:
                    return {
                        'error': 'market_id required for growth_hotspots analysis',
                        'analysis_type': analysis_type
                    }

                result = await self.location_analyzer.find_growth_hotspots(
                    market_id=market_id,
                    min_activity_score=kwargs.get('min_activity_score', 0.7),
                    lookback_days=kwargs.get('lookback_days', 180)
                )
                return result

            elif analysis_type == "neighborhood":
                latitude = kwargs.get('target_latitude') or kwargs.get('latitude')
                longitude = kwargs.get('target_longitude') or kwargs.get('longitude')

                if latitude is None or longitude is None:
                    return {
                        'error': 'latitude and longitude required for neighborhood analysis',
                        'analysis_type': analysis_type
                    }

                result = await self.location_analyzer.analyze_neighborhood(
                    latitude=latitude,
                    longitude=longitude,
                    radius_miles=kwargs.get('radius_miles', 0.5),
                    market_id=kwargs.get('market_id')
                )
                return result

            else:
                return {
                    'error': f'Unknown analysis_type: {analysis_type}',
                    'valid_types': ['nearby_properties', 'growth_hotspots', 'neighborhood']
                }

        except Exception as e:
            return {
                'error': f'Location analysis failed: {str(e)}',
                'analysis_type': analysis_type
            }

    async def _analyze_comparable_sales(
        self,
        subject_property_id: str,
        analysis_mode: str,
        asking_price: float = None,
        max_distance_miles: float = 1.0,
        max_age_days: int = 180,
        min_comps: int = 3,
        max_comps: int = 10,
        size_tolerance: float = 0.3,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze comparable sales for market valuation"""
        try:
            # Validate required parameters
            if analysis_mode in ['validate_price', 'full_cma'] and asking_price is None:
                return {
                    'error': f'asking_price required for {analysis_mode} mode',
                    'analysis_mode': analysis_mode
                }

            # Execute requested analysis
            if analysis_mode == "find_comps":
                result = await self.comparable_sales_analyzer.find_comparable_sales(
                    subject_property_id=subject_property_id,
                    max_distance_miles=max_distance_miles,
                    max_age_days=max_age_days,
                    min_comps=min_comps,
                    max_comps=max_comps,
                    size_tolerance=size_tolerance
                )
                return result

            elif analysis_mode == "estimate_value":
                result = await self.comparable_sales_analyzer.estimate_market_value(
                    subject_property_id=subject_property_id,
                    max_distance_miles=max_distance_miles,
                    max_age_days=max_age_days
                )
                return result

            elif analysis_mode == "validate_price":
                result = await self.comparable_sales_analyzer.validate_asking_price(
                    subject_property_id=subject_property_id,
                    asking_price=asking_price,
                    max_distance_miles=max_distance_miles,
                    max_age_days=max_age_days
                )
                return result

            elif analysis_mode == "full_cma":
                result = await self.comparable_sales_analyzer.analyze_comps(
                    subject_property_id=subject_property_id,
                    asking_price=asking_price,
                    max_distance_miles=max_distance_miles,
                    max_age_days=max_age_days
                )
                return result

            else:
                return {
                    'error': f'Unknown analysis_mode: {analysis_mode}',
                    'valid_modes': ['find_comps', 'estimate_value', 'validate_price', 'full_cma']
                }

        except Exception as e:
            return {
                'error': f'Comparable sales analysis failed: {str(e)}',
                'analysis_mode': analysis_mode,
                'subject_property_id': subject_property_id
            }

    def get_tool_definitions(self) -> list:
        """Get tool definitions for Gemini function calling"""
        return TOOL_DEFINITIONS
