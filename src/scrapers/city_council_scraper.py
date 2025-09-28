"""
Gainesville City Council & Development Boards Scraper (via eScribe AJAX)

Tracks all city meetings affecting real estate development:
- City Commission (final approvals)
- Development Review Board (site plans)
- Plan Board (comprehensive plan changes)
- Historic Preservation Board (renovation impacts)
- Housing Advisory Committee (affordable housing)
- CRA Boards (redevelopment areas)
- Board of Adjustment (variances)
- Public Works & Utility Boards (infrastructure)

Extracts development petitions (LD25-XXXXXX), rezoning requests, and assemblage signals.

Data Source: eScribe AJAX endpoints (migrated from Legistar 2020)
Update Frequency: Daily (8am to catch overnight agenda updates)
Intelligence Value: Early development signals, political sentiment, assemblage patterns
"""
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, validator
import PyPDF2
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

from .base.resilient_scraper import ResilientScraper, ScraperType, ScrapingResult
from ..database.connection import DatabaseManager
from .base.change_detector import ChangeDetector


class DocumentType(Enum):
    """Types of council documents."""
    AGENDA = "agenda"
    MINUTES = "minutes"
    ORDINANCE = "ordinance"
    RESOLUTION = "resolution"
    STAFF_REPORT = "staff_report"
    PUBLIC_HEARING = "public_hearing"
    BUDGET = "budget"
    ANNOUNCEMENT = "announcement"
    DEVELOPMENT_APPLICATION = "development_application"
    REZONING_REQUEST = "rezoning_request"
    VARIANCE_APPLICATION = "variance_application"
    OTHER = "other"


class MeetingType(Enum):
    """Types of meetings that affect real estate development."""
    CITY_COMMISSION = "City Commission"
    DEVELOPMENT_REVIEW_BOARD = "Development Review Board"
    PLAN_BOARD = "Plan Board"
    HISTORIC_PRESERVATION = "Historic Preservation Board"
    HOUSING_ADVISORY = "SHIP - Affordable Housing Advisory Committee"
    CRA_DOWNTOWN = "CRA Advisory Board - Downtown"
    CRA_EASTSIDE = "CRA Advisory Board - Eastside"
    BOARD_OF_ADJUSTMENT = "Board of Adjustment"
    TREE_ADVISORY = "Tree Advisory Board"
    PUBLIC_WORKS = "Public Works Committee"
    UTILITY_ADVISORY = "Utility Advisory Board"
    OTHER = "Other"


