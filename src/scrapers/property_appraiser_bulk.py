"""
Alachua County Property Appraiser CAMA Data Scraper

Downloads bulk property assessment data (CAMA) from Alachua County Property Appraiser.
This is the "GOLD" data source per mmm.txt - provides complete property intelligence.

Coverage: ALL properties, owners, sales, assessments, LLC ownership (10,986 LLCs)
Data Source: Alachua County Property Appraiser bulk download (13 TXT files)
Update Frequency: Every 6 hours (CAMA updates multiple times daily)
Intelligence Value: FOUNDATION data for all property analysis and relationship mapping
"""
import asyncio
import csv
import hashlib
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum
from urllib.parse import urljoin, urlparse
import zipfile
import tempfile

import aiofiles
import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, validator

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class PropertyDataFormat(Enum):
    """Supported property data formats."""
    CSV = "csv"
    XML = "xml"
    JSON = "json"
    EXCEL = "excel"
    ZIP = "zip"


class PropertyType(Enum):
    """Property types from assessor data."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    VACANT_LAND = "vacant_land"
    AGRICULTURAL = "agricultural"
    EXEMPT = "exempt"
    MOBILE_HOME = "mobile_home"
    CONDOMINIUM = "condominium"
    MULTI_FAMILY = "multi_family"
    OTHER = "other"


class PropertyRecord(BaseModel):
    """Model for property assessment data."""
    parcel_id: str = Field(..., min_length=1)
    account_number: Optional[str] = None
    property_address: str = Field(..., min_length=1)
    owner_name: str = Field(..., min_length=1)
    owner_address: Optional[str] = None
    property_type: PropertyType = PropertyType.OTHER
    use_code: Optional[str] = None
    legal_description: Optional[str] = None

    # Assessment values
    assessed_value: Optional[float] = None
    market_value: Optional[float] = None
    taxable_value: Optional[float] = None
    land_value: Optional[float] = None
    improvement_value: Optional[float] = None
    homestead_exemption: Optional[float] = None

    # Property characteristics
    year_built: Optional[int] = None
    square_footage: Optional[float] = None
    lot_size_acres: Optional[float] = None
    lot_size_sqft: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    stories: Optional[float] = None

    # Geographic data
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    subdivision: Optional[str] = None
    neighborhood: Optional[str] = None
    school_district: Optional[str] = None

    # Sale information
    last_sale_date: Optional[datetime] = None
    last_sale_price: Optional[float] = None
    sale_validation: Optional[str] = None

    # Tax information
    tax_year: Optional[int] = None
    millage_rate: Optional[float] = None
    annual_taxes: Optional[float] = None

    # Data provenance
    data_source: str
    extraction_date: datetime = Field(default_factory=datetime.utcnow)

    @validator('last_sale_date', pre=True)
    def parse_sale_date(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            for fmt in [
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%m-%d-%Y",
                "%Y/%m/%d",
                "%d/%m/%Y"
            ]:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            # Try pandas date parsing as fallback
            try:
                return pd.to_datetime(v).to_pydatetime()
            except:
                pass
        return v

    @validator('assessed_value', 'market_value', 'taxable_value', 'land_value',
              'improvement_value', 'homestead_exemption', 'last_sale_price',
              'square_footage', 'lot_size_acres', 'lot_size_sqft', 'bathrooms',
              'stories', 'millage_rate', 'annual_taxes', pre=True)
    def parse_numbers(cls, v):
        if v is None or v == "" or v == "N/A":
            return None
        if isinstance(v, str):
            # Remove currency symbols and commas
            v = v.replace('$', '').replace(',', '').replace('%', '')
            try:
                return float(v) if v else None
            except ValueError:
                return None
        return float(v) if v else None

    @validator('year_built', 'bedrooms', 'tax_year', pre=True)
    def parse_integers(cls, v):
        if v is None or v == "" or v == "N/A":
            return None
        try:
            return int(float(v)) if v else None
        except (ValueError, TypeError):
            return None

    def classify_property_type(self) -> PropertyType:
        """Classify property type from use code and characteristics."""
        if not self.use_code:
            return PropertyType.OTHER

        use_code_upper = self.use_code.upper()

        # Common use code patterns
        if any(code in use_code_upper for code in ['SF', 'SFR', 'SINGLE', 'RES']):
            return PropertyType.RESIDENTIAL
        elif any(code in use_code_upper for code in ['COMM', 'RETAIL', 'OFFICE', 'STORE']):
            return PropertyType.COMMERCIAL
        elif any(code in use_code_upper for code in ['IND', 'INDUSTRIAL', 'WAREHOUSE', 'MFG']):
            return PropertyType.INDUSTRIAL
        elif any(code in use_code_upper for code in ['VAC', 'VACANT', 'LAND']):
            return PropertyType.VACANT_LAND
        elif any(code in use_code_upper for code in ['AGR', 'FARM', 'AGRICULTURAL']):
            return PropertyType.AGRICULTURAL
        elif any(code in use_code_upper for code in ['EXEMPT', 'GOV', 'CHURCH', 'SCHOOL']):
            return PropertyType.EXEMPT
        elif any(code in use_code_upper for code in ['MH', 'MOBILE', 'MANUFACTURED']):
            return PropertyType.MOBILE_HOME
        elif any(code in use_code_upper for code in ['CONDO', 'CONDOMINIUM']):
            return PropertyType.CONDOMINIUM
        elif any(code in use_code_upper for code in ['APT', 'APARTMENT', 'DUPLEX', 'MULTI']):
            return PropertyType.MULTI_FAMILY
        else:
            return PropertyType.OTHER


class BulkDownloadConfig(BaseModel):
    """Configuration for bulk property data downloads."""
    portal_base_url: str = Field(..., min_length=1)
    portal_type: str = Field(default="qpublic")  # qpublic, cama, custom
    download_format: PropertyDataFormat = PropertyDataFormat.CSV
    download_schedule: str = Field(default="weekly")  # daily, weekly, monthly
    max_file_size_mb: int = Field(default=500, ge=1, le=2000)
    chunk_size_bytes: int = Field(default=8192, ge=1024)

    # Portal-specific configuration
    login_required: bool = Field(default=False)
    username: Optional[str] = None
    password: Optional[str] = None

    # File location patterns
    download_url_pattern: Optional[str] = None
    file_name_pattern: Optional[str] = None

    # Field mapping for different portal schemas
    field_mapping: Optional[Dict[str, str]] = None

    # Data filtering
    property_types_included: Optional[List[str]] = None
    min_assessed_value: Optional[float] = None
    exclude_exempt: bool = Field(default=True)


class PropertyAppraiseBulkScraper(ResilientScraper):
    """
    Bulk downloader for property assessment data from county appraisers.

    Supports multiple portal types with configurable extraction rules.
    Handles large CSV/XML files efficiently with streaming processing.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        download_config: BulkDownloadConfig,
        data_directory: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            scraper_id="property_appraiser_bulk",
            scraper_type=ScraperType.API,  # Bulk downloads are typically direct file access
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.config = download_config
        self.data_directory = Path(data_directory or "./data/property_bulk")

        # Create data directory
        self.data_directory.mkdir(parents=True, exist_ok=True)

        # Portal-specific configurations
        self.portal_configs = {
            "qpublic": {
                "download_paths": [
                    "/downloads/property_data.csv",
                    "/export/full_export.csv",
                    "/reports/assessor_export.csv"
                ],
                "search_patterns": [
                    "a[href*='download']",
                    "a[href*='export']",
                    "a[href*='bulk']",
                    "a[href*='csv']"
                ]
            },
            "cama": {
                "download_paths": [
                    "/data/property_export.xml",
                    "/export/property_data.csv",
                    "/public/assessor_data.csv"
                ],
                "search_patterns": [
                    "a[href*='property_export']",
                    "a[href*='assessor_data']",
                    "a[href*='public_data']"
                ]
            },
            "s3_direct": {
                # Direct S3 download URL - bypasses CloudFlare blocking
                "direct_url": "https://s3.amazonaws.com/acpa.cama/ACPA_CAMAData.zip",
                "update_time": "daily_23:45",  # CAMA data updates nightly at 11:45 PM
                "file_format": "zip",
                "download_paths": [],
                "search_patterns": []
            },
            "custom": {
                "download_paths": [],
                "search_patterns": [
                    "a[href*='download']",
                    "a[href*='export']",
                    "a[href*='data']"
                ]
            }
        }

        # Default field mappings for common schemas
        self.default_field_mappings = {
            "qpublic": {
                "parcel_id": ["PARCEL_ID", "PARCEL_NUMBER", "PIN", "APN"],
                "account_number": ["ACCOUNT_NUMBER", "ACCOUNT", "ACCT_NUM"],
                "property_address": ["PROPERTY_ADDRESS", "SITE_ADDRESS", "ADDRESS"],
                "owner_name": ["OWNER_NAME", "OWNER", "TAXPAYER_NAME"],
                "owner_address": ["OWNER_ADDRESS", "MAILING_ADDRESS", "TAXPAYER_ADDRESS"],
                "use_code": ["USE_CODE", "PROPERTY_USE", "USE_DESC"],
                "assessed_value": ["ASSESSED_VALUE", "TOTAL_ASSESSED", "ASSESSMENT"],
                "market_value": ["MARKET_VALUE", "FAIR_MARKET_VALUE", "APPRAISED_VALUE"],
                "land_value": ["LAND_VALUE", "LAND_ASSESSMENT"],
                "improvement_value": ["IMPROVEMENT_VALUE", "BUILDING_VALUE"],
                "year_built": ["YEAR_BUILT", "CONSTRUCTION_YEAR", "BUILT_YEAR"],
                "square_footage": ["SQUARE_FEET", "LIVING_AREA", "FLOOR_AREA"],
                "lot_size_acres": ["LOT_SIZE_ACRES", "ACRES", "ACREAGE"],
                "last_sale_date": ["SALE_DATE", "LAST_SALE_DATE", "TRANSFER_DATE"],
                "last_sale_price": ["SALE_PRICE", "LAST_SALE_PRICE", "TRANSFER_AMOUNT"]
            }
        }

        # Get field mapping from config or use default
        portal_type = self.config.portal_type.lower()
        self.field_mapping = (
            self.config.field_mapping or
            self.default_field_mappings.get(portal_type, {})
        )

    async def download_bulk_data(self, force_download: bool = False) -> Optional[Path]:
        """
        Download bulk property data file.

        Args:
            force_download: Force download even if file hasn't changed
        """
        # Find download URL
        download_url = await self._find_download_url()
        if not download_url:
            self.logger.error("Could not find bulk data download URL")
            return None

        # Check if file has changed (unless forced)
        if not force_download:
            change_result = await self.change_detector.track_content_change(
                url=download_url,
                content=b"",  # Will be filled by scraper
                metadata={"scraper": self.scraper_id, "check_type": "bulk_download"}
            )

            if change_result.change_type.value == "unchanged":
                self.logger.info("Bulk data file unchanged, skipping download")
                return None

        self.logger.info(f"Starting bulk data download from: {download_url}")

        # Download file
        result = await self._download_large_file(download_url)
        if not result:
            self.logger.error("Failed to download bulk data file")
            return None

        return result

    async def process_bulk_file(self, file_path: Path) -> List[PropertyRecord]:
        """
        Process downloaded bulk file and extract property records.

        Args:
            file_path: Path to downloaded file
        """
        if not file_path.exists():
            self.logger.error(f"Bulk file not found: {file_path}")
            return []

        # Determine file format
        file_format = self._determine_file_format(file_path)
        self.logger.info(f"Processing {file_format.value} file: {file_path}")

        # Process based on format
        if file_format == PropertyDataFormat.ZIP:
            return await self._process_zip_file(file_path)
        elif file_format == PropertyDataFormat.CSV:
            return await self._process_csv_file(file_path)
        elif file_format == PropertyDataFormat.XML:
            return await self._process_xml_file(file_path)
        elif file_format == PropertyDataFormat.JSON:
            return await self._process_json_file(file_path)
        else:
            self.logger.error(f"Unsupported file format: {file_format}")
            return []

    async def scrape_property_data(self, force_download: bool = False) -> List[PropertyRecord]:
        """
        Complete workflow: download and process bulk property data.

        Args:
            force_download: Force download even if file hasn't changed
        """
        # Download bulk data
        file_path = await self.download_bulk_data(force_download)
        if not file_path:
            return []

        # Process file
        properties = await self.process_bulk_file(file_path)

        self.logger.info(f"Processed {len(properties)} property records from bulk data")
        return properties

    async def store_property_data(self, properties: List[PropertyRecord]) -> int:
        """Store property records in database."""
        if not properties:
            return 0

        stored_count = 0
        batch_size = 1000  # Process in batches for memory efficiency

        async with self.db_manager.get_session() as session:
            for i in range(0, len(properties), batch_size):
                batch = properties[i:i + batch_size]

                for property_record in batch:
                    try:
                        # Create raw fact entry
                        fact_data = {
                            "property_data": property_record.dict(),
                            "scraped_from": "property_appraiser_bulk",
                            "scraper_version": "1.0",
                            "portal_type": self.config.portal_type,
                            "processing_notes": {
                                "data_quality": "official_government_assessment",
                                "confidence": 1.0,
                                "source_type": "bulk_property_data",
                                "property_type": property_record.property_type.value,
                                "has_sale_data": property_record.last_sale_date is not None,
                                "has_geographic_data": all([
                                    property_record.latitude,
                                    property_record.longitude
                                ])
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
                            "property_assessment",
                            f"{self.config.portal_base_url}/bulk_data",
                            datetime.utcnow(),
                            "property_bulk_v1.0",
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
                                "property_record",
                                json.dumps(property_record.dict(), default=str),
                                1.0  # High confidence for official assessment data
                            )

                    except Exception as e:
                        self.logger.error(f"Failed to store property {property_record.parcel_id}: {e}")
                        continue

                # Commit batch
                await session.commit()

                if i % (batch_size * 10) == 0:  # Log every 10 batches
                    self.logger.info(f"Processed {i + len(batch)}/{len(properties)} property records")

        self.logger.info(f"Stored {stored_count} new property records")
        return stored_count

    async def get_download_statistics(self) -> Dict[str, Any]:
        """Get statistics about property data downloads."""
        async with self.db_manager.get_session() as session:
            # Total properties by type
            query = """
                SELECT
                    (structured_data->>'property_type')::text as property_type,
                    COUNT(*) as count,
                    AVG((structured_data->>'assessed_value')::numeric) as avg_assessed_value,
                    SUM((structured_data->>'assessed_value')::numeric) as total_assessed_value
                FROM structured_facts sf
                JOIN raw_facts rf ON sf.raw_fact_id = rf.id
                WHERE sf.entity_type = 'property_record'
                AND rf.fact_type = 'property_assessment'
                GROUP BY (structured_data->>'property_type')::text
                ORDER BY count DESC
            """

            result = await session.execute(query)
            property_stats = {}

            for row in await result.fetchall():
                property_stats[row['property_type']] = {
                    'count': row['count'],
                    'avg_assessed_value': float(row['avg_assessed_value']) if row['avg_assessed_value'] else 0,
                    'total_assessed_value': float(row['total_assessed_value']) if row['total_assessed_value'] else 0
                }

            # Recent downloads
            recent_query = """
                SELECT
                    DATE(scraped_at) as download_date,
                    COUNT(*) as properties_added
                FROM raw_facts
                WHERE fact_type = 'property_assessment'
                AND scraped_at >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(scraped_at)
                ORDER BY download_date DESC
            """

            result = await session.execute(recent_query)
            recent_downloads = {
                row['download_date'].isoformat(): row['properties_added']
                for row in await result.fetchall()
            }

            return {
                'property_type_breakdown': property_stats,
                'recent_downloads': recent_downloads,
                'total_properties': sum(stats['count'] for stats in property_stats.values())
            }

    async def process_response(self, content: bytes, response: aiohttp.ClientResponse) -> Any:
        """Process response from property appraiser portal."""
        content_type = response.headers.get('Content-Type', '').lower()

        if 'text/html' in content_type:
            return content.decode('utf-8', errors='ignore')
        else:
            # Likely a file download
            return content

    async def _find_download_url(self) -> Optional[str]:
        """Find bulk data download URL."""
        # Check for direct S3 URL (bypasses CloudFlare blocking)
        portal_config = self.portal_configs.get(self.config.portal_type, {})
        if "direct_url" in portal_config:
            direct_url = portal_config["direct_url"]
            self.logger.info(f"Using direct S3 URL: {direct_url}")
            return direct_url

        # First try configured download URL pattern
        if self.config.download_url_pattern:
            full_url = urljoin(self.config.portal_base_url, self.config.download_url_pattern)
            if await self._url_exists(full_url):
                return full_url

        # Try common download paths for this portal type
        for path in portal_config.get("download_paths", []):
            full_url = urljoin(self.config.portal_base_url, path)
            if await self._url_exists(full_url):
                return full_url

        # Search portal homepage for download links
        return await self._search_for_download_links()

    async def _search_for_download_links(self) -> Optional[str]:
        """Search portal for bulk download links."""
        try:
            result = await self.scrape(self.config.portal_base_url)
            if not result.success:
                return None

            soup = BeautifulSoup(result.data, 'html.parser')
            portal_config = self.portal_configs.get(self.config.portal_type, {})

            for pattern in portal_config.get("search_patterns", []):
                links = soup.select(pattern)
                for link in links:
                    href = link.get('href')
                    if href:
                        # Check if this looks like a bulk data file
                        if self._looks_like_bulk_data_url(href):
                            return urljoin(self.config.portal_base_url, href)

            return None

        except Exception as e:
            self.logger.error(f"Failed to search for download links: {e}")
            return None

    def _looks_like_bulk_data_url(self, url: str) -> bool:
        """Check if URL looks like it points to bulk property data."""
        url_lower = url.lower()

        # Check for file extensions
        if any(ext in url_lower for ext in ['.csv', '.xml', '.xlsx', '.zip']):
            return True

        # Check for bulk data keywords
        bulk_keywords = [
            'property', 'assessor', 'assessment', 'parcel', 'real_estate',
            'bulk', 'export', 'download', 'data', 'full_export'
        ]

        return any(keyword in url_lower for keyword in bulk_keywords)

    async def _url_exists(self, url: str) -> bool:
        """Check if URL exists and returns data."""
        try:
            async with self.session.head(url) as response:
                return response.status == 200
        except:
            return False

    async def _download_large_file(self, url: str) -> Optional[Path]:
        """Download large file with streaming and progress tracking."""
        try:
            # Generate filename
            filename = self._generate_filename(url)
            file_path = self.data_directory / filename

            self.logger.info(f"Downloading {url} to {file_path}")

            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.error(f"Download failed with status {response.status}")
                    return None

                file_size = int(response.headers.get('content-length', 0))

                # Check file size limit
                if file_size > self.config.max_file_size_mb * 1024 * 1024:
                    self.logger.error(f"File too large: {file_size} bytes")
                    return None

                downloaded = 0
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(self.config.chunk_size_bytes):
                        await f.write(chunk)
                        downloaded += len(chunk)

                        # Progress logging
                        if downloaded % (1024 * 1024) == 0:  # Every MB
                            progress = (downloaded / file_size * 100) if file_size > 0 else 0
                            self.logger.debug(f"Downloaded {downloaded:,} bytes ({progress:.1f}%)")

            self.logger.info(f"Download complete: {downloaded:,} bytes")
            return file_path

        except Exception as e:
            self.logger.error(f"Failed to download {url}: {e}")
            return None

    def _generate_filename(self, url: str) -> str:
        """Generate filename for downloaded file."""
        if self.config.file_name_pattern:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return self.config.file_name_pattern.format(
                timestamp=timestamp,
                date=datetime.now().strftime("%Y%m%d")
            )

        # Generate from URL and timestamp
        parsed_url = urlparse(url)
        base_name = Path(parsed_url.path).name or "property_data"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        return f"{timestamp}_{base_name}"

    def _determine_file_format(self, file_path: Path) -> PropertyDataFormat:
        """Determine file format from extension and content."""
        suffix = file_path.suffix.lower()

        if suffix == '.csv':
            return PropertyDataFormat.CSV
        elif suffix in ['.xml']:
            return PropertyDataFormat.XML
        elif suffix in ['.json']:
            return PropertyDataFormat.JSON
        elif suffix in ['.xlsx', '.xls']:
            return PropertyDataFormat.EXCEL
        elif suffix == '.zip':
            return PropertyDataFormat.ZIP
        else:
            # Try to determine from content
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(1024).decode('utf-8', errors='ignore')

                if header.startswith('<?xml') or '<' in header:
                    return PropertyDataFormat.XML
                elif header.startswith('{') or header.startswith('['):
                    return PropertyDataFormat.JSON
                else:
                    return PropertyDataFormat.CSV  # Default to CSV

            except Exception:
                return PropertyDataFormat.CSV

    async def _process_zip_file(self, zip_path: Path) -> List[PropertyRecord]:
        """Process ZIP file containing property data."""
        properties = []

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if file_info.filename.endswith(('.csv', '.xml', '.json')):
                        # Extract to temp file and process
                        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                            temp_file.write(zip_ref.read(file_info.filename))
                            temp_path = Path(temp_file.name)

                        try:
                            if file_info.filename.endswith('.csv'):
                                batch_properties = await self._process_csv_file(temp_path)
                            elif file_info.filename.endswith('.xml'):
                                batch_properties = await self._process_xml_file(temp_path)
                            elif file_info.filename.endswith('.json'):
                                batch_properties = await self._process_json_file(temp_path)

                            properties.extend(batch_properties)

                        finally:
                            temp_path.unlink()  # Clean up temp file

        except Exception as e:
            self.logger.error(f"Failed to process ZIP file {zip_path}: {e}")

        return properties

    async def _process_csv_file(self, csv_path: Path) -> List[PropertyRecord]:
        """Process CSV file containing property data."""
        properties = []

        try:
            # Read with pandas for better handling of large files and data types
            df = pd.read_csv(csv_path, low_memory=False, dtype=str)

            self.logger.info(f"Processing CSV with {len(df)} rows, {len(df.columns)} columns")

            for _, row in df.iterrows():
                try:
                    property_data = self._map_row_to_property(row.to_dict())
                    if property_data:
                        properties.append(property_data)

                except Exception as e:
                    self.logger.debug(f"Failed to process row: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to process CSV file {csv_path}: {e}")

        return properties

    async def _process_xml_file(self, xml_path: Path) -> List[PropertyRecord]:
        """Process XML file containing property data."""
        properties = []

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Find property records (common XML structures)
            property_elements = (
                root.findall('.//property') or
                root.findall('.//record') or
                root.findall('.//parcel') or
                list(root)  # If root children are property records
            )

            self.logger.info(f"Processing XML with {len(property_elements)} property records")

            for prop_elem in property_elements:
                try:
                    # Convert XML element to dict
                    prop_dict = {}
                    for child in prop_elem:
                        prop_dict[child.tag] = child.text

                    property_data = self._map_row_to_property(prop_dict)
                    if property_data:
                        properties.append(property_data)

                except Exception as e:
                    self.logger.debug(f"Failed to process XML element: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to process XML file {xml_path}: {e}")

        return properties

    async def _process_json_file(self, json_path: Path) -> List[PropertyRecord]:
        """Process JSON file containing property data."""
        properties = []

        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            # Handle different JSON structures
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                # Look for common array keys
                records = (
                    data.get('properties', []) or
                    data.get('records', []) or
                    data.get('data', []) or
                    [data]  # Single record
                )
            else:
                records = []

            self.logger.info(f"Processing JSON with {len(records)} property records")

            for record in records:
                try:
                    property_data = self._map_row_to_property(record)
                    if property_data:
                        properties.append(property_data)

                except Exception as e:
                    self.logger.debug(f"Failed to process JSON record: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to process JSON file {json_path}: {e}")

        return properties

    def _map_row_to_property(self, row_data: Dict[str, Any]) -> Optional[PropertyRecord]:
        """Map raw data row to PropertyRecord using field mapping."""
        try:
            mapped_data = {}

            # Map fields using field mapping configuration
            for model_field, possible_fields in self.field_mapping.items():
                value = None

                for field_name in possible_fields:
                    if field_name in row_data and row_data[field_name]:
                        value = row_data[field_name]
                        break

                if value is not None:
                    mapped_data[model_field] = value

            # Ensure required fields are present
            if not mapped_data.get('parcel_id'):
                return None

            if not mapped_data.get('property_address'):
                return None

            if not mapped_data.get('owner_name'):
                return None

            # Add data source
            mapped_data['data_source'] = f"{self.config.portal_type}_bulk_download"

            # Create and classify property record
            property_record = PropertyRecord(**mapped_data)
            property_record.property_type = property_record.classify_property_type()

            # Apply filters
            if not self._passes_filters(property_record):
                return None

            return property_record

        except Exception as e:
            self.logger.debug(f"Failed to map property data: {e}")
            return None

    def _passes_filters(self, property_record: PropertyRecord) -> bool:
        """Check if property record passes configured filters."""
        # Exclude exempt properties if configured
        if self.config.exclude_exempt and property_record.property_type == PropertyType.EXEMPT:
            return False

        # Check minimum assessed value
        if (self.config.min_assessed_value and
            property_record.assessed_value and
            property_record.assessed_value < self.config.min_assessed_value):
            return False

        # Check property types filter
        if (self.config.property_types_included and
            property_record.property_type.value not in self.config.property_types_included):
            return False

        return True


async def create_property_bulk_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    portal_base_url: str,
    portal_type: str = "qpublic",
    download_format: PropertyDataFormat = PropertyDataFormat.CSV,
    data_directory: Optional[str] = None,
    **kwargs
) -> PropertyAppraiseBulkScraper:
    """Factory function to create configured property appraiser bulk scraper."""

    download_config = BulkDownloadConfig(
        portal_base_url=portal_base_url,
        portal_type=portal_type,
        download_format=download_format,
        **kwargs
    )

    scraper = PropertyAppraiseBulkScraper(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        download_config=download_config,
        data_directory=data_directory,
        **kwargs
    )
    await scraper.initialize()
    return scraper