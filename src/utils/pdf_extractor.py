"""
Comprehensive PDF extraction system with OCR capabilities.
Provides multiple extraction methods for different document types and quality levels.
Supports council minutes, permits, reports, and other government documents.
"""
import io
import logging
import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
import asyncio

import aiofiles
from PIL import Image, ImageEnhance, ImageFilter
import PyPDF2
import fitz  # PyMuPDF
import pytesseract
from pydantic import BaseModel, Field, validator

# Optional imports for advanced features
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    cv2 = None

try:
    import pdf2image
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    pdf2image = None


class ExtractionMethod(Enum):
    """PDF text extraction methods."""
    PYPDF2 = "pypdf2"
    PYMUPDF = "pymupdf"
    OCR_TESSERACT = "ocr_tesseract"
    HYBRID = "hybrid"  # Try multiple methods


class DocumentType(Enum):
    """Document types for specialized processing."""
    COUNCIL_MINUTES = "council_minutes"
    MEETING_AGENDA = "meeting_agenda"
    PERMIT_DOCUMENT = "permit_document"
    FINANCIAL_REPORT = "financial_report"
    LEGAL_DOCUMENT = "legal_document"
    TECHNICAL_DRAWING = "technical_drawing"
    FORM = "form"
    GENERAL = "general"


class OCRQuality(Enum):
    """OCR processing quality levels."""
    FAST = "fast"       # Quick processing, lower accuracy
    BALANCED = "balanced"  # Good balance of speed and accuracy
    ACCURATE = "accurate"  # Slower but more accurate
    CUSTOM = "custom"   # User-defined settings


class ExtractionResult(BaseModel):
    """Result of PDF text extraction."""
    success: bool
    text_content: str = ""
    page_count: int = 0
    extraction_method: str = ""
    extraction_confidence: float = 0.0
    processing_time_seconds: float = 0.0

    # Document analysis
    document_type: Optional[DocumentType] = None
    language_detected: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    images_processed: int = 0
    ocr_used: bool = False

    # Quality metrics
    word_count: int = 0
    average_confidence: Optional[float] = None
    low_confidence_pages: List[int] = Field(default_factory=list)

    # Error information
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @validator('word_count', always=True)
    def calculate_word_count(cls, v, values):
        text = values.get('text_content', '')
        return len(text.split()) if text else 0


class OCRConfig(BaseModel):
    """Configuration for OCR processing."""
    quality_level: OCRQuality = OCRQuality.BALANCED
    language: str = Field(default="eng", description="Tesseract language code")
    dpi: int = Field(default=300, ge=150, le=600, description="DPI for image conversion")

    # Image preprocessing
    enhance_contrast: bool = Field(default=True)
    denoise: bool = Field(default=True)
    deskew: bool = Field(default=True)
    remove_background: bool = Field(default=False)

    # Tesseract specific
    psm: int = Field(default=3, ge=0, le=13, description="Page segmentation mode")
    oem: int = Field(default=3, ge=0, le=3, description="OCR engine mode")

    # Quality control
    min_confidence: float = Field(default=30.0, ge=0.0, le=100.0)
    max_processing_time_minutes: int = Field(default=10, ge=1, le=60)


