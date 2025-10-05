"""
qPublic Property Scraper

Scrapes live property data from Alachua County qPublic portal.
Provides complete, authoritative property data that CAMA bulk exports lack.

Data Source: https://qpublic.schneidercorp.com (Alachua County)
Method: HTTP requests + BeautifulSoup parsing
Coverage: Individual property lookups by parcel ID

Advantages over CAMA bulk:
- Live, current data (not stale bulk export)
- Complete property addresses (CAMA has 0%)
- Complete financial data (CAMA missing 0.8% of parcels)
- All improvement records (CAMA only captures one per parcel)
"""
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)


class QPublicPropertyScraper:
    """
    Scrapes Alachua County property data from qPublic portal.

    Handles ASP.NET postback forms and parses property detail pages.
    """

    BASE_URL = "https://qpublic.schneidercorp.com"
    SEARCH_URL = f"{BASE_URL}/Application.aspx"

    # Alachua County app parameters
    APP_PARAMS = {
        "AppID": "1081",
        "LayerID": "26490",
        "PageTypeID": "2",
        "PageID": "10768"
    }

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize qPublic scraper.

        Args:
            rate_limit_delay: Seconds to wait between requests (default: 1.0)
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def search_by_parcel(self, parcel_id: str) -> Optional[str]:
        """
        Search for a property by parcel ID and get the detail page URL.

        Args:
            parcel_id: Parcel ID (e.g., "17757-003-004")

        Returns:
            Detail page URL or None if not found
        """
        self._rate_limit()

        logger.info("Searching qPublic for parcel", parcel_id=parcel_id)

        try:
            # First, establish session by visiting main search page
            main_url = f"{self.SEARCH_URL}?{urlencode(self.APP_PARAMS)}"
            logger.debug("Establishing session", url=main_url)

            session_response = self.session.get(main_url, timeout=30)
            session_response.raise_for_status()

            # Parse to get __VIEWSTATE and form fields
            soup = BeautifulSoup(session_response.content, 'html.parser')

            # Build form data for parcel search
            form_data = {}

            # Get ASP.NET viewstate fields
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            if viewstate and viewstate.get('value'):
                form_data['__VIEWSTATE'] = viewstate['value']

            viewstate_generator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
            if viewstate_generator and viewstate_generator.get('value'):
                form_data['__VIEWSTATEGENERATOR'] = viewstate_generator['value']

            event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})
            if event_validation and event_validation.get('value'):
                form_data['__EVENTVALIDATION'] = event_validation['value']

            # Add parcel search data
            form_data['ctlBodyPane$ctl03$ctl01$txtParcelID'] = parcel_id
            form_data['ctlBodyPane$ctl03$ctl01$btnSearch'] = 'Search'

            # Submit the search form
            logger.debug("Submitting parcel search", parcel_id=parcel_id)
            response = self.session.post(main_url, data=form_data, timeout=30, allow_redirects=True)
            response.raise_for_status()

            # Check if we got redirected to a detail page
            if '/SearchResults.aspx' in response.url:
                # Multiple results - need to parse and find exact match
                soup = BeautifulSoup(response.content, 'html.parser')

                # Find table of results
                results_table = soup.find('table', {'class': 'DataletResults'})
                if not results_table:
                    logger.warning("No results found", parcel_id=parcel_id)
                    return None

                # Look for our parcel in the results
                for row in results_table.find_all('tr')[1:]:  # Skip header
                    cells = row.find_all('td')
                    if cells and parcel_id in cells[0].text:
                        # Found our parcel - get the detail link
                        link = cells[0].find('a')
                        if link and 'href' in link.attrs:
                            detail_url = self.BASE_URL + link['href']
                            logger.info("Found parcel detail page", url=detail_url)
                            return detail_url

                logger.warning("Parcel not in results", parcel_id=parcel_id)
                return None

            elif '/SearchResult.aspx' in response.url or 'Datalet' in response.url:
                # Single result - we're already on detail page
                logger.info("Found parcel detail page", url=response.url)
                return response.url

            else:
                logger.warning("Unexpected response URL", url=response.url)
                return None

        except requests.RequestException as e:
            logger.error("Request failed", parcel_id=parcel_id, error=str(e))
            return None

    def scrape_property(self, parcel_id: str) -> Optional[Dict]:
        """
        Scrape complete property data for a given parcel ID.

        Args:
            parcel_id: Parcel ID (e.g., "17757-003-004")

        Returns:
            Dict with property data or None if not found/error
        """
        # First, search to get detail page URL
        detail_url = self.search_by_parcel(parcel_id)
        if not detail_url:
            return None

        # Now scrape the detail page
        return self.scrape_detail_page(detail_url, parcel_id)

    def scrape_detail_page(self, url: str, parcel_id: str) -> Optional[Dict]:
        """
        Scrape property data from a qPublic detail page.

        Args:
            url: Detail page URL
            parcel_id: Parcel ID for logging

        Returns:
            Dict with property data or None if error
        """
        self._rate_limit()

        logger.info("Scraping property detail page", parcel_id=parcel_id, url=url)

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract data using qPublic's standard HTML structure
            data = {
                'parcel_id': parcel_id,
                'source_url': url,
                'scraped_at': datetime.now().isoformat(),
            }

            # Property location section
            data.update(self._extract_location_data(soup))

            # Owner information section
            data.update(self._extract_owner_data(soup))

            # Valuation section
            data.update(self._extract_valuation_data(soup))

            # Building/characteristics section
            data.update(self._extract_building_data(soup))

            # Sales section
            data.update(self._extract_sales_data(soup))

            # Land/parcel section
            data.update(self._extract_land_data(soup))

            logger.info("Successfully scraped property", parcel_id=parcel_id,
                       has_address=bool(data.get('property_address')),
                       has_value=bool(data.get('market_value')))

            return data

        except requests.RequestException as e:
            logger.error("Failed to fetch detail page", parcel_id=parcel_id,
                        url=url, error=str(e))
            return None
        except Exception as e:
            logger.error("Failed to parse detail page", parcel_id=parcel_id,
                        url=url, error=str(e))
            return None

    def _extract_location_data(self, soup: BeautifulSoup) -> Dict:
        """Extract property location/address data."""
        data = {}

        # Common patterns in qPublic for property address
        # Look for "Property Location" or "Situs Address" sections
        location_section = soup.find('span', string=lambda t: t and 'Location' in t)
        if location_section:
            # Address is typically in next sibling or parent div
            parent = location_section.find_parent('div')
            if parent:
                addr_text = parent.get_text(separator=' ', strip=True)
                # Clean up the address
                addr_text = addr_text.replace('Property Location', '').strip()
                if addr_text:
                    data['property_address'] = addr_text

        # Alternative: Look for "Situs Address" label
        if not data.get('property_address'):
            situs_label = soup.find('td', string=lambda t: t and 'Situs' in t)
            if situs_label:
                situs_value = situs_label.find_next_sibling('td')
                if situs_value:
                    data['property_address'] = situs_value.get_text(strip=True)

        # Look for city/zip in similar patterns
        city_label = soup.find('td', string=lambda t: t and 'City' in t)
        if city_label:
            city_value = city_label.find_next_sibling('td')
            if city_value:
                data['city'] = city_value.get_text(strip=True)

        return data

    def _extract_owner_data(self, soup: BeautifulSoup) -> Dict:
        """Extract owner information."""
        data = {}

        # Owner name
        owner_label = soup.find('td', string=lambda t: t and 'Owner' in t and 'Name' in t)
        if owner_label:
            owner_value = owner_label.find_next_sibling('td')
            if owner_value:
                data['owner_name'] = owner_value.get_text(strip=True)

        # Owner mailing address
        mail_label = soup.find('td', string=lambda t: t and 'Mailing' in t)
        if mail_label:
            mail_value = mail_label.find_next_sibling('td')
            if mail_value:
                # Get all address lines
                addr_lines = [line.strip() for line in mail_value.stripped_strings]
                data['owner_address'] = ', '.join(addr_lines)

        return data

    def _extract_valuation_data(self, soup: BeautifulSoup) -> Dict:
        """Extract assessment and market values."""
        data = {}

        # Market/Just Value
        for label_text in ['Just Value', 'Market Value', 'Assessed Value']:
            label = soup.find('td', string=lambda t: t and label_text in t)
            if label:
                value_cell = label.find_next_sibling('td')
                if value_cell:
                    value_str = value_cell.get_text(strip=True)
                    value = self._parse_currency(value_str)

                    if 'Just' in label_text or 'Market' in label_text:
                        data['market_value'] = value
                    elif 'Assessed' in label_text:
                        data['assessed_value'] = value

        # Taxable value
        taxable_label = soup.find('td', string=lambda t: t and 'Taxable' in t)
        if taxable_label:
            taxable_value = taxable_label.find_next_sibling('td')
            if taxable_value:
                data['taxable_value'] = self._parse_currency(taxable_value.get_text(strip=True))

        return data

    def _extract_building_data(self, soup: BeautifulSoup) -> Dict:
        """Extract building characteristics."""
        data = {}

        # Year built
        year_label = soup.find('td', string=lambda t: t and 'Year Built' in t)
        if year_label:
            year_value = year_label.find_next_sibling('td')
            if year_value:
                year_text = year_value.get_text(strip=True)
                try:
                    data['year_built'] = int(year_text) if year_text and year_text.isdigit() else None
                except (ValueError, TypeError):
                    pass

        # Square footage - try multiple labels
        for sqft_label_text in ['Total Living Area', 'Living Area', 'Building Area',
                                'Heated Area', 'Square Feet']:
            sqft_label = soup.find('td', string=lambda t: t and sqft_label_text in t)
            if sqft_label:
                sqft_value = sqft_label.find_next_sibling('td')
                if sqft_value:
                    sqft = self._parse_number(sqft_value.get_text(strip=True))
                    if sqft:
                        data['square_footage'] = sqft
                        break

        # Bedrooms
        bed_label = soup.find('td', string=lambda t: t and 'Bedroom' in t)
        if bed_label:
            bed_value = bed_label.find_next_sibling('td')
            if bed_value:
                try:
                    data['bedrooms'] = int(self._parse_number(bed_value.get_text(strip=True)) or 0)
                except (ValueError, TypeError):
                    pass

        # Bathrooms
        bath_label = soup.find('td', string=lambda t: t and 'Bath' in t)
        if bath_label:
            bath_value = bath_label.find_next_sibling('td')
            if bath_value:
                data['bathrooms'] = self._parse_number(bath_value.get_text(strip=True))

        return data

    def _extract_sales_data(self, soup: BeautifulSoup) -> Dict:
        """Extract sales history data."""
        data = {}

        # Last sale date
        sale_date_label = soup.find('td', string=lambda t: t and 'Sale Date' in t)
        if sale_date_label:
            sale_date_value = sale_date_label.find_next_sibling('td')
            if sale_date_value:
                data['last_sale_date'] = sale_date_value.get_text(strip=True)

        # Last sale price
        sale_price_label = soup.find('td', string=lambda t: t and 'Sale Price' in t)
        if sale_price_label:
            sale_price_value = sale_price_label.find_next_sibling('td')
            if sale_price_value:
                data['last_sale_price'] = self._parse_currency(sale_price_value.get_text(strip=True))

        return data

    def _extract_land_data(self, soup: BeautifulSoup) -> Dict:
        """Extract land/lot information."""
        data = {}

        # Lot size/acreage
        for lot_label_text in ['Acres', 'Lot Size', 'Land Area']:
            lot_label = soup.find('td', string=lambda t: t and lot_label_text in t)
            if lot_label:
                lot_value = lot_label.find_next_sibling('td')
                if lot_value:
                    acres = self._parse_number(lot_value.get_text(strip=True))
                    if acres:
                        data['lot_size_acres'] = acres
                        break

        # Use code / zoning
        use_label = soup.find('td', string=lambda t: t and ('Use Code' in t or 'Land Use' in t))
        if use_label:
            use_value = use_label.find_next_sibling('td')
            if use_value:
                data['use_code'] = use_value.get_text(strip=True)

        return data

    def _parse_currency(self, value_str: str) -> Optional[float]:
        """Parse currency string to float."""
        if not value_str:
            return None
        # Remove $, commas, spaces
        cleaned = value_str.replace('$', '').replace(',', '').replace(' ', '').strip()
        try:
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None

    def _parse_number(self, value_str: str) -> Optional[float]:
        """Parse number string to float."""
        if not value_str:
            return None
        # Remove commas, spaces
        cleaned = value_str.replace(',', '').replace(' ', '').strip()
        try:
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None

    def scrape_batch(self, parcel_ids: List[str],
                     max_errors: int = 10) -> List[Dict]:
        """
        Scrape multiple properties in batch.

        Args:
            parcel_ids: List of parcel IDs to scrape
            max_errors: Maximum consecutive errors before stopping (default: 10)

        Returns:
            List of property data dicts
        """
        results = []
        consecutive_errors = 0

        logger.info("Starting batch scrape", count=len(parcel_ids))

        for i, parcel_id in enumerate(parcel_ids, 1):
            try:
                data = self.scrape_property(parcel_id)
                if data:
                    results.append(data)
                    consecutive_errors = 0  # Reset error counter
                else:
                    consecutive_errors += 1

                # Progress logging every 50 properties
                if i % 50 == 0:
                    logger.info("Batch progress",
                               completed=i,
                               total=len(parcel_ids),
                               success_rate=f"{len(results)/i*100:.1f}%")

            except Exception as e:
                logger.error("Batch scrape error", parcel_id=parcel_id, error=str(e))
                consecutive_errors += 1

            # Stop if too many consecutive errors
            if consecutive_errors >= max_errors:
                logger.error("Too many consecutive errors, stopping batch",
                           errors=consecutive_errors)
                break

        logger.info("Batch scrape complete",
                   total=len(parcel_ids),
                   successful=len(results),
                   success_rate=f"{len(results)/len(parcel_ids)*100:.1f}%")

        return results
