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
    """Simple property record model."""

    def __init__(self, data: Dict):
        self.parcel_id = data.get('parcel_id', '')
        self.account_number = data.get('account_number', '')
        self.property_address = data.get('property_address', '')
        self.owner_name = data.get('owner_name', '')
        self.owner_address = data.get('owner_address', '')
        self.use_code = data.get('use_code', '')  # Zoning/land use code

        # Assessment values
        self.assessed_value = self._parse_float(data.get('assessed_value'))
        self.market_value = self._parse_float(data.get('market_value'))
        self.taxable_value = self._parse_float(data.get('taxable_value'))
        self.land_value = self._parse_float(data.get('land_value'))

        # Characteristics
        self.year_built = self._parse_int(data.get('year_built'))
        self.square_footage = self._parse_float(data.get('square_footage'))
        self.lot_size_acres = self._parse_float(data.get('lot_size_acres'))
        self.bedrooms = self._parse_int(data.get('bedrooms'))
        self.bathrooms = self._parse_float(data.get('bathrooms'))

        # Sale info
        self.last_sale_date = data.get('last_sale_date', '')
        self.last_sale_price = self._parse_float(data.get('last_sale_price'))

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

    def is_llc(self) -> bool:
        """Check if owner is an LLC."""
        if not self.owner_name:
            return False
        owner_upper = self.owner_name.upper()
        return any(indicator in owner_upper for indicator in [
            'LLC', 'L.L.C', 'L L C', 'LIMITED LIABILITY'
        ])

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'parcel_id': self.parcel_id,
            'account_number': self.account_number,
            'property_address': self.property_address,
            'owner_name': self.owner_name,
            'owner_address': self.owner_address,
            'use_code': self.use_code,
            'assessed_value': self.assessed_value,
            'market_value': self.market_value,
            'taxable_value': self.taxable_value,
            'land_value': self.land_value,
            'year_built': self.year_built,
            'square_footage': self.square_footage,
            'lot_size_acres': self.lot_size_acres,
            'bedrooms': self.bedrooms,
            'bathrooms': self.bathrooms,
            'last_sale_date': self.last_sale_date,
            'last_sale_price': self.last_sale_price,
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

    def fetch_property_data(self, limit: Optional[int] = None) -> List[PropertyRecord]:
        """
        Fetch property data from the configured source.

        Args:
            limit: Max number of records to fetch (for testing)

        Returns:
            List of PropertyRecord objects
        """
        download_url = self._find_download_url()
        if not download_url:
            logger.error("download_url_not_found")
            return []

        file_path = self._download_file(download_url)
        if not file_path:
            logger.error("download_failed")
            return []

        records = self._parse_cama_file(file_path, limit=limit)

        logger.info("fetch_property_completed", records_count=len(records))

        return records

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

                    data = self._map_fields(row)

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

        # Common field mappings for different formats
        field_mappings = {
            # Core property fields
            'parcel_id': ['parcel', 'parcel_id', 'parcelid', 'pin', 'property_id', 'folio'],
            'account_number': ['prop_id', 'account', 'account_number', 'acct', 'acct_num'],
            'property_address': ['property_address', 'site_address', 'address', 'location', 'situs'],

            # Owner fields (from Owners.txt)
            'owner_name': ['owner_mail_name', 'owner_name', 'owner', 'owner1', 'name', 'taxpayer'],
            # CRITICAL: owner_mail_addr2 has 99.98% coverage, addr1 only 4%, addr3 only 0.3%
            'owner_address': ['owner_mail_addr2', 'owner_mail_addr1', 'owner_mail_addr3', 'owner_address', 'mail_address', 'mailing_address', 'owner_addr'],

            # Land use / zoning
            'use_code': ['prop_use_code', 'use_code', 'usecode', 'land_use', 'dor_uc', 'propertyuse'],

            # Assessment values (from HistoryRE.txt)
            'assessed_value': [
                'county_assessed_value',  # HistoryRE.txt
                'school_assessed_value',  # HistoryRE.txt alternative
                'assessed_value',
                'assessment',
                'assessed'
            ],
            'market_value': [
                'just_value',  # HistoryRE.txt MAIN field for market value
                'market_value',
                'appraised_value',
                'fmv'
            ],
            'taxable_value': [
                'county_taxable_value',  # HistoryRE.txt
                'school_taxable_value',  # HistoryRE.txt alternative
                'taxable_value',
                'taxable',
                'tax_value'
            ],
            'land_value': [
                'land_value',  # HistoryRE.txt
                'landval',
                'land'
            ],

            # Building characteristics (from Improvements.txt)
            'year_built': [
                'actual_yrblt',  # Improvements.txt MAIN field
                'effective_yrblt',  # Improvements.txt alternative
                'year_built',
                'yearbuilt',
                'yr_built',
                'yr_blt',
                'actual_year'
            ],
            'square_footage': [
                'heated_squarefeet',  # Improvements.txt and HistoryRE.txt
                'htdsqft',  # Property.txt
                'totsqft',  # Property.txt alternative
                'square_footage',
                'sqft',
                'total_area',
                'building_area',
                'heated_area'
            ],
            'lot_size_acres': [
                'acres',  # Property.txt and Land.txt
                'lot_size_acres',
                'acreage',
                'land_area'
            ],

            # Room counts (from ImprvAttributes.txt)
            'bedrooms': ['bedrooms', 'beds', 'bdrms', 'br', 'bed_count'],
            'bathrooms': ['bathrooms', 'baths', 'bath', 'full_bath', 'bath_count'],

            # Sales info (from Sales.txt)
            'last_sale_date': ['sale_date', 'last_sale_date', 'saledate', 'or_date'],
            'last_sale_price': ['sale_price', 'last_sale_price', 'saleprice', 'or_value'],
        }

        mapped_data = {}

        for field, possible_names in field_mappings.items():
            for name in possible_names:
                if name in row_lower:
                    value = row_lower[name]
                    # Skip empty/null values - try next field name
                    if value and value.strip() and value.strip().upper() not in ['NULL', 'N/A', 'NONE']:
                        mapped_data[field] = value
                        break
            # If no non-empty value found, set to None explicitly
            if field not in mapped_data:
                mapped_data[field] = None

        # Build complete mailing address from components (Owners.txt has separate city/state/zip)
        if mapped_data.get('owner_address'):
            # Check if we have city/state/zip to append
            city = row_lower.get('owner_mail_city', '').strip()
            state = row_lower.get('owner_mail_state', '').strip()
            zip_code = row_lower.get('owner_mail_zip', '').strip()

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


