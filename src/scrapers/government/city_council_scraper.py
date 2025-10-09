"""
City Council Scraper

Scrapes meeting minutes, agendas, and voting records from city council portals.
Config-driven to support multiple platforms.

Platforms:
- eScribe: Uses AJAX endpoints (JSON API)
- Legistar: Uses HTML scraping
- OnBase: Uses Playwright (more complex)
"""
import sys
import requests
import tempfile
import re
import urllib3
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import structlog

from ...config.schemas import MarketConfig

# Suppress InsecureRequestWarning when SSL verification is disabled
# This is intentional for self-signed certs on some government portals
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


class MeetingRecord:
    """City council meeting record model."""

    def __init__(self, data: Dict):
        self.meeting_id = data.get('meeting_id', '')
        self.escribe_id = data.get('escribe_id', '')
        self.meeting_date = data.get('meeting_date', '')
        self.meeting_type = data.get('meeting_type', '')
        self.board_name = data.get('board_name', '')
        self.title = data.get('title', '')
        self.status = data.get('status', '')
        self.location = data.get('location', '')
        self.start_time = data.get('start_time', '')
        self.agenda_url = data.get('agenda_url', '')
        self.minutes_url = data.get('minutes_url', '')
        self.video_url = data.get('video_url', '')
        self.is_cancelled = data.get('is_cancelled', False)
        self.agenda_items = data.get('agenda_items', [])
        self.extracted_text = data.get('extracted_text', '')

    def to_dict(self) -> Dict:
        return {
            'meeting_id': self.meeting_id,
            'escribe_id': self.escribe_id,
            'meeting_date': self.meeting_date,
            'meeting_type': self.meeting_type,
            'board_name': self.board_name,
            'title': self.title,
            'status': self.status,
            'location': self.location,
            'start_time': self.start_time,
            'agenda_url': self.agenda_url,
            'minutes_url': self.minutes_url,
            'video_url': self.video_url,
            'is_cancelled': self.is_cancelled,
            'agenda_items': self.agenda_items,  # FIXED: Actually include the items!
            'extracted_text': self.extracted_text,  # FIXED: Actually include the text!
            'agenda_items_count': len(self.agenda_items),
            'text_length': len(self.extracted_text),
        }


logger = structlog.get_logger(__name__)