class MeetingStatus(Enum):
    """Meeting status."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


class VoteResult(Enum):
    """Voting results."""
    APPROVED = "approved"
    DENIED = "denied"
    TABLED = "tabled"
    WITHDRAWN = "withdrawn"
    CONTINUED = "continued"


class CouncilMember(BaseModel):
    """Model for council member information."""
    name: str = Field(..., min_length=1)
    title: Optional[str] = None  # Mayor, Commissioner, etc.
    district: Optional[str] = None
    vote: Optional[str] = None  # For specific agenda items


class DevelopmentPetition(BaseModel):
    """Model for development petition extracted from agenda."""
    petition_id: str = Field(..., regex=r'^LD\d{2}-\d{6}$')  # LD25-000094 format
    petition_type: str  # Rezoning, Site Plan, Variance
    property_address: Optional[str] = None
    parcel_id: Optional[str] = None
    applicant_name: Optional[str] = None
    agent_attorney: Optional[str] = None
    description: Optional[str] = None
    current_zoning: Optional[str] = None
    proposed_zoning: Optional[str] = None
    development_details: Optional[str] = None


class AgendaItem(BaseModel):
    """Model for individual agenda items."""
    item_number: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    item_type: DocumentType = DocumentType.OTHER
    presenter: Optional[str] = None
    department: Optional[str] = None
    action_required: Optional[str] = None  # Vote, Discussion, Information
    vote_result: Optional[VoteResult] = None
    voting_record: Optional[List[CouncilMember]] = None
    attachments: Optional[List[str]] = None  # URLs to supporting documents
    public_comment: bool = False

    # Development-specific fields
    development_petition: Optional[DevelopmentPetition] = None
    affects_real_estate: bool = False
    assemblage_signal: bool = False


class CouncilMeeting(BaseModel):
    """Model for city council meeting data."""
    meeting_id: str = Field(..., min_length=1)
    meeting_date: datetime
    meeting_type: MeetingType = MeetingType.CITY_COMMISSION
    board_name: str = Field(default="City Commission")
    status: MeetingStatus = MeetingStatus.SCHEDULED
    title: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # eScribe specific fields
    escribe_meeting_id: Optional[str] = None
    calendar_id: Optional[str] = None
    is_cancelled: bool = False
    cancellation_reason: Optional[str] = None
    is_rescheduled: bool = False
    original_date: Optional[datetime] = None

    # Documents
    agenda_url: Optional[str] = None
    minutes_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None

    # Content
    agenda_items: List[AgendaItem] = Field(default_factory=list)
    attendees: List[CouncilMember] = Field(default_factory=list)
    absent_members: List[str] = Field(default_factory=list)

    # Extracted text
    agenda_text: Optional[str] = None
    minutes_text: Optional[str] = None

    # Metadata
    portal_url: str
    document_count: int = 0
    extraction_confidence: float = 0.0

    @validator('meeting_date', pre=True)
    def parse_meeting_date(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            # Try various date formats common in government portals
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y %I:%M %p",
                "%m/%d/%Y",
                "%B %d, %Y",
                "%b %d, %Y",
                "%A, %B %d, %Y"
            ]:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            # Try parsing with dateutil as fallback
            try:
                from dateutil import parser
                return parser.parse(v)
            except:
                raise ValueError(f"Unable to parse date: {v}")
        return v


class CityCouncilScraper(ResilientScraper):
    """
    Scraper for city council meetings, agendas, and minutes.

    Supports multiple portal types (Legistar, Granicus, etc.) with configurable
    extraction rules. Handles PDF documents with OCR capabilities.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        change_detector: ChangeDetector,
        portal_base_url: str,
        portal_type: str = "legistar",  # legistar, granicus, custom
        data_directory: Optional[str] = None,
        enable_ocr: bool = True,
        **kwargs
    ):
        super().__init__(
            scraper_id="city_council_scraper",
            scraper_type=ScraperType.WEB,
            enable_js=True,  # Many portals use JavaScript
            **kwargs
        )
        self.db_manager = db_manager
        self.change_detector = change_detector
        self.portal_base_url = portal_base_url.rstrip('/')
        self.portal_type = portal_type.lower()
        self.data_directory = Path(data_directory or "./data/council_docs")
        self.enable_ocr = enable_ocr

        # Create data directory
        self.data_directory.mkdir(parents=True, exist_ok=True)

        # eScribe AJAX endpoints configuration
        self.escribe_endpoints = {
            "calendar_meetings": "/MeetingsCalendarView.aspx/GetCalendarMeetings",
            "meeting_detail": "/MeetingDetailView.aspx/GetMeetingDetail",
            "agenda_items": "/AgendaView.aspx/GetAgendaItems"
        }

        # Development-focused meeting types to monitor
        self.target_meeting_types = {
            "City Commission": MeetingType.CITY_COMMISSION,
            "Development Review Board": MeetingType.DEVELOPMENT_REVIEW_BOARD,
            "Plan Board": MeetingType.PLAN_BOARD,
            "Historic Preservation Board": MeetingType.HISTORIC_PRESERVATION,
            "SHIP - Affordable Housing Advisory Committee": MeetingType.HOUSING_ADVISORY,
            "CRA Advisory Board - Downtown": MeetingType.CRA_DOWNTOWN,
            "CRA Advisory Board - Eastside": MeetingType.CRA_EASTSIDE,
            "Board of Adjustment": MeetingType.BOARD_OF_ADJUSTMENT,
            "Tree Advisory Board": MeetingType.TREE_ADVISORY,
            "Public Works Committee": MeetingType.PUBLIC_WORKS,
            "Utility Advisory Board": MeetingType.UTILITY_ADVISORY
        }

        # Headers to bypass CloudFlare
        self.ajax_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        }

    async def scrape_meeting_list(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[CouncilMeeting]:
        """
        Scrape list of council meetings using eScribe AJAX endpoints.

        Args:
            start_date: Start date for meeting search
            end_date: End date for meeting search
            limit: Maximum meetings to retrieve
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=90)  # Last 3 months
        if not end_date:
            end_date = datetime.now() + timedelta(days=30)    # Next month

        # Use eScribe AJAX endpoint to get calendar meetings
        calendar_url = self.portal_base_url + self.escribe_endpoints["calendar_meetings"]

        # Prepare AJAX request payload
        payload = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "maxResults": limit
        }

        meetings = []

        try:
            # Make AJAX request
            async with self.session.post(
                calendar_url,
                json=payload,
                headers=self.ajax_headers
            ) as response:
                if response.status != 200:
                    self.logger.error(f"Failed to fetch calendar data: HTTP {response.status}")
                    return []

                data = await response.json()
                meetings = await self._parse_escribe_calendar(data, start_date, end_date)

        except Exception as e:
            self.logger.error(f"Failed to fetch meetings from eScribe: {e}")
            return []

        # Filter by development-related meetings only
        development_meetings = []
        for meeting in meetings:
            if meeting.board_name in self.target_meeting_types:
                meeting.meeting_type = self.target_meeting_types[meeting.board_name]
                development_meetings.append(meeting)

        self.logger.info(f"Found {len(development_meetings)} development-related meetings out of {len(meetings)} total")
        return development_meetings

    async def scrape_meeting_details(self, meeting: CouncilMeeting) -> CouncilMeeting:
        """
        Scrape detailed information for a specific meeting using eScribe AJAX.

        Args:
            meeting: Basic meeting info to enhance with details
        """
        try:
            # Get meeting details from eScribe
            if meeting.escribe_meeting_id:
                meeting_details = await self._get_escribe_meeting_detail(meeting.escribe_meeting_id)
                if meeting_details:
                    # Update meeting with detailed info
                    meeting = self._merge_meeting_details(meeting, meeting_details)

            # Get agenda items with development petitions
            if meeting.escribe_meeting_id:
                agenda_items = await self._get_escribe_agenda_items(meeting.escribe_meeting_id)
                if agenda_items:
                    meeting.agenda_items = agenda_items

            # Download and process agenda PDF if available
            if meeting.agenda_url:
                agenda_text, _ = await self._process_document(
                    meeting.agenda_url, DocumentType.AGENDA
                )
                meeting.agenda_text = agenda_text

            # Download and process minutes PDF if available
            if meeting.minutes_url:
                minutes_text, _ = await self._process_document(
                    meeting.minutes_url, DocumentType.MINUTES
                )
                meeting.minutes_text = minutes_text

                # Extract additional details from minutes
                if minutes_text:
                    meeting.attendees, meeting.absent_members = self._extract_attendance(minutes_text)

                    # Update agenda items with voting results
                    if meeting.agenda_items:
                        meeting.agenda_items = self._extract_voting_results(
                            meeting.agenda_items, minutes_text
                        )

            # Calculate extraction confidence
            meeting.extraction_confidence = self._calculate_confidence(meeting)

            # Update document count
            meeting.document_count = sum([
                1 for url in [meeting.agenda_url, meeting.minutes_url]
                if url is not None
            ])

            return meeting

        except Exception as e:
            self.logger.error(f"Failed to scrape meeting details for {meeting.meeting_id}: {e}")
            return meeting

    async def scrape_recent_meetings(self, days_back: int = 30) -> List[CouncilMeeting]:
        """
        Scrape recent meetings with full details.

        Args:
            days_back: Number of days to look back for meetings
        """
        start_date = datetime.now() - timedelta(days=days_back)
        meetings = await self.scrape_meeting_list(start_date=start_date)

        detailed_meetings = []
        for meeting in meetings:
            try:
                detailed_meeting = await self.scrape_meeting_details(meeting)
                detailed_meetings.append(detailed_meeting)

                # Rate limiting
                await self.rate_limiter.acquire(self.scraper_id)

            except Exception as e:
                self.logger.warning(f"Failed to get details for meeting {meeting.meeting_id}: {e}")
                detailed_meetings.append(meeting)  # Keep basic info

        return detailed_meetings

    async def monitor_new_meetings(self) -> List[CouncilMeeting]:
        """Monitor for new meetings and agenda updates."""
        # Check for changes in the meeting list
        meeting_list_url = self.portal_base_url + self.config["meeting_list_path"]

        change_result = await self.change_detector.track_content_change(
            url=meeting_list_url,
            content=b"",  # Will be filled by scraper
            metadata={"scraper": self.scraper_id, "check_type": "monitor"}
        )

        if change_result.change_type.value == "unchanged":
            self.logger.debug("No new meetings detected")
            return []

        # Get meetings from last 7 days and next 30 days
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now() + timedelta(days=30)
        return await self.scrape_meeting_list(start_date=start_date, end_date=end_date)

    async def store_meetings(self, meetings: List[CouncilMeeting]) -> int:
        """Store council meetings in database."""
        if not meetings:
            return 0

        stored_count = 0

        async with self.db_manager.get_session() as session:
            for meeting in meetings:
                try:
                    # Create raw fact entry
                    fact_data = {
                        "meeting_data": meeting.dict(),
                        "scraped_from": "city_council_portal",
                        "scraper_version": "1.0",
                        "portal_type": self.portal_type,
                        "processing_notes": {
                            "data_quality": "municipal_government_portal",
                            "confidence": meeting.extraction_confidence,
                            "document_count": meeting.document_count,
                            "has_agenda": meeting.agenda_url is not None,
                            "has_minutes": meeting.minutes_url is not None,
                            "agenda_items_count": len(meeting.agenda_items)
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
                        "council_meeting",
                        meeting.portal_url,
                        datetime.utcnow(),
                        "city_council_v1.0",
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
                            "council_meeting",
                            json.dumps(meeting.dict(), default=str),
                            meeting.extraction_confidence
                        )

                except Exception as e:
                    self.logger.error(f"Failed to store meeting {meeting.meeting_id}: {e}")
                    continue

            await session.commit()

        self.logger.info(f"Stored {stored_count} new meetings")
        return stored_count

    async def process_response(self, content: bytes, response: aiohttp.ClientResponse) -> Any:
        """Process web response from council portal."""
        return content.decode('utf-8', errors='ignore')

    async def _parse_escribe_calendar(
        self,
        calendar_data: dict,
        start_date: datetime,
        end_date: datetime
    ) -> List[CouncilMeeting]:
        """Parse meeting list from eScribe calendar JSON response."""
        meetings = []

        if not calendar_data or 'd' not in calendar_data:
            self.logger.warning("Invalid calendar data received from eScribe")
            return meetings

        calendar_meetings = calendar_data.get('d', [])

        for meeting_data in calendar_meetings:
            try:
                meeting = await self._parse_escribe_meeting_item(meeting_data)
                if meeting and start_date <= meeting.meeting_date <= end_date:
                    meetings.append(meeting)

            except Exception as e:
                self.logger.warning(f"Failed to parse meeting item: {e}")
                continue

        return meetings

    async def _parse_escribe_meeting_item(self, meeting_data: dict) -> Optional[CouncilMeeting]:
        """Parse individual meeting from eScribe JSON."""
        try:
            # Extract basic meeting info
            meeting_id = meeting_data.get('MeetingId', '')
            calendar_id = meeting_data.get('CalendarId', '')
            board_name = meeting_data.get('BoardName', '').strip()

            # Parse meeting date
            date_str = meeting_data.get('MeetingDate', '')
            meeting_date = self._parse_escribe_date(date_str)
            if not meeting_date:
                return None

            # Check if cancelled or rescheduled
            status_text = meeting_data.get('Status', '').lower()
            is_cancelled = 'cancel' in status_text
            is_rescheduled = 'reschedule' in status_text or 'postpone' in status_text

            status = MeetingStatus.SCHEDULED
            if is_cancelled:
                status = MeetingStatus.CANCELLED
            elif is_rescheduled:
                status = MeetingStatus.POSTPONED
            elif 'complete' in status_text:
                status = MeetingStatus.COMPLETED

            # Extract time and location
            start_time = meeting_data.get('StartTime', '')
            location = meeting_data.get('Location', '')

            # Extract document URLs
            agenda_url = meeting_data.get('AgendaUrl', '')
            minutes_url = meeting_data.get('MinutesUrl', '')
            video_url = meeting_data.get('VideoUrl', '')

            # Generate meeting ID
            meeting_id_str = f"{meeting_date.strftime('%Y%m%d')}_{board_name.replace(' ', '_')}_{meeting_id}"

            return CouncilMeeting(
                meeting_id=meeting_id_str,
                meeting_date=meeting_date,
                board_name=board_name,
                status=status,
                title=f"{board_name} Meeting",
                location=location,
                start_time=start_time,
                agenda_url=agenda_url if agenda_url else None,
                minutes_url=minutes_url if minutes_url else None,
                video_url=video_url if video_url else None,
                escribe_meeting_id=meeting_id,
                calendar_id=calendar_id,
                is_cancelled=is_cancelled,
                is_rescheduled=is_rescheduled,
                portal_url=self.portal_base_url
            )

        except Exception as e:
            self.logger.debug(f"Error parsing eScribe meeting item: {e}")
            return None

    async def _get_escribe_meeting_detail(self, meeting_id: str) -> Optional[dict]:
        """Get detailed meeting information from eScribe."""
        detail_url = self.portal_base_url + self.escribe_endpoints["meeting_detail"]

        payload = {
            "meetingId": meeting_id
        }

        try:
            async with self.session.post(
                detail_url,
                json=payload,
                headers=self.ajax_headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('d', {}) if data else {}
                else:
                    self.logger.warning(f"Failed to get meeting detail: HTTP {response.status}")
                    return None

        except Exception as e:
            self.logger.error(f"Error fetching meeting detail for {meeting_id}: {e}")
            return None

    async def _get_escribe_agenda_items(self, meeting_id: str) -> List[AgendaItem]:
        """Get agenda items from eScribe with development petition extraction."""
        agenda_url = self.portal_base_url + self.escribe_endpoints["agenda_items"]

        payload = {
            "meetingId": meeting_id
        }

        try:
            async with self.session.post(
                agenda_url,
                json=payload,
                headers=self.ajax_headers
            ) as response:
                if response.status != 200:
                    self.logger.warning(f"Failed to get agenda items: HTTP {response.status}")
                    return []

                data = await response.json()
                agenda_data = data.get('d', []) if data else []

                agenda_items = []
                for item_data in agenda_data:
                    item = await self._parse_escribe_agenda_item(item_data)
                    if item:
                        agenda_items.append(item)

                return agenda_items

        except Exception as e:
            self.logger.error(f"Error fetching agenda items for {meeting_id}: {e}")
            return []

    async def _parse_escribe_agenda_item(self, item_data: dict) -> Optional[AgendaItem]:
        """Parse individual agenda item from eScribe JSON and extract development petitions."""
        try:
            item_number = item_data.get('ItemNumber', '').strip()
            title = item_data.get('Title', '').strip()
            description = item_data.get('Description', '').strip()

            if not item_number or not title:
                return None

            # Extract petition ID if present (LD25-XXXXXX format)
            petition_match = re.search(r'LD\d{2}-\d{6}', title + ' ' + description)
            development_petition = None
            affects_real_estate = False
            assemblage_signal = False

            if petition_match:
                petition_id = petition_match.group(0)
                development_petition = await self._extract_development_petition(
                    petition_id, title, description
                )
                affects_real_estate = True

            # Check for real estate keywords even without petition ID
            real_estate_keywords = [
                'zoning', 'rezoning', 'variance', 'site plan', 'subdivision',
                'development', 'property', 'land use', 'building permit',
                'comprehensive plan', 'annexation', 'assemblage'
            ]

            title_desc_lower = (title + ' ' + description).lower()
            if any(keyword in title_desc_lower for keyword in real_estate_keywords):
                affects_real_estate = True

            # Check for assemblage signals
            assemblage_keywords = [
                'multiple properties', 'adjacent parcels', 'assemblage',
                'master plan', 'phased development', 'multiple lots'
            ]
            if any(keyword in title_desc_lower for keyword in assemblage_keywords):
                assemblage_signal = True

            # Determine item type
            item_type = self._classify_agenda_item(title)
            if development_petition:
                if 'rezoning' in title.lower():
                    item_type = DocumentType.REZONING_REQUEST
                elif 'variance' in title.lower():
                    item_type = DocumentType.VARIANCE_APPLICATION
                else:
                    item_type = DocumentType.DEVELOPMENT_APPLICATION

            return AgendaItem(
                item_number=item_number,
                title=title,
                description=description,
                item_type=item_type,
                development_petition=development_petition,
                affects_real_estate=affects_real_estate,
                assemblage_signal=assemblage_signal
            )

        except Exception as e:
            self.logger.debug(f"Error parsing agenda item: {e}")
            return None

    async def _extract_development_petition(
        self,
        petition_id: str,
        title: str,
        description: str
    ) -> Optional[DevelopmentPetition]:
        """Extract development petition details from agenda item text."""
        try:
            combined_text = f"{title} {description}"

            # Extract petition type
            petition_type = "Unknown"
            if 'rezoning' in combined_text.lower():
                petition_type = "Rezoning"
            elif 'site plan' in combined_text.lower():
                petition_type = "Site Plan"
            elif 'variance' in combined_text.lower():
                petition_type = "Variance"
            elif 'subdivision' in combined_text.lower():
                petition_type = "Subdivision"

            # Extract address patterns
            address_patterns = [
                r'\d{1,5}\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Way|Circle|Cir|Court|Ct)',
                r'[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Way|Circle|Cir|Court|Ct)'
            ]

            property_address = None
            for pattern in address_patterns:
                match = re.search(pattern, combined_text, re.IGNORECASE)
                if match:
                    property_address = match.group(0).strip()
                    break

            # Extract zoning information
            zoning_pattern = r'from\s+([A-Z\-\d]+)\s+to\s+([A-Z\-\d]+)'
            zoning_match = re.search(zoning_pattern, combined_text, re.IGNORECASE)
            current_zoning = None
            proposed_zoning = None

            if zoning_match:
                current_zoning = zoning_match.group(1)
                proposed_zoning = zoning_match.group(2)

            # Extract applicant information
            applicant_patterns = [
                r'applicant:?\s*([^,\n]+)',
                r'petitioner:?\s*([^,\n]+)',
                r'by\s+([A-Za-z\s]+(?:LLC|Inc|Corp|Company))',
            ]

            applicant_name = None
            for pattern in applicant_patterns:
                match = re.search(pattern, combined_text, re.IGNORECASE)
                if match:
                    applicant_name = match.group(1).strip()
                    break

            return DevelopmentPetition(
                petition_id=petition_id,
                petition_type=petition_type,
                property_address=property_address,
                applicant_name=applicant_name,
                description=description[:500] if description else None,
                current_zoning=current_zoning,
                proposed_zoning=proposed_zoning,
                development_details=combined_text[:1000]
            )

        except Exception as e:
            self.logger.debug(f"Error extracting development petition {petition_id}: {e}")
            return None

    def _parse_escribe_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from eScribe JSON format."""
        if not date_str:
            return None

        # eScribe often uses Microsoft JSON date format: /Date(timestamp)/
        json_date_match = re.search(r'/Date\((\d+)\)/', date_str)
        if json_date_match:
            timestamp = int(json_date_match.group(1)) / 1000  # Convert to seconds
            return datetime.fromtimestamp(timestamp)

        # Try standard date formats
        for fmt in [
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

        return None

    def _merge_meeting_details(self, meeting: CouncilMeeting, details: dict) -> CouncilMeeting:
        """Merge additional details from eScribe meeting detail response."""
        try:
            # Update location if more detailed
            if details.get('Location') and not meeting.location:
                meeting.location = details['Location']

            # Update times
            if details.get('StartTime') and not meeting.start_time:
                meeting.start_time = details['StartTime']

            if details.get('EndTime') and not meeting.end_time:
                meeting.end_time = details['EndTime']

            # Update document URLs if better ones available
            if details.get('AgendaPacketUrl') and not meeting.agenda_url:
                meeting.agenda_url = details['AgendaPacketUrl']

            # Add video URL if available
            if details.get('VideoUrl') and not meeting.video_url:
                meeting.video_url = details['VideoUrl']

            return meeting

        except Exception as e:
            self.logger.debug(f"Error merging meeting details: {e}")
            return meeting

    async def _parse_meeting_list(
        self,
        soup: BeautifulSoup,
        start_date: datetime,
        end_date: datetime,
        limit: int
    ) -> List[CouncilMeeting]:
        """Parse meeting list from HTML."""
        meetings = []
        meeting_rows = soup.select(self.config["meeting_row_selector"])

        for row in meeting_rows[:limit]:
            try:
                meeting = await self._parse_meeting_row(row)
                if not meeting:
                    continue

                # Filter by date range
                if start_date <= meeting.meeting_date <= end_date:
                    meetings.append(meeting)

            except Exception as e:
                self.logger.warning(f"Failed to parse meeting row: {e}")
                continue

        return meetings

    async def _parse_meeting_row(self, row) -> Optional[CouncilMeeting]:
        """Parse individual meeting row."""
        try:
            # Extract date
            date_elem = row.select_one(self.config["date_selector"])
            if not date_elem:
                return None

            date_text = date_elem.get_text().strip()
            meeting_date = self._parse_date(date_text)
            if not meeting_date:
                return None

            # Extract title
            title_elem = row.select_one(self.config["title_selector"])
            title = title_elem.get_text().strip() if title_elem else "City Council Meeting"

            # Extract status
            status_elem = row.select_one(self.config["status_selector"])
            status_text = status_elem.get_text().strip().lower() if status_elem else "scheduled"

            status = MeetingStatus.SCHEDULED
            if "completed" in status_text or "final" in status_text:
                status = MeetingStatus.COMPLETED
            elif "cancelled" in status_text:
                status = MeetingStatus.CANCELLED
            elif "postponed" in status_text:
                status = MeetingStatus.POSTPONED

            # Find document links
            agenda_elem = row.select_one(self.config["agenda_selector"])
            minutes_elem = row.select_one(self.config["minutes_selector"])

            agenda_url = None
            if agenda_elem and agenda_elem.get('href'):
                agenda_url = urljoin(self.portal_base_url, agenda_elem['href'])

            minutes_url = None
            if minutes_elem and minutes_elem.get('href'):
                minutes_url = urljoin(self.portal_base_url, minutes_elem['href'])

            # Generate meeting ID
            meeting_id = f"{meeting_date.strftime('%Y%m%d')}_{hash(title) % 10000}"

            return CouncilMeeting(
                meeting_id=meeting_id,
                meeting_date=meeting_date,
                title=title,
                status=status,
                agenda_url=agenda_url,
                minutes_url=minutes_url,
                portal_url=self.portal_base_url
            )

        except Exception as e:
            self.logger.debug(f"Error parsing meeting row: {e}")
            return None

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse date string from portal."""
        # Clean up date text
        date_text = re.sub(r'\s+', ' ', date_text.strip())

        # Common date formats used in government portals
        formats = [
            "%m/%d/%Y",
            "%m-%d-%Y",
            "%Y-%m-%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%A, %B %d, %Y",
            "%A, %b %d, %Y"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue

        return None

    async def _process_document(self, url: str, doc_type: DocumentType) -> tuple[Optional[str], Optional[List[AgendaItem]]]:
        """Download and extract text from PDF document."""
        try:
            # Download document
            result = await self.scrape(url)
            if not result.success:
                self.logger.warning(f"Failed to download document: {url}")
                return None, None

            # Save document locally
            filename = f"{doc_type.value}_{hash(url) % 100000}.pdf"
            doc_path = self.data_directory / filename

            async with aiofiles.open(doc_path, 'wb') as f:
                await f.write(result.data)

            # Extract text
            text_content = await self._extract_text_from_pdf(doc_path)

            # Parse agenda items if this is an agenda
            agenda_items = None
            if doc_type == DocumentType.AGENDA and text_content:
                agenda_items = self._parse_agenda_items(text_content)

            return text_content, agenda_items

        except Exception as e:
            self.logger.error(f"Failed to process document {url}: {e}")
            return None, None

    async def _extract_text_from_pdf(self, pdf_path: Path) -> Optional[str]:
        """Extract text from PDF using multiple methods."""
        text_content = []

        try:
            # Method 1: PyPDF2 for text-based PDFs
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content.append(page_text)

                if text_content:
                    return '\n\n'.join(text_content)
            except Exception as e:
                self.logger.debug(f"PyPDF2 extraction failed: {e}")

            # Method 2: PyMuPDF for better text extraction
            try:
                doc = fitz.open(pdf_path)
                for page_num in range(doc.page_count):
                    page = doc[page_num]
                    page_text = page.get_text()
                    if page_text.strip():
                        text_content.append(page_text)
                doc.close()

                if text_content:
                    return '\n\n'.join(text_content)
            except Exception as e:
                self.logger.debug(f"PyMuPDF extraction failed: {e}")

            # Method 3: OCR for scanned PDFs (if enabled)
            if self.enable_ocr and not text_content:
                try:
                    doc = fitz.open(pdf_path)
                    for page_num in range(doc.page_count):
                        page = doc[page_num]
                        pix = page.get_pixmap()
                        img_data = pix.tobytes("png")

                        # Convert to PIL Image for OCR
                        image = Image.open(io.BytesIO(img_data))
                        ocr_text = pytesseract.image_to_string(image)
                        if ocr_text.strip():
                            text_content.append(ocr_text)

                    doc.close()

                    if text_content:
                        self.logger.info(f"Successfully extracted text via OCR from {pdf_path}")
                        return '\n\n'.join(text_content)

                except Exception as e:
                    self.logger.warning(f"OCR extraction failed: {e}")

            return None

        except Exception as e:
            self.logger.error(f"All PDF extraction methods failed for {pdf_path}: {e}")
            return None

    def _parse_agenda_items(self, text: str) -> List[AgendaItem]:
        """Parse agenda items from agenda text."""
        items = []

        # Common patterns for agenda items
        patterns = [
            r'(\d+\.?\d*\.?)\s+([^\n]+)',  # 1. Item title
            r'([A-Z]+\.?)\s+([^\n]+)',     # A. Item title
            r'Item\s+(\d+):\s*([^\n]+)',   # Item 1: Title
            r'(\d+)\.\s*([^\n]+)'          # 1. Title
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)

            for match in matches:
                item_number = match.group(1).strip()
                title = match.group(2).strip()

                # Skip if title is too short or likely not an agenda item
                if len(title) < 5 or title.lower() in ['agenda', 'meeting', 'council']:
                    continue

                # Determine item type from title keywords
                item_type = self._classify_agenda_item(title)

                # Check if public comment is mentioned
                public_comment = 'public' in title.lower() and 'comment' in title.lower()

                items.append(AgendaItem(
                    item_number=item_number,
                    title=title,
                    item_type=item_type,
                    public_comment=public_comment
                ))

        return items

    def _classify_agenda_item(self, title: str) -> DocumentType:
        """Classify agenda item based on title."""
        title_lower = title.lower()

        if any(word in title_lower for word in ['ordinance', 'ord.']):
            return DocumentType.ORDINANCE
        elif any(word in title_lower for word in ['resolution', 'res.']):
            return DocumentType.RESOLUTION
        elif any(word in title_lower for word in ['hearing', 'public comment']):
            return DocumentType.PUBLIC_HEARING
        elif any(word in title_lower for word in ['budget', 'financial', 'appropriation']):
            return DocumentType.BUDGET
        elif any(word in title_lower for word in ['staff report', 'report']):
            return DocumentType.STAFF_REPORT
        else:
            return DocumentType.OTHER

    def _extract_attendance(self, minutes_text: str) -> tuple[List[CouncilMember], List[str]]:
        """Extract attendance information from minutes text."""
        attendees = []
        absent_members = []

        # Look for attendance sections
        attendance_patterns = [
            r'present:?\s*([^\n]+)',
            r'attendance:?\s*([^\n]+)',
            r'members present:?\s*([^\n]+)'
        ]

        absent_patterns = [
            r'absent:?\s*([^\n]+)',
            r'excused:?\s*([^\n]+)',
            r'not present:?\s*([^\n]+)'
        ]

        # Extract present members
        for pattern in attendance_patterns:
            match = re.search(pattern, minutes_text, re.IGNORECASE | re.MULTILINE)
            if match:
                present_text = match.group(1)
                names = self._parse_member_names(present_text)
                attendees.extend([CouncilMember(name=name) for name in names])
                break

        # Extract absent members
        for pattern in absent_patterns:
            match = re.search(pattern, minutes_text, re.IGNORECASE | re.MULTILINE)
            if match:
                absent_text = match.group(1)
                absent_members.extend(self._parse_member_names(absent_text))
                break

        return attendees, absent_members

    def _parse_member_names(self, text: str) -> List[str]:
        """Parse member names from attendance text."""
        # Clean and split names
        text = re.sub(r'[,;]', ',', text)  # Normalize separators
        names = []

        for name in text.split(','):
            name = name.strip()
            # Remove titles and clean
            name = re.sub(r'^(Mayor|Commissioner|Council\s*member)\s+', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\s*(Mayor|Commissioner)$', '', name, flags=re.IGNORECASE)

            if len(name) > 2 and name not in ['and', 'or']:
                names.append(name)

        return names

    def _extract_voting_results(self, agenda_items: List[AgendaItem], minutes_text: str) -> List[AgendaItem]:
        """Extract voting results and update agenda items."""
        # This is a simplified implementation - real voting extraction would be more complex
        for item in agenda_items:
            # Look for voting patterns related to this item
            item_context = self._find_item_context(item, minutes_text)

            if item_context:
                # Simple pattern matching for vote results
                if re.search(r'\bapproved\b|\bpassed\b|\bcarried\b', item_context, re.IGNORECASE):
                    item.vote_result = VoteResult.APPROVED
                elif re.search(r'\bdenied\b|\bfailed\b|\brejected\b', item_context, re.IGNORECASE):
                    item.vote_result = VoteResult.DENIED
                elif re.search(r'\btabled\b|\bdeferred\b', item_context, re.IGNORECASE):
                    item.vote_result = VoteResult.TABLED

        return agenda_items

    def _find_item_context(self, item: AgendaItem, text: str) -> Optional[str]:
        """Find text context around a specific agenda item in minutes."""
        # Look for mentions of the item number or title
        patterns = [
            f"item\\s+{re.escape(item.item_number)}[^\\n]*[\\n][^\\n]*[\\n][^\\n]*",
            f"{re.escape(item.title[:30])}[^\\n]*[\\n][^\\n]*[\\n][^\\n]*"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(0)

        return None

    def _calculate_confidence(self, meeting: CouncilMeeting) -> float:
        """Calculate extraction confidence score."""
        score = 0.0

        # Base score for having basic meeting info
        if meeting.meeting_date and meeting.title:
            score += 0.3

        # Score for having documents
        if meeting.agenda_url:
            score += 0.2
        if meeting.minutes_url:
            score += 0.2

        # Score for having extracted text
        if meeting.agenda_text and len(meeting.agenda_text) > 100:
            score += 0.1
        if meeting.minutes_text and len(meeting.minutes_text) > 100:
            score += 0.1

        # Score for having structured data
        if meeting.agenda_items:
            score += 0.1

        return min(1.0, score)


async def create_city_council_scraper(
    db_manager: DatabaseManager,
    change_detector: ChangeDetector,
    redis_client,
    portal_base_url: str,
    portal_type: str = "legistar",
    data_directory: Optional[str] = None,
    enable_ocr: bool = True,
    **kwargs
) -> CityCouncilScraper:
    """Factory function to create configured city council scraper."""
    scraper = CityCouncilScraper(
        db_manager=db_manager,
        change_detector=change_detector,
        redis_client=redis_client,
        portal_base_url=portal_base_url,
        portal_type=portal_type,
        data_directory=data_directory,
        enable_ocr=enable_ocr,
        **kwargs
    )
    await scraper.initialize()
    return scraper