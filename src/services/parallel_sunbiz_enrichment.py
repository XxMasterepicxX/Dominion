"""
Parallel Sunbiz Enrichment - 10x faster than sequential

Instead of:
  for contractor in contractors:
      enrich(contractor)  # 5 seconds each = SLOW

We do:
  asyncio.gather(*[enrich(c) for c in contractors])  # All at once = FAST
"""
import asyncio
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger(__name__)


class ParallelSunbizEnricher:
    """Parallel web scraping for Sunbiz entities"""

    def __init__(self, sunbiz_service, max_concurrent=15):
        """
        Args:
            sunbiz_service: SunbizEnrichmentService instance
            max_concurrent: Max parallel requests (default 15)
        """
        self.sunbiz_service = sunbiz_service
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def enrich_one(self, name: str, context: Optional[Dict] = None) -> tuple:
        """
        Enrich one entity with rate limiting

        Returns:
            (name, result_dict or None)
        """
        async with self.semaphore:  # Limit concurrent requests
            try:
                result = await self.sunbiz_service.search_and_match(name, context)
                return (name, result)
            except Exception as e:
                logger.error(f"Enrichment failed for {name}: {e}")
                return (name, None)

    async def enrich_batch(
        self,
        names: List[str],
        contexts: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, Optional[Dict]]:
        """
        Enrich multiple entities in parallel

        Args:
            names: List of entity names to enrich
            contexts: Optional dict of {name: context} for better matching

        Returns:
            Dict of {name: enrichment_data or None}
        """
        if not names:
            return {}

        logger.info(f"Starting parallel enrichment for {len(names)} entities")

        # Create tasks for all names
        tasks = []
        for name in names:
            context = contexts.get(name) if contexts else None
            tasks.append(self.enrich_one(name, context))

        # Run all in parallel (with semaphore limiting concurrency)
        results = await asyncio.gather(*tasks)

        # Convert to dict
        enrichment_map = {name: data for name, data in results}

        success_count = sum(1 for data in enrichment_map.values() if data)
        logger.info(f"Parallel enrichment complete: {success_count}/{len(names)} succeeded")

        return enrichment_map
