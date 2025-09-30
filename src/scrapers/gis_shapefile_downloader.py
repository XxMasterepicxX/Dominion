"""
GIS Shapefile Downloader

Downloads property boundaries, zoning maps, and spatial data from government GIS portals.
Provides geospatial intelligence for property analysis and boundary mapping.

Coverage: Property boundaries, zoning maps, flood zones, development constraints
Data Source: Alachua County GIS, City of Gainesville GIS portals
Update Frequency: Monthly (when GIS data updated)
Intelligence Value: Spatial analysis, boundary verification, zoning compliance
"""
import asyncio
import hashlib
import json
import logging
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Tuple
from enum import Enum
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon
from pydantic import BaseModel, Field, validator
import pyproj
from pyproj import CRS, Transformer

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class ShapefileType(Enum):
    """Types of GIS shapefiles."""
    PROPERTY_PARCELS = "property_parcels"
    ZONING_DISTRICTS = "zoning_districts"
    POLITICAL_BOUNDARIES = "political_boundaries"
    SCHOOL_DISTRICTS = "school_districts"
    TRANSPORTATION = "transportation"
    UTILITIES = "utilities"
    ENVIRONMENTAL = "environmental"
    ADMINISTRATIVE = "administrative"
    OTHER = "other"


class CoordinateSystem(Enum):
    """Common coordinate systems."""
    WGS84 = "EPSG:4326"        # GPS coordinates (lat/lon)
    WEB_MERCATOR = "EPSG:3857"  # Web mapping standard
    FLORIDA_EAST = "EPSG:3086"  # Florida State Plane East
    FLORIDA_WEST = "EPSG:3087"  # Florida State Plane West
    NAD83_UTM17N = "EPSG:26917" # UTM Zone 17N (Florida)
    AUTO_DETECT = "auto"        # Detect from shapefile


