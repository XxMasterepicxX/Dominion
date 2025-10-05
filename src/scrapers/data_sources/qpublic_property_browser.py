"""
qPublic Property Scraper (Patchright/Browser-based)

Uses Patchright to bypass Cloudflare/bot protection on qPublic.
Similar approach to Sunbiz scraper.

Data Source: https://qpublic.schneidercorp.com (Alachua County)
Method: Patchright (Playwright-based with Cloudflare bypass)
"""
import asyncio
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

from patchright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from pyproj import Transformer
import structlog

logger = structlog.get_logger(__name__)


class QPublicBrowserScraper:
    """
    Scrapes Alachua County property data from qPublic using Patchright.

    Bypasses Cloudflare protection to access property detail pages.
    """

    BASE_URL = "https://qpublic.schneidercorp.com"
    APP_ID = "1081"
    LAYER_ID = "26490"

    def __init__(self, headless: bool = False, rate_limit_delay: float = 1.0):
        """
        Initialize browser-based scraper.

        Args:
            headless: Run browser in headless mode (default: False, recommended)
            rate_limit_delay: Seconds between requests (default: 1.0)

        Note:
            Cloudflare blocks headless browsers more aggressively. For reliable scraping,
            use headless=False (visible browser window).
        """
        self.headless = headless
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    async def scrape_property(self, parcel_id: str) -> Optional[Dict]:
        """
        Scrape property data for a parcel using browser automation.

        Args:
            parcel_id: Parcel ID (e.g., "17757-003-004")

        Returns:
            Dict with property data or None if error
        """
        logger.info("Scraping qPublic with browser", parcel_id=parcel_id)
        self._rate_limit()

        try:
            async with async_playwright() as p:
                # Use regular browser launch (persistent context gets blocked by Cloudflare)
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()
                page = await context.new_page()

                # Navigate to search page
                search_url = f"{self.BASE_URL}/Application.aspx?AppID={self.APP_ID}&LayerID={self.LAYER_ID}&PageTypeID=2&PageID=10768"
                logger.debug("Navigating to qPublic search", url=search_url)

                await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)

                # Wait for page to fully load with JavaScript
                await page.wait_for_load_state('networkidle', timeout=30000)

                # Give Cloudflare time to complete its checks
                await page.wait_for_timeout(5000)

                # Handle Terms and Conditions modal if it appears
                try:
                    # Wait for the Terms and Conditions modal
                    logger.debug("Checking for Terms and Conditions modal")
                    await page.wait_for_selector('text=Terms and Conditions', timeout=5000)
                    logger.debug("Found Terms and Conditions modal")

                    # Click the Agree button with force
                    await page.click('text=Agree', force=True, timeout=5000)
                    logger.debug("Force clicked Agree button")

                    # Wait for modal to actually disappear
                    modal_selector = '[aria-label="Terms and Conditions"]'
                    await page.wait_for_selector(modal_selector, state='hidden', timeout=5000)
                    logger.debug("Modal dismissed successfully")

                except PlaywrightTimeout:
                    logger.debug("No Terms and Conditions modal or already dismissed")

                # Wait for search interface to be ready
                await page.wait_for_timeout(2000)

                # Fill in parcel ID search - wait longer and ensure visible
                parcel_input = await page.wait_for_selector('#ctlBodyPane_ctl03_ctl01_txtParcelID',
                                                              state='visible', timeout=15000)
                await parcel_input.fill(parcel_id)

                # Click search button
                logger.debug("Searching for parcel", parcel_id=parcel_id)
                search_btn = await page.wait_for_selector('#ctlBodyPane_ctl03_ctl01_btnSearch', timeout=5000)
                await search_btn.click()

                # Wait for results page to load after search
                try:
                    await page.wait_for_load_state('networkidle', timeout=20000)
                except PlaywrightTimeout:
                    logger.warning("Page load timeout, continuing anyway")

                # Give the page a bit more time to fully render
                await page.wait_for_timeout(2000)

                # Scroll down to ensure all data is loaded
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(1000)

                # Extract all data from the page
                logger.debug("Extracting property data")
                data = await self._extract_data(page, parcel_id)

                await browser.close()

                if data:
                    logger.info("Successfully scraped property", parcel_id=parcel_id,
                               has_address=bool(data.get('property_address')),
                               has_value=bool(data.get('market_value')))
                    return data
                else:
                    logger.warning("No data extracted", parcel_id=parcel_id)
                    return None

        except Exception as e:
            logger.error("Failed to scrape property", parcel_id=parcel_id, error=str(e))
            return None

    async def _extract_data(self, page, parcel_id: str) -> Optional[Dict]:
        """Extract property data from qPublic detail page using JavaScript."""

        data = await page.evaluate('''() => {
            const pageText = document.body.innerText;

            // Helper: Find value after a label (handles tab/newline separation)
            const findAfterLabel = (label) => {
                // Try tab+value on same line
                const tabRegex = new RegExp(label + '\\t+([^\\n\\t]+)', 'i');
                let match = pageText.match(tabRegex);
                if (match && match[1].trim()) return match[1].trim();

                // Try tab+newline+value (common pattern in qPublic)
                const tabNewlineRegex = new RegExp(label + '\\t*\\n+\\s*([^\\n]+)', 'i');
                match = pageText.match(tabNewlineRegex);
                if (match && match[1].trim()) return match[1].trim();

                // Try just newline+value
                const newlineRegex = new RegExp(label + '\\s*\\n+\\s*([^\\n]+)', 'i');
                match = pageText.match(newlineRegex);
                return (match && match[1].trim()) ? match[1].trim() : null;
            };

            // Helper: Parse currency
            const parseCurrency = (str) => {
                if (!str) return null;
                const match = str.match(/\\$?([\\d,]+)/);
                if (!match) return null;
                return parseFloat(match[1].replace(/,/g, ''));
            };

            // Helper: Parse number
            const parseNum = (str) => {
                if (!str) return null;
                const match = str.match(/([\\d,]+(?:\\.\\d+)?)/);
                if (!match) return null;
                return parseFloat(match[1].replace(/,/g, ''));
            };

            const data = {
                // Additional data arrays
                trim_notices: [],
                sales_history: [],
                permits: [],
                land_info: [],
                sub_areas: [],
                building_details: {},
                links: {}
            };

            // Property address
            const locAddr = findAfterLabel('Location Address');
            if (locAddr) {
                const parts = locAddr.split('\\n');
                data.property_address = parts[0];
                if (parts[1]) {
                    const cityState = parts[1].match(/([^,]+),\\s*([A-Z]{2})\\s+(\\d{5})/);
                    if (cityState) {
                        data.city = cityState[1];
                    }
                }
            }

            // Owner
            const ownerSection = pageText.match(/Owner Information\\s*([^\\n]+)\\s*([^\\n]+)\\s*([^\\n]+)/);
            if (ownerSection) {
                data.owner_name = ownerSection[1].trim();
                data.owner_address = `${ownerSection[2].trim()}, ${ownerSection[3].trim()}`;
            }

            // Values
            data.market_value = parseCurrency(findAfterLabel('Just .Market. Value'));
            data.assessed_value = parseCurrency(findAfterLabel('Assessed Value'));
            data.taxable_value = parseCurrency(findAfterLabel('Taxable Value'));

            // Building
            data.year_built = parseNum(findAfterLabel('Actual Year Built'));
            data.square_footage = parseNum(findAfterLabel('Heated Area'));

            const beds = findAfterLabel('Bedrooms');
            data.bedrooms = beds ? parseNum(beds) : null;

            const baths = findAfterLabel('Bathrooms');
            data.bathrooms = baths ? parseNum(baths) : null;

            // Land
            data.lot_size_acres = parseNum(findAfterLabel('Acres'));
            data.use_code = findAfterLabel('Property Use Code');

            // Sales - get first sale date and price (for backward compatibility)
            const salesMatch = pageText.match(/Sales\\s*([\\d\\/]+)\\s+\\$([\\d,]+)/);
            if (salesMatch) {
                data.last_sale_date = salesMatch[1];
                data.last_sale_price = parseFloat(salesMatch[2].replace(/,/g, ''));
            }

            // Extract ALL sales history
            const salesSection = pageText.match(/Sales[\\s\\S]*?(?=Area Sales Report|Permits|$)/);
            if (salesSection) {
                const salesLines = salesSection[0].split('\\n');
                for (let i = 0; i < salesLines.length; i++) {
                    const line = salesLines[i];
                    // Match: date, price, instrument, book, page, qualification, vacant/improved, grantor, grantee
                    const saleMatch = line.match(/^(\\d+\\/\\d+\\/\\d+)\\s+\\$([\\d,]+)\\s+(\\w+)\\s+(\\d+)\\s+(\\d+)\\s+([^\\t]+)\\s+([^\\t]+)\\s+([^\\t]+)\\s+([^\\t]+)/);
                    if (saleMatch) {
                        data.sales_history.push({
                            sale_date: saleMatch[1],
                            sale_price: parseFloat(saleMatch[2].replace(/,/g, '')),
                            instrument: saleMatch[3],
                            book: saleMatch[4],
                            page: saleMatch[5],
                            qualification: saleMatch[6].trim(),
                            vacant_improved: saleMatch[7].trim(),
                            grantor: saleMatch[8].trim(),
                            grantee: saleMatch[9].trim()
                        });
                    }
                }
            }

            // Extract permits
            const permitsSection = pageText.match(/Permits[\\s\\S]*?(?=Tax Collector|Sketches|$)/);
            if (permitsSection) {
                const permitLines = permitsSection[0].split('\\n');
                for (let i = 0; i < permitLines.length; i++) {
                    const line = permitLines[i];
                    // Match: permit number, type, primary, active, issue date, value
                    const permitMatch = line.match(/^([\\w\\-]+)\\s+([^\\t]+)\\s+(Yes|No)\\s+(Yes|No)\\s+([\\d\\/]+)\\s+\\$([\\d,]+)/);
                    if (permitMatch) {
                        data.permits.push({
                            permit_number: permitMatch[1],
                            type: permitMatch[2].trim(),
                            primary: permitMatch[3] === 'Yes',
                            active: permitMatch[4] === 'Yes',
                            issue_date: permitMatch[5],
                            value: parseFloat(permitMatch[6].replace(/,/g, ''))
                        });
                    }
                }
            }

            // Extract TRIM notices
            const trimMatches = pageText.matchAll(/(\\d{4}) TRIM Notice \\(PDF\\)/g);
            for (const match of trimMatches) {
                data.trim_notices.push({
                    year: match[1],
                    type: 'PDF'
                });
            }

            // Extract detailed building information
            data.building_details = {
                exterior_walls: findAfterLabel('Exterior Walls'),
                interior_walls: findAfterLabel('Interior Walls'),
                roofing: findAfterLabel('Roofing'),
                roof_type: findAfterLabel('Roof Type'),
                frame: findAfterLabel('Frame'),
                floor_cover: findAfterLabel('Floor Cover'),
                heat: findAfterLabel('Heat'),
                hcv: findAfterLabel('HC&V'),
                hvac: findAfterLabel('HVAC'),
                stories: parseNum(findAfterLabel('Stories')),
                total_area: parseNum(findAfterLabel('Total Area')),
                effective_year_built: parseNum(findAfterLabel('Effective Year Built'))
            };

            // Extract land information
            const landSection = pageText.match(/Land Information[\\s\\S]*?Building Information/);
            if (landSection) {
                const landLines = landSection[0].split('\\n');
                for (let i = 0; i < landLines.length; i++) {
                    const line = landLines[i];
                    // Match: land use code, description, acres, sq ft, frontage, depth, zoning
                    const landMatch = line.match(/^(\\d+)\\s+([^\\t]*)\\s+([\\d.]+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)\\s+(\\w*)/);
                    if (landMatch) {
                        data.land_info.push({
                            use_code: landMatch[1],
                            description: landMatch[2].trim(),
                            acres: parseFloat(landMatch[3]),
                            square_feet: parseInt(landMatch[4]),
                            frontage: parseInt(landMatch[5]),
                            depth: parseInt(landMatch[6]),
                            zoning: landMatch[7]
                        });
                    }
                }
            }

            // Extract sub areas
            const subAreaSections = pageText.matchAll(/Sub Area[\\s\\S]*?Type\\s+Description\\s+Sq\\. Footage\\s+Act Year[\\s\\S]*?(?=Sub Area|Sales|Permits|$)/g);
            for (const section of subAreaSections) {
                const lines = section[0].split('\\n');
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    // Match sub area data rows
                    const subMatch = line.match(/^([A-Z\\d]+)\\s+([^\\t]+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)\\s+([^\\t]*)\\s+([^\\t]*)\\s+([^\\t]*)/);
                    if (subMatch) {
                        data.sub_areas.push({
                            type: subMatch[1],
                            description: subMatch[2].trim(),
                            sq_footage: parseInt(subMatch[3]),
                            actual_year: parseInt(subMatch[4]),
                            effective_year: parseInt(subMatch[5]),
                            quality: subMatch[6].trim(),
                            imprv_use: subMatch[7].trim(),
                            imprv_use_desc: subMatch[8].trim()
                        });
                    }
                }
            }

            // Extract additional valuation details
            data.improvement_value = parseCurrency(findAfterLabel('Improvement Value'));
            data.land_value = parseCurrency(findAfterLabel('Land Value'));
            data.land_agricultural_value = parseCurrency(findAfterLabel('Land Agricultural Value'));
            data.agricultural_market_value = parseCurrency(findAfterLabel('Agricultural .Market. Value'));
            data.exempt_value = parseCurrency(findAfterLabel('Exempt Value'));
            data.max_soh_portability = parseCurrency(findAfterLabel('Maximum Save Our Homes Portability'));

            // Extract links (these would need to be scraped from actual HTML, not text)
            // For now, note their presence
            if (pageText.includes('Tax Collector')) {
                data.links.tax_collector = 'Link to Tax Collector Record';
            }
            if (pageText.includes('Print Sketches')) {
                data.links.sketches = 'Building Sketches Available';
            }
            if (pageText.includes('Map Download')) {
                data.links.map = 'Map Download Available';
            }

            return data;
        }''')

        if not data:
            return None

        # Extract actual URLs from DOM (not available in text)
        urls = await page.evaluate('''() => {
            const urls = {};

            // Tax Collector link
            const allLinks = Array.from(document.querySelectorAll('a'));
            const taxLink = allLinks.find(a =>
                a.href.includes('taxcollector') ||
                a.textContent.includes('Tax Collector')
            );
            if (taxLink) urls.tax_collector_url = taxLink.href;

            // TRIM Notice PDFs
            const trimLinks = allLinks.filter(a =>
                a.href.includes('TRIM') || a.textContent.includes('TRIM Notice')
            );
            urls.trim_notice_urls = {};
            trimLinks.forEach(link => {
                const yearMatch = link.textContent.match(/(\\d{4})/);
                if (yearMatch) {
                    urls.trim_notice_urls[yearMatch[1]] = link.href;
                }
            });

            // Sketches link
            const sketchLink = allLinks.find(a =>
                a.href.toLowerCase().includes('sketch') ||
                a.textContent.includes('Sketch')
            );
            if (sketchLink) urls.sketches_url = sketchLink.href;

            // Map download - check for links and buttons
            const mapLink = allLinks.find(a =>
                a.href.toLowerCase().includes('map') ||
                a.textContent.includes('Map Download')
            );
            if (mapLink) urls.map_url = mapLink.href;

            return urls;
        }''')

        # Merge URLs into data
        if urls:
            data['links']['tax_collector_url'] = urls.get('tax_collector_url')
            data['links']['sketches_url'] = urls.get('sketches_url')
            data['links']['map_url'] = urls.get('map_url')
            data['links']['trim_notice_urls'] = urls.get('trim_notice_urls', {})

        # Extract and convert coordinates from map URL
        map_url = data['links'].get('map_url', '')
        if map_url:
            try:
                # Extract viewpoint coordinates (Florida State Plane East - EPSG:2238)
                viewpoint_match = re.search(r'viewpoint=([0-9.]+),([0-9.]+)', map_url)
                if viewpoint_match:
                    x = float(viewpoint_match.group(1))  # Easting in feet
                    y = float(viewpoint_match.group(2))  # Northing in feet

                    # Convert from EPSG:2238 (FL State Plane East) to EPSG:4326 (WGS84 lat/lon)
                    transformer = Transformer.from_crs('EPSG:2238', 'EPSG:4326', always_xy=True)
                    lon, lat = transformer.transform(x, y)

                    data['coordinates'] = {
                        'latitude': round(lat, 8),
                        'longitude': round(lon, 8),
                        'state_plane_x': round(x, 2),
                        'state_plane_y': round(y, 2),
                        'projection': 'EPSG:2238',
                        'coordinate_system': 'Florida State Plane East (NAD83)'
                    }

                    logger.debug(f"Extracted coordinates: lat={lat:.6f}, lon={lon:.6f}")
            except Exception as e:
                logger.warning(f"Failed to extract coordinates: {e}")

        # Add metadata
        data['parcel_id'] = parcel_id
        data['source_url'] = page.url
        data['scraped_at'] = datetime.now().isoformat()

        return data

    async def scrape_batch(self, parcel_ids: List[str],
                           max_errors: int = 10) -> List[Dict]:
        """
        Scrape multiple properties in batch.

        Args:
            parcel_ids: List of parcel IDs
            max_errors: Max consecutive errors before stopping

        Returns:
            List of property data dicts
        """
        results = []
        consecutive_errors = 0

        logger.info("Starting batch scrape", count=len(parcel_ids))

        for i, parcel_id in enumerate(parcel_ids, 1):
            try:
                data = await self.scrape_property(parcel_id)
                if data:
                    results.append(data)
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1

                if i % 10 == 0:
                    logger.info("Batch progress",
                               completed=i,
                               total=len(parcel_ids),
                               success_rate=f"{len(results)/i*100:.1f}%")

            except Exception as e:
                logger.error("Batch error", parcel_id=parcel_id, error=str(e))
                consecutive_errors += 1

            if consecutive_errors >= max_errors:
                logger.error("Too many errors, stopping", errors=consecutive_errors)
                break

        logger.info("Batch complete",
                   total=len(parcel_ids),
                   successful=len(results),
                   success_rate=f"{len(results)/len(parcel_ids)*100:.1f}%")

        return results


