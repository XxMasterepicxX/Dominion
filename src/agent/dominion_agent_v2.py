"""
Dominion AI Property Analysis Agent - Simplified Version

Uses Gemini 2.5 Pro with dynamic thinking, tool calling, and grounding.
Optimized for complex real estate analysis with no hardcoded limits.
"""

import os
import json
import re
import asyncio
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

from agent.tools import AgentTools, TOOL_DEFINITIONS
from agent.prompts import SYSTEM_PROMPT
from config import CurrentMarket

logger = structlog.get_logger(__name__)


def make_serializable(obj: Any) -> Any:
    """Convert objects to JSON-serializable format (Decimal, datetime, nested structures)."""
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
    """AI property analysis agent using Gemini 2.5 Pro with tool calling and thinking mode."""

    def __init__(self, session: AsyncSession, api_key: Optional[str] = None):
        if not GENAI_AVAILABLE:
            raise ImportError("google-generativeai not installed. Install with: pip install google-generativeai")

        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key required")

        self.session = session
        self.tools = AgentTools(session)

        # Configure Gemini (new SDK)
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = 'gemini-2.5-pro'
        self.system_instruction = SYSTEM_PROMPT

        # Configure rate limiting based on tier
        self.gemini_tier = os.getenv('GEMINI_TIER', 'free').lower()
        if self.gemini_tier == 'free':
            # Free tier: 2 RPM = 60 seconds between requests (conservative to avoid 429 errors)
            self.rate_limit_delay = 60.0
            self.max_rpm = 1
        else:
            # Paid tier: 300 RPM = 0.2 seconds between requests (very fast)
            self.rate_limit_delay = 0.2
            self.max_rpm = 300

        self.last_api_call = None

        logger.info("dominion_agent_initialized",
                   model="gemini-2.5-pro",
                   gemini_tier=self.gemini_tier,
                   max_rpm=self.max_rpm,
                   rate_limit_delay=self.rate_limit_delay,
                   thinking_mode=True,
                   sdk="google-genai")

    async def _apply_rate_limit(self):
        """Apply rate limiting delay before API call"""
        if self.last_api_call:
            elapsed = (datetime.now() - self.last_api_call).total_seconds()
            if elapsed < self.rate_limit_delay:
                delay = self.rate_limit_delay - elapsed
                logger.info("rate_limit_delay",
                           tier=self.gemini_tier,
                           delay_seconds=round(delay, 1),
                           elapsed_since_last=round(elapsed, 1))
                await asyncio.sleep(delay)

        self.last_api_call = datetime.now()

    async def analyze(self, user_query: str) -> Dict[str, Any]:
        """Run property analysis with autonomous tool calling."""
        logger.info("agent_analysis_started", query=user_query)

        # Classify query type to determine if tools are needed
        is_strategic_query = self._classify_query(user_query)

        # Build analysis prompt
        prompt = self._build_analysis_prompt(user_query)

        logger.info("sending_to_gemini",
                   query_type='strategic' if is_strategic_query else 'specific',
                   thinking_mode=True)

        try:
            if is_strategic_query:
                config = types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=-1,
                        include_thoughts=True
                    ),
                    temperature=0.7,
                    tools=self._convert_tools_to_gemini_format(),
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode='AUTO'
                        )
                    )
                )
                logger.info("strategic_query_config",
                           temperature=0.7,
                           thinking_budget="dynamic",
                           output_tokens="unlimited",
                           tools_enabled=len(TOOL_DEFINITIONS))

                # Execute with tool calling
                result = await self._execute_with_tools(prompt, config)

            else:
                config = types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=-1,
                        include_thoughts=True
                    ),
                    temperature=0.7,
                    tools=self._convert_tools_to_gemini_format(),
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode='AUTO'
                        )
                    )
                )
                logger.info("property_analysis_config",
                           temperature=0.7,
                           thinking_budget="dynamic",
                           output_tokens="unlimited")

                result = await self._execute_with_tools(prompt, config)

            # Add metadata
            result['query_type'] = 'strategic' if is_strategic_query else 'specific'
            result['query'] = user_query

            logger.info("agent_analysis_completed",
                       query_type=result['query_type'],
                       recommendation=result.get('recommendation'),
                       probability=result.get('deal_success_probability'),
                       tools_called=len(result.get('tool_calls_made', [])))

            return result

        except Exception as e:
            logger.error("analysis_failed", error=str(e), query=user_query)
            return {
                'error': f'Analysis failed: {str(e)}',
                'query': user_query,
                'recommendation': 'ERROR',
                'deal_success_probability': 0,
                'confidence': 'none'
            }

    def _classify_query(self, user_query: str) -> bool:
        """Classify if query is strategic (broad search) vs specific (single property)."""
        query_lower = user_query.lower()

        strategic_patterns = [
            'where should i buy',
            'what should i buy',
            'find properties',
            'find something',
            'find a property',
            'find an area',
            'search for',
            'what is buying',
            'what are they buying',
            'what did they buy',
            'follow the',
            'follow smart money',
            'assemblage',
            'gap parcel',
            'developer pattern',
            'what opportunities',
            'where to invest',
            'best area to buy'
        ]

        if any(pattern in query_lower for pattern in strategic_patterns):
            return True

        address_pattern = r'\d+\s+[A-Za-z\s]+(?:St(?:reet)?|Ave(?:nue)?|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place)'
        if re.search(address_pattern, user_query, re.IGNORECASE):
            return False

        return True

    def _build_analysis_prompt(self, user_query: str) -> str:
        """Build analysis prompt with institutional framework."""
        market_name = CurrentMarket.get_name()

        prompt = f"""Real Estate Analysis Request

Market: {market_name}
Query: {user_query}

INSTITUTIONAL ANALYSIS APPROACH:
1. Gather comprehensive data using tools
2. Calculate key ratios and patterns from raw data:
   - Permit-to-sales ratio (permits issued / sales completed)
   - Sales velocity (properties sold per month)
   - Developer concentration (% market share by permit count)
   - Acquisition frequency (properties bought per 30/90/180 days)
   - Geographic proximity (distances between parcels)
3. Compare current data to historical baselines (12-month, 24-month)
4. Analyze the numbers and draw your own conclusions

Instructions:
- Use available tools strategically to gather complete picture
- Think step by step like institutional analyst
- Cite specific numbers and evidence from tool responses
- Return structured JSON with recommendation and detailed reasoning
- For strategic queries, provide VERIFIED addresses from analyze_property calls

Output Format:
{{
  "recommendation": "BUY/AVOID/INVESTIGATE",
  "deal_success_probability": 0-100,
  "confidence": "high/medium/low",
  "reasoning": "Data-driven analysis with institutional metrics",
  "key_factors": {{
    "supply_demand": "Permit-to-sales ratio and velocity metrics",
    "smart_money": "Institutional investor activity patterns",
    "risks": "Concentration, oversupply, volatility indicators"
  }},
  "recommendations": [
    {{"address": "VERIFIED address from tools", "parcel_id": "ID", "priority": "HIGH/MEDIUM/LOW", "reasoning": "Why with data"}}
  ]
}}
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
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
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
            # Try parsing entire response first
            result = json.loads(response_text.strip())
            if thoughts_text:
                result['model_thoughts'] = thoughts_text
            return result
        except json.JSONDecodeError:
            # Try to find JSON in code block (```json ... ```)
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if code_block_match:
                try:
                    result = json.loads(code_block_match.group(1))
                    if thoughts_text:
                        result['model_thoughts'] = thoughts_text
                    return result
                except json.JSONDecodeError:
                    pass

            # Try to find any JSON object (use simpler greedy match as last resort)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    if thoughts_text:
                        result['model_thoughts'] = thoughts_text
                    return result
                except json.JSONDecodeError as e:
                    logger.warning("json_parse_failed", error=str(e), response_preview=response_text[:200])
        except Exception as e:
            logger.warning("json_extraction_failed", error=str(e))

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
        """Convert tool definitions to Gemini function calling format."""
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
        """Execute query with autonomous tool calling loop."""
        conversation = []
        conversation.append({'role': 'user', 'parts': [{'text': prompt}]})

        max_iterations = 30
        tool_calls_made = []
        vacant_land_found = False
        ordinances_checked = False

        for iteration in range(max_iterations):
            logger.info("tool_calling_iteration",
                       iteration=iteration + 1,
                       max=max_iterations)

            await self._apply_rate_limit()

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=conversation,
                config=config
            )

            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    parts = candidate.content.parts

                    has_function_call = False
                    for part in parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            has_function_call = True
                            tool_call = part.function_call

                            logger.info("executing_tool",
                                       tool=tool_call.name,
                                       args=dict(tool_call.args))

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

                                if tool_call.name == 'analyze_property':
                                    if isinstance(result, dict) and 'property' in result:
                                        prop = result['property']
                                        classification = prop.get('classification', {})
                                        prop_type = classification.get('property_type', prop.get('property_type', '')).upper()
                                        if 'VACANT' in prop_type:
                                            vacant_land_found = True
                                            logger.info("vacant_land_detected",
                                                       parcel_id=prop.get('parcel_id'),
                                                       property_type=prop_type)

                                elif tool_call.name == 'search_ordinances':
                                    ordinances_checked = True
                                    logger.info("ordinances_checked")

                                conversation.append({
                                    'role': 'model',
                                    'parts': [{'function_call': {
                                        'name': tool_call.name,
                                        'args': tool_call.args
                                    }}]
                                })

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

                                conversation.append({
                                    'role': 'user',
                                    'parts': [{'function_response': {
                                        'name': tool_call.name,
                                        'response': {'error': str(e)}
                                    }}]
                                })

                    if not has_function_call:
                        if vacant_land_found and not ordinances_checked:
                            logger.warning("vacant_land_without_ordinances",
                                          message="Forcing ordinance check for vacant land")

                            forced_prompt = """CRITICAL SAFETY REQUIREMENT VIOLATION DETECTED:

You analyzed vacant land properties but did NOT verify zoning/ordinance compliance.
This is UNACCEPTABLE for professional real estate due diligence.

You MUST now call search_ordinances to verify regulatory feasibility before providing recommendations.

Query the ordinances for:
- Zoning regulations for the vacant land properties you analyzed
- Minimum lot size requirements
- Development restrictions and requirements

City: Gainesville (or appropriate city for the properties)

This is NOT optional. This is a MANDATORY safety check."""

                            conversation.append({
                                'role': 'user',
                                'parts': [{'text': forced_prompt}]
                            })

                            forced_config = types.GenerateContentConfig(
                                system_instruction=self.system_instruction,
                                temperature=0.7,
                                tools=self._convert_tools_to_gemini_format(),
                                tool_config=types.ToolConfig(
                                    function_calling_config=types.FunctionCallingConfig(
                                        mode='ANY',
                                        allowed_function_names=['search_ordinances']
                                    )
                                )
                            )

                            logger.info("forcing_ordinance_check",
                                       mode='ANY',
                                       allowed_functions=['search_ordinances'])

                            config = forced_config
                            continue

                        result = self._parse_response(response)
                        result['tool_calls_made'] = tool_calls_made
                        return result

        logger.warning("max_tool_iterations_reached", iterations=max_iterations)
        return {
            'error': 'Max tool calling iterations reached',
            'tool_calls_made': tool_calls_made,
            'recommendation': 'INVESTIGATE',
            'deal_success_probability': 50,
            'confidence': 'low',
            'reasoning': 'Analysis incomplete - too many tool calls required'
        }