class ProcessingStatus(Enum):
    """Processing status for shapefiles."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PropertyBoundary(BaseModel):
    """Model for property boundary data."""
    parcel_id: str = Field(..., min_length=1)
    geometry_wkt: str = Field(..., min_length=1)  # Well-Known Text representation

    # Geographic properties
    area_sqft: Optional[float] = None
    area_acres: Optional[float] = None
    perimeter_ft: Optional[float] = None
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None

    # Address and identification
    property_address: Optional[str] = None
    owner_name: Optional[str] = None
    legal_description: Optional[str] = None

    # Administrative boundaries
    municipality: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = "FL"
    zip_code: Optional[str] = None
    school_district: Optional[str] = None
    voting_precinct: Optional[str] = None

    # Zoning and land use
    zoning_code: Optional[str] = None
    zoning_description: Optional[str] = None
    land_use_code: Optional[str] = None
    land_use_description: Optional[str] = None

    # Additional attributes from shapefile
    shapefile_attributes: Optional[Dict[str, Any]] = None

    # Data provenance
    shapefile_source: str
    coordinate_system: str
    processing_date: datetime = Field(default_factory=datetime.utcnow)

    @validator('area_acres', always=True)
    def calculate_acres(cls, v, values):
        area_sqft = values.get('area_sqft')
        if v is None and area_sqft:
            return area_sqft / 43560  # Convert square feet to acres
        return v


class ShapefileDownloadConfig(BaseModel):
    """Configuration for GIS shapefile downloads."""
    shapefile_urls: Dict[str, str] = Field(..., min_items=1)
    shapefile_types: Dict[str, ShapefileType] = Field(default_factory=dict)

    # Coordinate system handling
    target_crs: CoordinateSystem = CoordinateSystem.WGS84
    source_crs: CoordinateSystem = CoordinateSystem.AUTO_DETECT

    # Processing settings
    max_file_size_mb: int = Field(default=500, ge=1, le=2000)
    chunk_size_bytes: int = Field(default=8192, ge=1024)
    extract_to_temp: bool = Field(default=True)

    # Data filtering
    boundary_filter: Optional[Dict[str, Any]] = None  # Filter by geographic bounds
    attribute_filters: Optional[Dict[str, List[str]]] = None  # Filter by attributes

    # Field mapping for different data sources
    field_mappings: Optional[Dict[str, Dict[str, str]]] = None

    # Update schedule
    update_frequency_days: int = Field(default=7, ge=1, le=365)

    # PostGIS settings
    store_in_postgis: bool = Field(default=True)
    postgis_table_prefix: str = Field(default="gis_")


class GISShapefileDownloader(ResilientScraper):
    """
    Downloads and processes GIS shapefiles for spatial data integration.

    Handles property boundaries, zoning districts, and other spatial datasets
    from government GIS portals. Processes large files efficiently and stores
    in PostGIS for spatial queries and analysis.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        download_config: ShapefileDownloadConfig,
        data_directory: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            scraper_id="gis_shapefile_downloader",
            scraper_type=ScraperType.API,  # Direct file downloads
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.config = download_config
        self.data_directory = Path(data_directory or "./data/gis_shapefiles")

        # Create data directory
        self.data_directory.mkdir(parents=True, exist_ok=True)

        # Default field mappings for common shapefile schemas
        self.default_field_mappings = {
            'property_parcels': {
                'parcel_id': ['PARCEL_ID', 'PIN', 'APN', 'PARCEL_NUM', 'PARCELID'],
                'property_address': ['ADDRESS', 'SITE_ADDR', 'PROP_ADDR', 'SITUS_ADDR'],
                'owner_name': ['OWNER', 'OWNER_NAME', 'PROP_OWNER', 'TAXPAYER'],
                'legal_description': ['LEGAL_DESC', 'LEGAL', 'DESCRIPTION'],
                'area_sqft': ['AREA_SQFT', 'SQFT', 'AREA', 'SQ_FEET'],
                'zoning_code': ['ZONING', 'ZONE', 'ZONE_CODE', 'ZONING_CODE'],
                'land_use_code': ['LANDUSE', 'LU_CODE', 'USE_CODE', 'LAND_USE']
            },
            'zoning_districts': {
                'zoning_code': ['ZONE', 'ZONING', 'ZONE_CODE', 'DISTRICT'],
                'zoning_description': ['ZONE_DESC', 'DESCRIPTION', 'ZONE_NAME'],
                'municipality': ['CITY', 'MUNICIPALITY', 'JURISDICTION']
            }
        }

        # Merge with configured field mappings
        if self.config.field_mappings:
            self.default_field_mappings.update(self.config.field_mappings)

        # Processing status tracking
        self.processing_status: Dict[str, ProcessingStatus] = {}

    async def download_all_shapefiles(self, force_download: bool = False) -> Dict[str, List[PropertyBoundary]]:
        """
        Download and process all configured shapefiles.

        Args:
            force_download: Force download even if files haven't changed
        """
        all_results = {}

        for shapefile_name, shapefile_url in self.config.shapefile_urls.items():
            try:
                self.processing_status[shapefile_name] = ProcessingStatus.PENDING

                self.logger.info(f"Processing shapefile: {shapefile_name}")

                boundaries = await self.download_and_process_shapefile(
                    shapefile_name, shapefile_url, force_download
                )

                all_results[shapefile_name] = boundaries
                self.processing_status[shapefile_name] = ProcessingStatus.COMPLETED

                # Rate limiting between downloads
                await self.rate_limiter.acquire(self.scraper_id)

            except Exception as e:
                self.logger.error(f"Failed to process shapefile {shapefile_name}: {e}")
                self.processing_status[shapefile_name] = ProcessingStatus.FAILED
                all_results[shapefile_name] = []

        return all_results

    async def download_and_process_shapefile(
        self,
        shapefile_name: str,
        shapefile_url: str,
        force_download: bool = False
    ) -> List[PropertyBoundary]:
        """
        Download and process a single shapefile.

        Args:
            shapefile_name: Name identifier for the shapefile
            shapefile_url: URL to download the shapefile
            force_download: Force download even if file hasn't changed
        """
        # Check if file has changed (unless forced)
        if not force_download:
            change_result = await self.change_detector.track_content_change(
                url=shapefile_url,
                content=b"",  # Will be filled by scraper
                metadata={"scraper": self.scraper_id, "shapefile": shapefile_name}
            )

            if change_result.change_type.value == "unchanged":
                self.logger.info(f"Shapefile {shapefile_name} unchanged, skipping download")
                return []

        self.processing_status[shapefile_name] = ProcessingStatus.DOWNLOADING

        # Download shapefile
        downloaded_file = await self._download_shapefile(shapefile_url, shapefile_name)
        if not downloaded_file:
            raise Exception(f"Failed to download shapefile from {shapefile_url}")

        self.processing_status[shapefile_name] = ProcessingStatus.EXTRACTING

        # Extract if it's a zip file
        shapefile_path = await self._extract_shapefile(downloaded_file)
        if not shapefile_path:
            raise Exception(f"Failed to extract shapefile from {downloaded_file}")

        self.processing_status[shapefile_name] = ProcessingStatus.PROCESSING

        # Process shapefile
        boundaries = await self._process_shapefile(shapefile_path, shapefile_name, shapefile_url)

        # Clean up temporary files
        if self.config.extract_to_temp:
            try:
                if downloaded_file.exists():
                    downloaded_file.unlink()
                if shapefile_path != downloaded_file and shapefile_path.exists():
                    # Remove extracted directory
                    import shutil
                    if shapefile_path.is_dir():
                        shutil.rmtree(shapefile_path)
                    else:
                        shapefile_path.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to clean up temporary files: {e}")

        return boundaries

    async def monitor_shapefile_updates(self) -> Dict[str, List[PropertyBoundary]]:
        """Monitor for shapefile updates since last check."""
        updated_shapefiles = {}

        for shapefile_name, shapefile_url in self.config.shapefile_urls.items():
            try:
                change_result = await self.change_detector.track_content_change(
                    url=shapefile_url,
                    content=b"",
                    metadata={"scraper": self.scraper_id, "shapefile": shapefile_name, "check_type": "monitor"}
                )

                if change_result.change_type.value != "unchanged":
                    self.logger.info(f"Detected update in shapefile: {shapefile_name}")

                    boundaries = await self.download_and_process_shapefile(
                        shapefile_name, shapefile_url, force_download=True
                    )
                    updated_shapefiles[shapefile_name] = boundaries

            except Exception as e:
                self.logger.error(f"Failed to check for updates in {shapefile_name}: {e}")

        return updated_shapefiles

    async def store_boundaries(self, boundaries: List[PropertyBoundary]) -> int:
        """Store property boundaries in database."""
        if not boundaries:
            return 0

        stored_count = 0
        batch_size = 500  # Process in smaller batches for memory efficiency

        async with self.db_manager.get_session() as session:
            for i in range(0, len(boundaries), batch_size):
                batch = boundaries[i:i + batch_size]

                for boundary in batch:
                    try:
                        # Create raw fact entry
                        fact_data = {
                            "boundary_data": boundary.dict(),
                            "scraped_from": "gis_shapefile_download",
                            "scraper_version": "1.0",
                            "processing_notes": {
                                "data_quality": "official_government_gis",
                                "confidence": 1.0,
                                "source_type": "gis_shapefile",
                                "coordinate_system": boundary.coordinate_system,
                                "has_geometry": bool(boundary.geometry_wkt),
                                "area_acres": boundary.area_acres
                            }
                        }

                        # Calculate content hash
                        content_str = json.dumps(fact_data, sort_keys=True, default=str)
                        content_hash = hashlib.md5(content_str.encode()).hexdigest()

                        # Insert raw fact
                        query = """
                            INSERT INTO raw_facts (
                                fact_type, source_url, scraped_at, parser_version,
                                raw_content, content_hash, processed_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                            ON CONFLICT (content_hash) DO NOTHING
                            RETURNING id
                        """

                        result = await session.execute(
                            query,
                            "property_boundary",
                            boundary.shapefile_source,
                            datetime.utcnow(),
                            "gis_shapefile_v1.0",
                            json.dumps(fact_data),
                            content_hash,
                            datetime.utcnow()
                        )

                        if result.rowcount > 0:
                            stored_count += 1

                            # Create structured fact
                            raw_fact_id = (await result.fetchone())['id']

                            structured_query = """
                                INSERT INTO structured_facts (
                                    raw_fact_id, entity_type, structured_data, extraction_confidence
                                ) VALUES ($1, $2, $3, $4)
                            """

                            await session.execute(
                                structured_query,
                                raw_fact_id,
                                "property_boundary",
                                json.dumps(boundary.dict(), default=str),
                                1.0  # High confidence for official GIS data
                            )

                            # Store in PostGIS if enabled
                            if self.config.store_in_postgis:
                                await self._store_in_postgis(session, boundary, raw_fact_id)

                    except Exception as e:
                        self.logger.error(f"Failed to store boundary {boundary.parcel_id}: {e}")
                        continue

                # Commit batch
                await session.commit()

                if i % (batch_size * 10) == 0:  # Log every 10 batches
                    self.logger.info(f"Processed {i + len(batch)}/{len(boundaries)} property boundaries")

        self.logger.info(f"Stored {stored_count} new property boundaries")
        return stored_count

    async def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status for all shapefiles."""
        return {
            "status_by_shapefile": {
                name: status.value for name, status in self.processing_status.items()
            },
            "total_shapefiles": len(self.config.shapefile_urls),
            "completed": sum(1 for status in self.processing_status.values()
                           if status == ProcessingStatus.COMPLETED),
            "failed": sum(1 for status in self.processing_status.values()
                        if status == ProcessingStatus.FAILED),
            "in_progress": sum(1 for status in self.processing_status.values()
                             if status in [ProcessingStatus.DOWNLOADING, ProcessingStatus.EXTRACTING, ProcessingStatus.PROCESSING])
        }

    async def process_response(self, content: bytes, response: aiohttp.ClientResponse) -> Any:
        """Process response - return raw bytes for file downloads."""
        return content

    async def _download_shapefile(self, url: str, shapefile_name: str) -> Optional[Path]:
        """Download shapefile from URL."""
        try:
            self.logger.info(f"Downloading shapefile: {url}")

            result = await self.scrape(url)
            if not result.success:
                self.logger.error(f"Failed to download shapefile: {result.error}")
                return None

            # Generate filename
            filename = f"{shapefile_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            file_path = self.data_directory / filename

            # Check file size
            if len(result.data) > self.config.max_file_size_mb * 1024 * 1024:
                self.logger.error(f"Shapefile too large: {len(result.data)} bytes")
                return None

            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(result.data)

            self.logger.info(f"Downloaded shapefile: {file_path} ({len(result.data):,} bytes)")
            return file_path

        except Exception as e:
            self.logger.error(f"Failed to download shapefile from {url}: {e}")
            return None

    async def _extract_shapefile(self, file_path: Path) -> Optional[Path]:
        """Extract shapefile from zip archive if needed."""
        try:
            # If it's not a zip file, return as-is
            if not file_path.suffix.lower() == '.zip':
                return file_path

            # Extract zip file
            extract_dir = self.data_directory / f"extracted_{file_path.stem}"
            extract_dir.mkdir(exist_ok=True)

            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # Find the main shapefile (.shp)
            shp_files = list(extract_dir.glob("*.shp"))

            if not shp_files:
                self.logger.error(f"No .shp files found in {file_path}")
                return None

            if len(shp_files) == 1:
                return shp_files[0]
            else:
                # Multiple shapefiles - return the directory
                self.logger.info(f"Found {len(shp_files)} shapefiles in archive")
                return extract_dir

        except Exception as e:
            self.logger.error(f"Failed to extract shapefile {file_path}: {e}")
            return None

    async def _process_shapefile(
        self,
        shapefile_path: Path,
        shapefile_name: str,
        source_url: str
    ) -> List[PropertyBoundary]:
        """Process shapefile and extract property boundaries."""
        boundaries = []

        try:
            if shapefile_path.is_dir():
                # Multiple shapefiles in directory
                shp_files = list(shapefile_path.glob("*.shp"))
                for shp_file in shp_files:
                    batch_boundaries = await self._process_single_shapefile(
                        shp_file, shapefile_name, source_url
                    )
                    boundaries.extend(batch_boundaries)
            else:
                # Single shapefile
                boundaries = await self._process_single_shapefile(
                    shapefile_path, shapefile_name, source_url
                )

        except Exception as e:
            self.logger.error(f"Failed to process shapefile {shapefile_path}: {e}")

        return boundaries

    async def _process_single_shapefile(
        self,
        shp_file: Path,
        shapefile_name: str,
        source_url: str
    ) -> List[PropertyBoundary]:
        """Process a single .shp file."""
        boundaries = []

        try:
            self.logger.info(f"Reading shapefile: {shp_file}")

            # Read shapefile with geopandas
            gdf = gpd.read_file(shp_file)

            self.logger.info(f"Loaded {len(gdf)} features from shapefile")

            # Get or detect coordinate system
            source_crs = self._determine_coordinate_system(gdf)
            target_crs = self.config.target_crs.value

            # Reproject if needed
            if source_crs != target_crs and target_crs != CoordinateSystem.AUTO_DETECT.value:
                self.logger.info(f"Reprojecting from {source_crs} to {target_crs}")
                gdf = gdf.to_crs(target_crs)

            # Determine shapefile type
            shapefile_type = self.config.shapefile_types.get(shapefile_name, ShapefileType.OTHER)

            # Get field mapping for this shapefile type
            field_mapping = self.default_field_mappings.get(shapefile_type.value, {})

            # Process each feature
            for idx, row in gdf.iterrows():
                try:
                    boundary = self._create_boundary_from_row(
                        row, field_mapping, source_url, source_crs or target_crs
                    )
                    if boundary:
                        boundaries.append(boundary)

                except Exception as e:
                    self.logger.debug(f"Failed to process feature {idx}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to read shapefile {shp_file}: {e}")

        return boundaries

    def _determine_coordinate_system(self, gdf: gpd.GeoDataFrame) -> str:
        """Determine coordinate system from GeoDataFrame."""
        if self.config.source_crs != CoordinateSystem.AUTO_DETECT:
            return self.config.source_crs.value

        # Try to get CRS from GeoDataFrame
        if gdf.crs:
            try:
                return gdf.crs.to_string()
            except Exception:
                pass

        # Default to WGS84
        return CoordinateSystem.WGS84.value

    def _create_boundary_from_row(
        self,
        row: pd.Series,
        field_mapping: Dict[str, List[str]],
        source_url: str,
        coordinate_system: str
    ) -> Optional[PropertyBoundary]:
        """Create PropertyBoundary object from shapefile row."""
        try:
            # Get geometry
            geometry = row.geometry
            if geometry is None or geometry.is_empty:
                return None

            # Convert geometry to WKT
            geometry_wkt = geometry.wkt

            # Calculate geometric properties
            area_sqft = None
            perimeter_ft = None
            centroid_lat = None
            centroid_lon = None

            try:
                if coordinate_system == CoordinateSystem.WGS84.value:
                    # For WGS84, calculate approximate area in square feet
                    # This is a rough calculation - for precise calculations would need projection
                    centroid = geometry.centroid
                    centroid_lat = centroid.y
                    centroid_lon = centroid.x

                    # Very rough area calculation for lat/lon (not precise but gives magnitude)
                    if hasattr(geometry, 'area'):
                        # Convert degrees squared to approximate square feet
                        area_degrees = geometry.area
                        # At Florida latitude (~29°), 1 degree ≈ 364,000 feet
                        area_sqft = area_degrees * (364000 ** 2)
                else:
                    # For projected coordinate systems
                    if hasattr(geometry, 'area'):
                        area_sqft = geometry.area  # Assumed to be in square feet or similar

                    if hasattr(geometry, 'length'):
                        perimeter_ft = geometry.length

                    # Get centroid in original CRS then transform to WGS84 for lat/lon
                    centroid = geometry.centroid
                    if coordinate_system != CoordinateSystem.WGS84.value:
                        try:
                            transformer = Transformer.from_crs(coordinate_system, CoordinateSystem.WGS84.value)
                            centroid_lon, centroid_lat = transformer.transform(centroid.x, centroid.y)
                        except Exception:
                            centroid_lat = centroid.y
                            centroid_lon = centroid.x
                    else:
                        centroid_lat = centroid.y
                        centroid_lon = centroid.x

            except Exception as e:
                self.logger.debug(f"Failed to calculate geometric properties: {e}")

            # Map attributes from shapefile
            mapped_data = {}
            for model_field, possible_fields in field_mapping.items():
                for field_name in possible_fields:
                    if field_name in row and pd.notna(row[field_name]):
                        mapped_data[model_field] = row[field_name]
                        break

            # Generate parcel_id if not found
            if 'parcel_id' not in mapped_data:
                # Try to generate from other fields or use row index
                if 'property_address' in mapped_data:
                    mapped_data['parcel_id'] = f"addr_{hash(mapped_data['property_address']) % 100000}"
                else:
                    mapped_data['parcel_id'] = f"feature_{hash(str(row.to_dict())) % 100000}"

            # Collect all shapefile attributes
            shapefile_attributes = {
                key: value for key, value in row.to_dict().items()
                if key != 'geometry' and pd.notna(value)
            }

            # Create PropertyBoundary
            boundary_data = {
                'parcel_id': mapped_data.get('parcel_id'),
                'geometry_wkt': geometry_wkt,
                'area_sqft': area_sqft,
                'perimeter_ft': perimeter_ft,
                'centroid_lat': centroid_lat,
                'centroid_lon': centroid_lon,
                'shapefile_source': source_url,
                'coordinate_system': coordinate_system,
                'shapefile_attributes': shapefile_attributes,
                **mapped_data
            }

            return PropertyBoundary(**boundary_data)

        except Exception as e:
            self.logger.debug(f"Failed to create boundary from row: {e}")
            return None

    async def _store_in_postgis(self, session, boundary: PropertyBoundary, raw_fact_id: str) -> None:
        """Store boundary geometry in PostGIS format."""
        try:
            table_name = f"{self.config.postgis_table_prefix}property_boundaries"

            # Create PostGIS table if it doesn't exist
            create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    raw_fact_id UUID REFERENCES raw_facts(id),
                    parcel_id TEXT NOT NULL,
                    geometry GEOMETRY(GEOMETRY, 4326),
                    area_sqft DOUBLE PRECISION,
                    area_acres DOUBLE PRECISION,
                    centroid GEOMETRY(POINT, 4326),
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_{table_name}_geometry
                ON {table_name} USING GIST (geometry);

                CREATE INDEX IF NOT EXISTS idx_{table_name}_parcel_id
                ON {table_name} (parcel_id);
            """

            await session.execute(create_table_query)

            # Insert boundary with PostGIS geometry
            insert_query = f"""
                INSERT INTO {table_name} (
                    raw_fact_id, parcel_id, geometry, area_sqft, area_acres, centroid
                ) VALUES (
                    $1, $2, ST_GeomFromText($3, 4326), $4, $5,
                    ST_Centroid(ST_GeomFromText($3, 4326))
                )
                ON CONFLICT (parcel_id) DO UPDATE SET
                    raw_fact_id = $1,
                    geometry = ST_GeomFromText($3, 4326),
                    area_sqft = $4,
                    area_acres = $5,
                    centroid = ST_Centroid(ST_GeomFromText($3, 4326)),
                    created_at = NOW()
            """

            await session.execute(
                insert_query,
                raw_fact_id,
                boundary.parcel_id,
                boundary.geometry_wkt,
                boundary.area_sqft,
                boundary.area_acres
            )

        except Exception as e:
            self.logger.warning(f"Failed to store geometry in PostGIS: {e}")


async def create_gis_downloader(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    shapefile_urls: Dict[str, str],
    shapefile_types: Optional[Dict[str, ShapefileType]] = None,
    data_directory: Optional[str] = None,
    **config_kwargs
) -> GISShapefileDownloader:
    """Factory function to create configured GIS shapefile downloader."""

    download_config = ShapefileDownloadConfig(
        shapefile_urls=shapefile_urls,
        shapefile_types=shapefile_types or {},
        **config_kwargs
    )

    scraper = GISShapefileDownloader(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        download_config=download_config,
        data_directory=data_directory,
        **config_kwargs
    )

    await scraper.initialize()
    return scraper


# Default shapefile URLs for Alachua County
DEFAULT_SHAPEFILE_URLS = {
    "alachua_county_parcels": "https://s3.amazonaws.com/maps.acpafl.org/GIS/publicparcels.zip"
}

DEFAULT_SHAPEFILE_TYPES = {
    "alachua_county_parcels": ShapefileType.PROPERTY_PARCELS
}