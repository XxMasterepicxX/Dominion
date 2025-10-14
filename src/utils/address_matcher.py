"""
Address Normalization and Fuzzy Matching

Handles address variations, typos, and formats to improve property lookup success rate.
Target: Reduce failure rate from 43% to <5%
"""

import re
from typing import Optional, List, Tuple
from difflib import SequenceMatcher


class AddressMatcher:
    """
    Address normalization and fuzzy matching for property lookups
    """

    # Common abbreviations and variations
    STREET_ABBREV = {
        # Streets
        'street': 'st', 'str': 'st', 'st.': 'st',
        # Avenues
        'avenue': 'ave', 'av': 'ave', 'ave.': 'ave', 'avn': 'ave',
        # Boulevards
        'boulevard': 'blvd', 'boul': 'blvd', 'blv': 'blvd', 'blvd.': 'blvd',
        # Drives
        'drive': 'dr', 'drv': 'dr', 'dr.': 'dr',
        # Roads
        'road': 'rd', 'rd.': 'rd',
        # Lanes
        'lane': 'ln', 'ln.': 'ln',
        # Places
        'place': 'pl', 'pl.': 'pl',
        # Circles
        'circle': 'cir', 'circ': 'cir', 'cir.': 'cir', 'circl': 'cir',
        # Courts
        'court': 'ct', 'ct.': 'ct', 'crt': 'ct',
        # Terraces
        'terrace': 'ter', 'terr': 'ter', 'ter.': 'ter',
        # Trails
        'trail': 'trl', 'tr': 'trl', 'trl.': 'trl',
        # Ways
        'way': 'way', 'wy': 'way',
        # Highways
        'highway': 'hwy', 'hwy.': 'hwy', 'hiway': 'hwy',
        # Parkways
        'parkway': 'pkwy', 'pkwy.': 'pkwy', 'pky': 'pkwy', 'parkwy': 'pkwy',
        # Directions (normalize)
        'north': 'n', 'south': 's', 'east': 'e', 'west': 'w',
        'northeast': 'ne', 'northwest': 'nw', 'southeast': 'se', 'southwest': 'sw',
    }

    # Ordinal number patterns
    ORDINAL_PATTERN = re.compile(r'(\d+)(st|nd|rd|th)', re.IGNORECASE)

    def __init__(self):
        """Initialize address matcher"""
        pass

    def normalize_address(self, address: str) -> str:
        """
        Normalize address to standard format for comparison

        Args:
            address: Raw address string

        Returns:
            Normalized address string

        Example:
            "123 North Main Street" -> "123 n main st"
            "456 SW 39th Avenue" -> "456 sw 39 ave"
        """
        if not address:
            return ""

        # Convert to lowercase
        normalized = address.lower().strip()

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        # Remove punctuation (except hyphens in street names)
        normalized = re.sub(r'[,.]', '', normalized)

        # Normalize ordinal numbers (1st -> 1, 2nd -> 2, etc.)
        normalized = self.ORDINAL_PATTERN.sub(r'\1', normalized)

        # Split into tokens for abbreviation replacement
        tokens = normalized.split()
        normalized_tokens = []

        for token in tokens:
            # Replace with abbreviation if exists
            if token in self.STREET_ABBREV:
                normalized_tokens.append(self.STREET_ABBREV[token])
            else:
                normalized_tokens.append(token)

        return ' '.join(normalized_tokens)

    def extract_street_number(self, address: str) -> Optional[str]:
        """
        Extract street number from address

        Args:
            address: Address string

        Returns:
            Street number if found, None otherwise

        Example:
            "123 Main St" -> "123"
            "456-A SW 39th Ave" -> "456"
        """
        match = re.match(r'^(\d+)[-\s]?[A-Z]?\s+', address, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def similarity_score(self, addr1: str, addr2: str) -> float:
        """
        Calculate similarity between two addresses (0.0 to 1.0)

        Uses SequenceMatcher for fuzzy string comparison

        Args:
            addr1: First address
            addr2: Second address

        Returns:
            Similarity score from 0.0 (no match) to 1.0 (exact match)
        """
        # Normalize both addresses first
        norm1 = self.normalize_address(addr1)
        norm2 = self.normalize_address(addr2)

        # Calculate similarity
        return SequenceMatcher(None, norm1, norm2).ratio()

    def build_search_queries(self, address: str) -> List[str]:
        """
        Build multiple search query variations for an address

        Tries progressively broader searches:
        1. Normalized exact match
        2. Street number + street name only
        3. Street name only (last resort)

        Args:
            address: Input address

        Returns:
            List of search queries ordered by specificity
        """
        queries = []

        # Query 1: Full normalized address
        normalized = self.normalize_address(address)
        if normalized:
            queries.append(normalized)

        # Query 2: Street number + street name (remove city, state)
        # "123 main st, gainesville, fl" -> "123 main st"
        parts = normalized.split(',')
        if parts:
            street_part = parts[0].strip()
            if street_part and street_part != normalized:
                queries.append(street_part)

        # Query 3: Just the core street address (number + main words)
        # "123 nw 39th ave" -> "123 39 ave" (keep number + key words)
        tokens = normalized.split()
        if len(tokens) >= 2:
            # Keep street number + significant words (skip directionals if too specific)
            core_tokens = [tokens[0]]  # street number
            for token in tokens[1:]:
                # Skip very common directionals
                if token not in ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']:
                    core_tokens.append(token)

            core_address = ' '.join(core_tokens)
            if core_address not in queries:
                queries.append(core_address)

        return queries

    def rank_matches(
        self,
        query_address: str,
        candidate_addresses: List[Tuple[str, str, str]]
    ) -> List[Tuple[str, str, str, float]]:
        """
        Rank candidate addresses by similarity to query

        Args:
            query_address: The address we're searching for
            candidate_addresses: List of (property_id, parcel_id, site_address) tuples

        Returns:
            List of (property_id, parcel_id, site_address, score) tuples, ordered by score (highest first)
        """
        scored_candidates = []

        for property_id, parcel_id, site_address in candidate_addresses:
            score = self.similarity_score(query_address, site_address)
            scored_candidates.append((property_id, parcel_id, site_address, score))

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[3], reverse=True)

        return scored_candidates


# Global matcher instance
_address_matcher = None

def get_address_matcher() -> AddressMatcher:
    """Get singleton AddressMatcher instance"""
    global _address_matcher
    if _address_matcher is None:
        _address_matcher = AddressMatcher()
    return _address_matcher
