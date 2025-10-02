"""
DataIngestionService - Universal pipeline for all scrapers

Handles:
1. Raw data storage (immutable RawFact)
2. Content deduplication (hash-based)
3. Parsing to domain models (Property, Entity, Permit, etc.)
4. Entity resolution (linking related entities)

Design:
- Parser registry pattern - each fact_type has a parser
- Atomic transactions - all or nothing
- Idempotent - same data ingested twice = no duplicates
"""
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .entity_resolution import EntityResolver
from .sunbiz_enrichment import SunbizEnrichmentService

from ..database import (
    RawFact,
    Property,
    Entity,
    Permit,
    CrimeReport,
    LLCFormation,
    NewsArticle,
    CouncilMeeting,
)

logger = logging.getLogger(__name__)


class DataIngestionService:
    """Universal data ingestion pipeline for all scrapers"""

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: Optional LLM client for entity resolution
        """
        self.parsers: Dict[str, Callable] = {}
        self.entity_resolver = EntityResolver(llm_client=llm_client)
        self.sunbiz_enrichment = SunbizEnrichmentService(headless=True)
        self._register_default_parsers()

    def _register_default_parsers(self):
        """Register parsers for each fact type"""
        self.parsers['crime_report'] = self._parse_crime_report
        self.parsers['city_permit'] = self._parse_city_permit
        self.parsers['county_permit'] = self._parse_county_permit
        self.parsers['llc_formation'] = self._parse_llc_formation
        self.parsers['news_article'] = self._parse_news_article
        self.parsers['council_meeting'] = self._parse_council_meeting
        self.parsers['property_record'] = self._parse_property_record

    def register_parser(self, fact_type: str, parser_func: Callable):
        """Register a custom parser for a fact type"""
        self.parsers[fact_type] = parser_func
        logger.info(f"Registered parser for fact_type: {fact_type}")

    async def ingest(
        self,
        fact_type: str,
        source_url: str,
        raw_content: Dict[str, Any],
        parser_version: str,
        db_session: AsyncSession,
        scraped_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Ingest raw data from any scraper

        Args:
            fact_type: Type of data (crime_report, city_permit, etc.)
            source_url: Source URL of the data
            raw_content: Raw JSON data from scraper
            parser_version: Version of parser used
            db_session: Database session
            scraped_at: When data was scraped (defaults to now)

        Returns:
            Dict with ingestion results (raw_fact_id, domain_objects, is_duplicate)
        """
        scraped_at = scraped_at or datetime.utcnow()

        # 1. Generate content hash for deduplication
        content_hash = self._generate_hash(raw_content)

        # 2. Check if already ingested
        existing = await self._check_duplicate(db_session, content_hash)
        if existing:
            logger.info(f"Duplicate content detected: {content_hash[:16]}... (fact_id: {existing.id})")
            return {
                'is_duplicate': True,
                'raw_fact_id': existing.id,
                'domain_objects': [],
                'message': 'Content already ingested'
            }

        # 3. Create immutable RawFact
        raw_fact = RawFact(
            id=uuid4(),
            fact_type=fact_type,
            source_url=source_url,
            parser_version=parser_version,
            raw_content=raw_content,
            content_hash=content_hash,
            scraped_at=scraped_at,
            created_at=datetime.utcnow()
        )

        db_session.add(raw_fact)
        await db_session.flush()  # Get raw_fact.id

        logger.info(f"Created RawFact: {raw_fact.id} (type: {fact_type})")

        # 4. Parse into domain models
        domain_objects = []
        if fact_type in self.parsers:
            parser = self.parsers[fact_type]
            try:
                parsed = await parser(raw_fact, raw_content, db_session)
                if parsed:
                    domain_objects.extend(parsed if isinstance(parsed, list) else [parsed])
                    logger.info(f"Parsed {len(domain_objects)} domain objects from RawFact {raw_fact.id}")
            except Exception as e:
                logger.error(f"Parser failed for {fact_type}: {e}", exc_info=True)
                # Don't fail ingestion - raw data is saved
        else:
            logger.warning(f"No parser registered for fact_type: {fact_type}")

        # 5. Mark as processed
        raw_fact.processed_at = datetime.utcnow()

        # Note: Caller is responsible for commit/rollback (transaction boundary)

        return {
            'is_duplicate': False,
            'raw_fact_id': raw_fact.id,
            'domain_objects': domain_objects,
            'message': f'Ingested {len(domain_objects)} domain objects'
        }

    async def ingest_batch(
        self,
        fact_type: str,
        source_url: str,
        raw_contents: List[Dict[str, Any]],
        parser_version: str,
        db_session: AsyncSession,
        scraped_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Ingest multiple records in batch"""
        results = {
            'total': len(raw_contents),
            'ingested': 0,
            'duplicates': 0,
            'errors': 0,
            'raw_fact_ids': []
        }

        for raw_content in raw_contents:
            try:
                result = await self.ingest(
                    fact_type=fact_type,
                    source_url=source_url,
                    raw_content=raw_content,
                    parser_version=parser_version,
                    db_session=db_session,
                    scraped_at=scraped_at
                )

                if result['is_duplicate']:
                    results['duplicates'] += 1
                else:
                    results['ingested'] += 1
                    results['raw_fact_ids'].append(str(result['raw_fact_id']))

            except Exception as e:
                results['errors'] += 1
                logger.error(f"Batch ingestion error: {e}", exc_info=True)

        logger.info(f"Batch complete: {results['ingested']} ingested, {results['duplicates']} duplicates, {results['errors']} errors")
        return results

    def _generate_hash(self, content: Dict[str, Any]) -> str:
        """Generate SHA256 hash of content for deduplication"""
        import json
        # Sort keys for consistent hashing
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    async def _check_duplicate(self, db_session: AsyncSession, content_hash: str) -> Optional[RawFact]:
        """Check if content already exists"""
        result = await db_session.execute(
            select(RawFact).where(RawFact.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    # ==================== ENRICHMENT ====================

    def _is_company_name(self, name: str) -> bool:
        """Check if name is a company (has LLC, INC, CORP, etc)"""
        company_indicators = ['LLC', 'L.L.C', 'INC', 'CORP', 'CORPORATION', 'CO.', 'LTD', 'LP', 'PA']
        name_upper = name.upper()
        return any(ind in name_upper for ind in company_indicators)

    async def _enrich_llc(self, raw_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich LLC data from Sunbiz website (conditional - only if incomplete)

        Args:
            raw_content: Raw SFTP data (may have missing fields)

        Returns:
            Enriched data with full registered agent, officers, etc.
        """
        # Check if enrichment is needed
        is_complete = all([
            raw_content.get('registered_agent'),
            raw_content.get('officers'),
            raw_content.get('status')
        ])

        if is_complete:
            logger.info("LLC data already complete, skipping enrichment (fast path)")
            return raw_content

        # Get document number
        doc_num = raw_content.get('document_number') or raw_content.get('DocumentNumber')

        if not doc_num:
            logger.warning("Cannot enrich LLC: missing document_number")
            return raw_content

        # Enrich from website
        logger.info(f"Enriching LLC from Sunbiz website: {doc_num}")
        try:
            enriched = await self.sunbiz_enrichment.scraper.scrape_entity(doc_num)

            if not enriched:
                logger.warning(f"Sunbiz enrichment failed for {doc_num} - using SFTP data")
                return raw_content

            # Merge: website data takes precedence over SFTP
            merged = {
                **raw_content,  # SFTP data as base
                'name': enriched.get('entityName') or raw_content.get('name'),
                'registered_agent': enriched.get('registeredAgent', {}).get('name'),
                'registered_agent_address': enriched.get('registeredAgent', {}).get('address'),
                'officers': enriched.get('officers'),
                'status': (enriched.get('status') or 'active').lower(),
                'principal_address': enriched.get('principalAddress'),
                'mailing_address': enriched.get('mailingAddress'),
                'fei_ein': enriched.get('feiEin'),
                '_enriched': True  # Flag to track enrichment
            }

            logger.info(f"Successfully enriched LLC {doc_num}")
            return merged

        except Exception as e:
            logger.error(f"Error enriching LLC {doc_num}: {e}", exc_info=True)
            return raw_content

    # ==================== PARSERS ====================
    # Each parser extracts domain objects from raw data

    async def _parse_crime_report(
        self,
        raw_fact: RawFact,
        content: Dict[str, Any],
        db_session: AsyncSession
    ) -> List[CrimeReport]:
        """Parse crime report data"""
        from sqlalchemy import func

        crime = CrimeReport(
            id=uuid4(),
            raw_fact_id=raw_fact.id,
            incident_number=content.get('id', str(uuid4())),
            offense_type=content.get('narrative', ''),
            offense_date=self._parse_datetime(content.get('offense_date')) or datetime.utcnow(),
            address=content.get('address')
        )

        # Parse location if available
        lat = self._parse_float(content.get('latitude'))
        lon = self._parse_float(content.get('longitude'))
        if lat and lon:
            crime.location_geometry = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)

        # Try to link to property by address (basic implementation)
        address = content.get('address')
        if address:
            property = await self._find_or_create_property(address, db_session)
            if property:
                crime.property_id = property.id

        db_session.add(crime)
        return [crime]

    async def _parse_city_permit(
        self,
        raw_fact: RawFact,
        content: Dict[str, Any],
        db_session: AsyncSession
    ) -> List[Permit]:
        """Parse city permit data"""
        permit = Permit(
            id=uuid4(),
            raw_fact_id=raw_fact.id,
            permit_number=content.get('permit_number', content.get('Permit Number', '')),
            jurisdiction='Gainesville',  # City of Gainesville
            permit_type=content.get('permit_type', content.get('Permit Type', '')),
            status=content.get('status', content.get('Status', '')),
            application_date=self._parse_datetime(content.get('application_date')),
            issue_date=self._parse_datetime(content.get('issue_date')),
            valuation=self._parse_float(content.get('valuation', content.get('Valuation', 0))),
            description=content.get('description', '')
        )

        # Link to property
        address = content.get('address', content.get('Address'))
        if address:
            property = await self._find_or_create_property(address, db_session)
            if property:
                permit.property_id = property.id

        # Link to entities (applicant, contractor) with context
        source_context = {'source_type': 'city_permit', 'source_url': raw_fact.source_url}

        applicant_name = content.get('applicant', content.get('Applicant'))
        if applicant_name:
            applicant = await self._find_or_create_entity(
                name=applicant_name,
                entity_type='company',
                db_session=db_session,
                source_context=source_context,
                additional_data={
                    'address': content.get('applicant_address', content.get('ApplicantAddress', address)),
                    'phone': content.get('applicant_phone', content.get('ApplicantPhone', content.get('phone'))),
                    'email': content.get('applicant_email', content.get('ApplicantEmail', content.get('email')))
                }
            )
            if applicant:
                permit.applicant_entity_id = applicant.id

        contractor_name = content.get('contractor', content.get('Contractor'))
        if contractor_name:
            contractor = await self._find_or_create_entity(
                name=contractor_name,
                entity_type='company',
                db_session=db_session,
                source_context=source_context,
                additional_data={
                    'address': content.get('contractor_address', content.get('ContractorAddress')),
                    'phone': content.get('contractor_phone', content.get('ContractorPhone'))
                }
            )
            if contractor:
                permit.contractor_entity_id = contractor.id

        db_session.add(permit)
        return [permit]

    async def _parse_county_permit(
        self,
        raw_fact: RawFact,
        content: Dict[str, Any],
        db_session: AsyncSession
    ) -> List[Permit]:
        """Parse county permit data"""
        permit = Permit(
            id=uuid4(),
            raw_fact_id=raw_fact.id,
            permit_number=content.get('permit_number', content.get('Permit Number', '')),
            jurisdiction='Alachua County',  # County jurisdiction
            permit_type=content.get('permit_type', content.get('Permit Type', '')),
            subtype=content.get('sub_type'),
            status=content.get('status', content.get('Status', '')),
            application_date=self._parse_datetime(content.get('application_date')),
            issue_date=self._parse_datetime(content.get('issue_date')),
            valuation=self._parse_float(content.get('valuation', content.get('construction_cost', 0))),
            description=content.get('description', content.get('scope_of_work', ''))
        )

        # Link to property
        address = content.get('address', content.get('Address'))
        if address:
            property = await self._find_or_create_property(address, db_session)
            if property:
                permit.property_id = property.id

        # Link to entities (applicant, contractor) with context
        source_context = {'source_type': 'county_permit', 'source_url': raw_fact.source_url}

        applicant_name = content.get('applicant', content.get('Applicant'))
        if applicant_name:
            applicant = await self._find_or_create_entity(
                name=applicant_name,
                entity_type='company',
                db_session=db_session,
                source_context=source_context,
                additional_data={
                    'address': content.get('applicant_address'),
                    'phone': content.get('applicant_phone')
                }
            )
            if applicant:
                permit.applicant_entity_id = applicant.id

        contractor_name = content.get('contractor', content.get('Contractor'))
        if contractor_name:
            contractor = await self._find_or_create_entity(
                name=contractor_name,
                entity_type='company',
                db_session=db_session,
                source_context=source_context,
                additional_data={
                    'address': content.get('contractor_address'),
                    'phone': content.get('contractor_phone')
                }
            )
            if contractor:
                permit.contractor_entity_id = contractor.id

        db_session.add(permit)
        return [permit]

    async def _parse_llc_formation(
        self,
        raw_fact: RawFact,
        content: Dict[str, Any],
        db_session: AsyncSession
    ) -> List[LLCFormation]:
        """
        Parse LLC formation from Sunbiz

        ENRICHMENT: Automatically enriches incomplete data from Sunbiz website
        """
        # STEP 1: Enrich if data is incomplete (conditional, smart)
        if not content.get('_enriched'):
            content = await self._enrich_llc(content)

        # STEP 2: Create entity with ENRICHED canonical name
        entity = Entity(
            id=uuid4(),
            entity_type='llc',
            canonical_name=content.get('name', content.get('EntityName', '')),
            fact_based_attributes=content
        )
        db_session.add(entity)
        await db_session.flush()

        # STEP 3: Parse filing date
        filing_date = self._parse_datetime(content.get('filing_date', content.get('FilingDate')))
        if not filing_date:
            filing_date = datetime.utcnow()

        # STEP 4: Prepare registered agent (combine name + address if available)
        registered_agent = content.get('registered_agent', content.get('RegisteredAgent'))
        if registered_agent and content.get('registered_agent_address'):
            registered_agent = f"{registered_agent}\n{content.get('registered_agent_address')}"

        # STEP 5: Parse officers (already JSON/list from enrichment)
        import json
        officers = content.get('officers')
        if officers and isinstance(officers, list):
            officers = json.dumps(officers)  # Convert to JSON string for storage

        # STEP 6: Create LLC formation record with ENRICHED data
        llc = LLCFormation(
            id=uuid4(),
            raw_fact_id=raw_fact.id,
            entity_id=entity.id,
            document_number=content.get('document_number', content.get('DocumentNumber', '')),
            filing_date=filing_date,
            registered_agent=registered_agent,
            principal_address=content.get('principal_address', content.get('PrincipalAddress')),
            is_property_related=content.get('is_real_estate', False),
            status=content.get('status', 'active'),
            officers=officers  # Now populated from enrichment!
        )

        db_session.add(llc)
        logger.info(f"Created LLC formation: {entity.canonical_name} (enriched: {content.get('_enriched', False)})")
        return [llc]

    async def _parse_news_article(
        self,
        raw_fact: RawFact,
        content: Dict[str, Any],
        db_session: AsyncSession
    ) -> List[NewsArticle]:
        """Parse news article"""
        # Parse datetime
        pub_date = self._parse_datetime(content.get('publication_date', content.get('pubDate', content.get('published'))))
        if not pub_date:
            pub_date = datetime.utcnow()  # Fallback to now if no date

        article = NewsArticle(
            id=uuid4(),
            raw_fact_id=raw_fact.id,
            title=content.get('title', 'Untitled'),
            published_date=pub_date,
            source_publication=content.get('source', content.get('feed', 'Unknown')),
            author=content.get('author'),
            content=content.get('article_text', content.get('description', content.get('summary', ''))),
            summary=content.get('summary'),
            url=content.get('link', content.get('url', ''))
        )

        db_session.add(article)
        return [article]

    async def _parse_council_meeting(
        self,
        raw_fact: RawFact,
        content: Dict[str, Any],
        db_session: AsyncSession
    ) -> List[CouncilMeeting]:
        """Parse council meeting data"""
        meeting_date = self._parse_datetime(content.get('meeting_date', content.get('EventDate', content.get('start_time'))))
        if not meeting_date:
            meeting_date = datetime.utcnow()

        meeting = CouncilMeeting(
            id=uuid4(),
            raw_fact_id=raw_fact.id,
            meeting_date=meeting_date,
            meeting_type=content.get('meeting_type', content.get('EventBodyName', content.get('board_name', ''))),
            agenda_url=content.get('agenda_url'),
            minutes_url=content.get('minutes_url'),
            video_url=content.get('video_url'),
            agenda_items=content.get('agenda_items'),
            extracted_text=content.get('extracted_text')
        )

        db_session.add(meeting)
        return [meeting]

    async def _parse_property_record(
        self,
        raw_fact: RawFact,
        content: Dict[str, Any],
        db_session: AsyncSession
    ) -> List[Property]:
        """Parse property record from Property Appraiser"""
        property = Property(
            id=uuid4(),
            raw_fact_id=raw_fact.id,
            address=content.get('address', content.get('PropertyAddress', '')),
            parcel_id=content.get('parcel_id', content.get('ParcelID', '')),
            factual_data=content  # Store all data
        )

        # Parse coordinates if available
        from sqlalchemy import func
        lat = self._parse_float(content.get('latitude'))
        lon = self._parse_float(content.get('longitude'))
        if lat and lon:
            property.coordinates = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)

        db_session.add(property)
        return [property]

    # ==================== HELPER METHODS ====================

    async def _find_or_create_property(
        self,
        address: str,
        db_session: AsyncSession
    ) -> Optional[Property]:
        """Find existing property by address or create new one"""
        # Basic implementation - normalize address first
        normalized = address.strip().upper()

        result = await db_session.execute(
            select(Property).where(Property.address == normalized)
        )
        property = result.scalar_one_or_none()

        if not property:
            property = Property(
                id=uuid4(),
                address=normalized,
                factual_data={}
            )
            db_session.add(property)
            await db_session.flush()

        return property

    async def _find_or_create_entity(
        self,
        name: str,
        entity_type: str,
        db_session: AsyncSession,
        source_context: Optional[Dict[str, Any]] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Entity]:
        """
        Find existing entity or create new one using EntityResolver

        ENRICHMENT: If it's a company name (LLC/INC/CORP), tries to find in Sunbiz first

        Args:
            name: Entity name
            entity_type: Entity type (company, llc, etc.)
            db_session: Database session
            source_context: Context about where this data came from
            additional_data: Additional fields (address, phone, owner, etc.)

        Returns:
            Entity object or None
        """
        if not name or name.strip() == '':
            return None

        # ENRICHMENT STEP: If it's a company, check Sunbiz first
        if entity_type == 'company' and self._is_company_name(name):
            logger.info(f"Company name detected: {name} - checking Sunbiz")
            try:
                # Search Sunbiz with context (address helps disambiguate)
                context = {}
                if additional_data:
                    if additional_data.get('address'):
                        context['address'] = additional_data['address']
                    if additional_data.get('city'):
                        context['city'] = additional_data['city']

                sunbiz_data = await self.sunbiz_enrichment.search_and_match(name, context or None)

                if sunbiz_data:
                    # Found in Sunbiz! Create LLC with full data
                    logger.info(f"Found {name} in Sunbiz: {sunbiz_data.get('documentNumber')}")
                    return await self._create_llc_from_sunbiz(sunbiz_data, db_session)

            except Exception as e:
                logger.error(f"Sunbiz enrichment failed for {name}: {e}", exc_info=True)
                # Continue with normal resolution

        # Build scraped data for resolver
        scraped_data = {
            'name': name,
            'entity_type': entity_type,
            **(additional_data or {})
        }

        # Default source context
        if not source_context:
            source_context = {'source_type': 'unknown'}

        # Use EntityResolver
        try:
            result = await self.entity_resolver.resolve_entity(
                scraped_data=scraped_data,
                source_context=source_context,
                db_session=db_session
            )

            if result.entity:
                return result.entity
            elif result.needs_review:
                # Queued for review - return None for now
                logger.info(f"Entity '{name}' queued for human review")
                return None
            else:
                return None

        except Exception as e:
            logger.error(f"Entity resolution failed for '{name}': {e}")
            # Fallback to basic creation
            entity = Entity(
                id=uuid4(),
                entity_type=entity_type,
                canonical_name=name.strip().upper(),
                fact_based_attributes=scraped_data
            )
            db_session.add(entity)
            await db_session.flush()
            return entity

    async def _create_llc_from_sunbiz(
        self,
        sunbiz_data: Dict[str, Any],
        db_session: AsyncSession
    ) -> Entity:
        """
        Create Entity + LLCFormation from enriched Sunbiz data

        Args:
            sunbiz_data: Complete data from Sunbiz website scraper
            db_session: Database session

        Returns:
            Entity object
        """
        import json

        # Create entity
        entity = Entity(
            id=uuid4(),
            entity_type='llc',
            canonical_name=sunbiz_data.get('entityName', ''),
            fact_based_attributes=sunbiz_data
        )
        db_session.add(entity)
        await db_session.flush()

        # Parse filing date
        filing_date = self._parse_datetime(sunbiz_data.get('dateFiled'))
        if not filing_date:
            filing_date = datetime.utcnow()

        # Prepare registered agent (name + address)
        reg_agent = sunbiz_data.get('registeredAgent', {})
        registered_agent = reg_agent.get('name')
        if registered_agent and reg_agent.get('address'):
            registered_agent = f"{registered_agent}\n{reg_agent.get('address')}"

        # Parse officers
        officers = sunbiz_data.get('officers')
        if officers and isinstance(officers, list):
            officers = json.dumps(officers)

        # Create LLC formation
        llc = LLCFormation(
            id=uuid4(),
            raw_fact_id=None,  # Created from enrichment, not from raw fact
            entity_id=entity.id,
            document_number=sunbiz_data.get('documentNumber'),
            filing_date=filing_date,
            registered_agent=registered_agent,
            principal_address=sunbiz_data.get('principalAddress'),
            is_property_related=False,  # Unknown from enrichment
            status=(sunbiz_data.get('status') or 'active').lower(),
            officers=officers
        )

        db_session.add(llc)
        logger.info(f"Created LLC from Sunbiz enrichment: {entity.canonical_name}")

        return entity

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from various formats, returning naive UTC datetime"""
        if not value:
            return None

        if isinstance(value, datetime):
            # Convert timezone-aware to naive UTC
            if value.tzinfo is not None:
                return value.replace(tzinfo=None)
            return value

        if isinstance(value, str):
            from dateutil import parser
            try:
                dt = parser.parse(value)
                # Convert timezone-aware to naive UTC
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                return dt
            except:
                return None

        return None

    def _parse_float(self, value: Any) -> Optional[float]:
        """Parse float from string or number"""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            # Remove currency symbols, commas
            clean = value.replace('$', '').replace(',', '').strip()
            try:
                return float(clean)
            except:
                return None

        return None
