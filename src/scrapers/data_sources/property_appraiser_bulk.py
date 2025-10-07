"""
Property Appraiser (CAMA) Scraper

Downloads bulk property assessment data from county property appraisers.
Config-driven to support multiple Florida counties.

Data: Properties, owners, sales, assessments, LLC ownership, zoning (use_code)
"""
import csv
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
import structlog

from ...config.schemas import MarketConfig

logger = structlog.get_logger(__name__)


class PropertyRecord:
    """Comprehensive property record model with all 99 CAMA fields."""

    def __init__(self, data: Dict):
        # Identifiers
        self.parcel_id = data.get('parcel_id', '')
        self.account_number = data.get('account_number', '')

        # Owner info
        self.owner_name = data.get('owner_name', '')
        self.owner_address = data.get('owner_address', '')
        self.mailing_address = data.get('mailing_address', '')  # Owner_Mail_Addr2
        self.owner_city = data.get('owner_city', '')
        self.owner_state = data.get('owner_state', '')
        self.owner_zip = data.get('owner_zip', '')

        # Location
        self.property_address = data.get('property_address', '')
        self.latitude = self._parse_float(data.get('latitude'))
        self.longitude = self._parse_float(data.get('longitude'))
        self.city = data.get('city', '')
        self.lot_size_acres = self._parse_float(data.get('lot_size_acres'))
        self.section = data.get('section', '')
        self.township = data.get('township', '')
        self.range_value = data.get('range_value', '')
        self.neighborhood_code = data.get('neighborhood_code', '')
        self.neighborhood_desc = data.get('neighborhood_desc', '')
        self.subdivision_code = data.get('subdivision_code', '')
        self.subdivision_desc = data.get('subdivision_desc', '')

        # Property classification
        self.property_type = data.get('property_type', '')
        self.use_code = data.get('use_code', '')
        self.land_use_code = data.get('land_use_code', '')
        self.land_use_desc = data.get('land_use_desc', '')
        self.land_zoning_code = data.get('land_zoning_code', '')
        self.land_zoning_desc = data.get('land_zoning_desc', '')
        self.land_type = data.get('land_type', '')
        self.land_sqft = self._parse_float(data.get('land_sqft'))

        # Building - primary
        self.year_built = self._parse_int(data.get('year_built'))
        self.effective_year_built = self._parse_int(data.get('effective_year_built'))
        self.square_footage = self._parse_float(data.get('square_footage'))
        self.stories = self._parse_int(data.get('stories'))
        self.improvement_type = data.get('improvement_type', '')
        self.improvement_desc = data.get('improvement_desc', '')

        # Building - attributes
        self.bedrooms = self._parse_int(data.get('bedrooms'))
        self.bathrooms = self._parse_float(data.get('bathrooms'))
        self.roof_type = data.get('roof_type', '')
        self.wall_type = data.get('wall_type', '')
        self.exterior_type = data.get('exterior_type', '')
        self.heat_type = data.get('heat_type', '')
        self.ac_type = data.get('ac_type', '')
        self.building_quality = data.get('building_quality', '')
        self.building_condition = data.get('building_condition', '')

        # All structures - aggregated
        self.total_improvement_sqft = self._parse_float(data.get('total_improvement_sqft'))
        self.total_improvement_count = self._parse_int(data.get('total_improvement_count'))
        self.improvement_types_list = data.get('improvement_types_list', '')
        self.oldest_improvement_year = self._parse_int(data.get('oldest_improvement_year'))
        self.newest_improvement_year = self._parse_int(data.get('newest_improvement_year'))
        self.has_garage = self._parse_bool(data.get('has_garage'))
        self.has_porch = self._parse_bool(data.get('has_porch'))
        self.has_pool = self._parse_bool(data.get('has_pool'))
        self.has_fence = self._parse_bool(data.get('has_fence'))
        self.has_shed = self._parse_bool(data.get('has_shed'))

        # Valuation
        self.market_value = self._parse_float(data.get('market_value'))
        self.assessed_value = self._parse_float(data.get('assessed_value'))
        self.taxable_value = self._parse_float(data.get('taxable_value'))
        self.land_value = self._parse_float(data.get('land_value'))
        self.improvement_value = self._parse_float(data.get('improvement_value'))
        self.valuation_year = self._parse_int(data.get('valuation_year'))

        # Sales
        self.last_sale_date = data.get('last_sale_date', '')
        self.last_sale_price = self._parse_float(data.get('last_sale_price'))
        self.sale_qualified = data.get('sale_qualified', '')
        self.sale_type_vac_imp = data.get('sale_type_vac_imp', '')
        self.sale_book = data.get('sale_book', '')
        self.sale_page = data.get('sale_page', '')

        # Tax exemptions
        # Match CSV: default to 0.0 when no exemptions (not None)
        exemption_amt = self._parse_float(data.get('total_exemption_amount'))
        self.total_exemption_amount = exemption_amt if exemption_amt is not None else 0.0
        self.exemption_types_list = data.get('exemption_types_list', '')
        self.exemption_count = self._parse_int(data.get('exemption_count'))
        self.most_recent_exemption_year = self._parse_int(data.get('most_recent_exemption_year'))

        # Legal & Permits
        self.legal_description = data.get('legal_description', '')
        # Match CSV: default to 0 when no permits (not None)
        permits_count = self._parse_int(data.get('total_permits'))
        self.total_permits = permits_count if permits_count is not None else 0

    def _parse_float(self, value):
        """Parse float from string, handling currency and commas."""
        if not value or value in ['', 'N/A', None]:
            return None
        if isinstance(value, str):
            value = value.replace('$', '').replace(',', '').replace('%', '').strip()
        try:
            return float(value) if value else None
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value):
        """Parse int from string."""
        if not value or value in ['', 'N/A', None]:
            return None
        try:
            return int(float(value)) if value else None
        except (ValueError, TypeError):
            return None

    def _parse_bool(self, value):
        """Parse boolean from various formats."""
        if value is None or value == '':
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 't', 'y')
        return bool(value)

    def is_llc(self) -> bool:
        """Check if owner is an LLC."""
        if not self.owner_name:
            return False
        owner_upper = self.owner_name.upper()
        return any(indicator in owner_upper for indicator in [
            'LLC', 'L.L.C', 'L L C', 'LIMITED LIABILITY'
        ])

    def to_dict(self) -> Dict:
        """Convert to dictionary with all 99 fields."""
        return {
            # Identifiers
            'parcel_id': self.parcel_id,
            'account_number': self.account_number,

            # Owner info
            'owner_name': self.owner_name,
            'owner_address': self.owner_address,
            'owner_city': self.owner_city,
            'owner_state': self.owner_state,
            'owner_zip': self.owner_zip,

            # Location
            'property_address': self.property_address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'city': self.city,
            'lot_size_acres': self.lot_size_acres,
            'section': self.section,
            'township': self.township,
            'range_value': self.range_value,
            'neighborhood_code': self.neighborhood_code,
            'neighborhood_desc': self.neighborhood_desc,
            'subdivision_code': self.subdivision_code,
            'subdivision_desc': self.subdivision_desc,

            # Property classification
            'property_type': self.property_type,
            'use_code': self.use_code,
            'land_use_code': self.land_use_code,
            'land_use_desc': self.land_use_desc,
            'land_zoning_code': self.land_zoning_code,
            'land_zoning_desc': self.land_zoning_desc,
            'land_type': self.land_type,
            'land_sqft': self.land_sqft,

            # Building - primary
            'year_built': self.year_built,
            'effective_year_built': self.effective_year_built,
            'square_footage': self.square_footage,
            'stories': self.stories,
            'improvement_type': self.improvement_type,
            'improvement_desc': self.improvement_desc,

            # Building - attributes
            'bedrooms': self.bedrooms,
            'bathrooms': self.bathrooms,
            'roof_type': self.roof_type,
            'wall_type': self.wall_type,
            'exterior_type': self.exterior_type,
            'heat_type': self.heat_type,
            'ac_type': self.ac_type,
            'building_quality': self.building_quality,
            'building_condition': self.building_condition,

            # All structures - aggregated
            'total_improvement_sqft': self.total_improvement_sqft,
            'total_improvement_count': self.total_improvement_count,
            'improvement_types_list': self.improvement_types_list,
            'oldest_improvement_year': self.oldest_improvement_year,
            'newest_improvement_year': self.newest_improvement_year,
            'has_garage': self.has_garage,
            'has_porch': self.has_porch,
            'has_pool': self.has_pool,
            'has_fence': self.has_fence,
            'has_shed': self.has_shed,

            # Valuation
            'market_value': self.market_value,
            'assessed_value': self.assessed_value,
            'taxable_value': self.taxable_value,
            'land_value': self.land_value,
            'improvement_value': self.improvement_value,
            'valuation_year': self.valuation_year,

            # Sales
            'last_sale_date': self.last_sale_date,
            'last_sale_price': self.last_sale_price,
            'sale_qualified': self.sale_qualified,
            'sale_type_vac_imp': self.sale_type_vac_imp,
            'sale_book': self.sale_book,
            'sale_page': self.sale_page,

            # Tax exemptions
            'total_exemption_amount': self.total_exemption_amount,
            'exemption_types_list': self.exemption_types_list,
            'exemption_count': self.exemption_count,
            'most_recent_exemption_year': self.most_recent_exemption_year,

            # Legal & Permits
            'legal_description': self.legal_description,
            'total_permits': self.total_permits,
        }


