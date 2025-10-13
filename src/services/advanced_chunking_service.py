"""
Advanced Semantic Chunking for Legal Documents (2025)

Implements state-of-the-art chunking strategies:
1. NLTK sentence tokenization (legal abbreviation-aware)
2. Semantic similarity-based boundaries (embedding-driven)
3. Sliding window overlap for context preservation
4. Hierarchical structure parsing
5. Rich metadata extraction
6. Legal citation recognition

Based on 2025 best practices:
- Anthropic's contextual retrieval
- Max-Min semantic chunking
- LlamaIndex's semantic splitting approach
"""

import re
import nltk
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from sentence_transformers import SentenceTransformer


# Download NLTK data on first import
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)


@dataclass
class EnhancedChunk:
    """Enhanced chunk with extensive metadata"""
    # Core content
    text: str
    chunk_number: int

    # Hierarchical structure
    section_id: str
    section_title: str
    article: Optional[str] = None
    parent_section: Optional[str] = None
    subsection_level: int = 0

    # Content classification
    content_type: str = "text"  # text|table|list|definition|citation|mixed
    has_table: bool = False
    has_list: bool = False
    has_definition: bool = False
    has_citation: bool = False

    # Legal-specific metadata
    definitions: List[str] = field(default_factory=list)  # Terms defined in chunk
    citations: List[str] = field(default_factory=list)  # Legal citations found
    cross_references: List[str] = field(default_factory=list)  # Section references
    legal_entities: List[str] = field(default_factory=list)  # Parties, jurisdictions

    # Semantic metadata
    key_phrases: List[str] = field(default_factory=list)  # Important phrases
    semantic_density: float = 0.0  # Measure of information density
    coherence_score: float = 0.0  # Semantic coherence with neighbors

    # Contextual metadata
    prev_chunk_overlap: str = ""  # Overlapping text from previous chunk
    next_chunk_preview: str = ""  # Preview of next chunk
    document_position: float = 0.0  # Position in document (0.0-1.0)

    # Size metrics
    word_count: int = 0
    char_count: int = 0
    sentence_count: int = 0

    # Embedding (optional, for semantic search)
    embedding: Optional[np.ndarray] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            "text": self.text,
            "chunk_number": self.chunk_number,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "article": self.article,
            "parent_section": self.parent_section,
            "subsection_level": self.subsection_level,
            "content_type": self.content_type,
            "has_table": self.has_table,
            "has_list": self.has_list,
            "has_definition": self.has_definition,
            "has_citation": self.has_citation,
            "definitions": self.definitions,
            "citations": self.citations,
            "cross_references": self.cross_references,
            "legal_entities": self.legal_entities,
            "key_phrases": self.key_phrases,
            "semantic_density": self.semantic_density,
            "coherence_score": self.coherence_score,
            "prev_chunk_overlap": self.prev_chunk_overlap,
            "next_chunk_preview": self.next_chunk_preview,
            "document_position": self.document_position,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "sentence_count": self.sentence_count,
        }


