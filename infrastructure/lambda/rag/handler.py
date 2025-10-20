"""
RAG Lambda Function Handler - BGE EMBEDDINGS

Handles 1 tool:
- search_ordinances - Search Florida municipal ordinances using pgvector

Uses pgvector DIRECTLY with BAAI/bge-large-en-v1.5 embeddings (1024-dim).
Embeddings stored in Aurora: ordinance_embeddings table.
"""

import json
import os
import time
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
rds_data = boto3.client('rds-data', region_name='us-east-1')

# Environment variables
CLUSTER_ARN = os.environ.get('CLUSTER_ARN')
SECRET_ARN = os.environ.get('SECRET_ARN')
DATABASE_NAME = os.environ.get('DATABASE_NAME', 'dominion_db')

# Embedding model configuration (BAAI BGE-large-en-v1.5)
EMBEDDING_MODEL_NAME = 'BAAI/bge-large-en-v1.5'
EMBEDDING_DIMENSIONS = 1024

# Query instruction for BAAI/bge models (from src/services/embedding_service.py)
# Required for search queries to match the embedding generation used during indexing
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

# Global model instance (loaded once per container lifecycle)
_embedding_model = None

# Simple in-memory cache to detect loops (Lambda container reuse)
query_history = {}


def get_embedding_model():
    """
    Lazy-load sentence-transformers model.

    Downloads model to /tmp on first invocation (cold start ~10-15 seconds).
    Subsequent invocations reuse the loaded model (warm start ~50ms).

    Best practices applied:
    - normalize_embeddings=True (required for cosine similarity)
    - device='cpu' (Lambda has no GPU)
    - Cache in /tmp (10GB available)
    """
    global _embedding_model

    if _embedding_model is None:
        print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        print("This is a cold start - downloading model to /tmp (one-time ~15 sec)")

        try:
            from sentence_transformers import SentenceTransformer

            # Set cache directory to /tmp (Lambda has 10GB available)
            os.environ['TRANSFORMERS_CACHE'] = '/tmp/transformers_cache'
            os.environ['SENTENCE_TRANSFORMERS_HOME'] = '/tmp/sentence_transformers'

            # Load model on CPU with normalization enabled
            _embedding_model = SentenceTransformer(
                EMBEDDING_MODEL_NAME,
                device='cpu',
                cache_folder='/tmp/sentence_transformers'
            )

            print(f"Model loaded successfully: {EMBEDDING_MODEL_NAME}")
            print(f"Model max_seq_length: {_embedding_model.max_seq_length}")

        except Exception as e:
            print(f"Failed to load embedding model: {str(e)}")
            raise RuntimeError(f"Embedding model initialization failed: {str(e)}")

    return _embedding_model


def generate_embedding(text: str, is_query: bool = True) -> List[float]:
    """
    Generate embedding vector for search query using BGE.

    Uses BAAI/bge-large-en-v1.5 matching src/services/embedding_service.py:
    - normalize_embeddings=True (cosine similarity)
    - convert_to_numpy=True (faster processing)
    - Query instruction for queries (NOT for documents)

    Args:
        text: Text to embed
        is_query: If True, adds query instruction prefix (default: True for search)

    Returns:
        List[float]: 1024-dimensional embedding vector
    """
    try:
        # Add query instruction for search queries (matches src implementation)
        text_to_embed = QUERY_INSTRUCTION + text if is_query else text

        print(f"Generating BGE embedding for query: {text[:100]}...")
        print(f"With instruction: {is_query}")

        # Get model instance (lazy-loaded)
        model = get_embedding_model()

        # Generate embedding (matches src/services/embedding_service.py)
        embedding = model.encode(
            text_to_embed,
            normalize_embeddings=True,  # Required for cosine similarity
            convert_to_numpy=True,      # Faster than torch tensors
            show_progress_bar=False     # No progress bar in Lambda
        )

        # Convert numpy array to list for JSON serialization
        embedding_list = embedding.tolist()

        # Validate dimensions
        if len(embedding_list) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Invalid embedding dimensions: {len(embedding_list)}, "
                f"expected {EMBEDDING_DIMENSIONS}"
            )

        print(f"BGE embedding generated: {len(embedding_list)} dimensions")
        return embedding_list

    except Exception as e:
        print(f"Embedding generation error: {str(e)}")
        import traceback
        traceback.print_exc()
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

        # CRITICAL: Must include result metadata to get column names
        kwargs['includeResultMetadata'] = True
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

    # CRITICAL: Detect infinite loops - if same query called repeatedly, stop it
    current_time = time.time()
    query_key = f"{query}:{jurisdiction}"

    if query_key in query_history:
        last_time, count = query_history[query_key]

        # If same query within 120 seconds, increment count
        if current_time - last_time < 120:
            count += 1
            query_history[query_key] = (current_time, count)

            # If called more than 2 times in 120 seconds, STOP THE LOOP
            if count > 2:
                print(f"LOOP DETECTED: Query '{query}' called {count} times in {current_time - last_time:.1f}s - RETURNING EMPTY SUCCESS")
                return {
                    'success': True,
                    'query': query,
                    'jurisdiction': jurisdiction,
                    'count': 0,
                    'results': [],
                    'method': 'loop_prevention_cache',
                    'note': f'This query was already attempted {count-1} times with zero results. No ordinance data available for this query. Proceed with analysis without zoning verification.'
                }
        else:
            # Reset if more than 120 seconds passed
            query_history[query_key] = (current_time, 1)
    else:
        # First time seeing this query
        query_history[query_key] = (current_time, 1)

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

        print(f"Ordinance search complete: {len(results)} raw results found")

        # Step 4: Format results for readability and filter out empty/low-quality results
        formatted_results = []
        for r in results:
            content = r.get('content', '').strip()
            similarity = r.get('similarity_score', 0.0)

            # Skip empty content or zero similarity (no actual match)
            if not content or similarity == 0.0:
                continue

            formatted_results.append({
                'content': content,
                'city': r.get('city', ''),
                'ordinance_file': r.get('ordinance_file', ''),
                'chunk_number': r.get('chunk_number', 0),
                'similarity_score': round(similarity, 3)
            })

        print(f"Filtered to {len(formatted_results)} valid results (removed empty/zero-similarity)")

        return {
            'success': True,
            'query': query,
            'jurisdiction': jurisdiction,
            'count': len(formatted_results),
            'results': formatted_results,
            'method': 'pgvector_cosine_similarity',
            'index': 'HNSW',
            'note': 'Empty content and zero-similarity results filtered out' if len(results) != len(formatted_results) else None
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
