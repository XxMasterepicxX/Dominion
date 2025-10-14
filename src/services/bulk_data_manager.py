"""
Bulk Data Manager

Handles initial bulk downloads, MD5 change detection, and incremental updates.

Workflow:
1. Download bulk data to temp
2. Calculate MD5 hash
3. Check if changed from last snapshot
4. If changed: Process and upsert records
5. Track snapshot metadata
"""
import hashlib
import json
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.schemas import MarketConfig
from ..config.current_market import CurrentMarket
from ..database import DatabaseManager
from ..scrapers.data_sources.sunbiz import SunbizScraper
from ..scrapers.data_sources.property_appraiser_bulk import PropertyAppraiserScraper
from ..scrapers.data_sources.gis_shapefile_downloader import GISScraper

logger = structlog.get_logger(__name__)


class BulkSnapshot:
    """Represents a bulk data snapshot metadata record"""
    def __init__(self, data: Dict):
        self.id = data.get('id', uuid4())
        self.source_type = data['source_type']
        self.source_name = data['source_name']
        self.file_url = data.get('file_url')
        self.file_name = data.get('file_name')
        self.content_md5 = data['content_md5']
        self.record_count = data.get('record_count', 0)
        self.is_initial_load = data.get('is_initial_load', False)


class BulkDataManager:
    """
    Manages bulk data downloads, change detection, and incremental updates.

    Supports:
    - Sunbiz SFTP: Daily corporate formations
    - Property Appraiser (CAMA): Weekly/monthly parcel data
    - GIS: Monthly spatial data
    """

    def __init__(self, market_config: MarketConfig, db_manager: DatabaseManager):
        self.config = market_config
        self.db_manager = db_manager

        # Initialize scrapers
        self.sunbiz_scraper = None
        self.property_scraper = None
        self.gis_scraper = None

        try:
            self.sunbiz_scraper = SunbizScraper()
        except Exception as e:
            logger.warning("Sunbiz scraper not initialized", error=str(e))

        try:
            self.property_scraper = PropertyAppraiserScraper(market_config)
        except Exception as e:
            logger.warning("Property scraper not initialized", error=str(e))

        try:
            self.gis_scraper = GISScraper(market_config)
        except Exception as e:
            logger.warning("GIS scraper not initialized", error=str(e))


    # ==================== CORE WORKFLOW ====================

    async def sync_all_bulk_data(self, force_update: bool = False):
        """
        Sync all bulk data sources.

        Args:
            force_update: Force download even if MD5 unchanged
        """
        logger.info("bulk_sync_started", force=force_update)

        # Sunbiz SFTP (daily)
        if self.sunbiz_scraper:
            await self.sync_sunbiz(force_update=force_update)

        # Property Appraiser (weekly/monthly)
        if self.property_scraper:
            await self.sync_property_appraiser(force_update=force_update)

        # GIS (monthly)
        if self.gis_scraper:
            await self.sync_gis(force_update=force_update)

        logger.info("bulk_sync_completed")


    async def sync_sunbiz(self, force_update: bool = False) -> Optional[BulkSnapshot]:
        """
        Sync Sunbiz SFTP corporate data.

        Process:
        1. Use existing scraper to download + parse
        2. Calculate MD5 from records
        3. Check if changed
        4. If changed: Upsert LLC records
        """
        logger.info("sunbiz_sync_started")

        # Use existing scraper - it downloads and parses automatically
        # Try today first, fallback to yesterday if today's file not available
        today = datetime.now()
        records = self.sunbiz_scraper.scrape_corporate_data(date=today)

        if not records:
            # Try yesterday
            from datetime import timedelta
            yesterday = today - timedelta(days=1)
            logger.info("today_file_not_found_trying_yesterday", yesterday=yesterday)
            records = self.sunbiz_scraper.scrape_corporate_data(date=yesterday)
            today = yesterday  # Use yesterday's date for filename

        if not records:
            logger.error("sunbiz_scrape_failed", date=today)
            return None

        # Calculate MD5 from records (not file)
        import json
        records_json = json.dumps(records, sort_keys=True)
        md5_hash = hashlib.md5(records_json.encode()).hexdigest()

        # Check if changed
        async with self.db_manager.async_session_maker() as session:
            changed, prev_snapshot = await self._check_if_changed(
                session,
                source_type='sunbiz_sftp',
                source_name='daily_corporate',
                md5_hash=md5_hash
            )

            if not changed and not force_update:
                logger.info("sunbiz_unchanged", md5=md5_hash[:16])
                return prev_snapshot

            # Create snapshot record
            today_file = today.strftime('%Y%m%d') + 'c.txt'
            snapshot = await self._create_snapshot(
                session,
                source_type='sunbiz_sftp',
                source_name='daily_corporate',
                file_name=today_file,
                file_url=f"sftp://sftp.floridados.gov{self.sunbiz_scraper.CORPORATE_PATH}{today_file}",
                md5_hash=md5_hash,
                file_size=len(records_json),
                is_initial_load=(prev_snapshot is None)
            )

            # Process records
            logger.info("sunbiz_processing_started", snapshot_id=snapshot['id'], record_count=len(records))
            await self._mark_processing(session, snapshot['id'])
            await session.commit()

        # Upsert records (in new session to avoid long transactions)
        stats = await self._process_sunbiz_records(records, snapshot)

        # Mark completed
        async with self.db_manager.async_session_maker() as session:
            await self._mark_completed(session, snapshot['id'], stats)
            await session.commit()

        logger.info("sunbiz_sync_completed",
                   snapshot_id=snapshot['id'],
                   added=stats['added'],
                   updated=stats['updated'])

        return snapshot


    async def sync_property_appraiser(self, force_update: bool = False) -> Optional[BulkSnapshot]:
        """Sync Property Appraiser (CAMA) bulk data"""
        logger.info("property_sync_started")

        # Use existing scraper - it downloads and parses automatically
        property_records = self.property_scraper.fetch_property_data()

        if not property_records:
            logger.error("property_scrape_failed")
            return None

        # Calculate MD5 from records
        import json
        records_data = [p.to_dict() for p in property_records]
        records_json = json.dumps(records_data, sort_keys=True)
        md5_hash = hashlib.md5(records_json.encode()).hexdigest()

        # Check if changed
        async with self.db_manager.async_session_maker() as session:
            changed, prev_snapshot = await self._check_if_changed(
                session,
                source_type='property_appraiser',
                source_name=f"{self.config.market.name.lower()}_cama",
                md5_hash=md5_hash
            )

            if not changed and not force_update:
                logger.info("property_unchanged", md5=md5_hash[:16])
                return prev_snapshot

            # Create snapshot
            snapshot = await self._create_snapshot(
                session,
                source_type='property_appraiser',
                source_name=f"{self.config.market.name.lower()}_cama",
                file_name=f"cama_{datetime.now().strftime('%Y%m%d')}.csv",
                md5_hash=md5_hash,
                file_size=len(records_json),
                is_initial_load=(prev_snapshot is None)
            )

            await self._mark_processing(session, snapshot['id'])
            await session.commit()

        # Process records
        stats = await self._process_property_records(property_records, snapshot)

        # Mark completed
        async with self.db_manager.async_session_maker() as session:
            await self._mark_completed(session, snapshot['id'], stats)
            await session.commit()

        logger.info("property_sync_completed",
                   snapshot_id=snapshot['id'],
                   added=stats['added'],
                   updated=stats['updated'])

        return snapshot


    async def sync_gis(self, layer_name: str = 'parcels', force_update: bool = False) -> Optional[BulkSnapshot]:
        """Sync GIS spatial data - DISABLED for schema v2 (no GIS tables yet)"""
        logger.warning("gis_sync_disabled",
                      reason="GIS tables not in schema v2 yet - will be added in Phase 3",
                      layer=layer_name)
        return None

        # TODO: Re-enable when GIS tables added to schema v2
        # GIS is fetched as GeoJSON/Shapefile, not a single file
        # We'll track the layer URL as the "file"

        features = self.gis_scraper.fetch_layer(layer_name)

        if not features:
            logger.error("gis_fetch_failed", layer=layer_name)
            return None

        # Calculate MD5 from features (serialize to JSON)
        # Convert geometries and timestamps to JSON-serializable format
        import json
        from shapely.geometry import shape
        from shapely.geometry.base import BaseGeometry
        import pandas as pd

        def make_serializable(obj):
            """Recursively convert non-serializable objects to serializable formats"""
            if isinstance(obj, BaseGeometry):
                return obj.wkt
            elif isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_serializable(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return obj

        serializable_features = []
        for f in features:
            feature_dict = f.to_dict().copy()
            serializable_dict = make_serializable(feature_dict)
            serializable_features.append(serializable_dict)

        features_json = json.dumps(serializable_features, sort_keys=True)
        md5_hash = hashlib.md5(features_json.encode()).hexdigest()

        # Check if changed
        async with self.db_manager.async_session_maker() as session:
            changed, prev_snapshot = await self._check_if_changed(
                session,
                source_type='gis_parcels',
                source_name=f"{self.config.market.name.lower()}_{layer_name}",
                md5_hash=md5_hash
            )

            if not changed and not force_update:
                logger.info("gis_unchanged", layer=layer_name, md5=md5_hash[:16])
                return prev_snapshot

            # Create snapshot
            layer_url = self.gis_scraper.shapefile_urls.get(layer_name, '')
            snapshot = await self._create_snapshot(
                session,
                source_type='gis_parcels',
                source_name=f"{self.config.market.name.lower()}_{layer_name}",
                file_url=layer_url,
                md5_hash=md5_hash,
                file_size=len(features_json),
                is_initial_load=(prev_snapshot is None)
            )

            await self._mark_processing(session, snapshot['id'])
            await session.commit()

        # Process features
        stats = await self._process_gis_features(features, snapshot)

        # Mark completed
        async with self.db_manager.async_session_maker() as session:
            await self._mark_completed(session, snapshot['id'], stats)
            await session.commit()

        logger.info("gis_sync_completed",
                   snapshot_id=snapshot['id'],
                   layer=layer_name,
                   added=stats['added'])

        return snapshot


    async def sync_zoning(self, layer_name: str = 'zoning', force_update: bool = False) -> Optional[BulkSnapshot]:
        """Sync zoning GIS layer - DISABLED for schema v2 (no zoning tables yet)"""
        logger.warning("zoning_sync_disabled",
                      reason="Zoning tables not in schema v2 yet - will be added in Phase 3",
                      layer=layer_name)
        return None

        # TODO: Re-enable when zoning tables added to schema v2
        features = self.gis_scraper.fetch_layer(layer_name)

        if not features:
            logger.error("zoning_fetch_failed", layer=layer_name)
            return None

        # Calculate MD5
        import json
        from shapely.geometry.base import BaseGeometry
        import pandas as pd

        def make_serializable(obj):
            if isinstance(obj, BaseGeometry):
                return obj.wkt
            elif isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_serializable(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return obj

        serializable_features = []
        for f in features:
            feature_dict = f.to_dict().copy()
            serializable_dict = make_serializable(feature_dict)
            serializable_features.append(serializable_dict)

        features_json = json.dumps(serializable_features, sort_keys=True)
        md5_hash = hashlib.md5(features_json.encode()).hexdigest()

        # Check if changed
        async with self.db_manager.async_session_maker() as session:
            changed, prev_snapshot = await self._check_if_changed(
                session,
                source_type='gis_zoning',
                source_name=f"{self.config.market.name.lower()}_{layer_name}",
                md5_hash=md5_hash
            )

            if not changed and not force_update:
                logger.info("zoning_unchanged", layer=layer_name, md5=md5_hash[:16])
                return prev_snapshot

            # Create snapshot
            layer_url = self.gis_scraper.shapefile_urls.get(layer_name, '')
            snapshot = await self._create_snapshot(
                session,
                source_type='gis_zoning',
                source_name=f"{self.config.market.name.lower()}_{layer_name}",
                file_url=layer_url,
                md5_hash=md5_hash,
                file_size=len(features_json),
                is_initial_load=(prev_snapshot is None)
            )

            await self._mark_processing(session, snapshot['id'])
            await session.commit()

        # Process features
        stats = await self._process_zoning_features(features, snapshot)

        # Mark completed
        async with self.db_manager.async_session_maker() as session:
            await self._mark_completed(session, snapshot['id'], stats)
            await session.commit()

        logger.info("zoning_sync_completed",
                   snapshot_id=snapshot['id'],
                   layer=layer_name,
                   added=stats['added'])

        return snapshot


    # ==================== PROCESSING ====================

    async def _process_sunbiz_records(
        self,
        records: List[Dict],
        snapshot: BulkSnapshot
    ) -> Dict[str, int]:
        """Upsert Sunbiz LLC records into bulk table"""
        added, updated, unchanged = 0, 0, 0

        async with self.db_manager.async_session_maker() as session:
            for record in records:
                # UPSERT using raw SQL (no ORM models for bulk tables)
                # Record fields from scraper: document_number, entity_name, filing_date, principal_address, etc.
                filing_date = self._parse_date(record.get('filing_date'))

                # Fallback: use scraped_at date if filing_date not found
                if not filing_date and record.get('scraped_at'):
                    filing_date = self._parse_date(record.get('scraped_at'))

                # Skip if we still don't have a date
                if not filing_date:
                    logger.warning("skipping_record_no_date", doc_num=record.get('document_number'))
                    unchanged += 1
                    continue

                # Schema v2 fields: document_number, name (not entity_name), filing_date, status, filing_type (not entity_type),
                # principal_address, mailing_address, registered_agent, entity_id, snapshot_id
                result = await session.execute(text("""
                    INSERT INTO bulk_llc_records (
                        id, document_number, name, filing_date, status, filing_type,
                        principal_address, mailing_address, registered_agent,
                        snapshot_id, created_at
                    ) VALUES (
                        gen_random_uuid(),
                        :doc_num,
                        :name,
                        :filing_date,
                        :status,
                        :filing_type,
                        :principal_address,
                        :mailing_address,
                        :registered_agent,
                        :snapshot_id,
                        NOW()
                    )
                    ON CONFLICT (document_number, snapshot_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        status = EXCLUDED.status
                """), {
                    'doc_num': record.get('document_number'),
                    'name': record.get('entity_name'),  # entity_name from scraper -> name in schema v2
                    'filing_date': filing_date,
                    'status': record.get('status', 'ACTIVE'),
                    'filing_type': record.get('entity_type'),  # entity_type from scraper -> filing_type in schema v2
                    'principal_address': record.get('principal_address'),
                    'mailing_address': record.get('mailing_address'),
                    'registered_agent': record.get('registered_agent_name'),  # Map registered_agent_name -> registered_agent
                    'snapshot_id': str(snapshot['id'])
                })

                # Simplified: just count as added (ON CONFLICT handles updates)
                added += 1

            await session.commit()

        logger.info("sunbiz_processed",
                   total=len(records),
                   added=added,
                   updated=updated)

        return {
            'total': len(records),
            'added': added,
            'updated': updated,
            'unchanged': unchanged
        }


    async def _process_property_records(
        self,
        property_records: List,
        snapshot: BulkSnapshot
    ) -> Dict[str, int]:
        """Upsert property records into bulk table - Schema v2 compatible"""
        added, updated = 0, 0

        # Get current market_id from CurrentMarket
        market_id = CurrentMarket.get_id()

        async with self.db_manager.async_session_maker() as session:
            for prop in property_records:
                sale_date = self._parse_date(prop.last_sale_date)

                # Comprehensive 99-field insert
                await session.execute(text("""
                    INSERT INTO bulk_property_records (
                        id, market_id, parcel_id, snapshot_id,
                        -- Owner (5 fields)
                        owner_name, mailing_address, owner_city, owner_state, owner_zip,
                        -- Location (11 fields)
                        site_address, latitude, longitude, city, lot_size_acres,
                        section, township, range_value, neighborhood_code, neighborhood_desc,
                        subdivision_code, subdivision_desc,
                        -- Classification (8 fields)
                        property_type, use_code, land_use_code, land_use_desc,
                        land_zoning_code, land_zoning_desc, land_type, land_sqft,
                        -- Building primary (6 fields)
                        year_built, effective_year_built, square_feet, stories,
                        improvement_type, improvement_desc,
                        -- Building attributes (9 fields)
                        bedrooms, bathrooms, roof_type, wall_type, exterior_type,
                        heat_type, ac_type, building_quality, building_condition,
                        -- Aggregated structures (10 fields)
                        total_improvement_sqft, total_improvement_count, improvement_types_list,
                        oldest_improvement_year, newest_improvement_year,
                        has_garage, has_porch, has_pool, has_fence, has_shed,
                        -- Valuation (6 fields)
                        market_value, assessed_value, taxable_value, land_value,
                        improvement_value, valuation_year,
                        -- Sales (6 fields)
                        last_sale_date, last_sale_price, sale_qualified,
                        sale_type_vac_imp, sale_book, sale_page,
                        -- Exemptions (4 fields)
                        total_exemption_amount, exemption_types_list, exemption_count,
                        most_recent_exemption_year,
                        -- Legal & Permits (2 fields)
                        legal_description, total_permits,
                        created_at, updated_at
                    ) VALUES (
                        gen_random_uuid(), :market_id, :parcel_id, :snapshot_id,
                        :owner_name, :mailing_address, :owner_city, :owner_state, :owner_zip,
                        :site_address, :latitude, :longitude, :city, :lot_size_acres,
                        :section, :township, :range_value, :neighborhood_code, :neighborhood_desc,
                        :subdivision_code, :subdivision_desc,
                        :property_type, :use_code, :land_use_code, :land_use_desc,
                        :land_zoning_code, :land_zoning_desc, :land_type, :land_sqft,
                        :year_built, :effective_year_built, :square_feet, :stories,
                        :improvement_type, :improvement_desc,
                        :bedrooms, :bathrooms, :roof_type, :wall_type, :exterior_type,
                        :heat_type, :ac_type, :building_quality, :building_condition,
                        :total_improvement_sqft, :total_improvement_count, :improvement_types_list,
                        :oldest_improvement_year, :newest_improvement_year,
                        :has_garage, :has_porch, :has_pool, :has_fence, :has_shed,
                        :market_value, :assessed_value, :taxable_value, :land_value,
                        :improvement_value, :valuation_year,
                        :last_sale_date, :last_sale_price, :sale_qualified,
                        :sale_type_vac_imp, :sale_book, :sale_page,
                        :total_exemption_amount, :exemption_types_list, :exemption_count,
                        :most_recent_exemption_year,
                        :legal_description, :total_permits,
                        NOW(), NOW()
                    )
                    ON CONFLICT (parcel_id, market_id, snapshot_id) DO UPDATE SET
                        updated_at = NOW(),
                        owner_name = EXCLUDED.owner_name,
                        mailing_address = EXCLUDED.mailing_address,
                        owner_city = EXCLUDED.owner_city,
                        owner_state = EXCLUDED.owner_state,
                        owner_zip = EXCLUDED.owner_zip,
                        site_address = EXCLUDED.site_address,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        city = EXCLUDED.city,
                        lot_size_acres = EXCLUDED.lot_size_acres,
                        section = EXCLUDED.section,
                        township = EXCLUDED.township,
                        range_value = EXCLUDED.range_value,
                        neighborhood_code = EXCLUDED.neighborhood_code,
                        neighborhood_desc = EXCLUDED.neighborhood_desc,
                        subdivision_code = EXCLUDED.subdivision_code,
                        subdivision_desc = EXCLUDED.subdivision_desc,
                        property_type = EXCLUDED.property_type,
                        use_code = EXCLUDED.use_code,
                        land_use_code = EXCLUDED.land_use_code,
                        land_use_desc = EXCLUDED.land_use_desc,
                        land_zoning_code = EXCLUDED.land_zoning_code,
                        land_zoning_desc = EXCLUDED.land_zoning_desc,
                        land_type = EXCLUDED.land_type,
                        land_sqft = EXCLUDED.land_sqft,
                        year_built = EXCLUDED.year_built,
                        effective_year_built = EXCLUDED.effective_year_built,
                        square_feet = EXCLUDED.square_feet,
                        stories = EXCLUDED.stories,
                        improvement_type = EXCLUDED.improvement_type,
                        improvement_desc = EXCLUDED.improvement_desc,
                        bedrooms = EXCLUDED.bedrooms,
                        bathrooms = EXCLUDED.bathrooms,
                        roof_type = EXCLUDED.roof_type,
                        wall_type = EXCLUDED.wall_type,
                        exterior_type = EXCLUDED.exterior_type,
                        heat_type = EXCLUDED.heat_type,
                        ac_type = EXCLUDED.ac_type,
                        building_quality = EXCLUDED.building_quality,
                        building_condition = EXCLUDED.building_condition,
                        total_improvement_sqft = EXCLUDED.total_improvement_sqft,
                        total_improvement_count = EXCLUDED.total_improvement_count,
                        improvement_types_list = EXCLUDED.improvement_types_list,
                        oldest_improvement_year = EXCLUDED.oldest_improvement_year,
                        newest_improvement_year = EXCLUDED.newest_improvement_year,
                        has_garage = EXCLUDED.has_garage,
                        has_porch = EXCLUDED.has_porch,
                        has_pool = EXCLUDED.has_pool,
                        has_fence = EXCLUDED.has_fence,
                        has_shed = EXCLUDED.has_shed,
                        market_value = EXCLUDED.market_value,
                        assessed_value = EXCLUDED.assessed_value,
                        taxable_value = EXCLUDED.taxable_value,
                        land_value = EXCLUDED.land_value,
                        improvement_value = EXCLUDED.improvement_value,
                        valuation_year = EXCLUDED.valuation_year,
                        last_sale_date = EXCLUDED.last_sale_date,
                        last_sale_price = EXCLUDED.last_sale_price,
                        sale_qualified = EXCLUDED.sale_qualified,
                        sale_type_vac_imp = EXCLUDED.sale_type_vac_imp,
                        sale_book = EXCLUDED.sale_book,
                        sale_page = EXCLUDED.sale_page,
                        total_exemption_amount = EXCLUDED.total_exemption_amount,
                        exemption_types_list = EXCLUDED.exemption_types_list,
                        exemption_count = EXCLUDED.exemption_count,
                        most_recent_exemption_year = EXCLUDED.most_recent_exemption_year,
                        legal_description = EXCLUDED.legal_description,
                        total_permits = EXCLUDED.total_permits
                """), {
                    'market_id': str(market_id),
                    'parcel_id': prop.parcel_id,
                    'snapshot_id': str(snapshot['id']),
                    # Owner
                    'owner_name': prop.owner_name,
                    'mailing_address': prop.owner_address,
                    'owner_city': getattr(prop, 'owner_city', None),
                    'owner_state': getattr(prop, 'owner_state', None),
                    'owner_zip': getattr(prop, 'owner_zip', None),
                    # Location
                    'site_address': prop.property_address,
                    'latitude': getattr(prop, 'latitude', None),
                    'longitude': getattr(prop, 'longitude', None),
                    'city': getattr(prop, 'city', None),
                    'lot_size_acres': prop.lot_size_acres,
                    'section': getattr(prop, 'section', None),
                    'township': getattr(prop, 'township', None),
                    'range_value': getattr(prop, 'range_value', None),
                    'neighborhood_code': getattr(prop, 'neighborhood_code', None),
                    'neighborhood_desc': getattr(prop, 'neighborhood_desc', None),
                    'subdivision_code': getattr(prop, 'subdivision_code', None),
                    'subdivision_desc': getattr(prop, 'subdivision_desc', None),
                    # Classification
                    'property_type': getattr(prop, 'property_type', None),
                    'use_code': getattr(prop, 'use_code', None),
                    'land_use_code': getattr(prop, 'land_use_code', None),
                    'land_use_desc': getattr(prop, 'land_use_desc', None),
                    'land_zoning_code': getattr(prop, 'land_zoning_code', None),
                    'land_zoning_desc': getattr(prop, 'land_zoning_desc', None),
                    'land_type': getattr(prop, 'land_type', None),
                    'land_sqft': getattr(prop, 'land_sqft', None),
                    # Building primary
                    'year_built': prop.year_built,
                    'effective_year_built': getattr(prop, 'effective_year_built', None),
                    'square_feet': prop.square_footage,
                    'stories': getattr(prop, 'stories', None),
                    'improvement_type': getattr(prop, 'improvement_type', None),
                    'improvement_desc': getattr(prop, 'improvement_desc', None),
                    # Building attributes
                    'bedrooms': prop.bedrooms,
                    'bathrooms': prop.bathrooms,
                    'roof_type': getattr(prop, 'roof_type', None),
                    'wall_type': getattr(prop, 'wall_type', None),
                    'exterior_type': getattr(prop, 'exterior_type', None),
                    'heat_type': getattr(prop, 'heat_type', None),
                    'ac_type': getattr(prop, 'ac_type', None),
                    'building_quality': getattr(prop, 'building_quality', None),
                    'building_condition': getattr(prop, 'building_condition', None),
                    # Aggregated structures
                    'total_improvement_sqft': getattr(prop, 'total_improvement_sqft', None),
                    'total_improvement_count': getattr(prop, 'total_improvement_count', None),
                    'improvement_types_list': getattr(prop, 'improvement_types_list', None),
                    'oldest_improvement_year': getattr(prop, 'oldest_improvement_year', None),
                    'newest_improvement_year': getattr(prop, 'newest_improvement_year', None),
                    'has_garage': getattr(prop, 'has_garage', None),
                    'has_porch': getattr(prop, 'has_porch', None),
                    'has_pool': getattr(prop, 'has_pool', None),
                    'has_fence': getattr(prop, 'has_fence', None),
                    'has_shed': getattr(prop, 'has_shed', None),
                    # Valuation
                    'market_value': prop.market_value,
                    'assessed_value': prop.assessed_value,
                    'taxable_value': getattr(prop, 'taxable_value', None),
                    'land_value': prop.land_value,
                    'improvement_value': getattr(prop, 'improvement_value', None),
                    'valuation_year': getattr(prop, 'valuation_year', None),
                    # Sales
                    'last_sale_date': sale_date,
                    'last_sale_price': prop.last_sale_price,
                    'sale_qualified': getattr(prop, 'sale_qualified', None),
                    'sale_type_vac_imp': getattr(prop, 'sale_type_vac_imp', None),
                    'sale_book': getattr(prop, 'sale_book', None),
                    'sale_page': getattr(prop, 'sale_page', None),
                    # Exemptions
                    'total_exemption_amount': getattr(prop, 'total_exemption_amount', None),
                    'exemption_types_list': getattr(prop, 'exemption_types_list', None),
                    'exemption_count': getattr(prop, 'exemption_count', None),
                    'most_recent_exemption_year': getattr(prop, 'most_recent_exemption_year', None),
                    # Legal & Permits
                    'legal_description': getattr(prop, 'legal_description', None),
                    'total_permits': getattr(prop, 'total_permits', None),
                })

                added += 1

            await session.commit()

        return {'total': len(property_records), 'added': added, 'updated': updated, 'unchanged': 0}


    async def _process_gis_features(
        self,
        features: List,
        snapshot: BulkSnapshot
    ) -> Dict[str, int]:
        """Process GIS features and upsert parcel records"""
        from shapely.geometry.base import BaseGeometry
        from shapely.geometry import shape
        import json
        import pandas as pd

        def make_serializable(obj):
            """Recursively convert non-serializable objects"""
            if isinstance(obj, BaseGeometry):
                return obj.wkt
            elif isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_serializable(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return obj

        added = 0
        skipped = 0

        async with self.db_manager.async_session_maker() as session:
            for feature in features:
                feature_dict = feature.to_dict()

                # Extract parcel ID with fallbacks
                parcel_id = (
                    feature_dict.get('Name') or
                    feature_dict.get('PARCEL_ID') or
                    feature_dict.get('parcelid') or
                    feature_dict.get('PIN') or
                    str(feature_dict.get('Prop_ID')) if feature_dict.get('Prop_ID') else None
                )

                # Skip parcels without valid ID
                if not parcel_id or parcel_id == '0':
                    logger.warning("parcel_missing_id", prop_id=feature_dict.get('Prop_ID'))
                    skipped += 1
                    continue

                # Extract geometry and convert to WKT
                geometry_wkt = None
                geom_data = feature_dict.get('geometry')

                if geom_data:
                    try:
                        if isinstance(geom_data, BaseGeometry):
                            geometry_wkt = geom_data.wkt
                        elif isinstance(geom_data, dict):
                            geom = shape(geom_data)
                            geometry_wkt = geom.wkt
                        elif isinstance(geom_data, str):
                            geometry_wkt = geom_data
                    except Exception as e:
                        logger.warning("geometry_conversion_failed", error=str(e))
                        geometry_wkt = None

                # Make all data JSON-serializable
                serializable_dict = make_serializable(feature_dict)

                await session.execute(text("""
                    INSERT INTO bulk_gis_parcels (
                        id, parcel_id, jurisdiction, geometry, zoning_code, land_use, acreage,
                        snapshot_id, raw_data, created_at, updated_at
                    ) VALUES (
                        gen_random_uuid(),
                        :parcel_id, :jurisdiction,
                        ST_Multi(ST_Force2D(ST_GeomFromText(:geometry_wkt, 4326))),
                        :zoning_code, :land_use, :acreage,
                        :snapshot_id, CAST(:raw_data AS jsonb), NOW(), NOW()
                    )
                    ON CONFLICT (parcel_id, jurisdiction, snapshot_id) DO UPDATE SET
                        updated_at = NOW()
                """), {
                    'parcel_id': parcel_id,
                    'jurisdiction': self.config.market.name.lower(),
                    'geometry_wkt': geometry_wkt,
                    'zoning_code': feature_dict.get('ZONING') or feature_dict.get('ZONECODE'),
                    'land_use': feature_dict.get('LAND_USE') or feature_dict.get('LANDUSE'),
                    'acreage': feature_dict.get('ACREAGE') or feature_dict.get('ACRES'),
                    'snapshot_id': str(snapshot['id']),
                    'raw_data': json.dumps(serializable_dict)
                })

                added += 1

            await session.commit()

        return {'total': len(features), 'added': added, 'updated': 0, 'unchanged': 0, 'skipped': skipped}


    async def _process_zoning_features(
        self,
        features: List,
        snapshot: BulkSnapshot
    ) -> Dict[str, int]:
        """Process zoning features and insert into bulk_gis_zoning table"""
        from shapely.geometry.base import BaseGeometry
        from shapely.geometry import shape
        import json
        import pandas as pd

        def make_serializable(obj):
            if isinstance(obj, BaseGeometry):
                return obj.wkt
            elif isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_serializable(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return obj

        added = 0
        skipped = 0

        async with self.db_manager.async_session_maker() as session:
            for feature in features:
                feature_dict = feature.to_dict()

                # Extract zoning code (most important field)
                zoning_code = (
                    feature_dict.get('ZONING') or
                    feature_dict.get('ZONECODE') or
                    feature_dict.get('ZONE_CODE') or
                    feature_dict.get('ZONE') or
                    feature_dict.get('DISTRICT') or
                    feature_dict.get('FLU')  # Future Land Use
                )

                if not zoning_code:
                    logger.warning("zoning_missing_code", feature=feature_dict)
                    skipped += 1
                    continue

                # Extract zoning name/description
                zoning_name = (
                    feature_dict.get('ZONEDEFIN') or      # Alachua County uses this
                    feature_dict.get('ZONEDISTRICT') or   # Alachua County alternative
                    feature_dict.get('ZONING_NAME') or
                    feature_dict.get('ZONE_NAME') or
                    feature_dict.get('DESCRIPTION') or
                    feature_dict.get('DISTRICT_NAME')
                )

                # Extract geometry
                geometry_wkt = None
                geom_data = feature_dict.get('geometry')

                if geom_data:
                    try:
                        if isinstance(geom_data, BaseGeometry):
                            geometry_wkt = geom_data.wkt
                        elif isinstance(geom_data, dict):
                            geom = shape(geom_data)
                            geometry_wkt = geom.wkt
                        elif isinstance(geom_data, str):
                            geometry_wkt = geom_data
                    except Exception as e:
                        logger.warning("geometry_conversion_failed", error=str(e))
                        geometry_wkt = None

                # Make data JSON-serializable
                serializable_dict = make_serializable(feature_dict)

                await session.execute(text("""
                    INSERT INTO bulk_gis_zoning (
                        id, zoning_code, zoning_name, jurisdiction, geometry,
                        snapshot_id, raw_data, created_at, updated_at
                    ) VALUES (
                        gen_random_uuid(),
                        :zoning_code, :zoning_name, :jurisdiction,
                        ST_Multi(ST_Force2D(ST_GeomFromText(:geometry_wkt, 4326))),
                        :snapshot_id, CAST(:raw_data AS jsonb), NOW(), NOW()
                    )
                """), {
                    'zoning_code': zoning_code,
                    'zoning_name': zoning_name,
                    'jurisdiction': self.config.market.name.lower(),
                    'geometry_wkt': geometry_wkt,
                    'snapshot_id': str(snapshot['id']),
                    'raw_data': json.dumps(serializable_dict)
                })

                added += 1

            await session.commit()

        return {'total': len(features), 'added': added, 'updated': 0, 'unchanged': 0, 'skipped': skipped}


    # ==================== HELPERS ====================

    async def _check_if_changed(
        self,
        session: AsyncSession,
        source_type: str,
        source_name: str,
        md5_hash: str
    ) -> Tuple[bool, Optional[Dict]]:
        """Check if MD5 changed from last snapshot - Schema V2 compatible"""
        # Schema v2: data_source (not source_type/source_name), file_hash (not content_md5), status (not processing_status)
        data_source = f"{source_type}_{source_name}"  # Combine into single data_source field

        result = await session.execute(text("""
            SELECT id, file_hash
            FROM bulk_data_snapshots
            WHERE data_source = :data_source
              AND status = 'completed'
            ORDER BY download_completed_at DESC
            LIMIT 1
        """), {
            'data_source': data_source
        })

        row = result.fetchone()

        if not row:
            logger.info("no_previous_snapshot", source=data_source)
            return True, None

        prev_hash = row[1]
        changed = prev_hash != md5_hash

        logger.info("md5_check",
                   source=data_source,
                   previous_hash=prev_hash[:16] if prev_hash else None,
                   current_hash=md5_hash[:16],
                   changed=changed)

        return changed, {'id': row[0], 'file_hash': prev_hash}


    async def _create_snapshot(
        self,
        session: AsyncSession,
        source_type: str,
        source_name: str,
        md5_hash: str,
        file_size: int,
        file_name: str = None,
        file_url: str = None,
        is_initial_load: bool = False
    ) -> Dict:
        """Create snapshot metadata record - Schema V2 compatible"""
        snapshot_id = uuid4()

        # Schema v2: data_source (combined), file_hash (not content_md5), status (not processing_status)
        # Get market_id from CurrentMarket
        market_id = CurrentMarket.get_id()
        data_source = f"{source_type}_{source_name}"

        await session.execute(text("""
            INSERT INTO bulk_data_snapshots (
                id, market_id, data_source, file_name, source_url,
                file_hash, file_size_bytes, status,
                download_started_at, snapshot_date, is_current, created_at
            ) VALUES (
                :id, :market_id, :data_source, :file_name, :source_url,
                :file_hash, :file_size_bytes, 'pending',
                NOW(), CURRENT_DATE, TRUE, NOW()
            )
        """), {
            'id': str(snapshot_id),
            'market_id': str(market_id),
            'data_source': data_source,
            'file_name': file_name,
            'source_url': file_url,
            'file_hash': md5_hash,
            'file_size_bytes': file_size
        })

        await session.flush()

        return {'id': snapshot_id, 'data_source': data_source}


    async def _mark_processing(self, session: AsyncSession, snapshot_id: uuid4):
        """Mark snapshot as processing - Schema V2 compatible (no SQL function)"""
        await session.execute(text("""
            UPDATE bulk_data_snapshots
            SET status = 'processing',
                processing_started_at = NOW()
            WHERE id = :snapshot_id
        """), {'snapshot_id': str(snapshot_id)})


    async def _mark_completed(
        self,
        session: AsyncSession,
        snapshot_id: uuid4,
        stats: Dict[str, int]
    ):
        """Mark snapshot as completed with stats - Schema V2 compatible (no SQL function)"""
        await session.execute(text("""
            UPDATE bulk_data_snapshots
            SET status = 'completed',
                processing_completed_at = NOW(),
                download_completed_at = NOW(),
                records_total = :total,
                records_inserted = :added,
                records_updated = :updated,
                records_skipped = :unchanged
            WHERE id = :snapshot_id
        """), {
            'snapshot_id': str(snapshot_id),
            'total': stats['total'],
            'added': stats['added'],
            'updated': stats.get('updated', 0),
            'unchanged': stats.get('unchanged', 0)
        })


    def _calculate_md5(self, file_path: Path) -> str:
        """Calculate MD5 hash of file"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


    # Removed _download_to_temp - scrapers handle downloading directly


    def _is_property_related(self, entity_name: str) -> bool:
        """
        Check if LLC name suggests property/real estate business.

        Uses same logic as SunbizScraper for consistency.
        """
        name_upper = entity_name.upper()

        # Exclusion patterns - these indicate NOT property-related
        exclusions = [
            'HOME CARE', 'HOMECARE', 'HOME HEALTH',
            'HOMESCHOOL', 'HOME SCHOOL',
            'GAMING RENTAL', 'EQUIPMENT RENTAL',
            'CAR RENTAL', 'VEHICLE RENTAL',
            'MOBILE HOME', 'NURSING HOME',
            'MENTAL HEALTH', 'HOME THERAPY'
        ]

        # Check exclusions first
        for exclusion in exclusions:
            if exclusion in name_upper:
                return False

        # Strong signals - almost always property-related
        strong_keywords = [
            'REAL ESTATE', 'REALTY', 'PROPERTY', 'PROPERTIES',
            'DEVELOPMENT', 'DEVELOPMENTS', 'DEVELOPER',
            'LAND', 'HOLDINGS', 'APARTMENT', 'APARTMENTS',
            'CONDOS', 'CONDO', 'TOWNHOME', 'TOWNHOMES',
            'ESTATES', 'TITLE', 'MORTGAGE', 'LENDING',
            'RENTAL', 'RENTALS', 'LEASE', 'LEASING'
        ]

        for keyword in strong_keywords:
            if keyword in name_upper:
                return True

        # Medium signals - often property-related
        medium_keywords = [
            'CONSTRUCTION', 'BUILDING', 'BUILDERS',
            'INVESTMENT', 'INVESTMENTS', 'HOUSING',
            'RESIDENTIAL', 'COMMERCIAL', 'VENTURES',
            'CAPITAL', 'RENOVATIONS', 'MANAGEMENT',
            'ACQUISITION', 'EQUITY', 'ASSET', 'ASSETS',
            'HOME', 'HOMES', 'ROOFING', 'ROOF',
            'FLOORING', 'FLOOR', 'HVAC', 'PLUMBING',
            'SOLAR', 'LANDSCAPING', 'LANDSCAPE'
        ]

        for keyword in medium_keywords:
            if keyword in name_upper:
                return True

        return False


    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object"""
        if not date_str:
            return None
        # Handle various formats including ISO
        try:
            # Try ISO format first (from scraper: '2025-09-25T00:00:00')
            return datetime.fromisoformat(date_str).date()
        except:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                try:
                    return datetime.strptime(date_str, '%m/%d/%Y').date()
                except:
                    return None


    async def enrich_properties_from_bulk(self, similarity_threshold: float = 0.7) -> Dict[str, int]:
        """
        Enrich properties with data from bulk GIS records.

        DISABLED for schema v2 - GIS tables not yet implemented.
        Will be re-enabled in Phase 3 when GIS data is imported.

        Args:
            similarity_threshold: Minimum similarity score for address matching (0.0 to 1.0)

        Returns:
            Dict with enrichment stats (matched, updated, skipped)
        """
        logger.warning("property_enrichment_disabled",
                      reason="GIS tables not in schema v2 yet - will be added in Phase 3",
                      threshold=similarity_threshold)
        return {'matched': 0, 'updated': 0, 'skipped': 0}

        # TODO: Re-enable when bulk_gis_parcels table added to schema v2
        logger.info("property_enrichment_started", threshold=similarity_threshold)

        matched = 0
        updated = 0
        skipped = 0

        async with self.db_manager.async_session_maker() as session:
            # Find properties missing parcel IDs
            result = await session.execute(text("""
                SELECT id, address
                FROM properties
                WHERE parcel_id IS NULL
                  AND address IS NOT NULL
                  AND address != ''
                LIMIT 1000
            """))

            properties_to_enrich = result.fetchall()
            logger.info("properties_found_for_enrichment", count=len(properties_to_enrich))

            for prop_id, prop_address in properties_to_enrich:
                # Find best match in GIS bulk data using address similarity
                match_result = await session.execute(text("""
                    SELECT
                        parcel_id,
                        raw_data->>'FULLADDR' as gis_address,
                        raw_data->>'Owner_Mail' as owner_name,
                        ST_Y(ST_Centroid(geometry)) as latitude,
                        ST_X(ST_Centroid(geometry)) as longitude,
                        similarity(raw_data->>'FULLADDR', :address) as similarity_score
                    FROM current_bulk_gis
                    WHERE raw_data->>'FULLADDR' IS NOT NULL
                      AND raw_data->>'FULLADDR' != ''
                      AND similarity(raw_data->>'FULLADDR', :address) > :threshold
                    ORDER BY similarity_score DESC
                    LIMIT 1
                """), {
                    'address': prop_address,
                    'threshold': similarity_threshold
                })

                match = match_result.fetchone()

                if match:
                    matched += 1

                    parcel_id, gis_address, owner_name, lat, lon, score = match

                    # Skip if parcel_id already assigned to another property
                    check_result = await session.execute(text("""
                        SELECT id FROM properties WHERE parcel_id = :parcel_id AND id != :prop_id
                    """), {
                        'parcel_id': parcel_id,
                        'prop_id': str(prop_id)
                    })

                    if check_result.fetchone():
                        logger.warning("parcel_id_already_assigned",
                                     parcel_id=parcel_id,
                                     prop_id=str(prop_id),
                                     prop_address=prop_address)
                        skipped += 1
                        continue

                    # Build coordinates point from geometry centroid
                    coordinates_sql = None
                    if lat and lon:
                        coordinates_sql = f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)"

                    # Update property with bulk data
                    try:
                        if coordinates_sql:
                            await session.execute(text(f"""
                                UPDATE properties
                                SET parcel_id = :parcel_id,
                                    coordinates = {coordinates_sql},
                                    updated_at = NOW()
                                WHERE id = :prop_id
                            """), {
                                'parcel_id': parcel_id,
                                'prop_id': str(prop_id)
                            })
                        else:
                            await session.execute(text("""
                                UPDATE properties
                                SET parcel_id = :parcel_id,
                                    updated_at = NOW()
                                WHERE id = :prop_id
                            """), {
                                'parcel_id': parcel_id,
                                'prop_id': str(prop_id)
                            })

                        updated += 1

                        logger.debug("property_enriched",
                                    prop_id=str(prop_id),
                                    parcel_id=parcel_id,
                                    gis_address=gis_address,
                                    similarity=f"{score:.2f}")
                    except Exception as e:
                        logger.warning("property_update_failed",
                                     prop_id=str(prop_id),
                                     parcel_id=parcel_id,
                                     error=str(e))
                        skipped += 1
                else:
                    skipped += 1

            await session.commit()

        stats = {'matched': matched, 'updated': updated, 'skipped': skipped}
        logger.info("property_enrichment_completed", **stats)

        return stats


# Note: Using raw SQL for UPSERT since bulk tables are not in ORM models yet
# Tables are created via migration 004_bulk_data_tracking.sql
