"""
Sunbiz Enrichment Service

Enriches entity data by searching Florida Sunbiz website.
Handles company names, person names, and document numbers.
Integrates with entity resolution and database.
"""
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import structlog
from difflib import SequenceMatcher

from ..scrapers.data_sources.sunbiz_website import SunbizWebsiteScraper
from ..database.connection import db_manager

logger = structlog.get_logger(__name__)


class SunbizEnrichmentService:
    """
    Enrich entities with Sunbiz data.

    Handles:
    - Company names (LLC, INC, CORP) → Search by entity name
    - Person names → Search by officer/registered agent
    - Document numbers → Direct lookup
    - Fuzzy matching when multiple results
    """

    def __init__(self, headless: bool = True):
        self.scraper = SunbizWebsiteScraper(headless=headless)

    def is_company_name(self, name: str) -> bool:
        """Check if name is a company (has LLC, INC, CORP, etc)"""
        company_indicators = ['LLC', 'L.L.C', 'INC', 'CORP', 'CORPORATION', 'CO.', 'LTD', 'LP', 'PA']
        name_upper = name.upper()
        return any(ind in name_upper for ind in company_indicators)

    def fuzzy_match_score(self, name1: str, name2: str) -> float:
        """Calculate fuzzy match score between two names (0-1)"""
        return SequenceMatcher(None, name1.upper(), name2.upper()).ratio()

    async def search_and_match(
        self,
        name: str,
        additional_context: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Search Sunbiz and find best match.

        Args:
            name: Company or person name
            additional_context: Optional dict with address, city, etc for better matching

        Returns:
            Best match entity data or None
        """
        logger.info("Searching Sunbiz for entity", name=name)

        # Determine search strategy
        is_company = self.is_company_name(name)

        if is_company:
            # Search by entity name
            results = await self.scraper.search_by_name(name, max_results=10)
            search_type = "entity"
        else:
            # Search by officer/registered agent
            results = await self.scraper.search_by_officer_or_agent(name, max_results=10)
            search_type = "person"

        if not results:
            logger.info("No Sunbiz results found", name=name)
            return None

        # Find best match
        best_match = await self._find_best_match(name, results, additional_context)

        if not best_match:
            logger.warning("No good match found", name=name, result_count=len(results))
            return None

        # Get full details
        doc_number = best_match['documentNumber']
        full_data = await self.scraper.scrape_entity(doc_number)

        if full_data:
            logger.info(
                "Successfully matched and enriched",
                name=name,
                doc_number=doc_number,
                matched_name=full_data.get('entityName'),
                has_reg_agent=bool(full_data.get('registeredAgent', {}).get('name'))
            )

        return full_data

    async def _find_best_match(
        self,
        query_name: str,
        results: List[Dict],
        additional_context: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Find best match from search results using fuzzy matching.
        Fetches full details for top matches when context is provided.

        Args:
            query_name: Name we're searching for
            results: List of search results
            additional_context: Optional address, city, etc

        Returns:
            Best match or None
        """
        if not results:
            return None

        # Score each result
        scored_results = []

        for result in results:
            score = self.fuzzy_match_score(query_name, result['name'])

            # Boost score for active companies
            if result.get('status', '').upper() == 'ACTIVE':
                score += 0.1

            scored_results.append((score, result))

        # Sort by score
        scored_results.sort(reverse=True, key=lambda x: x[0])

        # If we have context and multiple good matches, fetch full details to compare
        if additional_context and len(scored_results) > 1:
            top_candidates = [r for score, r in scored_results[:3] if score >= 0.7]

            if len(top_candidates) > 1:
                logger.info(
                    "Multiple good matches, fetching full details for context matching",
                    count=len(top_candidates)
                )

                # Fetch full details for top candidates
                for candidate in top_candidates:
                    full_data = await self.scraper.scrape_entity(candidate['documentNumber'])
                    if full_data:
                        candidate['_full_data'] = full_data

                # Re-score with address context
                return await self._match_with_context(query_name, top_candidates, additional_context)

        # Return best match if score is good enough
        best_score, best_match = scored_results[0]

        if best_score >= 0.8:  # 80% match threshold
            logger.info(
                "Found good match",
                query=query_name,
                match=best_match['name'],
                score=best_score
            )
            return best_match
        else:
            logger.warning(
                "Best match score too low",
                query=query_name,
                match=best_match['name'],
                score=best_score
            )
            return None

    async def _match_with_context(
        self,
        query_name: str,
        candidates: List[Dict],
        context: Dict
    ) -> Optional[Dict]:
        """
        Use additional context (address, city) to pick best match from candidates.

        Args:
            query_name: Original search name
            candidates: List of candidate results with _full_data
            context: Dict with address, city, etc

        Returns:
            Best match based on context
        """
        context_address = context.get('address', '').upper()
        context_city = context.get('city', '').upper()

        best_match = None
        best_context_score = 0

        for candidate in candidates:
            full_data = candidate.get('_full_data')
            if not full_data:
                continue

            context_score = 0

            # Check principal address
            principal_addr = (full_data.get('principalAddress') or '').upper()

            if context_address and context_address in principal_addr:
                context_score += 1.0
                logger.info(
                    "Address match",
                    candidate=candidate['name'],
                    context_addr=context_address
                )

            if context_city and context_city in principal_addr:
                context_score += 0.5
                logger.info(
                    "City match",
                    candidate=candidate['name'],
                    context_city=context_city
                )

            if context_score > best_context_score:
                best_context_score = context_score
                best_match = candidate

        if best_match:
            logger.info(
                "Selected match using context",
                match=best_match['name'],
                context_score=best_context_score
            )
            return best_match

        # Fall back to first candidate if no context match
        logger.warning("No context match, using first candidate")
        return candidates[0] if candidates else None

    async def enrich_entity_by_name(
        self,
        entity_name: str,
        entity_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Enrich entity with Sunbiz data and optionally update database.

        Args:
            entity_name: Entity name to search
            entity_id: Optional UUID of entity in database to update

        Returns:
            Enriched data dict or None
        """
        # Search and match
        sunbiz_data = await self.search_and_match(entity_name)

        if not sunbiz_data:
            return None

        # Update database if entity_id provided
        if entity_id:
            await self._update_entity_in_db(entity_id, sunbiz_data)

        return sunbiz_data

    async def _update_entity_in_db(self, entity_id: str, sunbiz_data: Dict):
        """Update entity in database with Sunbiz data"""
        async with db_manager.get_session() as session:
            try:
                # Update entities table with registered agent
                reg_agent = sunbiz_data.get('registeredAgent', {})

                await session.execute("""
                    UPDATE entities
                    SET
                        sunbiz_document_number = $1,
                        sunbiz_registered_agent = $2,
                        sunbiz_registered_agent_address = $3,
                        sunbiz_fei_ein = $4,
                        sunbiz_status = $5,
                        sunbiz_filing_date = $6,
                        sunbiz_data = $7,
                        updated_at = NOW()
                    WHERE id = $8
                """,
                    sunbiz_data.get('documentNumber'),
                    reg_agent.get('name'),
                    reg_agent.get('address'),
                    sunbiz_data.get('feiEin'),
                    sunbiz_data.get('status'),
                    sunbiz_data.get('dateFiled'),
                    sunbiz_data,  # Store full JSON
                    entity_id
                )

                await session.commit()

                logger.info("Updated entity with Sunbiz data", entity_id=entity_id)

            except Exception as e:
                await session.rollback()
                logger.error("Failed to update entity", entity_id=entity_id, error=str(e))

    async def enrich_contractors_from_permits(
        self,
        limit: int = 100,
        only_missing: bool = True
    ):
        """
        Batch enrich contractors from permits that are missing Sunbiz data.

        Args:
            limit: Max number of contractors to enrich
            only_missing: Only enrich those without registered agent

        Returns:
            Stats dict
        """
        async with db_manager.get_session() as session:
            # Get contractors missing Sunbiz data
            query = """
                SELECT DISTINCT
                    e.id,
                    e.canonical_name
                FROM entities e
                WHERE e.id IN (
                    SELECT contractor_entity_id
                    FROM permits
                    WHERE contractor_entity_id IS NOT NULL
                )
            """

            if only_missing:
                query += " AND e.sunbiz_registered_agent IS NULL"

            query += f" LIMIT {limit}"

            contractors = await session.fetch(query)

        logger.info(
            "Starting batch enrichment",
            total_contractors=len(contractors),
            only_missing=only_missing
        )

        stats = {
            'total': len(contractors),
            'enriched': 0,
            'not_found': 0,
            'errors': 0
        }

        for contractor in contractors:
            try:
                result = await self.enrich_entity_by_name(
                    contractor['canonical_name'],
                    contractor['id']
                )

                if result:
                    stats['enriched'] += 1
                else:
                    stats['not_found'] += 1

            except Exception as e:
                stats['errors'] += 1
                logger.error(
                    "Error enriching contractor",
                    name=contractor['canonical_name'],
                    error=str(e)
                )

        logger.info("Batch enrichment complete", **stats)

        return stats


# Convenience function
async def enrich_contractor(name: str) -> Optional[Dict]:
    """Quick function to enrich a single contractor by name"""
    service = SunbizEnrichmentService(headless=True)
    return await service.search_and_match(name)