# Convenience function for async usage
async def scrape_parcel_async(parcel_id: str, headless: bool = True) -> Optional[Dict]:
    """
    Convenience function to scrape a single parcel.

    Args:
        parcel_id: Parcel ID to scrape
        headless: Run browser in headless mode

    Returns:
        Property data dict or None
    """
    scraper = QPublicBrowserScraper(headless=headless)
    return await scraper.scrape_property(parcel_id)


# Sync wrapper for convenience
def scrape_parcel(parcel_id: str, headless: bool = True) -> Optional[Dict]:
    """
    Synchronous wrapper to scrape a single parcel.

    Args:
        parcel_id: Parcel ID to scrape
        headless: Run browser in headless mode

    Returns:
        Property data dict or None
    """
    return asyncio.run(scrape_parcel_async(parcel_id, headless))


if __name__ == "__main__":
    # Test the scraper
    test_parcel = "17757-003-004"
    print(f"Testing qPublic browser scraper with parcel: {test_parcel}\n")

    data = scrape_parcel(test_parcel, headless=True)

    if data:
        print("SUCCESS! Scraped property data:")
        print(f"  Parcel ID: {data.get('parcel_id')}")
        print(f"  Address: {data.get('property_address')}")
        print(f"  Owner: {data.get('owner_name')}")
        print(f"  Market Value: ${data.get('market_value', 0):,.0f}")
        print(f"  Year Built: {data.get('year_built')}")
        print(f"  Square Feet: {data.get('square_footage')}")
    else:
        print("FAILED to scrape property")