class CouncilScraper:
    """City council scraper with meeting data extraction using platform-specific methods."""

    def __init__(self, market_config: MarketConfig, verify_ssl: bool = False):
        """
        Initialize with market config.

        Args:
            market_config: Market configuration
            verify_ssl: Enable SSL verification (default False for self-signed certs on gov portals)
        """
        self.config = market_config
        self.council_config = market_config.scrapers.council

        if not self.council_config or not self.council_config.enabled:
            raise ValueError("Council scraper not enabled in config")

        self.platform = self.council_config.platform.lower()
        self.endpoint = self.council_config.endpoint
        self.verify_ssl = verify_ssl

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        })

        if not verify_ssl:
            logger.warning("ssl_verification_disabled",
                         market=self.config.market.name,
                         reason="self_signed_cert_on_gov_portal")

        logger.info("council_scraper_initialized",
                   market=self.config.market.name,
                   platform=self.platform,
                   ssl_verify=verify_ssl)

    def fetch_recent_meetings(self, months_back: int = 3) -> List[Dict]:
        """
        Fetch meetings from the last N months.

        Args:
            months_back: Number of months to look back

        Returns:
            List of meeting dictionaries (converted from MeetingRecord objects)
        """
        meetings = []

        if self.platform == "escribe":
            meetings = self._fetch_escribe_ajax_meetings(months_back)
        elif self.platform == "legistar":
            meetings = self._fetch_legistar_meetings(months_back)
        elif self.platform == "onbase":
            meetings = self._fetch_onbase_meetings(months_back)
        else:
            logger.error("unknown_platform", platform=self.platform)
            return []

        # Convert MeetingRecord objects to dicts for compatibility
        return [meeting.to_dict() for meeting in meetings]

    def _fetch_escribe_ajax_meetings(self, months_back: int) -> List[MeetingRecord]:
        """Fetch meetings from eScribe using AJAX endpoints."""
        meetings = []

        try:
            end_date = datetime.now() + timedelta(days=30)
            start_date = datetime.now() - timedelta(days=90)

            calendar_url = f"{self.endpoint.rstrip('/')}/MeetingsCalendarView.aspx/GetCalendarMeetings"

            payload = {
                "calendarStartDate": start_date.strftime("%Y-%m-%d"),
                "calendarEndDate": end_date.strftime("%Y-%m-%d")
            }

            logger.info("fetch_escribe_meetings_started",
                       endpoint=calendar_url,
                       date_range=f"{start_date.date()} to {end_date.date()}")

            response = self.session.post(
                calendar_url,
                json=payload,
                headers=self.session.headers,
                timeout=30,
                verify=self.verify_ssl
            )

            if response.status_code != 200:
                logger.error("escribe_request_failed",
                           status_code=response.status_code,
                           response_preview=response.text[:500])

            response.raise_for_status()

            data = response.json()
            calendar_data = data.get('d', [])

            logger.info("escribe_response_received", meetings_count=len(calendar_data))

            for meeting_data in calendar_data:
                try:
                    meeting = self._parse_escribe_meeting(meeting_data)
                    if meeting and start_date <= self._parse_escribe_date(meeting.meeting_date) <= end_date:
                        meetings.append(meeting)

                        # Extract content from PDFs
                        if meeting.agenda_url and meeting.agenda_url.endswith('.pdf'):
                            self._extract_pdf_text(meeting, 'agenda')
                        # NEW: Extract content from HTML pages
                        elif meeting.agenda_url:
                            self._extract_html_content(meeting, 'agenda')

                        if meeting.minutes_url and meeting.minutes_url.endswith('.pdf'):
                            self._extract_pdf_text(meeting, 'minutes')
                        # NEW: Extract content from HTML pages
                        elif meeting.minutes_url:
                            self._extract_html_content(meeting, 'minutes')

                except Exception as e:
                    logger.warning("meeting_parse_failed", error=str(e))
                    continue

            logger.info("fetch_escribe_meetings_completed",
                       meetings_found=len(meetings))

        except Exception as e:
            logger.error("escribe_scraping_failed", error=str(e))
            import traceback
            traceback.print_exc()

        return meetings

    def _parse_escribe_meeting(self, meeting_data: Dict) -> Optional[MeetingRecord]:
        """Parse individual meeting from eScribe JSON."""
        try:
            meeting_id = meeting_data.get('ID', '')
            board_name = meeting_data.get('MeetingName', '').strip()

            date_str = meeting_data.get('StartDate', '')
            meeting_date_parsed = self._parse_escribe_date(date_str)
            if not meeting_date_parsed:
                return None

            description = meeting_data.get('Description', '').lower()
            is_cancelled = 'cancel' in description

            start_time = date_str
            location = meeting_data.get('Location', '')
            agenda_url = ''
            minutes_url = ''
            doc_links = meeting_data.get('MeetingDocumentLink', [])
            for doc in doc_links:
                doc_type = doc.get('Type', '').lower()
                if 'agenda' in doc_type:
                    url = doc.get('Url', '')
                    if url:
                        agenda_url = f"{self.endpoint.rstrip('/')}/{url}" if not url.startswith('http') else url
                elif 'minute' in doc_type:
                    url = doc.get('Url', '')
                    if url:
                        minutes_url = f"{self.endpoint.rstrip('/')}/{url}" if not url.startswith('http') else url

            video_url = '' if not meeting_data.get('HasVideo', False) else meeting_data.get('Url', '')

            meeting_id_str = f"{meeting_date_parsed.strftime('%Y%m%d')}_{board_name.replace(' ', '_')}_{meeting_id}"

            return MeetingRecord({
                'meeting_id': meeting_id_str,
                'escribe_id': meeting_id,
                'meeting_date': meeting_date_parsed.strftime('%m/%d/%Y'),
                'meeting_type': board_name,
                'board_name': board_name,
                'title': f"{board_name} Meeting",
                'status': 'Cancelled' if is_cancelled else 'Scheduled',
                'location': location,
                'start_time': start_time,
                'agenda_url': agenda_url if agenda_url else None,
                'minutes_url': minutes_url if minutes_url else None,
                'video_url': video_url if video_url else None,
                'is_cancelled': is_cancelled,
            })

        except Exception as e:
            logger.debug("escribe_meeting_parse_error", error=str(e))
            return None

    def _parse_escribe_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from eScribe JSON format."""
        if not date_str:
            return None

        for fmt in [
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y"
        ]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        json_date_match = re.search(r'/Date\((\d+)\)/', date_str)
        if json_date_match:
            timestamp = int(json_date_match.group(1)) / 1000
            return datetime.fromtimestamp(timestamp)

        return None

    def _extract_html_content(self, meeting: MeetingRecord, doc_type: str):
        """
        Extract content from HTML meeting pages using simple parsing.

        Based on testing, we found eScribe pages contain extractable content
        in the <article> tag and raw text, even though they use JavaScript.

        This method uses BeautifulSoup to extract:
        - Agenda items
        - Recommendations
        - Resolutions
        - Full meeting text
        """
        from bs4 import BeautifulSoup

        try:
            url = meeting.agenda_url if doc_type == 'agenda' else meeting.minutes_url
            if not url:
                return

            logger.info(f"extracting_html_content_{doc_type}", url=url[:80])

            response = self.session.get(url, timeout=30, verify=self.verify_ssl)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract from <article> tag (most reliable)
            article = soup.find('article')
            if article:
                # Get all text
                text = article.get_text(separator='\n', strip=True)

                # Store extracted text
                if meeting.extracted_text:
                    meeting.extracted_text += f"\n\n--- {doc_type.upper()} ---\n\n" + text
                else:
                    meeting.extracted_text = text

                # Extract agenda items
                agenda_items = self._parse_agenda_items(text)
                if agenda_items:
                    meeting.agenda_items.extend(agenda_items)

                logger.info(f"html_content_extracted_{doc_type}",
                           text_length=len(text),
                           agenda_items=len(agenda_items))
            else:
                logger.warning(f"no_article_tag_{doc_type}", url=url[:80])

        except Exception as e:
            logger.error(f"html_extraction_failed_{doc_type}", error=str(e), url=url[:80] if 'url' in locals() else 'unknown')

    def _parse_agenda_items(self, text: str) -> list:
        """Parse agenda items from meeting text"""
        items = []

        # Pattern 1: Numbered items (1., 2., 3.)
        numbered = re.findall(r'\n(\d+\..+?)(?=\n\d+\.|\nRecommendation:|\Z)', text, re.DOTALL)
        items.extend([item.strip() for item in numbered if len(item.strip()) > 10])

        # Pattern 2: Standard agenda keywords
        keywords = [
            'CALL TO ORDER',
            'ROLL CALL',
            'APPROVAL OF MINUTES',
            'APPROVAL OF THE AGENDA',
            'PUBLIC COMMENT',
            'NEW BUSINESS',
            'OLD BUSINESS',
            'ADJOURNMENT'
        ]

        for keyword in keywords:
            if keyword in text.upper():
                items.append(keyword)

        # Pattern 3: Recommendations
        recommendations = re.findall(r'Recommendation:\s*(.+?)(?=\nRecommendation:|\n\d+\.|\Z)', text, re.DOTALL | re.IGNORECASE)
        for rec in recommendations:
            rec = rec.strip()
            rec = re.sub(r'\s+', ' ', rec)  # Normalize whitespace
            if len(rec) > 20:
                items.append(f"RECOMMENDATION: {rec}")

        # Pattern 4: Resolutions (2025-807, etc.)
        resolutions = re.findall(r'\b(20\d{2}-\d{3,4})\b', text)
        for resolution in resolutions:
            items.append(f"RESOLUTION {resolution}")

        return items

    def _extract_pdf_text(self, meeting: MeetingRecord, doc_type: str):
        """Download and extract text from PDF (agenda or minutes)."""
        if not PyPDF2:
            logger.warning("pypdf2_not_installed")
            return

        temp_file_path = None
        try:
            url = meeting.agenda_url if doc_type == 'agenda' else meeting.minutes_url
            if not url:
                return

            response = self.session.get(url, timeout=60, verify=self.verify_ssl)
            response.raise_for_status()

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file_path = temp_file.name
            temp_file.write(response.content)
            temp_file.close()

            with open(temp_file_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                text_parts = []

                for page_num in range(min(len(pdf_reader.pages), 50)):
                    page = pdf_reader.pages[page_num]
                    text_parts.append(page.extract_text())

                extracted_text = '\n'.join(text_parts)
                meeting.extracted_text += f"\n\n=== {doc_type.upper()} ===\n{extracted_text}"

                logger.info("pdf_text_extracted",
                           doc_type=doc_type,
                           chars_extracted=len(extracted_text))

        except Exception as e:
            logger.warning("pdf_extraction_failed", doc_type=doc_type, error=str(e))

        finally:
            # Always cleanup temp file, even on error
            if temp_file_path and Path(temp_file_path).exists():
                try:
                    Path(temp_file_path).unlink()
                except Exception as cleanup_error:
                    logger.warning("temp_file_cleanup_failed", path=temp_file_path, error=str(cleanup_error))

    def _fetch_legistar_meetings(self, months_back: int) -> List[MeetingRecord]:
        """Fetch meetings from Legistar (HTML scraping)."""
        logger.info("legistar_not_implemented")
        return []

    def _fetch_onbase_meetings(self, months_back: int) -> List[MeetingRecord]:
        """Fetch meetings from OnBase (Tampa's platform)."""
        logger.info("onbase_not_implemented")
        return []


def test_scraper():
    """Test the council scraper."""
    from ...config.loader import load_market_config

    print("\n=== Testing Council Scraper ===\n")

    try:
        config = load_market_config('gainesville_fl')
        print(f"[OK] Loaded config for {config.market.name}")
    except Exception as e:
        print(f"[FAIL] Failed to load config: {e}")
        return

    # Initialize scraper
    try:
        scraper = CouncilScraper(config)
        print(f"[OK] Initialized scraper for {config.market.name}")
        print(f"     Platform: {scraper.platform}")
        print(f"     Endpoint: {scraper.endpoint}")
    except Exception as e:
        print(f"[FAIL] Failed to initialize scraper: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"\n[TEST] Fetching meeting data (last 3 months)...")
    meetings = scraper.fetch_recent_meetings(months_back=3)

    if meetings:
        print(f"\n[SUCCESS] Fetched {len(meetings)} meetings!")

        first = meetings[0]
        print(f"\n--- Sample Meeting ---")
        print(f"Meeting ID: {first.meeting_id}")
        print(f"eScribe ID: {first.escribe_id}")
        print(f"Date: {first.meeting_date}")
        print(f"Board: {first.board_name}")
        print(f"Title: {first.title}")
        print(f"Status: {first.status}")
        print(f"Location: {first.location}")
        if first.start_time:
            print(f"Start Time: {first.start_time}")
        if first.agenda_url:
            print(f"Agenda: {first.agenda_url[:80]}...")
        if first.minutes_url:
            print(f"Minutes: {first.minutes_url[:80]}...")
        if first.video_url:
            print(f"Video: {first.video_url[:80]}...")
        if first.extracted_text:
            print(f"Extracted Text: {len(first.extracted_text)} chars")
            print(f"  Preview: {first.extracted_text[:200].strip()}...")

        # Show summary
        print(f"\n--- Summary ---")
        print(f"Total Meetings: {len(meetings)}")

        # Count by board
        board_types = {}
        for m in meetings:
            board_types[m.board_name] = board_types.get(m.board_name, 0) + 1
        print(f"By Board:")
        for board, count in sorted(board_types.items(), key=lambda x: -x[1])[:5]:
            print(f"  - {board}: {count}")

        # Count meetings with documents
        with_agenda = sum(1 for m in meetings if m.agenda_url)
        with_minutes = sum(1 for m in meetings if m.minutes_url)
        with_video = sum(1 for m in meetings if m.video_url)
        with_text = sum(1 for m in meetings if m.extracted_text)

        print(f"\nDocuments:")
        print(f"  With Agenda: {with_agenda}")
        print(f"  With Minutes: {with_minutes}")
        print(f"  With Video: {with_video}")
        print(f"  With Extracted Text: {with_text}")

    else:
        print(f"\n[WARN] No meetings found")
        print(f"[INFO] This may be normal if:")
        print(f"       - eScribe endpoint URL is incorrect")
        print(f"       - No meetings in the date range")
        print(f"       - Network/authentication issues")

    print(f"\n[INFO] Council scraper test complete")


if __name__ == "__main__":
    import warnings
    from urllib3.exceptions import InsecureRequestWarning
    warnings.simplefilter('ignore', InsecureRequestWarning)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    test_scraper()
