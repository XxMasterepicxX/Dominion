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

from src.agent.tools import AgentTools, TOOL_DEFINITIONS
from src.agent.prompts import SYSTEM_PROMPT
from src.config import CurrentMarket

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

        Args:
            user_query: User's question (any format - agent will interpret)

        Returns:
            Complete analysis with recommendations
        """
        logger.info("agent_analysis_started", query=user_query)

        # Classify query type to determine if tools are needed
        is_strategic_query = self._classify_query(user_query)

        # Build analysis prompt
        prompt = self._build_analysis_prompt(user_query)

        logger.info("sending_to_gemini",
                   query_type='strategic' if is_strategic_query else 'specific',
                   thinking_mode=True)

        try:
            # Configure for strategic vs property-specific queries
            if is_strategic_query:
                # Strategic query: Enable autonomous tool calling
                # NOTE: Grounding (Google Search) is incompatible with function calling in Gemini API
                # For now, prioritize database tools which provide comprehensive real estate data

                config = types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=-1,  # Dynamic: adapts to query complexity
                        include_thoughts=True  # Capture reasoning for learning
                    ),
                    temperature=0.7,  # Optimal for analytical reasoning (Google 2025 best practice)
                    # No max_output_tokens: Let model write comprehensive analysis (2.5 Pro supports 64k)
                    tools=self._convert_tools_to_gemini_format(),
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode='AUTO'  # Autonomous tool selection
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
                # Property-specific query: May still need tools for data lookup
                config = types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=-1,  # Dynamic thinking for best analysis
                        include_thoughts=True  # Capture reasoning
                    ),
                    temperature=0.7,  # Analytical depth for complex real estate decisions
                    # No max_output_tokens: Allow comprehensive property analysis
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

                # Execute with tool calling (tools available for both query types)
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
        """
        Classify if query is strategic (needs extensive tool usage) vs specific (targeted analysis).

        Strategic queries: "Where should I buy?", "Find something to invest in", "What is [ENTITY] buying?"
        Specific queries: "Should I buy [ADDRESS]?", "Analyze [ADDRESS]"

        Args:
            user_query: User's natural language query

        Returns:
            True if strategic query, False if specific property query
        """
        query_lower = user_query.lower()

        # Strategic query patterns (general investment search, entity research, pattern analysis)
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

        # Check for strategic patterns
        if any(pattern in query_lower for pattern in strategic_patterns):
            return True

        # Check for specific address pattern (property-specific query)
        address_pattern = r'\d+\s+[A-Za-z\s]+(?:St(?:reet)?|Ave(?:nue)?|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place)'
        if re.search(address_pattern, user_query, re.IGNORECASE):
            return False

        # Default to strategic (safer to enable tools)
        return True

    def _build_analysis_prompt(self, user_query: str) -> str:
        """
        Build dynamic analysis prompt based on query.
        No hardcoded text - agent decides tool usage autonomously.

        Args:
            user_query: User's natural language query

        Returns:
            Formatted prompt for Gemini
        """
        market_name = CurrentMarket.get_name()

        # Build prompt dynamically
        prompt = f"""Real Estate Analysis Request

Market: {market_name}
Query: {user_query}

Instructions:
- Use available tools to gather data
- Think through the analysis step by step
- Cite specific evidence from tool responses
- Return structured JSON with recommendation and reasoning
- For strategic queries, provide specific addresses and parcel IDs (not generic examples)

Output Format:
{{
  "recommendation": "BUY/AVOID/INVESTIGATE",
  "deal_success_probability": 0-100,
  "confidence": "high/medium/low",
  "reasoning": "Evidence-based analysis",
  "recommendations": [
    {{"address": "Specific address", "parcel_id": "ID", "priority": "HIGH/MEDIUM/LOW", "reasoning": "Why"}}
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

                    # Rate limit: Wait 30 seconds between iterations (2 requests/minute free tier)
                    # TODO: Remove this delay when upgraded to paid tier
                    if iteration < max_iterations - 1:  # Don't sleep on last iteration
                        logger.info("rate_limit_delay", seconds=30, reason="gemini_free_tier")
                        await asyncio.sleep(30)

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

