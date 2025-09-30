"""
Parser for Florida Sunbiz fixed-width corporate data files.

File format: 1440 character fixed-width records
Source: Florida Division of Corporations SFTP server
"""
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import structlog

logger = structlog.get_logger("dominion.parsers.sunbiz")


class SunbizCorporateParser:
    """
    Parser for Florida Sunbiz fixed-width corporate/LLC formation files.

    Field positions reverse-engineered from actual data files:
    - Positions 1-12: Document Number (e.g., L25000439150)
    - Positions 13-158: Entity Name
    - Positions 200-400: Addresses
    - Positions 460-480: Filing Date (MMDDYYYY format)
    - Positions 520+: Officers and registered agents
    """

    def parse_record(self, line: str) -> Dict:
        """
        Parse a single 1440-character record.

        Args:
            line: Fixed-width record string

        Returns:
            Dict with extracted fields
        """
        # Pad line if needed
        if len(line) < 1440:
            line = line.ljust(1440)

        record = {}

        try:
            # Document Number (1-12) - REQUIRED
            record['document_number'] = line[0:12].strip()

            # Entity Name (13-158)
            record['entity_name'] = line[12:158].strip()

            # Status (around 160-200)
            status_area = line[158:200].strip()
            if 'AFL' in status_area:
                record['status'] = 'Active'
                record['state'] = 'FL'
            else:
                record['status'] = 'Unknown'

            # Principal Address (~220-310)
            street = line[220:310].strip()
            if street and len(street) > 3:
                record['principal_address'] = street

            # City (~310-340)
            city = line[310:340].strip()
            if city and city != 'FL' and len(city) > 1:
                record['principal_city'] = city

            # ZIP Code (~330-345)
            zip_code = line[330:345].strip().replace('FL', '').strip()
            if zip_code and len(zip_code) >= 5:
                record['principal_zip'] = zip_code[:5]

            # Mailing Address (~340-420)
            mailing = line[340:420].strip()
            if mailing and len(mailing) > 5:
                record['mailing_address'] = mailing

            # Filing Date (~460-490, format: MMDDYYYY)
            date_area = line[460:490]
            for i in range(len(date_area) - 7):
                potential_date = date_area[i:i+8]
                if potential_date.isdigit():
                    try:
                        month = int(potential_date[0:2])
                        day = int(potential_date[2:4])
                        year = int(potential_date[4:8])
                        if 1 <= month <= 12 and 1 <= day <= 31 and 2020 <= year <= 2030:
                            record['filing_date'] = datetime(year, month, day)
                            break
                    except:
                        pass

            # Officers/Agents (~520-800)
            officer_area = line[520:800]
            officers = []

            # Extract officer names (look for common role indicators)
            for role_code in ['P', 'MGR', 'AMBR', 'PRES', 'VP', 'SEC', 'TREAS']:
                idx = officer_area.find(role_code)
                if idx > 0 and idx < len(officer_area) - 20:
                    name_snippet = officer_area[idx:idx+50].strip()
                    if len(name_snippet) > 5:
                        # Clean up the snippet
                        officers.append(name_snippet[:40])  # Limit length

            if officers:
                record['officers'] = list(set(officers[:3]))  # Unique, max 3

        except Exception as e:
            logger.warning("Failed to parse some fields", error=str(e))

        return record

    def parse_file(self, filepath: Path) -> List[Dict]:
        """
        Parse entire file.

        Args:
            filepath: Path to corporate data file

        Returns:
            List of parsed records
        """
        records = []

        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        line = line.rstrip('\n\r')
                        record = self.parse_record(line)
                        record['_line_number'] = line_num
                        records.append(record)
                    except Exception as e:
                        logger.warning(
                            "Failed to parse line",
                            line_number=line_num,
                            error=str(e)
                        )
                        continue

            logger.info(
                "Parsed file",
                filepath=filepath.name,
                total_records=len(records)
            )

        except Exception as e:
            logger.error("Failed to parse file", filepath=str(filepath), error=str(e))
            raise

        return records

    @staticmethod
    def is_llc(record: Dict) -> bool:
        """Check if entity is an LLC."""
        entity_name = record.get('entity_name', '').upper()
        return 'LLC' in entity_name or 'L.L.C' in entity_name

    @staticmethod
    def is_real_estate_related(record: Dict) -> bool:
        """Check if entity appears to be real estate related."""
        keywords = [
            'REAL ESTATE', 'REALTY', 'DEVELOPMENT', 'DEVELOPER',
            'PROPERTY', 'PROPERTIES', 'CONSTRUCTION', 'BUILDING',
            'LAND', 'INVESTMENT', 'HOLDINGS', 'HOME', 'HOMES',
            'RESIDENTIAL', 'COMMERCIAL', 'APARTMENT', 'CONDO',
            'CONDOS', 'RENTAL', 'RENTALS', 'ASSET', 'ASSETS',
            'EQUITY', 'CAPITAL', 'VENTURES'
        ]

        searchable = ' '.join([
            record.get('entity_name', ''),
            record.get('principal_address', ''),
        ]).upper()

        return any(kw in searchable for kw in keywords)

    def filter_llcs(self, records: List[Dict]) -> List[Dict]:
        """Filter for LLC entities."""
        return [r for r in records if self.is_llc(r)]

    def filter_real_estate(self, records: List[Dict]) -> List[Dict]:
        """Filter for real estate related entities."""
        return [r for r in records if self.is_real_estate_related(r)]

    def filter_real_estate_llcs(self, records: List[Dict]) -> List[Dict]:
        """Filter for real estate related LLCs."""
        return [
            r for r in records
            if self.is_llc(r) and self.is_real_estate_related(r)
        ]