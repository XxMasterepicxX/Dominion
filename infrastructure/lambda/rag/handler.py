"""
RAG Lambda Function Handler

Handles 1 tool:
- search_ordinances - Search Florida municipal ordinances using Bedrock Knowledge Base

Uses Bedrock Knowledge Base Retrieve and RetrieveAndGenerate APIs.
Self-contained - no external module dependencies.
"""

import json
import os
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

# Initialize Bedrock Agent Runtime client
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

# Environment variables
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', 'placeholder')


def search_ordinances(params: Dict) -> Dict[str, Any]:
    """
    Search ordinances using Bedrock Knowledge Base.

    Parameters:
    - query: str (required) - Search query
    - jurisdiction: str (optional) - Filter by jurisdiction
    - max_results: int (default: 5) - Maximum results
    - generate_answer: bool (default: False) - Use RetrieveAndGenerate

    Returns:
        {
            "success": True,
            "results": [...],
            "count": 5
        }
    """
    query = params.get('query')
    jurisdiction = params.get('jurisdiction')
    max_results = params.get('max_results', 5)
    generate_answer = params.get('generate_answer', False)

    if not query:
        return {'success': False, 'error': 'query parameter is required'}

    # Check if Knowledge Base is configured
    if KNOWLEDGE_BASE_ID == 'placeholder':
        return {
            'success': False,
            'error': 'Knowledge Base not yet deployed. Deploy Phase 4 first.',
            'note': 'This tool will work after deploying Dominion-Knowledge stack'
        }

    try:
        print(f"Searching ordinances: query={query}, jurisdiction={jurisdiction}")

        # Build retrieval query
        retrieval_query = query
        if jurisdiction:
            retrieval_query = f"{query} in {jurisdiction}"

        # Option 1: Just retrieve (default)
        if not generate_answer:
            response = bedrock_agent_runtime.retrieve(
                knowledgeBaseId=KNOWLEDGE_BASE_ID,
                retrievalQuery={'text': retrieval_query},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': max_results,
                    }
                }
            )

            # Parse results
            results = []
            for item in response.get('retrievalResults', []):
                results.append({
                    'content': item.get('content', {}).get('text', ''),
                    'source': item.get('location', {}).get('s3Location', {}).get('uri', ''),
                    'score': item.get('score', 0.0),
                    'metadata': item.get('metadata', {})
                })

            print(f"Ordinance search complete: {len(results)} results")

            return {
                'success': True,
                'query': query,
                'jurisdiction': jurisdiction,
                'count': len(results),
                'results': results
            }

        # Option 2: Retrieve and generate answer
        else:
            response = bedrock_agent_runtime.retrieve_and_generate(
                input={'text': retrieval_query},
                retrieveAndGenerateConfiguration={
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                        'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-premier-v1:0',
                        'retrievalConfiguration': {
                            'vectorSearchConfiguration': {
                                'numberOfResults': max_results
                            }
                        }
                    }
                }
            )

            # Parse response
            answer = response.get('output', {}).get('text', '')
            citations = response.get('citations', [])

            # Extract sources
            sources = []
            for citation in citations:
                for ref in citation.get('retrievedReferences', []):
                    location = ref.get('location', {}).get('s3Location', {})
                    sources.append({
                        'uri': location.get('uri', ''),
                        'content': ref.get('content', {}).get('text', '')[:500]  # First 500 chars
                    })

            print(f"Generated answer with {len(sources)} sources")

            return {
                'success': True,
                'query': query,
                'jurisdiction': jurisdiction,
                'answer': answer,
                'sources': sources,
                'citations_count': len(citations)
            }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = str(e)

        # Handle specific errors
        if error_code == 'ResourceNotFoundException':
            return {
                'success': False,
                'error': 'Knowledge Base not found',
                'note': 'Make sure to deploy Dominion-Knowledge stack first'
            }
        elif error_code == 'ValidationException':
            return {
                'success': False,
                'error': 'Invalid Knowledge Base configuration',
                'details': error_msg
            }
        else:
            print(f"Bedrock error: {error_code} - {error_msg}")
            return {
                'success': False,
                'error': f'Bedrock API error: {error_code}',
                'details': error_msg
            }

    except Exception as e:
        print(f"Ordinance search error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'error': str(e)
        }


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for RAG tool.

    Event format:
    {
        "tool": "search_ordinances",
        "parameters": {
            "query": "What are the setback requirements?",
            "jurisdiction": "Gainesville",
            "max_results": 5,
            "generate_answer": false
        }
    }
    """
    try:
        print(f"RAG function invoked: {json.dumps(event)}")

        tool_name = event.get('tool')
        parameters = event.get('parameters', {})

        if tool_name != 'search_ordinances':
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'Unknown tool: {tool_name}',
                    'expected': 'search_ordinances'
                })
            }

        # Execute tool
        result = search_ordinances(parameters)

        print(f"RAG tool executed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str)
        }

    except Exception as e:
        print(f"RAG function error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
