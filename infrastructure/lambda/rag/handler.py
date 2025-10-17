"""
RAG Lambda Function Handler - FIXED VERSION

Handles 1 tool:
- search_ordinances - Search Florida municipal ordinances using pgvector

Uses pgvector DIRECTLY (embeddings already in Aurora: ordinance_embeddings table).
No Bedrock Knowledge Base required!
"""

import json
import os
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError

# Initialize clients
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
rds_data = boto3.client('rds-data', region_name='us-east-1')

# Environment variables
CLUSTER_ARN = os.environ.get('CLUSTER_ARN')
SECRET_ARN = os.environ.get('SECRET_ARN')
DATABASE_NAME = os.environ.get('DATABASE_NAME', 'dominion_db')

# Embedding model (use Amazon Titan for consistency)
EMBEDDING_MODEL_ID = 'amazon.titan-embed-text-v2:0'


def generate_embedding(text: str) -> List[float]:
    """Generate embedding vector for search query using Bedrock."""
    try:
        print(f"Generating embedding for query: {text[:100]}...")

        response = bedrock_runtime.invoke_model(
            modelId=EMBEDDING_MODEL_ID,
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                'inputText': text,
                'dimensions': 1024,
                'normalize': True
            })
        )

        result = json.loads(response['body'].read())
        embedding = result.get('embedding')

        if not embedding:
            raise ValueError("No embedding returned from Bedrock")

        if len(embedding) != 1024:
            raise ValueError(f"Invalid embedding dimensions: {len(embedding)}, expected 1024")

        print(f"Embedding generated successfully: {len(embedding)} dimensions")
        return embedding

    except Exception as e:
        print(f"Embedding generation error: {str(e)}")
        raise


def execute_sql(sql: str, params: List[Dict] = None) -> Dict:
    """Execute SQL using RDS Data API."""
    try:
        kwargs = {
            'resourceArn': CLUSTER_ARN,
            'secretArn': SECRET_ARN,
            'database': DATABASE_NAME,
            'sql': sql
        }

        if params:
            kwargs['parameters'] = params

        response = rds_data.execute_statement(**kwargs)
        return response

    except Exception as e:
        print(f"SQL execution error: {str(e)}")
        raise


def format_rds_response(response: Dict) -> List[Dict]:
    """Convert RDS Data API response to list of dicts."""
    if 'records' not in response:
        return []

    records = response['records']
    column_metadata = response.get('columnMetadata', [])

    # Get column names
    columns = [col.get('label', col.get('name', f'col_{i}'))
               for i, col in enumerate(column_metadata)]

    # Convert to list of dicts
    results = []
    for record in records:
        row = {}
        for i, field in enumerate(record):
            col_name = columns[i] if i < len(columns) else f'col_{i}'

            # Extract value from RDS Data API format
            if 'stringValue' in field:
                row[col_name] = field['stringValue']
            elif 'longValue' in field:
                row[col_name] = field['longValue']
            elif 'doubleValue' in field:
                row[col_name] = field['doubleValue']
            elif 'booleanValue' in field:
                row[col_name] = field['booleanValue']
            elif 'isNull' in field:
                row[col_name] = None
            else:
                row[col_name] = str(field)

        results.append(row)

    return results


def search_ordinances(params: Dict) -> Dict[str, Any]:
    """
    Search ordinances using pgvector similarity search.

    Searches the ordinance_embeddings table in Aurora PostgreSQL.
    Uses cosine similarity with HNSW index for <100ms search.

    Parameters:
    - query: str (required) - Search query
    - jurisdiction: str (optional) - Filter by city (e.g., "Gainesville")
    - max_results: int (default: 5) - Maximum results to return

    Returns:
        {
            "success": True,
            "results": [
                {
                    "content": str,           # Ordinance text chunk
                    "city": str,              # City name
                    "ordinance_file": str,    # Source PDF filename
                    "chunk_number": int,      # Position in document
                    "similarity_score": float # 0-1 (higher = more relevant)
                }
            ],
            "count": int,
            "method": "pgvector_cosine_similarity"
        }
    """
    query = params.get('query')
    jurisdiction = params.get('jurisdiction')  # User-facing param name
    max_results = params.get('max_results', 5)

    if not query:
        return {'success': False, 'error': 'query parameter is required'}

    # Validate environment variables
    if not CLUSTER_ARN or not SECRET_ARN:
        return {
            'success': False,
            'error': 'Database connection not configured',
            'note': 'CLUSTER_ARN and SECRET_ARN environment variables required'
        }

    try:
        print(f"Searching ordinances (pgvector): query='{query}', jurisdiction={jurisdiction}, max_results={max_results}")

        # Step 1: Generate embedding for query
        query_embedding = generate_embedding(query)

        # Step 2: Build pgvector similarity search SQL
        # Convert embedding list to PostgreSQL array format for vector type
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

        if jurisdiction:
            # Filter by city (case-insensitive)
            sql = f"""
                SELECT
                    chunk_text as content,
                    city,
                    ordinance_file,
                    chunk_number,
                    1 - (embedding <=> '{embedding_str}'::vector) as similarity_score
                FROM ordinance_embeddings
                WHERE LOWER(city) LIKE LOWER(:city)
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT :max_results
            """
            sql_params = [
                {'name': 'city', 'value': {'stringValue': f'%{jurisdiction}%'}},
                {'name': 'max_results', 'value': {'longValue': max_results}}
            ]
        else:
            # Search all cities
            sql = f"""
                SELECT
                    chunk_text as content,
                    city,
                    ordinance_file,
                    chunk_number,
                    1 - (embedding <=> '{embedding_str}'::vector) as similarity_score
                FROM ordinance_embeddings
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT :max_results
            """
            sql_params = [
                {'name': 'max_results', 'value': {'longValue': max_results}}
            ]

        # Step 3: Execute query
        print(f"Executing pgvector search...")
        response = execute_sql(sql, sql_params)
        results = format_rds_response(response)

        print(f"Ordinance search complete: {len(results)} results found")

        # Step 4: Format results for readability
        formatted_results = []
        for r in results:
            formatted_results.append({
                'content': r.get('content', ''),
                'city': r.get('city', ''),
                'ordinance_file': r.get('ordinance_file', ''),
                'chunk_number': r.get('chunk_number', 0),
                'similarity_score': round(r.get('similarity_score', 0.0), 3)
            })

        return {
            'success': True,
            'query': query,
            'jurisdiction': jurisdiction,
            'count': len(formatted_results),
            'results': formatted_results,
            'method': 'pgvector_cosine_similarity',
            'index': 'HNSW'
        }

    except Exception as e:
        print(f"Ordinance search error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
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
            "max_results": 5
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

        print(f"RAG tool executed: success={result.get('success')}")

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
            'body': json.dumps({
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            })
        }
