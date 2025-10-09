"""
Dominion AI Property Analysis Agent - Simplified Version

Uses Gemini 2.0 Flash with manual tool configuration for better control.
"""

import os
import json
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, date
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


def make_serializable(obj: Any) -> Any:
    """
    Convert objects to JSON-serializable format.

    Handles:
    - Decimal -> float
    - datetime/date -> ISO string
    - dict -> recursively serialize values
    - list -> recursively serialize items
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: make_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_serializable(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        # Handle custom objects
        return make_serializable(obj.__dict__)
    else:
        return obj


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

        The agent autonomously decides whether to:
        - Call analyze_property() for specific property questions
        - Call search_properties() for strategic "where to buy" questions
        - Call get_entity_properties() to analyze buyer patterns

        No hardcoded query classification - agent is smart enough to choose.

        Args:
            user_query: User's question (any format - agent will interpret)

        Returns:
            Complete analysis with recommendations
        """
        logger.info("agent_analysis_started", query=user_query)

        # Minimal context - let agent decide what tools to use
        context = {
            'user_query': user_query,
            'market': CurrentMarket.get_config().market.name,
            'note': 'Use tools to gather data. For specific properties, call analyze_property(address). For strategic queries, use search_properties() or get_entity_properties().'
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
                'query': user_query
            }

    def _build_analysis_prompt(self, context: Dict[str, Any], user_query: str) -> str:
        """
        Build analysis prompt - agent autonomously decides what tools to use.

        No hardcoded query classification - agent is smart enough to:
        - Recognize specific property questions and call analyze_property()
        - Recognize strategic queries and call search_properties()
        - Analyze patterns and call get_entity_properties()
        """

        prompt = f"""
┌─────────────────────────────────────────────────────────────┐
│ DOMINION REAL ESTATE INVESTMENT ADVISOR                    │
│ Market: {context.get('market', 'Unknown')}                  │
└─────────────────────────────────────────────────────────────┘

USER QUERY: {user_query}

=== YOUR TOOLS ===

You have access to these tools to gather data:

1. **analyze_property(address)** - Get complete property analysis
   Returns: Property details, owner portfolio, permits, crime, news, council activity

2. **search_properties(filters)** - Find properties by criteria
   Filters: property_type, max_price, min_lot_size, zoning, city, owner_type, etc.
   Returns: List of matching properties with addresses and parcel IDs

3. **get_entity_properties(entity_name, property_type)** - Get entity's portfolio
   Returns: All properties owned by entity with addresses and purchase dates

4. **analyze_entity(entity_name)** - Get entity statistics
   Returns: Portfolio size, acquisition patterns, activity trends

5. **analyze_market()** - Get market overview
   Returns: Market trends, active buyers, development patterns

=== YOUR TASK ===

**Autonomously decide which tools to use based on the query:**

**If user asks about a specific property** (e.g., "Should I buy 123 Main St?"):
1. Call analyze_property("123 Main St")
2. Analyze the returned data
3. Return recommendation with deal_success_probability score

**If user asks WHERE to buy** (e.g., "What land should I buy?"):
1. Call analyze_market() to understand current trends
2. Call search_properties() to find opportunities
3. Call get_entity_properties() to see what smart money is buying
4. Return SPECIFIC addresses and parcel IDs

**If user asks about an entity/developer** (e.g., "What is D.R. Horton buying?"):
1. Call analyze_entity("D R HORTON")
2. Call get_entity_properties("D R HORTON")
3. Analyze geographic clustering
4. Return pattern analysis and gap parcels

=== OUTPUT FORMAT ===

Return JSON with:
{{
  "recommendation": "BUY/AVOID/INVESTIGATE",
  "deal_success_probability": 0-100,
  "confidence": "high/medium/low",
  "reasoning": "Cite specific numbers and data",
  "recommendations": [
    {{
      "address": "SPECIFIC ADDRESS",
      "parcel_id": "PARCEL-ID",
      "priority": "HIGH/MEDIUM/LOW",
      "reasoning": "Why this property"
    }}
  ],
  "tool_calls_made": ["List tools you called"]
}}

CRITICAL RULES:
- ALWAYS call tools to get fresh data - don't guess
- For strategic queries, return SPECIFIC addresses, not hypothetical examples
- Cite actual numbers from tool responses
- If you don't have data, call the appropriate tool to get it
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

                                # Add function result (serialize to handle Decimal, datetime, etc.)
                                conversation.append({
                                    'role': 'user',
                                    'parts': [{'function_response': {
                                        'name': tool_call.name,
                                        'response': make_serializable(result)
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

