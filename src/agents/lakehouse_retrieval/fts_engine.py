"""
Full-Text Search Integration
Handle keyword extraction and FTS queries.
"""

import re
from typing import List, Set


class KeywordExtractor:
    """Extract keywords from text queries."""

    def __init__(self):
        """Initialize extractor."""
        # Simple stop words for English/Chinese
        self.stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "的", "是", "在", "了", "有", "和", "中", "人", "这", "以"
        }

    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """
        Extract keywords from text.

        Args:
            text: Input text
            top_k: Number of top keywords to return

        Returns:
            List of keywords
        """
        # Convert to lowercase and split
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter stop words and short words
        keywords = [w for w in words if w not in self.stop_words and len(w) > 2]

        # Return top frequent
        from collections import Counter
        counter = Counter(keywords)
        return [kw for kw, _ in counter.most_common(top_k)]


class FTSQueryEngine:
    """Full-Text Search query engine."""

    def __init__(self):
        """Initialize FTS engine."""
        self.inverted_index: dict = {}
        self.metadata_store: dict = {}

    def index_metadata(self, slide_id: str, metadata: dict) -> None:
        """
        Index slide metadata for FTS.

        Args:
            slide_id: Slide ID
            metadata: Metadata dictionary
        """
        self.metadata_store[slide_id] = metadata

        # Extract text from metadata
        text_parts = []
        if isinstance(metadata, dict):
            text_parts = [str(v) for v in metadata.values() if isinstance(v, str)]

        # Tokenize and index
        extractor = KeywordExtractor()
        keywords = extractor.extract_keywords(" ".join(text_parts))

        for keyword in keywords:
            if keyword not in self.inverted_index:
                self.inverted_index[keyword] = set()
            self.inverted_index[keyword].add(slide_id)

    def search(self, keywords: List[str], mode: str = "AND") -> Set[str]:
        """
        Search for slides matching keywords.

        Args:
            keywords: List of keywords
            mode: "AND" (all must match) or "OR" (any match)

        Returns:
            Set of matching slide IDs
        """
        if not keywords:
            return set()

        results = []
        for keyword in keywords:
            matching = self.inverted_index.get(keyword, set())
            results.append(matching)

        if mode == "AND":
            # Intersection: all keywords must appear
            if results:
                return set.intersection(*results) if len(results) > 0 else set()
            return set()
        else:  # OR mode
            # Union: any keyword can appear
            return set.union(*results) if results else set()
