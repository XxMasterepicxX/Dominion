"""
Sunbiz Website Scraper

Scrapes complete LLC/corporation data from Florida Sunbiz website using Patchright.
Bypasses Cloudflare and extracts registered agent, officers, FEI/EIN, and more.

Data Source: https://search.sunbiz.org
Method: Patchright (Playwright-based with Cloudflare bypass)
"""
from datetime import datetime
from typing import Dict, List, Optional
from patchright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import structlog

logger = structlog.get_logger(__name__)


class SunbizWebsiteScraper:
    """
    Scrapes Florida Sunbiz website for complete LLC/corporation data.

    Uses Patchright to bypass Cloudflare protection and extract:
    - Registered agent (name + address)
    - Officers with titles
    - FEI/EIN number
    - Filing dates and status
    - Annual reports
    - Event history
    """

    BASE_URL = "https://search.sunbiz.org"

    def __init__(self, headless: bool = True):
        """
        Initialize Sunbiz website scraper.

        Args:
            headless: Run browser in headless mode (default: True)
        """
        self.headless = headless

    def get_search_url(self) -> str:
        """Get the document number search page URL"""
        return f"{self.BASE_URL}/Inquiry/CorporationSearch/ByDocumentNumber"

    async def scrape_entity(self, document_number: str) -> Optional[Dict]:
        """
        Scrape complete entity data from Sunbiz website.

        Args:
            document_number: Sunbiz document number (e.g., "L25000442910")

        Returns:
            Dict with complete entity data or None if error
        """
        search_url = self.get_search_url()

        logger.info("Scraping Sunbiz entity", document_number=document_number)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                page = await browser.new_page()

                # Go to document number search page
                logger.info("Navigating to search page", url=search_url)
                await page.goto(search_url, wait_until='networkidle', timeout=30000)

                # Fill in document number and submit
                logger.info("Searching for document number", document_number=document_number)
                await page.fill('#SearchTerm', document_number)
                await page.click('input[type="submit"]')

                # Wait for detail page to load
                await page.wait_for_selector('.corporationName', timeout=10000)
                logger.info("Detail page loaded")

                # Extract all data using JavaScript
                data = await page.evaluate('''() => {
                    const sections = document.querySelectorAll('.detailSection');

                    // Helper to clean address
                    const cleanAddress = (div) => {
                        if (!div) return '';
                        return div.innerHTML.replace(/<br\\s*\\/?>/gi, ', ').trim();
                    };

                    // Helper to get label value
                    const getLabelValue = (labelFor) => {
                        const label = document.querySelector(`label[for="${labelFor}"]`);
                        return label?.nextElementSibling?.textContent?.trim() || null;
                    };

                    const data = {
                        // Entity info
                        entityType: document.querySelector('.corporationName p:nth-child(1)')?.textContent?.trim(),
                        entityName: document.querySelector('.corporationName p:nth-child(2)')?.textContent?.trim(),

                        // Filing information
                        documentNumber: getLabelValue('Detail_DocumentId'),
                        feiEin: getLabelValue('Detail_FeiEinNumber'),
                        dateFiled: getLabelValue('Detail_FileDate'),
                        state: getLabelValue('Detail_EntityStateCountry'),
                        status: getLabelValue('Detail_Status'),
                        lastEvent: getLabelValue('Detail_LastEvent'),
                        eventDateFiled: getLabelValue('Detail_LastEventFileDate'),
                        eventEffectiveDate: getLabelValue('Detail_EventEffectiveDate'),

                        // Addresses
                        principalAddress: null,
                        mailingAddress: null,

                        // Registered agent
                        registeredAgent: {
                            name: null,
                            address: null
                        },

                        // Officers
                        officers: [],

                        // Annual reports
                        annualReports: [],

                        // Metadata
                        scrapedAt: new Date().toISOString(),
                        sourceUrl: window.location.href
                    };

                    // Extract addresses (sections 2 and 3)
                    if (sections[2]) {
                        const addrDiv = sections[2].querySelector('span:nth-child(2) div');
                        data.principalAddress = cleanAddress(addrDiv);
                    }

                    if (sections[3]) {
                        const addrDiv = sections[3].querySelector('span:nth-child(2) div');
                        data.mailingAddress = cleanAddress(addrDiv);
                    }

                    // Extract registered agent (section 4)
                    if (sections[4]) {
                        data.registeredAgent.name = sections[4].querySelector('span:nth-child(2)')?.textContent?.trim();
                        const agentAddrDiv = sections[4].querySelector('span:nth-child(3) div');
                        data.registeredAgent.address = cleanAddress(agentAddrDiv);
                    }

                    // Extract officers (section 5)
                    if (sections[5]) {
                        const officerSpans = sections[5].querySelectorAll('span');
                        let currentOfficer = null;

                        officerSpans.forEach(span => {
                            const text = span.textContent.trim();

                            if (text.startsWith('Title')) {
                                // Save previous officer
                                if (currentOfficer) {
                                    data.officers.push(currentOfficer);
                                }

                                // Start new officer
                                currentOfficer = {
                                    title: text.replace(/Title\\s+/, ''),
                                    name: '',
                                    address: ''
                                };
                            } else if (currentOfficer && !currentOfficer.name && !span.querySelector('div')) {
                                // Name comes after title
                                currentOfficer.name = text;
                            } else if (currentOfficer && span.querySelector('div')) {
                                // Address in div
                                currentOfficer.address = cleanAddress(span.querySelector('div'));
                            }
                        });

                        // Save last officer
                        if (currentOfficer) {
                            data.officers.push(currentOfficer);
                        }
                    }

                    // Extract annual reports (section 6)
                    if (sections[6]) {
                        const reportRows = sections[6].querySelectorAll('tbody tr');
                        reportRows.forEach((row, i) => {
                            if (i > 0) { // Skip header row
                                const cells = row.querySelectorAll('td');
                                if (cells.length >= 2) {
                                    data.annualReports.push({
                                        year: cells[0].textContent.trim(),
                                        filedDate: cells[1].textContent.trim()
                                    });
                                }
                            }
                        });
                    }

                    return data;
                }''')

                await browser.close()

                logger.info(
                    "Successfully scraped Sunbiz entity",
                    document_number=document_number,
                    name=data.get('entityName'),
                    has_reg_agent=bool(data.get('registeredAgent', {}).get('name')),
                    officer_count=len(data.get('officers', []))
                )

                return data

        except PlaywrightTimeout:
            logger.error("Timeout scraping Sunbiz entity", document_number=document_number)
            return None
        except Exception as e:
            logger.error("Error scraping Sunbiz entity", document_number=document_number, error=str(e))
            return None

    async def scrape_multiple(self, document_numbers: List[str]) -> Dict[str, Dict]:
        """
        Scrape multiple entities in batch.

        Args:
            document_numbers: List of document numbers to scrape

        Returns:
            Dict mapping document_number -> entity data
        """
        results = {}

        logger.info("Batch scraping Sunbiz entities", count=len(document_numbers))

        for doc_num in document_numbers:
            data = await self.scrape_entity(doc_num)
            if data:
                results[doc_num] = data

        logger.info(
            "Batch scrape complete",
            total=len(document_numbers),
            successful=len(results),
            failed=len(document_numbers) - len(results)
        )

        return results

    async def search_by_officer_or_agent(self, person_name: str, max_results: int = 10) -> List[Dict]:
        """
        Search for entities by officer or registered agent name.

        Args:
            person_name: Person's name to search for
            max_results: Maximum number of results to return

        Returns:
            List of dicts with entity info where person is officer/agent
        """
        search_url = f"{self.BASE_URL}/Inquiry/CorporationSearch/ByOfficerOrRegisteredAgent"

        logger.info("Searching Sunbiz by officer/agent", person_name=person_name)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                page = await browser.new_page()

                # Navigate to search page
                await page.goto(search_url, wait_until='networkidle')

                # Fill search form
                await page.fill('#SearchTerm', person_name)
                await page.click('input[type="submit"]')

                # Wait for results
                await page.wait_for_selector('#search-results', timeout=10000)

                # Extract results (different column structure!)
                results = await page.evaluate('''(maxResults) => {
                    const rows = document.querySelectorAll('#search-results tbody tr');
                    const results = [];

                    rows.forEach((row, i) => {
                        if (i >= maxResults) return;

                        const cells = row.querySelectorAll('td');
                        const link = row.querySelector('a');

                        if (cells.length >= 3 && link) {
                            results.push({
                                officerName: cells[0].textContent.trim(),
                                name: cells[1].textContent.trim(),  // Company name
                                documentNumber: cells[2].textContent.trim(),
                                detailUrl: link.href
                            });
                        }
                    });

                    return results;
                }''', max_results)

                await browser.close()

                logger.info(
                    "Officer/agent search complete",
                    person_name=person_name,
                    results_found=len(results)
                )

                return results

        except Exception as e:
            logger.error("Error searching by officer/agent", person_name=person_name, error=str(e))
            return []

    async def search_by_name(self, entity_name: str, max_results: int = 10) -> List[Dict]:
        """
        Search for entities by name and return list of matches.

        Args:
            entity_name: Entity name to search for
            max_results: Maximum number of results to return

        Returns:
            List of dicts with basic entity info (name, document_number, status)
        """
        search_url = f"{self.BASE_URL}/Inquiry/CorporationSearch/ByName"

        logger.info("Searching Sunbiz by name", entity_name=entity_name)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                page = await browser.new_page()

                # Navigate to search page
                await page.goto(search_url, wait_until='networkidle')

                # Fill search form
                await page.fill('#SearchTerm', entity_name)
                await page.click('input[type="submit"]')

                # Wait for results
                await page.wait_for_selector('#search-results', timeout=10000)

                # Extract results
                results = await page.evaluate('''(maxResults) => {
                    const rows = document.querySelectorAll('#search-results tbody tr');
                    const results = [];

                    rows.forEach((row, i) => {
                        if (i >= maxResults) return;

                        const nameLink = row.querySelector('td:nth-child(1) a');
                        const docNumCell = row.querySelector('td:nth-child(2)');
                        const statusCell = row.querySelector('td:nth-child(3)');

                        if (nameLink && docNumCell) {
                            results.push({
                                name: nameLink.textContent.trim(),
                                documentNumber: docNumCell.textContent.trim(),
                                status: statusCell?.textContent?.trim() || 'Unknown',
                                detailUrl: nameLink.href
                            });
                        }
                    });

                    return results;
                }''', max_results)

                await browser.close()

                logger.info(
                    "Search complete",
                    entity_name=entity_name,
                    results_found=len(results)
                )

                return results

        except Exception as e:
            logger.error("Error searching Sunbiz", entity_name=entity_name, error=str(e))
            return []


# Convenience function
async def scrape_sunbiz_entity(document_number: str, headless: bool = True) -> Optional[Dict]:
    """
    Quick function to scrape a single Sunbiz entity.

    Args:
        document_number: Sunbiz document number
        headless: Run browser in headless mode

    Returns:
        Entity data dict or None
    """
    scraper = SunbizWebsiteScraper(headless=headless)
    return await scraper.scrape_entity(document_number)