def test_scraper():
    """Test the property scraper with a market config."""
    from ...config.loader import load_market_config

    # Load Gainesville config
    print("\n=== Testing Property Appraiser Scraper ===\n")

    try:
        config = load_market_config('gainesville_fl')
        print(f"[OK] Loaded config for {config.market.name}")
    except Exception as e:
        print(f"[FAIL] Failed to load config: {e}")
        return

    # Initialize scraper
    try:
        scraper = PropertyAppraiserScraper(config)
        print(f"[OK] Initialized scraper for {scraper.county_code} County")
        print(f"     Base URL: {scraper.base_url}")
        print(f"     Portal Type: {scraper.portal_type}")
    except Exception as e:
        print(f"[FAIL] Failed to initialize scraper: {e}")
        return

    # Fetch sample data (limit to 100 for testing)
    print(f"\n[TEST] Fetching sample property data (limit: 100)...")
    try:
        records = scraper.fetch_property_data(limit=100)

        if records:
            print(f"[OK] Fetched {len(records)} property records")

            # Show first record
            if records:
                first = records[0]
                print(f"\n--- Sample Property Record ---")
                print(f"Parcel ID: {first.parcel_id}")
                print(f"Address: {first.property_address}")
                print(f"Owner: {first.owner_name}")
                print(f"Use Code: {first.use_code}")
                print(f"Assessed Value: ${first.assessed_value:,.2f}" if first.assessed_value else "Assessed Value: N/A")
                print(f"Market Value: ${first.market_value:,.2f}" if first.market_value else "Market Value: N/A")
                print(f"Year Built: {first.year_built}" if first.year_built else "Year Built: N/A")
                print(f"LLC Owned: {'Yes' if first.is_llc() else 'No'}")

            # Summary stats
            stats = scraper.get_summary_stats(records)
            print(f"\n--- Summary Statistics ---")
            print(f"Total Properties: {stats['total_properties']:,}")
            print(f"LLC Owned: {stats['llc_owned']:,} ({stats['llc_percentage']:.1f}%)")
            if stats['avg_assessed_value']:
                print(f"Avg Assessed Value: ${stats['avg_assessed_value']:,.2f}")
            if stats['avg_market_value']:
                print(f"Avg Market Value: ${stats['avg_market_value']:,.2f}")
        else:
            print(f"[WARN] No records fetched (may need manual download URL)")

    except Exception as e:
        print(f"[FAIL] Error fetching data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
        ]
    )
    test_scraper()
