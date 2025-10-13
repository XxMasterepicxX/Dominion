"""
Municipal Ordinance RAG Search Service

Semantic search over municipal ordinances using pgvector.
Supports location filtering (city-specific or county-wide).

NOTE: torch and transformers are imported lazily to avoid import errors
in environments where they're not installed (like venv_src for agent).
"""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = structlog.get_logger(__name__)


class OrdinanceRAG:
    """
    RAG system for municipal ordinance search

    Features:
    - Semantic search using BAAI/bge-large-en-v1.5
    - Location filtering (city or state level)
    - Configurable result count
    - Relevance scoring
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-en-v1.5",
        cache_dir: Optional[str] = None
    ):
        """
        Initialize RAG system

        Args:
            model_name: Embedding model to use
            cache_dir: Directory to cache model files
        """
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.tokenizer = None
        self.model = None
        self.device = None

    def _ensure_model_loaded(self):
        """Lazy load embedding model (imports torch/transformers on first use)"""
        if self.model is None:
            # Import here to avoid import errors in environments without torch
            import torch
            from transformers import AutoTokenizer, AutoModel

            logger.info("loading_embedding_model", model=self.model_name)

            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )
            self.model = AutoModel.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )
            self.model.eval()

            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.model = self.model.to(self.device)

            logger.info("embedding_model_loaded", device=self.device)

    def _embed_query(self, query: str):
        """
        Embed a query using the model

        Args:
            query: Text query

        Returns:
            Normalized embedding vector
        """
        # Import torch here (lazy import)
        import torch
        import numpy as np

        self._ensure_model_loaded()

        # Tokenize
        encoded = self.tokenizer(
            [query],
            padding=True,
            truncation=True,
            return_tensors='pt'
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        # Generate embedding
        with torch.no_grad():
            output = self.model(**encoded)
            embeddings = output.last_hidden_state[:, 0]  # CLS token

        # Normalize
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        return embeddings.cpu().numpy()[0]

    async def search(
        self,
        session: AsyncSession,
        query: str,
        city: Optional[str] = None,
        state: str = "FL",
        top_k: int = 5,
        min_relevance: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search ordinances semantically

        Args:
            session: Database session
            query: Natural language query
            city: Optional city filter (e.g., "Gainesville")
            state: State filter (default: "FL")
            top_k: Number of results to return
            min_relevance: Minimum cosine similarity score (0-1)

        Returns:
            List of matching ordinance chunks with metadata

        Example:
            results = await rag.search(
                session,
                query="What are parking requirements?",
                city="Gainesville",
                top_k=3
            )
        """

        logger.info(
            "ordinance_search",
            query=query[:100],
            city=city,
            state=state,
            top_k=top_k
        )

        # Embed query
        query_embedding = self._embed_query(query)
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

        # Build SQL with optional city filter
        sql_parts = ["""
            SELECT
                id,
                ordinance_file,
                city,
                state,
                chunk_number,
                chunk_text,
                chunk_chars,
                chunk_words,
                content_hash,
                file_modified_timestamp,
                scraped_date,
                metadata,
                1 - (embedding <=> CAST(:query_embedding AS vector)) AS relevance_score
            FROM ordinance_embeddings
            WHERE state = :state
        """]

        params = {
            'query_embedding': embedding_str,
            'state': state,
            'top_k': top_k
        }

        # Add city filter if specified
        if city:
            sql_parts.append("AND city = :city")
            params['city'] = city

        # Add relevance threshold if specified
        if min_relevance > 0:
            sql_parts.append("AND 1 - (embedding <=> CAST(:query_embedding AS vector)) >= :min_relevance")
            params['min_relevance'] = min_relevance

        # Order by relevance and limit
        sql_parts.append("""
            ORDER BY relevance_score DESC
            LIMIT :top_k
        """)

        sql = text(' '.join(sql_parts))

        # Execute query
        result = await session.execute(sql, params)
        rows = result.fetchall()

        # Format results
        results = []
        for row in rows:
            results.append({
                'id': str(row[0]),
                'ordinance_file': row[1],
                'city': row[2],
                'state': row[3],
                'chunk_number': row[4],
                'chunk_text': row[5],
                'chunk_chars': row[6],
                'chunk_words': row[7],
                'content_hash': row[8],
                'file_modified_timestamp': row[9],
                'scraped_date': row[10],
                'metadata': row[11] if row[11] else {},
                'relevance_score': float(row[12])
            })

        logger.info(
            "search_complete",
            results_count=len(results),
            top_score=results[0]['relevance_score'] if results else 0.0
        )

        return results

    async def get_available_cities(
        self,
        session: AsyncSession,
        state: str = "FL"
    ) -> List[Dict[str, Any]]:
        """
        Get list of cities with ordinances available

        Args:
            session: Database session
            state: State filter

        Returns:
            List of cities with chunk counts
        """

        sql = text("""
            SELECT city, COUNT(*) as chunk_count
            FROM ordinance_embeddings
            WHERE state = :state
            GROUP BY city
            ORDER BY chunk_count DESC
        """)

        result = await session.execute(sql, {'state': state})
        rows = result.fetchall()

        return [
            {'city': row[0], 'chunk_count': row[1]}
            for row in rows
        ]


# Global instance (lazy-loaded)
_rag_instance: Optional[OrdinanceRAG] = None


def get_ordinance_rag() -> OrdinanceRAG:
    """Get global RAG instance"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = OrdinanceRAG()
    return _rag_instance