class PropertyAppraiserScraper:
    """
    Scraper for county property appraiser CAMA bulk data.

    Supports:
    - QPublic portals (common in Florida)
    - Direct CAMA file downloads
    - CSV parsing with field mapping
    """

    def __init__(self, market_config: MarketConfig):
        """Initialize with market config."""
        self.config = market_config
        self.property_config = market_config.scrapers.property

        if not self.property_config or not self.property_config.enabled:
            raise ValueError("Property scraper not enabled in config")

        self.base_url = self.property_config.portal_base_url
        self.portal_type = self.property_config.portal_type
        self.county_code = self.property_config.county_code
        self.download_url = self.property_config.download_url_pattern

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; DominionScraper/1.0; +https://example.com/bot)'
        })

        logger.info("property_scraper_initialized",
                   county=self.county_code,
                   portal_type=self.portal_type)

    def fetch_property_data(self, limit: Optional[int] = None, local_first: bool = True) -> List[PropertyRecord]:
        """
        Fetch property data from the configured source.

        Args:
            limit: Max number of records to fetch (for testing)
            local_first: Check for local CAMA files before downloading (default: True)

        Returns:
            List of PropertyRecord objects

        Auto-downloads CAMA files if not found locally.
        Auto-downloads GIS shapefile if not found locally.
        """
        logger.info("property_fetch_started", local_first=local_first)

        # Try local files first if enabled
        if local_first:
            local_cama = self._find_local_cama_files()
            if local_cama:
                logger.info("using_local_cama_files", files=list(local_cama.keys()))
                records = self._parse_and_join_cama_files(local_cama, limit=limit)
                logger.info("fetch_property_completed", records_count=len(records), source="local")
                return records

        # Download if not found locally
        logger.info("downloading_cama_from_web")
        download_url = self._find_download_url()
        if not download_url:
            logger.error("download_url_not_found")
            return []

        file_path = self._download_file(download_url)
        if not file_path:
            logger.error("download_failed")
            return []

        records = self._parse_cama_file(file_path, limit=limit)

        logger.info("fetch_property_completed", records_count=len(records), source="download")

        return records

    def _find_local_cama_files(self) -> Optional[Dict[str, Path]]:
        """
        Find local CAMA files in common locations.

        Returns dict of {file_type: Path} if found, None otherwise.
        """
        search_paths = [
            Path("CAMA"),
            Path(__file__).parent.parent.parent.parent / "CAMA",
        ]

        for base_path in search_paths:
            if not base_path.exists():
                continue

            cama_files = {}
            for txt_file in base_path.glob('*.txt'):
                name_lower = txt_file.name.lower()
                if name_lower == 'property.txt':
                    cama_files['property'] = txt_file
                elif name_lower == 'owners.txt':
                    cama_files['owners'] = txt_file
                elif name_lower == 'sales.txt':
                    cama_files['sales'] = txt_file
                elif name_lower == 'historyre.txt':
                    cama_files['history'] = txt_file
                elif name_lower == 'improvements.txt':
                    cama_files['improvements'] = txt_file
                elif name_lower == 'imprvattributes.txt':
                    cama_files['imprv_attributes'] = txt_file
                elif name_lower == 'imprvdetails.txt':
                    cama_files['imprv_details'] = txt_file
                elif name_lower == 'land.txt':
                    cama_files['land'] = txt_file
                elif name_lower == 'legals.txt':
                    cama_files['legals'] = txt_file
                elif name_lower == 'permits.txt':
                    cama_files['permits'] = txt_file
                elif name_lower == 'exemptionsre_history.txt':
                    cama_files['exemptions'] = txt_file

            # Must have at least Property.txt to be valid
            if cama_files.get('property'):
                return cama_files

        return None

    def _find_download_url(self) -> Optional[str]:
        """Find the CAMA download URL."""
        # If explicit URL provided, use it
        if self.download_url:
            if self.download_url.startswith('http'):
                return self.download_url
            else:
                return f"{self.base_url.rstrip('/')}/{self.download_url.lstrip('/')}"

        # Try common patterns based on portal type
        if self.portal_type == "qpublic":
            # QPublic pattern: /downloads or /data
            common_paths = [
                '/downloads',
                '/data',
                '/bulk',
                '/export',
            ]

            for path in common_paths:
                test_url = f"{self.base_url.rstrip('/')}{path}"
                try:
                    response = self.session.head(test_url, timeout=10)
                    if response.status_code == 200:
                        return test_url
                except Exception as e:
                    continue

        try:
            response = self.session.get(self.base_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                for link in soup.find_all('a', href=True):
                    href = link['href'].lower()
                    if any(keyword in href for keyword in ['download', 'export', 'bulk', 'cama', '.csv', '.zip']):
                        if href.startswith('http'):
                            return href
                        else:
                            return f"{self.base_url.rstrip('/')}/{href.lstrip('/')}"
        except Exception as e:
            logger.error("download_url_search_failed", error=str(e))

        return f"{self.base_url}/downloads"

    def _download_file(self, url: str) -> Optional[Path]:
        """Download CAMA file."""
        try:
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')

            if 'zip' in content_type or url.endswith('.zip'):
                suffix = '.zip'
            elif 'csv' in content_type or url.endswith('.csv'):
                suffix = '.csv'
            else:
                suffix = '.txt'

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)

            temp_file.close()

            file_path = Path(temp_file.name)
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            logger.info("file_downloaded", size_mb=f"{file_size_mb:.2f}")

            return file_path

        except Exception as e:
            logger.error("file_download_failed", error=str(e))
            return None

    def _parse_cama_file(self, file_path: Path, limit: Optional[int] = None) -> List[PropertyRecord]:
        """Parse CAMA file (CSV or ZIP containing CSVs)."""
        records = []

        try:
            # Handle ZIP files
            if file_path.suffix == '.zip':
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    # Extract to temp directory
                    temp_dir = tempfile.mkdtemp()
                    zip_ref.extractall(temp_dir)
                    temp_path = Path(temp_dir)

                    # Find ALL key files in CAMA ZIP
                    cama_files = {}

                    for csv_file in temp_path.glob('*.txt'):
                        name_lower = csv_file.name.lower()

                        # Core files
                        if name_lower == 'property.txt':
                            cama_files['property'] = csv_file
                        elif name_lower == 'owners.txt':
                            cama_files['owners'] = csv_file
                        elif name_lower == 'sales.txt':
                            cama_files['sales'] = csv_file

                        # CRITICAL: Assessment values and year built
                        elif name_lower == 'historyre.txt':
                            cama_files['history'] = csv_file
                        elif name_lower == 'improvements.txt':
                            cama_files['improvements'] = csv_file

                        # Additional detail files
                        elif name_lower == 'imprvattributes.txt':
                            cama_files['imprv_attributes'] = csv_file
                        elif name_lower == 'imprvdetails.txt':
                            cama_files['imprv_details'] = csv_file
                        elif name_lower == 'land.txt':
                            cama_files['land'] = csv_file
                        elif name_lower == 'legals.txt':
                            cama_files['legals'] = csv_file
                        elif name_lower == 'permits.txt':
                            cama_files['permits'] = csv_file
                        elif name_lower == 'exemptionsre_history.txt':
                            cama_files['exemptions'] = csv_file

                    if cama_files.get('property'):
                        logger.info("cama_files_found", files=list(cama_files.keys()))
                        records = self._parse_and_join_cama_files(cama_files, limit)
                    else:
                        csv_files = list(temp_path.glob('*.csv')) + list(temp_path.glob('*.txt'))
                        if csv_files:
                            records = self._parse_csv(csv_files[0], limit)

            else:
                records = self._parse_csv(file_path, limit)

        except Exception as e:
            logger.error("cama_parse_failed", error=str(e))

        # Merge GIS coordinates if available
        if records:
            records = self._merge_gis_coordinates(records)

        return records

    def _parse_and_join_cama_files(
        self,
        cama_files: Dict[str, Path],
        limit: Optional[int] = None
    ) -> List[PropertyRecord]:
        """
        Parse and join ALL CAMA files on parcel ID.

        Files joined:
        - Property.txt (base)
        - Owners.txt (owner info)
        - Sales.txt (sales history)
        - HistoryRE.txt (CRITICAL: assessed_value, market_value, land_value)
        - Improvements.txt (CRITICAL: year_built, heated_sqft)
        - ImprvAttributes.txt (building attributes)
        - ImprvDetails.txt (detailed building info)
        - Land.txt (land characteristics)
        - Legals.txt (legal descriptions)
        - Permits.txt (permit history)
        - ExemptionsRE_History.txt (exemptions)
        """
        records = []

        try:
            # Load all lookup dictionaries indexed by Parcel ID
            lookup_tables = {}

            # Owners
            if cama_files.get('owners'):
                logger.info("loading_owners_data")
                lookup_tables['owners'] = {}
                with open(cama_files['owners'], 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f, delimiter='\t')
                    for row in reader:
                        parcel = row.get('Parcel', '').strip()
                        if parcel:
                            lookup_tables['owners'][parcel] = row

            # Sales (get most recent sale per parcel)
            if cama_files.get('sales'):
                logger.info("loading_sales_data")
                lookup_tables['sales'] = {}
                with open(cama_files['sales'], 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f, delimiter='\t')
                    for row in reader:
                        parcel = row.get('Parcel', '').strip()
                        if parcel and parcel not in lookup_tables['sales']:
                            lookup_tables['sales'][parcel] = row

            # HistoryRE (get LATEST tax year per parcel - contains assessed/market values)
            if cama_files.get('history'):
                logger.info("loading_history_data")
                lookup_tables['history'] = {}
                with open(cama_files['history'], 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f, delimiter='\t')
                    for row in reader:
                        parcel = row.get('Parcel', '').strip()
                        if parcel:
                            # Keep latest tax year only
                            if parcel not in lookup_tables['history']:
                                lookup_tables['history'][parcel] = row
                            else:
                                current_year = int(row.get('Hist_Tax_Year', 0) or 0)
                                existing_year = int(lookup_tables['history'][parcel].get('Hist_Tax_Year', 0) or 0)
                                if current_year > existing_year:
                                    lookup_tables['history'][parcel] = row

            # Improvements (get most recent improvement per parcel - contains year_built)
            if cama_files.get('improvements'):
                logger.info("loading_improvements_data")
                lookup_tables['improvements'] = {}
                with open(cama_files['improvements'], 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f, delimiter='\t')
                    for row in reader:
                        parcel = row.get('Parcel', '').strip()
                        if parcel:
                            # Get latest tax year improvement
                            if parcel not in lookup_tables['improvements']:
                                lookup_tables['improvements'][parcel] = row
                            else:
                                current_year = int(row.get('TaxYear', 0) or 0)
                                existing_year = int(lookup_tables['improvements'][parcel].get('TaxYear', 0) or 0)
                                if current_year > existing_year:
                                    lookup_tables['improvements'][parcel] = row

            # ImprvAttributes (building attributes - get first/primary)
            if cama_files.get('imprv_attributes'):
                logger.info("loading_imprv_attributes_data")
                lookup_tables['imprv_attributes'] = {}
                with open(cama_files['imprv_attributes'], 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f, delimiter='\t')
                    for row in reader:
                        parcel = row.get('Parcel', '').strip()
                        if parcel and parcel not in lookup_tables['imprv_attributes']:
                            lookup_tables['imprv_attributes'][parcel] = row

            # Land
            if cama_files.get('land'):
                logger.info("loading_land_data")
                lookup_tables['land'] = {}
                with open(cama_files['land'], 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f, delimiter='\t')
                    for row in reader:
                        parcel = row.get('Parcel', '').strip()
                        if parcel and parcel not in lookup_tables['land']:
                            lookup_tables['land'][parcel] = row

            # Legals
            if cama_files.get('legals'):
                logger.info("loading_legals_data")
                lookup_tables['legals'] = {}
                with open(cama_files['legals'], 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f, delimiter='\t')
                    for row in reader:
                        parcel = row.get('Parcel', '').strip()
                        if parcel and parcel not in lookup_tables['legals']:
                            lookup_tables['legals'][parcel] = row

            # AGGREGATED DATA: Aggregate ImprvDetails, Permits, Exemptions
            if cama_files.get('imprv_details'):
                logger.info("aggregating_improvement_details")
                lookup_tables['imprv_details_agg'] = self._aggregate_improvements(cama_files['imprv_details'])

            if cama_files.get('permits'):
                logger.info("aggregating_permits")
                lookup_tables['permits_agg'] = self._aggregate_permits(cama_files['permits'])

            if cama_files.get('exemptions'):
                logger.info("aggregating_exemptions")
                lookup_tables['exemptions_agg'] = self._aggregate_exemptions(cama_files['exemptions'])

            # Join all data on Property.txt
            property_file = cama_files['property']
            with open(property_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f, delimiter='\t')

                for i, row in enumerate(reader):
                    if limit and i >= limit:
                        break

                    parcel = row.get('Parcel', '').strip()

                    # Merge ALL related data
                    if parcel in lookup_tables.get('owners', {}):
                        row.update(lookup_tables['owners'][parcel])

                    if parcel in lookup_tables.get('sales', {}):
                        row.update(lookup_tables['sales'][parcel])

                    if parcel in lookup_tables.get('history', {}):
                        row.update(lookup_tables['history'][parcel])

                    if parcel in lookup_tables.get('improvements', {}):
                        row.update(lookup_tables['improvements'][parcel])

                    if parcel in lookup_tables.get('imprv_attributes', {}):
                        row.update(lookup_tables['imprv_attributes'][parcel])

                    if parcel in lookup_tables.get('land', {}):
                        row.update(lookup_tables['land'][parcel])

                    if parcel in lookup_tables.get('legals', {}):
                        row.update(lookup_tables['legals'][parcel])

                    # Merge aggregated data
                    if parcel in lookup_tables.get('imprv_details_agg', {}):
                        row.update(lookup_tables['imprv_details_agg'][parcel])

                    if parcel in lookup_tables.get('permits_agg', {}):
                        row['total_permits'] = lookup_tables['permits_agg'][parcel]

                    if parcel in lookup_tables.get('exemptions_agg', {}):
                        row.update(lookup_tables['exemptions_agg'][parcel])

                    data = self._map_fields(row)

                    # FALLBACK: Use oldest_improvement_year for year_built if empty (matches CSV logic)
                    if not data.get('year_built') and data.get('oldest_improvement_year'):
                        data['year_built'] = data['oldest_improvement_year']

                    if data.get('parcel_id'):
                        record = PropertyRecord(data)
                        records.append(record)

            logger.info("cama_files_joined",
                       records_count=len(records),
                       files_used=len(lookup_tables))

        except Exception as e:
            logger.error("cama_join_failed", error=str(e))
            import traceback
            traceback.print_exc()

        # ALWAYS merge GIS coordinates after parsing (matches CSV workflow)
        if records:
            records = self._merge_gis_coordinates(records)

        return records

    def _parse_csv(self, file_path: Path, limit: Optional[int] = None) -> List[PropertyRecord]:
        """Parse CSV file into PropertyRecords."""
        records = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect delimiter
                sample = f.read(1024)
                f.seek(0)

                delimiter = '\t' if '\t' in sample else ','

                reader = csv.DictReader(f, delimiter=delimiter)

                for i, row in enumerate(reader):
                    if limit and i >= limit:
                        break

                    # Map fields (try common field names)
                    data = self._map_fields(row)

                    if data.get('parcel_id') or data.get('property_address'):
                        record = PropertyRecord(data)
                        records.append(record)

            logger.info("csv_parsed", records_count=len(records))

        except Exception as e:
            logger.error("csv_parse_failed", error=str(e))

        return records

    def _map_fields(self, row: Dict) -> Dict:
        """
        Map CSV fields to standard property record fields.
        Handles different field naming conventions.
        """
        # Create case-insensitive lookup
        row_lower = {k.lower().strip(): v for k, v in row.items()}

        # Common field mappings for different formats - COMPREHENSIVE (99 fields)
        field_mappings = {
            # Core property fields
            'parcel_id': ['parcel', 'parcel_id', 'parcelid', 'pin', 'property_id', 'folio'],
            'account_number': ['prop_id', 'account', 'account_number', 'acct', 'acct_num'],
            'property_address': ['property_address', 'site_address', 'address', 'location', 'situs'],

            # Owner fields (from Owners.txt)
            'owner_name': ['owner_mail_name', 'owner_name', 'owner', 'owner1', 'name', 'taxpayer'],
            'owner_address': ['owner_mail_addr1', 'owner_address', 'owner_addr'],  # Primary address line
            'mailing_address': ['owner_mail_addr2'],  # Secondary address line (matches CSV)
            'owner_city': ['owner_mail_city', 'owner_city', 'mail_city'],
            'owner_state': ['owner_mail_state', 'owner_state', 'mail_state'],
            'owner_zip': ['owner_mail_zip', 'owner_zip', 'mail_zip', 'zip'],

            # Location fields
            'latitude': ['latitude', 'lat', 'y'],
            'longitude': ['longitude', 'lon', 'long', 'x'],
            'city': ['city_desc', 'city', 'municipality'],
            'section': ['section', 'sec'],
            'township': ['township', 'twp'],
            'range_value': ['range', 'rng'],
            'neighborhood_code': ['nbhd_code', 'neighborhood_code', 'neighborhood'],
            'neighborhood_desc': ['nbhd_desc', 'neighborhood_desc', 'neighborhood_name'],
            'subdivision_code': ['sbdv_code', 'subdivision_code', 'subdiv_code'],
            'subdivision_desc': ['sbdv_desc', 'subdivision_desc', 'subdivision', 'subdiv'],

            # Property classification
            'property_type': ['prop_use_desc', 'property_type', 'use_desc', 'property_use'],
            'use_code': ['prop_use_code', 'use_code', 'usecode', 'land_use', 'dor_uc', 'propertyuse'],
            'land_use_code': ['land_use_code', 'landuse', 'lu_code'],
            'land_use_desc': ['land_use_desc', 'land_use', 'lu_desc'],
            'land_zoning_code': ['land_zoning_code', 'zoning_code', 'zoning'],
            'land_zoning_desc': ['land_zoning_desc', 'zoning_desc', 'zone_desc'],
            'land_type': ['land_type', 'landtype'],
            'land_sqft': ['land_sqft', 'land_sf', 'landsqft'],

            # Building - primary (from Improvements.txt and Property.txt)
            'year_built': ['actual_yrblt', 'year_built', 'yearbuilt', 'yr_built', 'yr_blt', 'actual_year'],
            'effective_year_built': ['effective_yrblt', 'effective_year_built', 'eff_year_built'],
            'square_footage': ['heated_squarefeet', 'htdsqft', 'totsqft', 'square_footage', 'sqft', 'total_area', 'building_area', 'heated_area'],
            'stories': ['stories', 'story', 'num_stories'],
            'improvement_type': ['imprv_type', 'improvement_type', 'bldg_type'],
            'improvement_desc': ['imprv_desc', 'improvement_desc', 'bldg_desc'],
            'lot_size_acres': ['acres', 'lot_size_acres', 'acreage', 'land_area'],

            # Building attributes (from ImprvAttributes.txt)
            'bedrooms': ['bedrooms', 'beds', 'bdrms', 'br', 'bed_count'],
            'bathrooms': ['bathrooms', 'baths', 'bath', 'full_bath', 'bath_count'],
            'roof_type': ['roof_type', 'roof', 'roofing'],
            'wall_type': ['wall_type', 'wall', 'walls'],
            'exterior_type': ['exterior_type', 'exterior', 'ext_type'],
            'heat_type': ['heat_type', 'heat', 'heating'],
            'ac_type': ['ac_type', 'ac', 'air_conditioning', 'cooling'],
            'building_quality': ['quality', 'bldg_quality', 'grade'],
            'building_condition': ['condition', 'bldg_condition'],

            # Assessment values (from HistoryRE.txt)
            'assessed_value': ['county_assessed_value', 'school_assessed_value', 'assessed_value', 'assessment', 'assessed'],
            'market_value': ['just_value', 'market_value', 'appraised_value', 'fmv'],
            'taxable_value': ['county_taxable_value', 'school_taxable_value', 'taxable_value', 'taxable', 'tax_value'],
            'land_value': ['land_value', 'landval', 'land'],
            'improvement_value': ['improvement_value', 'improvementval', 'bldg_value'],
            'valuation_year': ['hist_tax_year', 'tax_year', 'valuation_year', 'year'],

            # Sales info (from Sales.txt)
            'last_sale_date': ['sale_date', 'last_sale_date', 'saledate', 'or_date'],
            'last_sale_price': ['sale_price', 'last_sale_price', 'saleprice', 'or_value'],
            'sale_qualified': ['sale_qualified', 'qualified', 'qual'],
            'sale_type_vac_imp': ['sale_vac_imp', 'vac_imp', 'vacant_improved'],
            'sale_book': ['sale_book', 'book', 'or_book'],
            'sale_page': ['sale_page', 'page', 'or_page'],

            # Legal description (from Legals.txt)
            'legal_description': ['legal_desc', 'legal_description', 'legal'],

            # Aggregated fields - will be populated by aggregation logic
            'total_improvement_sqft': ['total_improvement_sqft'],
            'total_improvement_count': ['total_improvement_count'],
            'improvement_types_list': ['improvement_types', 'improvement_types_list'],
            'oldest_improvement_year': ['oldest_improvement_year'],
            'newest_improvement_year': ['newest_improvement_year'],
            'has_garage': ['has_garage'],
            'has_porch': ['has_porch'],
            'has_pool': ['has_pool'],
            'has_fence': ['has_fence'],
            'has_shed': ['has_shed'],
            'total_exemption_amount': ['total_exemption_amount'],
            'exemption_types_list': ['exemption_types', 'exemption_types_list'],
            'exemption_count': ['exemption_count'],
            'most_recent_exemption_year': ['most_recent_exemption_year'],
            'total_permits': ['total_permits'],
        }

        mapped_data = {}

        for field, possible_names in field_mappings.items():
            for name in possible_names:
                if name in row_lower:
                    value = row_lower[name]
                    # Skip empty/null values - try next field name
                    if value is not None and value != '':
                        # Handle string values
                        if isinstance(value, str):
                            value = value.strip()
                            if value.upper() in ['NULL', 'N/A', 'NONE', '']:
                                continue
                        # Accept non-string values as-is (int, float, etc.)
                        mapped_data[field] = value
                        break
            # If no non-empty value found, set to None explicitly
            if field not in mapped_data:
                mapped_data[field] = None

        # Build complete mailing address from components (Owners.txt has separate city/state/zip)
        if mapped_data.get('owner_address'):
            # Check if we have city/state/zip to append
            city = row_lower.get('owner_mail_city', '')
            if isinstance(city, str):
                city = city.strip()
            state = row_lower.get('owner_mail_state', '')
            if isinstance(state, str):
                state = state.strip()
            zip_code = row_lower.get('owner_mail_zip', '')
            if isinstance(zip_code, str):
                zip_code = zip_code.strip()

            # Build full address: "123 MAIN ST, CITY, ST ZIP"
            address_parts = [mapped_data['owner_address']]
            if city:
                address_parts.append(city)
            if state and zip_code:
                address_parts.append(f"{state} {zip_code}")
            elif state:
                address_parts.append(state)
            elif zip_code:
                address_parts.append(zip_code)

            if len(address_parts) > 1:
                mapped_data['owner_address'] = ', '.join(address_parts)

        return mapped_data

    def _aggregate_improvements(self, file_path: Path) -> Dict[str, Dict]:
        """
        Aggregate ImprvDetails.txt data per parcel.

        Calculates:
        - total_improvement_sqft
        - total_improvement_count
        - improvement_types_list
        - oldest_improvement_year, newest_improvement_year
        - has_garage, has_porch, has_pool, has_fence, has_shed
        """
        aggregated = {}

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f, delimiter='\t')

                for row in reader:
                    parcel = row.get('Parcel', '')
                    if isinstance(parcel, str):
                        parcel = parcel.strip()
                    if not parcel:
                        continue
                    parcel = str(parcel)  # Ensure it's a string

                    if parcel not in aggregated:
                        aggregated[parcel] = {
                            'total_improvement_sqft': 0,
                            'total_improvement_count': 0,
                            'improvement_types': [],
                            'oldest_improvement_year': None,
                            'newest_improvement_year': None,
                            'has_garage': False,
                            'has_porch': False,
                            'has_pool': False,
                            'has_fence': False,
                            'has_shed': False,
                        }

                    # Aggregate square footage
                    sqft = row.get('Imprv_SqFt', '')
                    if isinstance(sqft, str):
                        sqft = sqft.strip()
                    if sqft:
                        try:
                            aggregated[parcel]['total_improvement_sqft'] += float(sqft)
                        except:
                            pass

                    aggregated[parcel]['total_improvement_count'] += 1

                    # Track improvement types
                    impr_desc = str(row.get('Imprv_Desc', '')).upper()
                    if impr_desc and impr_desc != 'NAN':
                        aggregated[parcel]['improvement_types'].append(impr_desc)

                        # Check for specific features
                        if 'GARAGE' in impr_desc or 'CARPORT' in impr_desc:
                            aggregated[parcel]['has_garage'] = True
                        if 'PORCH' in impr_desc or 'DECK' in impr_desc or 'PATIO' in impr_desc:
                            aggregated[parcel]['has_porch'] = True
                        if 'POOL' in impr_desc or 'SPA' in impr_desc:
                            aggregated[parcel]['has_pool'] = True
                        if 'FENCE' in impr_desc:
                            aggregated[parcel]['has_fence'] = True
                        if 'SHED' in impr_desc or 'STORAGE' in impr_desc or 'BARN' in impr_desc:
                            aggregated[parcel]['has_shed'] = True

                    # Track years
                    year = row.get('Year', '')
                    if isinstance(year, str):
                        year = year.strip()
                    if year:
                        try:
                            year_int = int(float(year))
                            if year_int > 0:
                                if aggregated[parcel]['oldest_improvement_year'] is None or year_int < aggregated[parcel]['oldest_improvement_year']:
                                    aggregated[parcel]['oldest_improvement_year'] = year_int
                                if aggregated[parcel]['newest_improvement_year'] is None or year_int > aggregated[parcel]['newest_improvement_year']:
                                    aggregated[parcel]['newest_improvement_year'] = year_int
                        except:
                            pass

            # Join improvement types into comma-separated list
            for parcel in aggregated:
                aggregated[parcel]['improvement_types_list'] = ', '.join(set(aggregated[parcel]['improvement_types']))
                del aggregated[parcel]['improvement_types']

            logger.info("improvements_aggregated", parcels_count=len(aggregated))

        except Exception as e:
            logger.error("improvements_aggregation_failed", error=str(e))

        return aggregated

    def _aggregate_permits(self, file_path: Path) -> Dict[str, int]:
        """Count total permits per parcel."""
        permits_count = {}

        try:
            # Increase CSV field size limit for large permit text fields
            # Set to 10MB instead of sys.maxsize to avoid overflow on Windows
            csv.field_size_limit(10485760)

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    parcel = row.get('Parcel', '')
                    if isinstance(parcel, str):
                        parcel = parcel.strip()
                    parcel = str(parcel) if parcel else ''
                    if parcel:
                        permits_count[parcel] = permits_count.get(parcel, 0) + 1

            logger.info("permits_aggregated", parcels_count=len(permits_count))

        except Exception as e:
            logger.error("permits_aggregation_failed", error=str(e))

        return permits_count

    def _aggregate_exemptions(self, file_path: Path) -> Dict[str, Dict]:
        """
        Aggregate ExemptionsRE_History.txt data per parcel.

        IMPORTANT: Uses MOST RECENT YEAR ONLY (matches CSV script logic)

        Calculates:
        - total_exemption_amount (from most recent year)
        - exemption_types_list (from most recent year)
        - exemption_count (all years)
        - most_recent_exemption_year
        """
        exemptions = {}
        all_rows = []

        try:
            # First pass: collect all rows
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    parcel = row.get('Parcel', '')
                    if isinstance(parcel, str):
                        parcel = parcel.strip()
                    parcel = str(parcel) if parcel else ''
                    if parcel:
                        all_rows.append(row)

            # Second pass: group by parcel and find most recent year
            parcel_groups = {}
            for row in all_rows:
                parcel = str(row.get('Parcel', '')).strip()
                if parcel not in parcel_groups:
                    parcel_groups[parcel] = []
                parcel_groups[parcel].append(row)

            # Third pass: aggregate per parcel using MOST RECENT YEAR
            for parcel, rows in parcel_groups.items():
                # Find most recent year
                most_recent_year = None
                for row in rows:
                    year = row.get('Hist_Tax_Year', '')  # CORRECT FIELD NAME
                    if isinstance(year, str):
                        year = year.strip()
                    if year:
                        try:
                            year_int = int(year)
                            if most_recent_year is None or year_int > most_recent_year:
                                most_recent_year = year_int
                        except:
                            pass

                exemptions[parcel] = {
                    'total_exemption_amount': 0,
                    'exemption_types': [],
                    'exemption_count': len(rows),  # Count ALL exemptions
                    'most_recent_exemption_year': most_recent_year
                }

                # Sum exemptions ONLY from most recent year (matches CSV logic)
                for row in rows:
                    year = row.get('Hist_Tax_Year', '')  # CORRECT FIELD NAME
                    if isinstance(year, str):
                        year = year.strip()

                    # Only process most recent year
                    if year:
                        try:
                            year_int = int(year)
                            if year_int == most_recent_year:
                                # Sum amount
                                amount = row.get('Hist_Ex_Amount', '')  # CORRECT FIELD NAME
                                if isinstance(amount, str):
                                    amount = amount.strip()
                                if amount:
                                    try:
                                        exemptions[parcel]['total_exemption_amount'] += float(str(amount).replace(',', ''))
                                    except:
                                        pass

                                # Track type
                                exemp_type = row.get('Hist_Ex_Desc', '')  # CORRECT FIELD NAME
                                if isinstance(exemp_type, str):
                                    exemp_type = exemp_type.strip()
                                if exemp_type:
                                    exemptions[parcel]['exemption_types'].append(str(exemp_type))
                        except:
                            pass

                # Join exemption types
                exemptions[parcel]['exemption_types_list'] = ', '.join(set(exemptions[parcel]['exemption_types']))
                del exemptions[parcel]['exemption_types']

            logger.info("exemptions_aggregated", parcels_count=len(exemptions))

        except Exception as e:
            logger.error("exemptions_aggregation_failed", error=str(e))

        return exemptions

    def _merge_gis_coordinates(self, records: List[PropertyRecord]) -> List[PropertyRecord]:
        """
        Merge coordinates from GIS shapefile into property records.

        Auto-downloads shapefile if missing using GIS scraper.
        """
        try:
            # Try to import geopandas
            try:
                import geopandas as gpd
            except ImportError:
                logger.warning("geopandas_not_installed", message="Skipping GIS coordinate merge")
                return records

            # Look for shapefile in common locations
            shapefile_paths = [
                Path("publicparcels/PublicParcels.shp"),
                Path(__file__).parent.parent.parent.parent / "publicparcels" / "PublicParcels.shp",
            ]

            shapefile_path = None
            for path in shapefile_paths:
                if path.exists():
                    shapefile_path = path
                    break

            # AUTO-DOWNLOAD if not found
            if not shapefile_path:
                logger.info("gis_shapefile_not_found", message="Attempting to download from GIS server")
                try:
                    from .gis_shapefile_downloader import GISScraper

                    # Download parcels layer
                    gis_scraper = GISScraper(self.config)
                    gis_features = gis_scraper.fetch_layer('parcels', limit=None)  # Get ALL parcels

                    if gis_features:
                        # Convert GISFeature objects to GeoDataFrame
                        import geopandas as gpd
                        from shapely.geometry import shape

                        # Convert features to dictionaries
                        features_data = []
                        for feature in gis_features:
                            data = feature.to_dict()
                            # Convert geometry dict to shapely geometry
                            if 'geometry' in data and data['geometry']:
                                data['geometry'] = shape(data['geometry'])
                            features_data.append(data)

                        # Create GeoDataFrame with CRS (EPSG:4326 = WGS84 lat/lon)
                        gdf = gpd.GeoDataFrame(features_data, crs="EPSG:4326")

                        # Create output directory
                        output_dir = Path("publicparcels")
                        output_dir.mkdir(exist_ok=True)

                        # Save shapefile
                        shapefile_path = output_dir / "PublicParcels.shp"
                        gdf.to_file(shapefile_path)
                        logger.info("gis_shapefile_downloaded", path=str(shapefile_path), features=len(gis_features))
                    else:
                        logger.warning("gis_download_failed", message="No features returned from GIS server")
                        return records
                except Exception as e:
                    logger.warning("gis_download_error", error=str(e), message="Skipping coordinate merge")
                    return records

            if not shapefile_path:
                logger.info("gis_shapefile_unavailable", message="Skipping coordinate merge")
                return records

            logger.info("loading_gis_coordinates", shapefile=str(shapefile_path))

            # Load shapefile
            gdf = gpd.read_file(shapefile_path)

            # Convert to WGS84 (EPSG:4326) and get centroids
            gdf_wgs84 = gdf.to_crs(epsg=4326)
            gdf_wgs84['latitude'] = gdf_wgs84.geometry.centroid.y
            gdf_wgs84['longitude'] = gdf_wgs84.geometry.centroid.x

            # Create lookup by parcel (use first geometry for each parcel to avoid duplicates)
            gis_lookup = {}
            for idx, row in gdf_wgs84.iterrows():
                parcel = str(row.get('Name', '')).strip()
                if parcel and parcel not in gis_lookup:  # Take first geometry only
                    gis_lookup[parcel] = {
                        'latitude': round(row['latitude'], 8),
                        'longitude': round(row['longitude'], 8)
                    }

            logger.info("gis_coordinates_loaded", parcels_count=len(gis_lookup))

            # Merge coordinates into records
            matched = 0
            for record in records:
                coords = gis_lookup.get(record.parcel_id)
                if coords:
                    record.latitude = coords['latitude']
                    record.longitude = coords['longitude']
                    matched += 1

            logger.info("gis_coordinates_merged", matched=matched, total=len(records))

        except Exception as e:
            logger.warning("gis_coordinate_merge_failed", error=str(e))

        return records

    def get_summary_stats(self, records: List[PropertyRecord]) -> Dict:
        """Get summary statistics from property records."""
        if not records:
            return {}

        total_properties = len(records)
        llc_owned = sum(1 for r in records if r.is_llc())

        assessed_values = [r.assessed_value for r in records if r.assessed_value]
        market_values = [r.market_value for r in records if r.market_value]

        stats = {
            'total_properties': total_properties,
            'llc_owned': llc_owned,
            'llc_percentage': (llc_owned / total_properties * 100) if total_properties else 0,
            'avg_assessed_value': sum(assessed_values) / len(assessed_values) if assessed_values else 0,
            'avg_market_value': sum(market_values) / len(market_values) if market_values else 0,
            'total_assessed_value': sum(assessed_values) if assessed_values else 0,
        }

        return stats
