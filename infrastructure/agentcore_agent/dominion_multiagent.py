"""
Dominion Multi-Agent Real Estate Intelligence System for AWS Bedrock AgentCore

Architecture:
- 1 Supervisor Agent (Nova Premier) - Orchestration, cross-verification, synthesis
- 4 Specialist Agents (Nova Lite) - Domain expertise

Supervisor coordinates:
1. Property Specialist - Spatial analysis, clustering, assemblage (5 tools)
2. Market Specialist - Trends, absorption, valuation, comps (3 tools)
3. Developer Intelligence - Portfolio analysis, entity profiling (2 tools)
4. Regulatory & Risk - Zoning, permits, risk assessment (4 tools)

Total: 12 intelligence tools across 3 Lambda functions:
- Intelligence Lambda: 9 tools (property search, entity analysis, market trends, comps, etc.)
- RAG Lambda: 1 tool (ordinance search)
- Enrichment Lambda: 2 tools (QPublic, SunBiz scraping)

All prompts loaded from markdown files (no hardcoding).
"""

import os
import uuid
from typing import Dict, Any
import structlog

# Import supervisor (which imports all specialists)
from agents import supervisor

logger = structlog.get_logger()


# AgentCore HTTP server wrapper using BedrockAgentCoreApp
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    AgentCore entrypoint for multi-agent system.

    Automatically provides /invocations and /ping HTTP endpoints.

    Payload format from AgentCore:
    {
        "prompt": "Find investment properties under $150K in Phoenix",
        "session_id": "session-123",
        "user_id": "user-456"
    }

    Flow:
    1. User query → Supervisor Agent
    2. Supervisor delegates to 4 Specialist Agents
    3. Specialists execute tools and return analysis
    4. Supervisor cross-verifies, validates, synthesizes
    5. Supervisor returns institutional-grade recommendation
    """
    try:
        logger.info("Dominion Multi-Agent System invoked", payload=payload)

        user_query = payload.get('prompt')
        # Generate unique session ID per invocation to prevent conversation bleed
        session_id = str(uuid.uuid4())
        user_id = payload.get('user_id', 'anonymous')

        if not user_query:
            logger.error("Missing prompt in payload")
            return {
                'success': False,
                'error': 'Missing prompt in payload'
            }

        # Invoke Supervisor Agent with unique session_id for isolation
        logger.info("Invoking Supervisor Agent", query=user_query, session_id=session_id)

        result = supervisor.invoke(user_query, session_id=session_id)

        logger.info("Multi-Agent analysis completed",
                   session_id=session_id,
                   user_id=user_id,
                   response_length=len(result))

        return {
            'success': True,
            'message': result,
            'architecture': 'multi-agent',
            'supervisor': 'Nova Premier',
            'specialists': 4,
            'session_id': session_id
        }

    except Exception as e:
        logger.error("Multi-Agent system error", error=str(e), exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'architecture': 'multi-agent'
        }


# Health check is handled automatically by BedrockAgentCoreApp via /ping endpoint


if __name__ == "__main__":
    # Start HTTP server on port 8080 when run directly
    logger.info("Starting Dominion Multi-Agent System on port 8080")
    app.run()