class PDFExtractor:
    """
    Comprehensive PDF text extraction system.

    Supports multiple extraction methods with automatic fallback and OCR capabilities.
    Optimized for government documents, permits, and meeting records.
    """

    def __init__(
        self,
        temp_dir: Optional[Path] = None,
        enable_ocr: bool = True,
        ocr_config: Optional[OCRConfig] = None,
        cache_enabled: bool = True
    ):
        self.temp_dir = Path(temp_dir or tempfile.gettempdir()) / "dominion_pdf_extraction"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.enable_ocr = enable_ocr
        self.ocr_config = ocr_config or OCRConfig()
        self.cache_enabled = cache_enabled

        self.logger = logging.getLogger("pdf_extractor")

        # Cache for processed documents
        self._extraction_cache: Dict[str, ExtractionResult] = {}

        # Document type detection patterns
        self.document_patterns = {
            DocumentType.COUNCIL_MINUTES: [
                r'minutes?.*meeting', r'city council', r'commission meeting',
                r'present:', r'absent:', r'motion.*second', r'approved.*denied'
            ],
            DocumentType.MEETING_AGENDA: [
                r'agenda', r'meeting.*agenda', r'order.*business',
                r'call.*order', r'item\s+\d+', r'public.*comment'
            ],
            DocumentType.PERMIT_DOCUMENT: [
                r'permit', r'building.*permit', r'zoning.*permit',
                r'application', r'permit.*number', r'issued.*date'
            ],
            DocumentType.FINANCIAL_REPORT: [
                r'financial.*report', r'budget', r'revenue', r'expenditure',
                r'fiscal.*year', r'\$[\d,]+', r'balance.*sheet'
            ],
            DocumentType.LEGAL_DOCUMENT: [
                r'ordinance', r'resolution', r'whereas', r'now.*therefore',
                r'be.*ordained', r'section\s+\d+', r'legal.*description'
            ]
        }

    async def extract_text_from_file(
        self,
        file_path: Union[str, Path],
        method: ExtractionMethod = ExtractionMethod.HYBRID,
        document_type: Optional[DocumentType] = None
    ) -> ExtractionResult:
        """
        Extract text from PDF file.

        Args:
            file_path: Path to PDF file
            method: Extraction method to use
            document_type: Type of document for specialized processing
        """
        file_path = Path(file_path)
        start_time = datetime.now()

        if not file_path.exists():
            return ExtractionResult(
                success=False,
                errors=[f"File not found: {file_path}"]
            )

        # Check cache
        file_hash = self._calculate_file_hash(file_path)
        cache_key = f"{file_hash}_{method.value}_{document_type.value if document_type else 'auto'}"

        if self.cache_enabled and cache_key in self._extraction_cache:
            self.logger.debug(f"Returning cached extraction result for {file_path.name}")
            return self._extraction_cache[cache_key]

        try:
            # Extract text based on method
            if method == ExtractionMethod.HYBRID:
                result = await self._extract_hybrid(file_path, document_type)
            elif method == ExtractionMethod.PYPDF2:
                result = await self._extract_with_pypdf2(file_path)
            elif method == ExtractionMethod.PYMUPDF:
                result = await self._extract_with_pymupdf(file_path)
            elif method == ExtractionMethod.OCR_TESSERACT:
                result = await self._extract_with_ocr(file_path)
            else:
                result = ExtractionResult(
                    success=False,
                    errors=[f"Unsupported extraction method: {method}"]
                )

            # Post-processing
            if result.success:
                result = self._post_process_result(result, document_type)
                result.processing_time_seconds = (datetime.now() - start_time).total_seconds()

            # Cache successful results
            if self.cache_enabled and result.success:
                self._extraction_cache[cache_key] = result

            return result

        except Exception as e:
            self.logger.error(f"Failed to extract text from {file_path}: {e}")
            return ExtractionResult(
                success=False,
                errors=[str(e)],
                processing_time_seconds=(datetime.now() - start_time).total_seconds()
            )

    async def extract_text_from_bytes(
        self,
        pdf_data: bytes,
        filename: str = "document.pdf",
        method: ExtractionMethod = ExtractionMethod.HYBRID,
        document_type: Optional[DocumentType] = None
    ) -> ExtractionResult:
        """
        Extract text from PDF bytes data.

        Args:
            pdf_data: PDF file content as bytes
            filename: Original filename for caching and logging
            method: Extraction method to use
            document_type: Type of document for specialized processing
        """
        # Create temporary file
        temp_file = self.temp_dir / f"temp_{hashlib.md5(pdf_data).hexdigest()[:8]}_{filename}"

        try:
            async with aiofiles.open(temp_file, 'wb') as f:
                await f.write(pdf_data)

            return await self.extract_text_from_file(temp_file, method, document_type)

        finally:
            # Clean up temporary file
            if temp_file.exists():
                temp_file.unlink()

    async def batch_extract(
        self,
        file_paths: List[Union[str, Path]],
        method: ExtractionMethod = ExtractionMethod.HYBRID,
        max_concurrent: int = 3
    ) -> Dict[str, ExtractionResult]:
        """
        Extract text from multiple PDF files concurrently.

        Args:
            file_paths: List of PDF file paths
            method: Extraction method to use
            max_concurrent: Maximum concurrent extractions
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_single(file_path: Union[str, Path]) -> Tuple[str, ExtractionResult]:
            async with semaphore:
                result = await self.extract_text_from_file(file_path, method)
                return str(file_path), result

        # Execute extractions concurrently
        tasks = [extract_single(file_path) for file_path in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        extraction_results = {}
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Batch extraction error: {result}")
                continue

            file_path, extraction_result = result
            extraction_results[file_path] = extraction_result

        return extraction_results

    def analyze_document_quality(self, result: ExtractionResult) -> Dict[str, Any]:
        """Analyze the quality of extracted document."""
        if not result.success:
            return {"quality_score": 0.0, "issues": ["Extraction failed"]}

        quality_score = 100.0
        issues = []

        # Text length check
        if len(result.text_content) < 100:
            quality_score -= 20
            issues.append("Very short text extracted")
        elif len(result.text_content) < 500:
            quality_score -= 10
            issues.append("Short text extracted")

        # Word count check
        if result.word_count < 50:
            quality_score -= 15
            issues.append("Low word count")

        # OCR confidence check
        if result.ocr_used and result.average_confidence:
            if result.average_confidence < 70:
                quality_score -= 25
                issues.append("Low OCR confidence")
            elif result.average_confidence < 85:
                quality_score -= 10
                issues.append("Moderate OCR confidence")

        # Low confidence pages
        if result.low_confidence_pages:
            penalty = min(20, len(result.low_confidence_pages) * 5)
            quality_score -= penalty
            issues.append(f"{len(result.low_confidence_pages)} pages with low confidence")

        # Processing errors
        if result.errors:
            quality_score -= len(result.errors) * 5
            issues.extend(result.errors)

        # Processing warnings
        if result.warnings:
            quality_score -= len(result.warnings) * 2

        return {
            "quality_score": max(0.0, quality_score),
            "issues": issues,
            "recommendations": self._get_quality_recommendations(result, issues)
        }

    def clear_cache(self) -> None:
        """Clear the extraction cache."""
        self._extraction_cache.clear()

    async def _extract_hybrid(
        self,
        file_path: Path,
        document_type: Optional[DocumentType]
    ) -> ExtractionResult:
        """Extract using hybrid approach - try multiple methods."""
        self.logger.debug(f"Starting hybrid extraction for {file_path.name}")

        # Try PyMuPDF first (usually best results)
        result = await self._extract_with_pymupdf(file_path)

        if result.success and len(result.text_content.strip()) > 100:
            result.extraction_method = "pymupdf_primary"
            return result

        self.logger.debug("PyMuPDF extraction insufficient, trying PyPDF2")

        # Try PyPDF2 as fallback
        pypdf2_result = await self._extract_with_pypdf2(file_path)

        if pypdf2_result.success and len(pypdf2_result.text_content.strip()) > len(result.text_content.strip()):
            pypdf2_result.extraction_method = "pypdf2_fallback"
            result = pypdf2_result

        # If still insufficient, try OCR
        if self.enable_ocr and len(result.text_content.strip()) < 100:
            self.logger.debug("Text-based extraction insufficient, trying OCR")
            ocr_result = await self._extract_with_ocr(file_path)

            if ocr_result.success and len(ocr_result.text_content.strip()) > len(result.text_content.strip()):
                ocr_result.extraction_method = "ocr_fallback"
                result = ocr_result

        result.extraction_method = f"hybrid_{result.extraction_method}"
        return result

    async def _extract_with_pypdf2(self, file_path: Path) -> ExtractionResult:
        """Extract text using PyPDF2."""
        try:
            text_parts = []
            page_count = 0

            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                page_count = len(pdf_reader.pages)

                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_parts.append(page_text)
                    except Exception as e:
                        self.logger.warning(f"Failed to extract page {page_num + 1} with PyPDF2: {e}")

            text_content = '\n\n'.join(text_parts) if text_parts else ""

            return ExtractionResult(
                success=len(text_content.strip()) > 0,
                text_content=text_content,
                page_count=page_count,
                extraction_method="pypdf2",
                extraction_confidence=0.8 if text_content.strip() else 0.1
            )

        except Exception as e:
            return ExtractionResult(
                success=False,
                errors=[f"PyPDF2 extraction failed: {str(e)}"],
                extraction_method="pypdf2"
            )

    async def _extract_with_pymupdf(self, file_path: Path) -> ExtractionResult:
        """Extract text using PyMuPDF."""
        try:
            text_parts = []
            page_count = 0
            metadata = {}

            doc = fitz.open(file_path)
            page_count = doc.page_count

            # Extract metadata
            doc_metadata = doc.metadata
            if doc_metadata:
                metadata.update({
                    k: v for k, v in doc_metadata.items()
                    if v and k in ['title', 'author', 'subject', 'creator', 'producer']
                })

            for page_num in range(page_count):
                try:
                    page = doc[page_num]
                    page_text = page.get_text()
                    if page_text.strip():
                        text_parts.append(page_text)
                except Exception as e:
                    self.logger.warning(f"Failed to extract page {page_num + 1} with PyMuPDF: {e}")

            doc.close()

            text_content = '\n\n'.join(text_parts) if text_parts else ""

            return ExtractionResult(
                success=len(text_content.strip()) > 0,
                text_content=text_content,
                page_count=page_count,
                extraction_method="pymupdf",
                extraction_confidence=0.9 if text_content.strip() else 0.1,
                metadata=metadata
            )

        except Exception as e:
            return ExtractionResult(
                success=False,
                errors=[f"PyMuPDF extraction failed: {str(e)}"],
                extraction_method="pymupdf"
            )

    async def _extract_with_ocr(self, file_path: Path) -> ExtractionResult:
        """Extract text using OCR (Tesseract)."""
        if not self.enable_ocr:
            return ExtractionResult(
                success=False,
                errors=["OCR is disabled"],
                extraction_method="ocr_tesseract"
            )

        try:
            text_parts = []
            confidence_scores = []
            low_confidence_pages = []
            images_processed = 0

            doc = fitz.open(file_path)
            page_count = doc.page_count

            for page_num in range(page_count):
                try:
                    page = doc[page_num]

                    # Convert page to image
                    pix = page.get_pixmap(matrix=fitz.Matrix(self.ocr_config.dpi/72, self.ocr_config.dpi/72))
                    img_data = pix.tobytes("png")

                    # Load image for preprocessing
                    image = Image.open(io.BytesIO(img_data))

                    # Preprocess image for better OCR
                    processed_image = self._preprocess_image(image)
                    images_processed += 1

                    # Perform OCR with confidence scores
                    ocr_config = f'--psm {self.ocr_config.psm} --oem {self.ocr_config.oem} -l {self.ocr_config.language}'

                    # Get text with confidence
                    ocr_data = pytesseract.image_to_data(
                        processed_image,
                        config=ocr_config,
                        output_type=pytesseract.Output.DICT
                    )

                    # Extract text and calculate page confidence
                    page_words = []
                    page_confidences = []

                    for i, confidence in enumerate(ocr_data['conf']):
                        if int(confidence) > 0:  # Valid confidence score
                            word = ocr_data['text'][i].strip()
                            if word:
                                page_words.append(word)
                                page_confidences.append(int(confidence))

                    if page_words:
                        page_text = ' '.join(page_words)
                        page_confidence = sum(page_confidences) / len(page_confidences)

                        if page_confidence >= self.ocr_config.min_confidence:
                            text_parts.append(page_text)
                            confidence_scores.append(page_confidence)
                        else:
                            low_confidence_pages.append(page_num + 1)
                            # Still include low confidence pages but mark them
                            text_parts.append(f"[LOW CONFIDENCE PAGE {page_num + 1}]\n{page_text}")
                            confidence_scores.append(page_confidence)

                except Exception as e:
                    self.logger.warning(f"OCR failed for page {page_num + 1}: {e}")
                    continue

            doc.close()

            text_content = '\n\n'.join(text_parts) if text_parts else ""
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

            return ExtractionResult(
                success=len(text_content.strip()) > 0,
                text_content=text_content,
                page_count=page_count,
                extraction_method="ocr_tesseract",
                extraction_confidence=min(0.9, avg_confidence / 100.0),
                ocr_used=True,
                images_processed=images_processed,
                average_confidence=avg_confidence,
                low_confidence_pages=low_confidence_pages
            )

        except Exception as e:
            return ExtractionResult(
                success=False,
                errors=[f"OCR extraction failed: {str(e)}"],
                extraction_method="ocr_tesseract",
                ocr_used=True
            )

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results."""
        try:
            # Convert to grayscale if not already
            if image.mode != 'L':
                image = image.convert('L')

            # Enhance contrast
            if self.ocr_config.enhance_contrast:
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.5)

            # Denoise
            if self.ocr_config.denoise:
                image = image.filter(ImageFilter.MedianFilter(size=3))

            # Additional preprocessing with OpenCV if available
            if OPENCV_AVAILABLE and self.ocr_config.deskew:
                import numpy as np

                # Convert PIL to OpenCV format
                opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_GRAY2BGR)

                # Deskew if needed (simplified version)
                gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150, apertureSize=3)
                lines = cv2.HoughLines(edges, 1, np.pi/180, 100)

                if lines is not None and len(lines) > 0:
                    # Calculate average angle
                    angles = []
                    for line in lines[:10]:  # Use first 10 lines
                        rho, theta = line[0]
                        angle = theta * 180 / np.pi
                        if angle > 45:
                            angle = angle - 90
                        angles.append(angle)

                    if angles:
                        avg_angle = np.mean(angles)
                        if abs(avg_angle) > 0.5:  # Only correct if significant skew
                            height, width = gray.shape
                            center = (width // 2, height // 2)
                            rotation_matrix = cv2.getRotationMatrix2D(center, avg_angle, 1.0)
                            opencv_image = cv2.warpAffine(opencv_image, rotation_matrix, (width, height))

                # Convert back to PIL
                image = Image.fromarray(cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB))

            return image

        except Exception as e:
            self.logger.warning(f"Image preprocessing failed: {e}")
            return image

    def _post_process_result(
        self,
        result: ExtractionResult,
        document_type: Optional[DocumentType]
    ) -> ExtractionResult:
        """Post-process extraction result."""
        if not result.success:
            return result

        # Detect document type if not provided
        if not document_type:
            result.document_type = self._detect_document_type(result.text_content)
        else:
            result.document_type = document_type

        # Clean and normalize text
        result.text_content = self._clean_text(result.text_content)

        # Detect language (simplified)
        result.language_detected = self._detect_language(result.text_content)

        return result

    def _detect_document_type(self, text: str) -> DocumentType:
        """Detect document type based on content patterns."""
        text_lower = text.lower()

        for doc_type, patterns in self.document_patterns.items():
            matches = sum(1 for pattern in patterns if len(list(re.finditer(pattern, text_lower))) > 0)
            if matches >= 2:  # Require at least 2 pattern matches
                return doc_type

        return DocumentType.GENERAL

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        import re

        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove page markers and artifacts
        text = re.sub(r'\[LOW CONFIDENCE PAGE \d+\]', '', text)
        text = re.sub(r'Page \d+ of \d+', '', text)

        # Fix common OCR errors
        text = text.replace(' 0 ', ' O ')  # Zero to O
        text = text.replace(' l ', ' I ')  # Lowercase l to I

        return text.strip()

    def _detect_language(self, text: str) -> str:
        """Detect text language (simplified detection)."""
        # Very basic language detection - in production might want to use langdetect
        english_indicators = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for']

        words = text.lower().split()[:100]  # Check first 100 words
        english_count = sum(1 for word in words if word in english_indicators)

        if english_count > len(words) * 0.1:  # 10% threshold
            return "eng"

        return "unknown"

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate hash of file for caching."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _get_quality_recommendations(
        self,
        result: ExtractionResult,
        issues: List[str]
    ) -> List[str]:
        """Get recommendations for improving extraction quality."""
        recommendations = []

        if "Low OCR confidence" in issues:
            recommendations.extend([
                "Try increasing DPI for image conversion",
                "Enable image preprocessing options",
                "Check if document is scanned at high resolution"
            ])

        if "Very short text extracted" in issues:
            recommendations.extend([
                "Verify PDF contains actual text (not just images)",
                "Try OCR extraction method for scanned documents",
                "Check if PDF is corrupted"
            ])

        if result.low_confidence_pages:
            recommendations.append("Review pages with low confidence manually")

        if not recommendations:
            recommendations.append("Extraction quality looks good")

        return recommendations


# Convenience functions for common use cases
async def extract_council_minutes(file_path: Union[str, Path]) -> ExtractionResult:
    """Extract text from council minutes PDF."""
    extractor = PDFExtractor()
    return await extractor.extract_text_from_file(
        file_path,
        method=ExtractionMethod.HYBRID,
        document_type=DocumentType.COUNCIL_MINUTES
    )


async def extract_permit_document(file_path: Union[str, Path]) -> ExtractionResult:
    """Extract text from permit document PDF."""
    extractor = PDFExtractor()
    return await extractor.extract_text_from_file(
        file_path,
        method=ExtractionMethod.HYBRID,
        document_type=DocumentType.PERMIT_DOCUMENT
    )


async def quick_extract(file_path: Union[str, Path]) -> str:
    """Quick text extraction - returns just the text content."""
    extractor = PDFExtractor()
    result = await extractor.extract_text_from_file(file_path)
    return result.text_content if result.success else ""