"""
Dominion AI Property Analysis Agent - Simplified Version

Uses Gemini 2.0 Flash with manual tool configuration for better control.
"""

import os
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, will use system env vars

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from src.agent.tools import AgentTools, TOOL_DEFINITIONS
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.context_builder import ContextBuilder

logger = structlog.get_logger(__name__)


class DominionAgent:
    """Simplified AI agent with better tool integration"""

    def __init__(self, session: AsyncSession, api_key: Optional[str] = None):
        if not GENAI_AVAILABLE:
            raise ImportError("google-generativeai not installed. Install with: pip install google-generativeai")

        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key required")

        self.session = session
        self.tools = AgentTools(session)
        self.context_builder = ContextBuilder(session)

        # Configure Gemini (new SDK)
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = 'gemini-2.5-pro'
        self.system_instruction = SYSTEM_PROMPT

        logger.info("dominion_agent_initialized",
                   model="gemini-2.5-pro",
                   thinking_mode=True,
                   sdk="google-genai")

    async def analyze(self, user_query: str) -> Dict[str, Any]:
        """
        Enhanced property analysis with Gemini 2.5 Pro thinking mode + grounding.

        Uses 50k token context + autonomous tool calling + Google grounding.

        Args:
            user_query: User's question (e.g., "Should I buy 7230 SW 42ND PL?")

        Returns:
            Complete analysis with deal success probability
        """
        logger.info("agent_analysis_started", query=user_query)

        # Detect query type
        query_lower = user_query.lower()
        is_strategic_query = any(phrase in query_lower for phrase in [
            'where should i buy',
            'where to buy',
            'what should i buy',
            'which properties',
            'follow this pattern',
            'follow the pattern',
            'land assembly',
            'has been buying'
        ])

        if is_strategic_query:
            # Strategic query - pass full query to Gemini for analysis
            # It will need to query database itself or use provided context
            logger.info("strategic_query_detected", query=user_query)

            # Build minimal context (no specific property)
            context = {
                'query_type': 'strategic',
                'user_query': user_query,
                'database_available': True,
                'note': 'This is a strategic WHERE to buy question, not a specific property analysis'
            }
        else:
            # Specific property query - extract address
            import re
            cleaned_query = re.sub(r'[?!.,;]', '', user_query)
            words = cleaned_query.split()
            address_parts = [w for w in words if w and not w.lower() in ['should', 'i', 'buy', 'the', 'property', 'at', 'a']]
            address = ' '.join(address_parts)

            logger.info("building_context", address=address)

            # Build comprehensive 50k token context
            context = await self.context_builder.build_full_context(property_address=address)

            if not context['property']:
                return {
                    'error': f'Property not found: {address}',
                    'suggestion': 'Try different address format or rephrase as strategic query'
                }

        # Build analysis prompt (QUERY AT END per research best practices)
        prompt = self._build_analysis_prompt(context, user_query)

        logger.info("sending_to_gemini",
                   context_size=len(json.dumps(context, default=str)),
                   thinking_mode=True)

        try:
            # VISION: AI Investment Partner that predicts with 80%+ accuracy
            # GOAL: BEST possible analysis through deep reasoning
            # ACCEPT: 5-10pt variance is NORMAL for complex real estate decisions
            #
            # We want the agent to:
            # 1. Think deeply about every property (not rush to conclusion)
            # 2. Consider multiple scenarios and risk factors
            # 3. Learn patterns from reasoning (capture thoughts)
            # 4. Provide accurate predictions (not just consistent scores)
            #
            # Use maximum thinking for ALL queries

            # Configure for strategic vs property-specific queries
            if is_strategic_query:
                # Strategic query: Enable autonomous tool calling
                config = types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=-1,  # MAXIMUM dynamic thinking
                        include_thoughts=True
                    ),
                    temperature=0.3,
                    max_output_tokens=8192,
                    tools=self._convert_tools_to_gemini_format(),  # Enable tools
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode='AUTO'  # Let Gemini decide when to call tools
                        )
                    )
                )
                logger.info("using_autonomous_tool_calling",
                           temperature=0.3,
                           thinking="dynamic_unlimited",
                           tools_enabled=len(TOOL_DEFINITIONS),
                           mode="AUTO")

                # Execute with tool calling
                result = await self._execute_with_tools(prompt, config)

            else:
                # Property-specific query: Pre-loaded context, no tools needed
                config = types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=-1,  # MAXIMUM dynamic thinking for best analysis
                        include_thoughts=True  # Capture reasoning for pattern learning
                    ),
                    temperature=0.3,  # Balanced: thoughtful but focused
                    max_output_tokens=8192
                )
                logger.info("using_deep_analysis_mode",
                           temperature=0.3,
                           thinking="dynamic_unlimited",
                           goal="best_prediction_accuracy")

                # Send prompt with appropriate config
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )

                # Parse response
                result = self._parse_response(response)

            # Add metadata
            if is_strategic_query:
                result['query_type'] = 'strategic'
                result['query'] = user_query
            else:
                result['property_analyzed'] = context['property']['site_address']
                result['context_provided'] = {
                    'portfolio_size': len(context['owner_portfolio']),
                    'recent_activity': len(context['owner_activity']),
                    'permits': len(context['permits'].get('at_property', [])),
                    'crime_incidents': len(context['crime']),
                    'council_mentions': len(context['council']),
                    'news_articles': len(context['news'])
                }

            logger.info("agent_analysis_completed",
                       recommendation=result.get('recommendation'),
                       probability=result.get('deal_success_probability'))

            return result

        except Exception as e:
            logger.error("analysis_failed", error=str(e))
            return {
                'error': f'Analysis failed: {str(e)}',
                'property': context['property']['site_address']
            }

    def _build_analysis_prompt(self, context: Dict[str, Any], user_query: str) -> str:
        """
        Build analysis prompt with full context.

        Research best practices:
        - Put query at END of context
        - Structure context clearly
        - Use 50k tokens (5% of capacity)
        """

        # Check if strategic query
        if context.get('query_type') == 'strategic':
            # Strategic query - minimal context, let Gemini query database
            prompt = f"""
┌─────────────────────────────────────────────────────────────┐
│ STRATEGIC QUERY DETECTED                                    │
└─────────────────────────────────────────────────────────────┘

User Query: {user_query}

This is a TYPE 2 query: "WHERE should I buy to follow a pattern?"

INSTRUCTIONS:
1. Parse the query to identify the DEVELOPER/OWNER name
2. You have these tools available:
   - analyze_entity: Get complete portfolio for an owner
   - analyze_property: Get specific property details

3. Your task:
   a. Get the owner's complete portfolio
   b. Analyze their geographic clustering (look for patterns in addresses)
   c. Identify GAPS in their assemblage
   d. Recommend SPECIFIC ADDRESSES to target
   e. Predict likelihood and timeline of acquisition

4. Output FORMAT:
{{
  "query_type": "strategic_acquisition",
  "developer_pattern_analysis": {{
    "entity_name": "...",
    "total_parcels": X,
    "geographic_pattern": "Describe clustering by street",
    "strategy": "Land assembly for subdivision / Commercial development / etc"
  }},
  "parcel_mapping": {{
    "owned_parcels": ["List all addresses"],
    "street_clusters": ["[STREET NAME]: parcels [range]", ...],
    "gaps_identified": ["[ADDRESS] (between [ADDR1] and [ADDR2])", ...],
    "edge_parcels": ["[ADDRESS] (high end of block)", ...]
  }},
  "recommendations": [
    {{
      "address": "[SPECIFIC ADDRESS]",
      "priority": "HIGH/MEDIUM/LOW",
      "acquisition_probability": "[X]%",
      "reasoning": "Fills critical gap between [ADDR1] and [ADDR2]",
      "estimated_offer_timeline": "[X]-[Y] days",
      "suggested_price": "$[AMOUNT] ([X]% above current market)"
    }}
  ],
  "predicted_timeline": "Rezoning Q[X] [YEAR], development [YEAR]"
}}

START by calling analyze_entity with the developer name from the query.
"""
            return prompt

        # Normal property-specific query
        prompt = f"""
┌─────────────────────────────────────────────────────────────┐
│ TIER 1: DATABASE CONTEXT (Historical Truth)                │
└─────────────────────────────────────────────────────────────┘

PROPERTY DETAILS:
{json.dumps(context['property'], indent=2, default=str)}

OWNER PORTFOLIO (All {len(context['owner_portfolio'])} properties):
{json.dumps(context['owner_portfolio'], indent=2, default=str)}

RECENT OWNER ACTIVITY (Last 180 days):
{json.dumps(context['owner_activity'], indent=2, default=str)}

NEIGHBORHOOD CONTEXT:
{json.dumps(context['neighborhood'], indent=2, default=str)}

PERMIT HISTORY:
{json.dumps(context['permits'], indent=2, default=str)}

CRIME DATA (Last 12 months, within 0.5 miles):
{json.dumps(context['crime'], indent=2, default=str)}

CITY COUNCIL ACTIVITY (Last 180 days):
{json.dumps(context['council'], indent=2, default=str)}

NEWS COVERAGE (Last 180 days):
{json.dumps(context['news'], indent=2, default=str)}

GEOGRAPHIC CLUSTERING ANALYSIS:
{json.dumps(context.get('geographic_analysis'), indent=2, default=str) if context.get('geographic_analysis') else 'No clustering analysis (less than 4 recent transactions)'}

┌─────────────────────────────────────────────────────────────┐
│ YOUR TASK (Query at END for best performance!)             │
└─────────────────────────────────────────────────────────────┘

User Query: {user_query}

=== ANALYSIS INSTRUCTIONS ===

STEP 1: DETECT QUERY TYPE
- Is this "Should I buy [ADDRESS]?" → TYPE 1
- Is this "WHERE should I buy to follow [PATTERN]?" → TYPE 2
- Is this "What's the pattern with [OWNER]?" → TYPE 3

STEP 2: APPLY FRAMEWORK SCORING

A. INVESTOR BEHAVIOR (40 points max):
   Portfolio: {len(context['owner_portfolio'])} properties
   Recent activity: {len(context['owner_activity'])} transactions (last 180 days)

   Score:
   - 20+ properties = sophisticated (40 points if buying, 20 if selling)
   - 10-19 properties = experienced (30 points if buying, 15 if selling)
   - Recent land purchases = +10 points (development signal)
   - Recent buying in same area = +10 points (conviction signal)

B. VALUATION (30 points max):
   Property value: {context['property'].get('market_value', 'N/A')}
   Neighborhood avg: {context['neighborhood'].get('avg_market_value', 'N/A')}

   Score:
   - 20%+ below average = 30 points (strong value)
   - 10-20% below = 20 points
   - At average = 10 points
   - Above average = 0 points

C. MARKET CONTEXT (20 points max):
   Recent sales: {context['neighborhood'].get('recent_sales', 0)}

   Score based on liquidity, appreciation, development activity

D. RISK ADJUSTMENT (-20 to 0 points):
   Property age, crime, deferred maintenance, seller motivation

TOTAL SCORE = A + B + C + D (max 100)

STEP 3: GEOGRAPHIC PATTERN ANALYSIS (if multiple properties in owner_activity)

IF owner has 4+ recent acquisitions:
1. Extract all addresses from owner_portfolio
2. Identify street clustering (e.g., "[X] parcels on [STREET NAME]")
3. Find gaps (missing house numbers between owned parcels)
4. Identify edge parcels (adjacent to cluster)
5. Recommend specific addresses to target

STEP 4: OUTPUT

For TYPE 1 (specific property):
{{
  "deal_success_probability": [SCORE],
  "confidence": "high/medium/low",
  "recommendation": "BUY/AVOID",
  "framework_breakdown": {{
    "investor_behavior_score": X,
    "valuation_score": Y,
    "market_context_score": Z,
    "risk_adjustment": -W
  }},
  "reasoning": "Cite SPECIFIC numbers from context",
  "patterns_identified": [...],
  "opportunities": [...],
  "risks": [...]
}}

For TYPE 2 (WHERE to buy):
{{
  "query_type": "strategic_acquisition",
  "developer_pattern_analysis": {{
    "total_parcels": X,
    "geographic_pattern": "Describe clustering",
    "strategy": "Land assembly/subdivision/etc"
  }},
  "parcel_mapping": {{
    "owned_parcels": ["List addresses"],
    "gaps_identified": ["Missing addresses between owned parcels"],
    "edge_parcels": ["Adjacent to cluster"]
  }},
  "recommendations": [
    {{
      "address": "SPECIFIC ADDRESS",
      "priority": "HIGH/MEDIUM/LOW",
      "acquisition_probability": "X%",
      "reasoning": "Why this parcel",
      "estimated_offer_timeline": "X days"
    }}
  ]
}}

CRITICAL:
- Use the FRAMEWORK SCORES every time (consistency)
- When sophisticated investor (20+ properties) is BUYING → Score investor_behavior at 35-40 points
- When you see land assembly pattern → Recommend WHERE to buy next
- ALWAYS cite specific numbers (addresses, values, dates)
"""

        return prompt

    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse Gemini response into structured result"""

        # Extract text from new SDK response
        response_text = ""
        thoughts_text = ""

        try:
            # New SDK structure
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        # Check for thoughts
                        if hasattr(part, 'thought') and part.thought:
                            thoughts_text += str(part.text) + "\n"
                        # Regular text
                        elif hasattr(part, 'text'):
                            response_text += str(part.text)

            # Fallback: try to get text attribute
            if not response_text and hasattr(response, 'text'):
                response_text = response.text

        except Exception as e:
            logger.warning("response_extraction_failed", error=str(e))
            response_text = str(response)

        # Log thoughts if present
        if thoughts_text:
            logger.info("model_thoughts", thoughts=thoughts_text[:500])

        # Try to parse as JSON
        try:
            # Look for JSON in response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if thoughts_text:
                    result['model_thoughts'] = thoughts_text
                return result
        except Exception as e:
            logger.warning("json_parse_failed", error=str(e))

        # Fallback: return raw response
        return {
            'raw_response': response_text,
            'model_thoughts': thoughts_text if thoughts_text else None,
            'recommendation': 'INVESTIGATE',
            'deal_success_probability': 50,
            'confidence': 'low',
            'reasoning': response_text
        }

    def _convert_tools_to_gemini_format(self) -> List[Dict[str, Any]]:
        """
        Convert tool definitions to Gemini function calling format.

        Gemini expects tools in this format:
        {
            "function_declarations": [
                {
                    "name": "tool_name",
                    "description": "tool description",
                    "parameters": {...}
                }
            ]
        }
        """
        function_declarations = []

        for tool in TOOL_DEFINITIONS:
            function_declarations.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            })

        return [{"function_declarations": function_declarations}]

    async def _execute_with_tools(
        self,
        prompt: str,
        config: types.GenerateContentConfig
    ) -> Dict[str, Any]:
        """
        Execute query with autonomous tool calling.

        Implements tool execution loop:
        1. Send query with tools enabled
        2. Check for tool calls in response
        3. Execute tools
        4. Send results back to Gemini
        5. Repeat until final answer

        Args:
            prompt: User query
            config: Gemini config with tools enabled

        Returns:
            Final analysis result
        """
        conversation = []
        conversation.append({'role': 'user', 'parts': [{'text': prompt}]})

        max_iterations = 5
        tool_calls_made = []

        for iteration in range(max_iterations):
            logger.info("tool_calling_iteration",
                       iteration=iteration + 1,
                       max=max_iterations)

            # Call Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=conversation,
                config=config
            )

            # Check for tool calls
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    parts = candidate.content.parts

                    # Check if any part is a function call
                    has_function_call = False
                    for part in parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            has_function_call = True
                            tool_call = part.function_call

                            logger.info("executing_tool",
                                       tool=tool_call.name,
                                       args=dict(tool_call.args))

                            # Execute tool
                            try:
                                result = await self.tools.execute_tool(
                                    tool_call.name,
                                    dict(tool_call.args)
                                )
                                tool_calls_made.append({
                                    'tool': tool_call.name,
                                    'args': dict(tool_call.args),
                                    'result': result
                                })

                                # Add model response to conversation
                                conversation.append({
                                    'role': 'model',
                                    'parts': [{'function_call': {
                                        'name': tool_call.name,
                                        'args': tool_call.args
                                    }}]
                                })

                                # Add function result
                                conversation.append({
                                    'role': 'user',
                                    'parts': [{'function_response': {
                                        'name': tool_call.name,
                                        'response': result
                                    }}]
                                })

                            except Exception as e:
                                logger.error("tool_execution_failed",
                                           tool=tool_call.name,
                                           error=str(e))

                                # Send error back to Gemini
                                conversation.append({
                                    'role': 'user',
                                    'parts': [{'function_response': {
                                        'name': tool_call.name,
                                        'response': {'error': str(e)}
                                    }}]
                                })

                    if not has_function_call:
                        # Final answer
                        result = self._parse_response(response)
                        result['tool_calls_made'] = tool_calls_made
                        return result

        # Max iterations reached
        logger.warning("max_tool_iterations_reached", iterations=max_iterations)
        return {
            'error': 'Max tool calling iterations reached',
            'tool_calls_made': tool_calls_made,
            'recommendation': 'INVESTIGATE',
            'deal_success_probability': 50,
            'confidence': 'low',
            'reasoning': 'Analysis incomplete - too many tool calls required'
        }

