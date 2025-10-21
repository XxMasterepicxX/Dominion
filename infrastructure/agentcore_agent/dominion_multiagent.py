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
import asyncio
from typing import Dict, Any, Optional
import structlog

# Import supervisor (which imports all specialists)
from agents import supervisor

logger = structlog.get_logger()


# AgentCore HTTP server wrapper using BedrockAgentCoreApp
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload: Dict[str, Any], context=None) -> Dict[str, Any]:
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
        # Use session_id from frontend (projectId) for traceability
        session_id = payload.get('session_id') or str(uuid.uuid4())
        user_id = payload.get('user_id', 'anonymous')

        if not user_query:
            logger.error("Missing prompt in payload")
            return {
                'success': False,
                'error': 'Missing prompt in payload'
            }

        # Invoke Supervisor Agent with unique session_id for isolation
        logger.info("Invoking Supervisor Agent", query=user_query, session_id=session_id)

        # Create async ping handler to keep session alive during long-running work
        # This allows AgentCore to run for up to 8 hours instead of 15-minute timeout
        task_running = True

        async def ping_handler():
            """Ping every 30 seconds with HEALTHY_BUSY status to prevent timeout"""
            while task_running:
                if context:
                    try:
                        await context.ping(status="HEALTHY_BUSY")
                        logger.debug("Sent HEALTHY_BUSY ping", session_id=session_id)
                    except Exception as e:
                        logger.warning("Ping failed", error=str(e))
                await asyncio.sleep(30)

        # Start ping handler in background
        ping_task = asyncio.create_task(ping_handler()) if context else None

        # Invoke supervisor - returns both text response and structured data
        # This may take 10-20 minutes for complex multi-agent analysis
        result = supervisor.invoke(user_query, session_id=session_id)

        # Stop ping handler
        task_running = False
        if ping_task:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass

        # Supervisor returns dict with 'message' and 'structured_data'
        if isinstance(result, dict):
            message = result.get('message', str(result))
            structured_data = result.get('structured_data', {})
        else:
            message = result
            structured_data = {}

        logger.info("Multi-Agent analysis completed",
                   session_id=session_id,
                   user_id=user_id,
                   response_length=len(message),
                   has_structured_data=bool(structured_data))

        return {
            'success': True,
            'message': message,
            'architecture': 'multi-agent',
            'supervisor': 'Nova Premier',
            'specialists': 4,
            'session_id': session_id,
            'structured_data': structured_data  # Includes properties, developers, etc.
        }

    except Exception as e:
        logger.error("Multi-Agent system error", error=str(e), exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'architecture': 'multi-agent'
        }


# Lambda handler wrapper for AWS Lambda
def lambda_handler(event, context):
    """
    AWS Lambda handler that wraps the AgentCore entrypoint.

    Lambda Function URLs send events like:
    {
        "body": '{"prompt": "...", "session_id": "..."}',
        "headers": {...},
        ...
    }
    """
    import json

    try:
        # Parse body from Lambda Function URL event
        if 'body' in event:
            payload = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            # Direct invocation
            payload = event

        logger.info("Lambda handler invoked", event_keys=list(event.keys()))

        # Handle CORS for Lambda Function URL
        # Even though CORS is configured in CDK, we need to set headers in response
        cors_headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        }

        # Handle preflight OPTIONS requests
        method = None
        if isinstance(event, dict):
            method = event.get('httpMethod')
            if not method:
                request_context = event.get('requestContext') or {}
                http_info = request_context.get('http') if isinstance(request_context, dict) else {}
                method = http_info.get('method')
        if method and method.upper() == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({'success': True, 'message': 'CORS preflight OK'})
            }

        # Call the entrypoint (which is async)
        import asyncio
        result = asyncio.run(invoke(payload, context))

        # Return Lambda Function URL response format with CORS headers
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps(result)
        }
    except Exception as e:
        logger.error("Lambda handler error", error=str(e), exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            },
            'body': json.dumps({'success': False, 'error': str(e)})
        }


# Health check is handled automatically by BedrockAgentCoreApp via /ping endpoint


if __name__ == "__main__":
    # Start HTTP server on port 8080 when run directly (for local development)
    logger.info("Starting Dominion Multi-Agent System on port 8080")
    app.run()
# Force rebuild
# Force rebuild
