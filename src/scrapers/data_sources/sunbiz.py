"""
Florida Sunbiz Data Scraper

Downloads and processes corporate formation and event data from Florida Division of Corporations.
Uses official SFTP bulk data source - no bot detection, reliable, complete data.

Data sources:
- Corporate formations (daily): New LLCs, corporations, partnerships
- Corporate events (daily): Dissolutions, amendments, officer changes

Output: Cleaned, normalized records ready for database upload.
"""
import os
import paramiko
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import structlog

logger = structlog.get_logger("dominion.scrapers.sunbiz")


class SunbizScraper:
    """
    Florida Sunbiz SFTP data scraper.

    Downloads and parses daily corporate formation and event files.
    Filters for real estate-relevant entities.
    """

    # SFTP Configuration (defaults for public access)
    SFTP_HOST = "sftp.floridados.gov"
    CORPORATE_PATH = "/Public/doc/cor/"
    EVENTS_PATH = "/Public/doc/cor/Events/"

    # Real estate keywords for filtering (weighted by strength of signal)
    # Strong signals - almost always property-related
    STRONG_REAL_ESTATE_KEYWORDS = [
        'REAL ESTATE', 'REALTY', 'PROPERTY', 'PROPERTIES',
        'DEVELOPMENT', 'DEVELOPMENTS', 'DEVELOPER',
        'LAND', 'HOLDINGS', 'APARTMENT', 'APARTMENTS',
        'CONDOS', 'CONDO', 'TOWNHOME', 'TOWNHOMES',
        'ESTATES', 'TITLE', 'MORTGAGE', 'LENDING',
        'RENTAL', 'RENTALS', 'LEASE', 'LEASING'
    ]

    # Medium signals - often property-related but context-dependent
    MEDIUM_REAL_ESTATE_KEYWORDS = [
        'CONSTRUCTION', 'BUILDING', 'BUILDERS',
        'INVESTMENT', 'INVESTMENTS', 'HOUSING',
        'RESIDENTIAL', 'COMMERCIAL', 'VENTURES',
        'CAPITAL', 'RENOVATIONS', 'MANAGEMENT',
        'ACQUISITION', 'EQUITY', 'ASSET', 'ASSETS',
        'HOME', 'HOMES', 'ROOFING', 'ROOF',
        'FLOORING', 'FLOOR', 'HVAC', 'PLUMBING',
        'SOLAR', 'LANDSCAPING', 'LANDSCAPE'
    ]

    # Exclusion patterns - these indicate NOT property-related
    EXCLUSION_PATTERNS = [
        'HOME CARE', 'HOMECARE', 'HOME HEALTH',
        'HOMESCHOOL', 'HOME SCHOOL',
        'GAMING RENTAL', 'EQUIPMENT RENTAL',
        'CAR RENTAL', 'VEHICLE RENTAL',
        'HOME IMPROVEMENT STORE', 'HOME DECOR',
        'MOBILE HOME', 'NURSING HOME',
        'MENTAL HEALTH', 'HOME THERAPY'
    ]

    # Event type classifications
    EVENT_TYPES = {
        'VOLDS': 'voluntary_dissolution',
        'ADMDS': 'administrative_dissolution',
        'AMND': 'amendment',
        'NMCHG': 'name_change',
        'CHANGE': 'general_change',
        'WITH': 'withdrawal',
        'REINST': 'reinstatement',
        'MERGER': 'merger',
        'CAN': 'cancellation',
        'REVOK': 'revocation',
    }

    def __init__(self, download_dir: Optional[Path] = None, sftp_username: Optional[str] = None, sftp_password: Optional[str] = None):
        """
        Initialize Sunbiz scraper.

        Args:
            download_dir: Directory for downloaded files (default: ./data/sunbiz)
            sftp_username: SFTP username (default: from env SUNBIZ_SFTP_USER or 'Public')
            sftp_password: SFTP password (default: from env SUNBIZ_SFTP_PASS or public credentials)
        """
        self.download_dir = download_dir or Path("./data/sunbiz")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Get credentials from env vars with fallback to public access
        self.sftp_username = sftp_username or os.getenv('SUNBIZ_SFTP_USER', 'Public')
        self.sftp_password = sftp_password or os.getenv('SUNBIZ_SFTP_PASS', 'PubAccess1845!')

    def _connect_sftp(self) -> Tuple[paramiko.SSHClient, paramiko.SFTPClient]:
        """Establish SFTP connection."""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                hostname=self.SFTP_HOST,
                username=self.sftp_username,
                password=self.sftp_password,
                look_for_keys=False,
                allow_agent=False,
                timeout=30
            )

            sftp = ssh.open_sftp()
            logger.info("SFTP connection established", host=self.SFTP_HOST)

            return ssh, sftp

        except Exception as e:
            logger.error("SFTP connection failed", error=str(e))
            raise

    def _download_file(self, remote_path: str, local_filename: str) -> Optional[Path]:
        """Download a file from SFTP."""
        ssh, sftp = self._connect_sftp()

        try:
            local_path = self.download_dir / local_filename

            logger.info("Downloading file", remote_path=remote_path)
            sftp.get(remote_path, str(local_path))

            file_size = local_path.stat().st_size
            logger.info(
                "File downloaded",
                filename=local_filename,
                size_bytes=file_size,
                size_kb=f"{file_size/1024:.1f}"
            )

            return local_path

        except FileNotFoundError:
            logger.warning("File not found", remote_path=remote_path)
            return None
        except Exception as e:
            logger.error("Download failed", remote_path=remote_path, error=str(e))
            return None
        finally:
            sftp.close()
            ssh.close()

    def _parse_corporate_record(self, line: str) -> Optional[Dict]:
        """
        Parse a 1440-character fixed-width corporate formation record.

        Field positions discovered through analysis:
        - 1-12: Document Number
        - 13-158: Entity Name
        - 220-310: Principal Address
        - 310-340: City
        - 330-345: ZIP Code
        - 460-490: Filing Date (MMDDYYYY)
        - 520-800: Officers
        """
        if len(line) < 1440:
            line = line.ljust(1440)

        try:
            record = {}

            # Document Number (1-12)
            doc_num = line[0:12].strip()
            if not doc_num:
                return None
            record['document_number'] = doc_num

            # Entity Name (13-158)
            name = line[12:158].strip()
            if name:
                record['entity_name'] = name

            # Principal Address
            street = line[220:310].strip()
            city = line[310:340].strip()
            zip_code = line[330:345].strip().replace('FL', '').strip()

            if street:
                record['principal_address'] = street
            if city:
                record['principal_city'] = city
            if zip_code:
                record['principal_zip'] = zip_code
            record['principal_state'] = 'FL'

            # Filing Date (search for MMDDYYYY pattern around position 460-490)
            date_area = line[460:490]
            filing_date = self._extract_date(date_area)
            if filing_date:
                record['filing_date'] = filing_date

            # Officers (rough area 520-800)
            officers_area = line[520:800].strip()
            if officers_area:
                record['officers_raw'] = officers_area

            # Classify entity type
            record['entity_type'] = self._classify_entity_type(name, line)

            # Check real estate relevance
            record['is_real_estate'] = self._is_real_estate_related(name)

            # Metadata
            record['record_type'] = 'formation'
            record['scraped_at'] = datetime.now().isoformat()

            return record

        except Exception as e:
            logger.warning("Failed to parse corporate record", error=str(e))
            return None

    def _parse_event_record(self, line: str) -> Optional[Dict]:
        """
        Parse a 662-character fixed-width event record.

        Field positions:
        - 1-12: Document Number
        - 13-18: Event sequence number
        - 19-32: Event type code
        - 33-73: Event description
        - 74-100: Event date (MMDDYYYY)
        """
        if len(line) < 662:
            line = line.ljust(662)

        try:
            record = {}

            # Document Number (1-12)
            doc_num = line[0:12].strip()
            if not doc_num:
                return None
            record['document_number'] = doc_num

            # Event sequence (13-18)
            seq_num = line[12:18].strip()
            if seq_num:
                record['event_sequence'] = seq_num

            # Event type code (19-32)
            event_code = line[18:32].strip()
            if event_code:
                record['event_code'] = event_code
                record['event_type'] = self._classify_event_type(event_code)

            # Event description (33-73)
            event_desc = line[32:73].strip()
            if event_desc:
                record['event_description'] = event_desc

            # Event date (74-100)
            date_area = line[73:110]
            event_date = self._extract_date(date_area)
            if event_date:
                record['event_date'] = event_date

            # Metadata
            record['record_type'] = 'event'
            record['scraped_at'] = datetime.now().isoformat()

            return record

        except Exception as e:
            logger.warning("Failed to parse event record", error=str(e))
            return None

    def _extract_date(self, date_area: str) -> Optional[str]:
        """Extract date from area (MMDDYYYY format) and return ISO string."""
        for i in range(len(date_area) - 7):
            potential_date = date_area[i:i+8]
            if potential_date.isdigit():
                try:
                    month = int(potential_date[0:2])
                    day = int(potential_date[2:4])
                    year = int(potential_date[4:8])

                    if 1 <= month <= 12 and 1 <= day <= 31 and 2020 <= year <= 2030:
                        return datetime(year, month, day).isoformat()
                except (ValueError, IndexError):
                    # Invalid date format or out of range
                    continue
        return None

    def _classify_entity_type(self, name: str, full_record: str) -> str:
        """Classify entity type from name and record."""
        name_upper = name.upper()

        if 'LLC' in name_upper or 'L.L.C.' in name_upper:
            return 'LLC'
        elif 'INC' in name_upper or 'CORP' in name_upper:
            return 'Corporation'
        elif 'LP' in name_upper or 'L.P.' in name_upper:
            return 'Limited Partnership'
        elif 'LLP' in name_upper:
            return 'Limited Liability Partnership'
        else:
            return 'Other'

    def _classify_event_type(self, event_code: str) -> str:
        """Classify event type from code."""
        event_code_upper = event_code.upper()

        for code_fragment, event_type in self.EVENT_TYPES.items():
            if code_fragment in event_code_upper:
                return event_type

        return 'unknown'

    def _is_real_estate_related(self, name: str) -> bool:
        """
        Check if entity name suggests real estate focus.

        Uses weighted keyword matching with exclusion patterns:
        - Strong keywords = automatic match
        - Medium keywords = match only if no exclusions
        - Exclusion patterns = automatic rejection
        """
        name_upper = name.upper()

        # Check exclusion patterns first
        for exclusion in self.EXCLUSION_PATTERNS:
            if exclusion in name_upper:
                return False

        # Check strong keywords - automatic match
        for keyword in self.STRONG_REAL_ESTATE_KEYWORDS:
            if keyword in name_upper:
                return True

        # Check medium keywords - match if found
        for keyword in self.MEDIUM_REAL_ESTATE_KEYWORDS:
            if keyword in name_upper:
                return True

        return False

    def scrape_corporate_data(self, date: Optional[datetime] = None) -> List[Dict]:
        """
        Scrape corporate formation data for a specific date.

        Args:
            date: Date to scrape (default: yesterday)

        Returns:
            List of cleaned corporate records ready for database
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)

        filename = f"{date.strftime('%Y%m%d')}c.txt"
        remote_path = f"{self.CORPORATE_PATH}{filename}"

        # Download file
        local_path = self._download_file(remote_path, filename)
        if not local_path:
            logger.error("Could not download corporate file", date=date.strftime('%Y-%m-%d'))
            return []

        # Parse file
        records = []
        try:
            with open(local_path, 'r', encoding='latin-1') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.rstrip('\n\r')
                    record = self._parse_corporate_record(line)

                    if record:
                        record['_line_number'] = line_num
                        records.append(record)

            logger.info(
                "Parsed corporate file",
                date=date.strftime('%Y-%m-%d'),
                total_records=len(records),
                llcs=sum(1 for r in records if r.get('entity_type') == 'LLC'),
                real_estate=sum(1 for r in records if r.get('is_real_estate'))
            )

        except Exception as e:
            logger.error("Failed to parse corporate file", filepath=str(local_path), error=str(e))

        return records

    def scrape_events_data(self, date: Optional[datetime] = None) -> List[Dict]:
        """
        Scrape corporate event data for a specific date.

        Args:
            date: Date to scrape (default: yesterday)

        Returns:
            List of cleaned event records ready for database
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)

        filename = f"{date.strftime('%Y%m%d')}ce.txt"
        remote_path = f"{self.EVENTS_PATH}{filename}"

        # Download file
        local_path = self._download_file(remote_path, f"events_{filename}")
        if not local_path:
            logger.error("Could not download events file", date=date.strftime('%Y-%m-%d'))
            return []

        # Parse file
        records = []
        try:
            with open(local_path, 'r', encoding='latin-1') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.rstrip('\n\r')
                    record = self._parse_event_record(line)

                    if record:
                        record['_line_number'] = line_num
                        records.append(record)

            logger.info(
                "Parsed events file",
                date=date.strftime('%Y-%m-%d'),
                total_events=len(records),
                dissolutions=sum(1 for r in records if 'dissolution' in r.get('event_type', ''))
            )

        except Exception as e:
            logger.error("Failed to parse events file", filepath=str(local_path), error=str(e))

        return records

    def scrape_all(self, date: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        """
        Scrape both corporate and events data for a date.

        Args:
            date: Date to scrape (default: yesterday)

        Returns:
            Dict with 'formations' and 'events' keys containing cleaned records
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)

        logger.info("Starting Sunbiz scrape", date=date.strftime('%Y-%m-%d'))

        formations = self.scrape_corporate_data(date)
        events = self.scrape_events_data(date)

        result = {
            'formations': formations,
            'events': events,
            'date': date,
            'summary': {
                'total_formations': len(formations),
                'llc_formations': sum(1 for r in formations if r.get('entity_type') == 'LLC'),
                'real_estate_formations': sum(1 for r in formations if r.get('is_real_estate')),
                'total_events': len(events),
                'dissolutions': sum(1 for r in events if 'dissolution' in r.get('event_type', '')),
                'amendments': sum(1 for r in events if 'amendment' in r.get('event_type', '')),
            }
        }

        logger.info(
            "Sunbiz scrape complete",
            date=date.strftime('%Y-%m-%d'),
            **result['summary']
        )

        return result

    def filter_llcs(self, records: List[Dict]) -> List[Dict]:
        """Filter for LLC entities only."""
        return [r for r in records if r.get('entity_type') == 'LLC']

    def filter_real_estate(self, records: List[Dict]) -> List[Dict]:
        """Filter for real estate related entities."""
        return [r for r in records if r.get('is_real_estate')]

    def filter_dissolutions(self, records: List[Dict]) -> List[Dict]:
        """Filter for dissolution events."""
        return [r for r in records if 'dissolution' in r.get('event_type', '')]


# Convenience function for quick scraping
def scrape_sunbiz(date: Optional[datetime] = None) -> Dict[str, List[Dict]]:
    """
    Quick function to scrape Sunbiz data for a date.

    Args:
        date: Date to scrape (default: yesterday)

    Returns:
        Dict with cleaned formations and events data
    """
    scraper = SunbizScraper()
    return scraper.scrape_all(date)