class AdvancedSemanticChunker:
    """
    Advanced semantic chunker using 2025 best practices

    Features:
    - Semantic similarity-based boundaries
    - Legal abbreviation-aware sentence splitting
    - Sliding window overlap
    - Rich metadata extraction
    - Adaptive chunk sizing
    """

    # Legal abbreviations that should NOT trigger sentence breaks
    LEGAL_ABBREVIATIONS = [
        r'U\.S\.', r'Inc\.', r'Corp\.', r'Ltd\.', r'Co\.',
        r'Fla\.', r'Cal\.', r'N\.Y\.', r'Stat\.', r'Rev\.',
        r'Art\.', r'Sec\.', r'§', r'¶', r'No\.', r'v\.',
        r'et al\.', r'i\.e\.', r'e\.g\.', r'etc\.',
        r'Dr\.', r'Mr\.', r'Mrs\.', r'Ms\.', r'Prof\.',
    ]

    # Legal citation patterns
    CITATION_PATTERNS = [
        r'\d+\s+U\.S\.C\.\s+§\s+\d+',  # Federal code
        r'Fla\.\s+Stat\.\s+§\s+[\d\.]+',  # Florida statutes
        r'\d+\s+[A-Z][a-z]+\.\s+\d+',  # Case citations
        r'§\s*\d+\.\d+',  # Section references
    ]

    # Definition patterns
    DEFINITION_PATTERNS = [
        r'"([^"]+)"\s+means',  # "Term" means
        r'"([^"]+)"\s+shall mean',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+means',  # Term means
        r'The term\s+"([^"]+)"',
    ]

    def __init__(
        self,
        target_words: int = 400,
        max_words: int = 500,
        overlap_sentences: int = 2,
        semantic_threshold: float = 0.75,
        embedding_model: Optional[SentenceTransformer] = None
    ):
        """
        Initialize advanced chunker

        Args:
            target_words: Ideal chunk size
            max_words: Maximum chunk size
            overlap_sentences: Number of sentences to overlap between chunks
            semantic_threshold: Similarity threshold for semantic boundaries
            embedding_model: Optional pre-loaded embedding model for semantic analysis
        """
        self.target_words = target_words
        self.max_words = max_words
        self.overlap_sentences = overlap_sentences
        self.semantic_threshold = semantic_threshold

        # Load embedding model for semantic analysis (lightweight)
        self.embedding_model = embedding_model
        self.use_semantic_boundaries = embedding_model is not None

    def chunk_ordinance(self, markdown_text: str) -> List[EnhancedChunk]:
        """
        Main entry point: Advanced semantic chunking

        Args:
            markdown_text: Full ordinance text

        Returns:
            List of enhanced chunks with rich metadata
        """
        # 1. Preprocess
        text = self._preprocess_text(markdown_text)

        # 2. Split into sentences (NLTK with legal abbreviation handling)
        sentences = self._split_sentences_legal(text)

        # 3. If semantic boundaries enabled, find natural breakpoints
        if self.use_semantic_boundaries:
            boundaries = self._find_semantic_boundaries(sentences)
        else:
            boundaries = self._find_structural_boundaries(text, sentences)

        # 4. Create chunks at boundaries with overlap
        chunks = self._create_chunks_with_overlap(sentences, boundaries, len(text))

        # 5. Extract rich metadata for each chunk
        chunks = self._enhance_metadata(chunks)

        return chunks

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text (same as before but optimized)"""
        # Remove navigation elements
        text = re.sub(r'Share Link to section.*?Compare versions', '', text, flags=re.DOTALL)
        text = re.sub(r'Print section.*?Email section', '', text)
        text = re.sub(r'Loading, please wait|Show Changes.*?more', '', text, flags=re.DOTALL)

        # Handle images
        def replace_image(match):
            alt_text = match.group(1)
            if len(alt_text) > 10 and not any(skip in alt_text.lower()
                for skip in ['logo', 'icon', 'button', 'image']):
                return f'[Image: {alt_text}]'
            return ''

        text = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_image, text)

        # Normalize whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def _split_sentences_legal(self, text: str) -> List[str]:
        """
        Split text into sentences with legal abbreviation handling

        Uses NLTK's punkt tokenizer with custom legal abbreviation rules
        """
        # Use NLTK's sentence tokenizer
        sentences = nltk.sent_tokenize(text)

        # Post-process: Merge sentences that were incorrectly split on abbreviations
        merged_sentences = []
        i = 0

        while i < len(sentences):
            current = sentences[i]

            # Check if current sentence ends with a legal abbreviation
            ends_with_abbrev = any(
                re.search(pattern + r'\s*$', current)
                for pattern in self.LEGAL_ABBREVIATIONS
            )

            # If yes, and there's a next sentence starting lowercase, merge them
            if ends_with_abbrev and i + 1 < len(sentences):
                next_sent = sentences[i + 1]
                if next_sent and next_sent[0].islower():
                    merged_sentences.append(current + ' ' + next_sent)
                    i += 2
                    continue

            merged_sentences.append(current)
            i += 1

        return merged_sentences

    def _find_semantic_boundaries(self, sentences: List[str]) -> List[int]:
        """
        Find natural chunk boundaries using semantic similarity

        Approach (based on LlamaIndex SemanticSplitter):
        1. Embed each sentence
        2. Calculate similarity between consecutive sentences
        3. Identify low-similarity points as boundaries
        4. Ensure chunks don't exceed max_words
        """
        if not sentences or not self.embedding_model:
            return []

        # Embed all sentences
        embeddings = self.embedding_model.encode(
            sentences,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True
        )

        # Calculate cosine similarity between consecutive sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = np.dot(embeddings[i], embeddings[i + 1])
            similarities.append(sim)

        # Find boundaries (low similarity points)
        boundaries = [0]  # Start
        current_words = 0

        for i, sim in enumerate(similarities):
            sent_words = len(sentences[i].split())
            current_words += sent_words

            # Boundary conditions:
            # 1. Semantic shift (similarity < threshold)
            # 2. Approaching max_words
            # 3. Reaching target_words and next sentence is a good break

            if current_words >= self.max_words:
                # Force boundary at max_words
                boundaries.append(i + 1)
                current_words = 0

            elif current_words >= self.target_words and sim < self.semantic_threshold:
                # Natural semantic boundary
                boundaries.append(i + 1)
                current_words = 0

        boundaries.append(len(sentences))  # End

        return boundaries

    def _find_structural_boundaries(self, text: str, sentences: List[str]) -> List[int]:
        """
        Find boundaries based on document structure (fallback if no embeddings)

        Looks for:
        - Section headers (ARTICLE, numbered sections)
        - Paragraph breaks
        - Table boundaries
        - List boundaries
        """
        boundaries = [0]
        current_words = 0
        current_pos = 0

        for i, sent in enumerate(sentences):
            sent_words = len(sent.split())
            current_words += sent_words

            # Find sentence position in original text
            sent_pos = text.find(sent, current_pos)
            current_pos = sent_pos + len(sent)

            # Check for structural markers
            is_section_header = bool(re.match(r'^(ARTICLE [IVXLCDM]+|\d+\.\d+\.?)\s*[-—]', sent))
            is_paragraph_break = i > 0 and text[sent_pos - 10:sent_pos].count('\n') >= 2

            # Boundary conditions
            if current_words >= self.max_words:
                boundaries.append(i + 1)
                current_words = 0

            elif current_words >= self.target_words and (is_section_header or is_paragraph_break):
                boundaries.append(i + 1)
                current_words = 0

        boundaries.append(len(sentences))

        return boundaries

    def _create_chunks_with_overlap(
        self,
        sentences: List[str],
        boundaries: List[int],
        total_text_len: int
    ) -> List[EnhancedChunk]:
        """
        Create chunks with sliding window overlap

        Overlap strategy: Include last N sentences from previous chunk
        """
        chunks = []

        for i in range(len(boundaries) - 1):
            start_idx = boundaries[i]
            end_idx = boundaries[i + 1]

            # Main chunk sentences
            chunk_sentences = sentences[start_idx:end_idx]

            # Add overlap from previous chunk
            prev_overlap = ""
            if i > 0 and self.overlap_sentences > 0:
                overlap_start = max(0, boundaries[i] - self.overlap_sentences)
                prev_sentences = sentences[overlap_start:start_idx]
                prev_overlap = " ".join(prev_sentences)

            # Add preview of next chunk
            next_preview = ""
            if i < len(boundaries) - 2 and self.overlap_sentences > 0:
                next_end = min(len(sentences), boundaries[i + 1] + self.overlap_sentences)
                next_sentences = sentences[end_idx:next_end]
                next_preview = " ".join(next_sentences)

            # Create chunk text
            chunk_text = " ".join(chunk_sentences)

            # Calculate document position (0.0 to 1.0)
            approx_char_pos = sum(len(s) for s in sentences[:start_idx])
            doc_position = approx_char_pos / total_text_len if total_text_len > 0 else 0.0

            # Extract basic structure info
            section_id, section_title = self._extract_section_info(chunk_text)
            article = self._extract_article(chunk_text)

            # Create enhanced chunk
            chunk = EnhancedChunk(
                text=chunk_text,
                chunk_number=i,
                section_id=section_id,
                section_title=section_title,
                article=article,
                prev_chunk_overlap=prev_overlap,
                next_chunk_preview=next_preview,
                document_position=doc_position,
                word_count=len(chunk_text.split()),
                char_count=len(chunk_text),
                sentence_count=len(chunk_sentences)
            )

            chunks.append(chunk)

        return chunks

    def _enhance_metadata(self, chunks: List[EnhancedChunk]) -> List[EnhancedChunk]:
        """
        Extract rich metadata for each chunk

        Extracts:
        - Content type (table, list, definition, citation)
        - Definitions
        - Citations
        - Cross-references
        - Legal entities
        - Key phrases
        - Semantic density
        - Coherence scores
        """
        for chunk in chunks:
            text = chunk.text

            # Content type detection
            chunk.has_table = bool(re.search(r'\|.*?\|.*?\n\|[-:| ]+\|', text))
            chunk.has_list = bool(re.search(r'^\((\d+|[a-z])\)', text, re.MULTILINE))
            chunk.has_definition = bool(self._extract_definitions(text))
            chunk.has_citation = bool(self._extract_citations(text))

            # Set primary content type
            if chunk.has_definition:
                chunk.content_type = "definition"
            elif chunk.has_citation:
                chunk.content_type = "citation"
            elif chunk.has_table and chunk.has_list:
                chunk.content_type = "mixed"
            elif chunk.has_table:
                chunk.content_type = "table"
            elif chunk.has_list:
                chunk.content_type = "list"
            else:
                chunk.content_type = "text"

            # Extract structured metadata
            chunk.definitions = self._extract_definitions(text)
            chunk.citations = self._extract_citations(text)
            chunk.cross_references = self._extract_cross_references(text)
            chunk.legal_entities = self._extract_legal_entities(text)
            chunk.key_phrases = self._extract_key_phrases(text)

            # Calculate semantic metrics
            chunk.semantic_density = self._calculate_semantic_density(text)

        # Calculate coherence scores (requires comparing with neighbors)
        if self.use_semantic_boundaries and len(chunks) > 1:
            chunks = self._calculate_coherence_scores(chunks)

        return chunks

    def _extract_section_info(self, text: str) -> Tuple[str, str]:
        """Extract section ID and title"""
        # Look for numbered section
        section_match = re.match(r'^(\d+\.\d+\.?)\s*[-—]\s*(.+?)\.?\s*$', text, re.MULTILINE)
        if section_match:
            return section_match.group(1), section_match.group(2)

        # Look for article
        article_match = re.match(r'^(ARTICLE [IVXLCDM]+\.?)\s*[-—]\s*(.+)$', text, re.MULTILINE)
        if article_match:
            return article_match.group(1), article_match.group(2)

        return "UNKNOWN", "Unknown Section"

    def _extract_article(self, text: str) -> Optional[str]:
        """Extract parent article"""
        match = re.search(r'(ARTICLE [IVXLCDM]+)', text)
        return match.group(1) if match else None

    def _extract_definitions(self, text: str) -> List[str]:
        """Extract terms being defined"""
        definitions = []
        for pattern in self.DEFINITION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            definitions.extend(matches)
        return list(set(definitions))

    def _extract_citations(self, text: str) -> List[str]:
        """Extract legal citations"""
        citations = []
        for pattern in self.CITATION_PATTERNS:
            matches = re.findall(pattern, text)
            citations.extend(matches)
        return list(set(citations))

    def _extract_cross_references(self, text: str) -> List[str]:
        """Extract section cross-references"""
        refs = set()
        refs.update(re.findall(r'(?:Section|§)\s*(\d+\.\d+)', text))
        refs.update(re.findall(r'nodeId=.*?(\d+\.\d+)', text))
        return sorted(list(refs))

    def _extract_legal_entities(self, text: str) -> List[str]:
        """Extract legal entities (parties, jurisdictions)"""
        entities = []

        # Common entities in municipal ordinances
        patterns = [
            r'\bCity of [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # City of Gainesville
            r'\b[A-Z][a-z]+\s+County\b',  # Alachua County
            r'\bState of [A-Z][a-z]+\b',  # State of Florida
            r'\b[A-Z][a-z]+\s+Commission\b',  # City Commission
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)

        return list(set(entities))

    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases (important terms)"""
        # Simple approach: Extract capitalized multi-word phrases
        phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b', text)

        # Filter common noise
        filtered = [p for p in phrases if p not in ['The City', 'As Provided', 'In Accordance']]

        return list(set(filtered))[:10]  # Top 10

    def _calculate_semantic_density(self, text: str) -> float:
        """
        Calculate semantic density (information richness)

        Heuristic:
        - High density: Many unique words, technical terms, numbers, citations
        - Low density: Repetitive, filler words
        """
        words = text.lower().split()
        if not words:
            return 0.0

        unique_ratio = len(set(words)) / len(words)

        # Bonus for technical indicators
        has_numbers = len(re.findall(r'\d+', text)) / len(words)
        has_citations = len(re.findall(r'§|\d+\.\d+', text)) / len(words)
        has_caps = len(re.findall(r'\b[A-Z][a-z]+\b', text)) / len(words)

        density = (unique_ratio * 0.5 +
                  has_numbers * 0.2 +
                  has_citations * 0.2 +
                  has_caps * 0.1)

        return min(1.0, density)

    def _calculate_coherence_scores(self, chunks: List[EnhancedChunk]) -> List[EnhancedChunk]:
        """
        Calculate semantic coherence with neighboring chunks

        Uses embedding similarity if model available
        """
        if not self.embedding_model or len(chunks) < 2:
            return chunks

        # Embed all chunks
        chunk_texts = [c.text for c in chunks]
        embeddings = self.embedding_model.encode(
            chunk_texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True
        )

        # Calculate coherence with neighbors
        for i, chunk in enumerate(chunks):
            coherence_scores = []

            # Compare with previous chunk
            if i > 0:
                prev_sim = np.dot(embeddings[i], embeddings[i - 1])
                coherence_scores.append(prev_sim)

            # Compare with next chunk
            if i < len(chunks) - 1:
                next_sim = np.dot(embeddings[i], embeddings[i + 1])
                coherence_scores.append(next_sim)

            # Average coherence
            chunk.coherence_score = float(np.mean(coherence_scores)) if coherence_scores else 0.0
            chunk.embedding = embeddings[i]

        return chunks


def create_advanced_chunker(
    target_words: int = 400,
    max_words: int = 500,
    overlap_sentences: int = 2,
    use_semantic_boundaries: bool = True,
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
) -> AdvancedSemanticChunker:
    """
    Factory function to create advanced chunker

    Args:
        target_words: Ideal chunk size
        max_words: Maximum chunk size
        overlap_sentences: Sentences to overlap between chunks
        use_semantic_boundaries: Use embedding-based boundaries
        embedding_model_name: Model for semantic analysis (small/fast)

    Returns:
        Configured AdvancedSemanticChunker
    """
    embedding_model = None
    if use_semantic_boundaries:
        print(f"Loading embedding model for semantic boundaries: {embedding_model_name}...")
        embedding_model = SentenceTransformer(embedding_model_name, device='cpu')
        print(f"Model loaded ({embedding_model.get_sentence_embedding_dimension()} dims)")

    return AdvancedSemanticChunker(
        target_words=target_words,
        max_words=max_words,
        overlap_sentences=overlap_sentences,
        semantic_threshold=0.75,
        embedding_model=embedding_model
    )
