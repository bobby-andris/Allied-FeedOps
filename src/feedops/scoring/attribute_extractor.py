"""Attribute extraction for feed alignment scoring.

Identifies finishes, collections, product types, dimensions, model numbers,
and brand terms in search queries using fuzzy matching and regex patterns.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# --- Known finish data (28 finishes) ---
# These are the canonical finish names and their short codes.
# Used as defaults when Supabase data is not available (e.g., in tests).
KNOWN_FINISHES: dict[str, list[str]] = {
    "Polished Chrome": ["PC", "chrome"],
    "Polished Brass": ["PB", "brass"],
    "Polished Nickel": ["PN", "nickel"],
    "Satin Brass": ["SB"],
    "Satin Chrome": ["SC"],
    "Satin Nickel": ["SN"],
    "Matte White": ["WHM"],
    "Matte Black": ["BKM"],
    "Oil Rubbed Bronze": ["ORB", "oil bronze"],
    "Antique Brass": ["ABR"],
    "Antique Copper": ["CA"],
    "Antique Pewter": ["PEW"],
    "Venetian Bronze": ["VB"],
    "Brushed Bronze": ["BBR"],
    "Unlacquered Brass": ["UNL"],
    "French Gold": ["FR"],
    "Polished Gold": ["PG"],
    "Matte Gray": ["GYM"],
    "Vintage Bronze": ["VNB"],
    "Powder Coated White": ["WHP"],
    "Pacific Grove": [],  # Collection, sometimes confused as finish
    "Polished Copper": ["PCO"],
    "Satin Bronze": ["SBR"],
    "Flat Nickel": ["FN"],
    "Flat White": ["FW"],
    "Flat Black": ["FK"],
    "Titanium Gray": ["TG"],
    "Black Nickel": ["BNK"],
}

# Known collections (41 collections from Allied Brass catalog)
KNOWN_COLLECTIONS: list[str] = [
    "Prestige Regal",
    "Prestige Skyline",
    "Prestige Que New",
    "Waverly Place",
    "Carolina Collection",
    "Carolina Crystal",
    "Dottingham",
    "Montero",
    "Prestige Monte Carlo",
    "Mercury",
    "Pacific Grove",
    "Retro Dot",
    "Retro Wave",
    "Satellite Orbit One",
    "Satellite Orbit Two",
    "Skyline",
    "SoHo",
    "South Beach",
    "Tango",
    "Pipeline",
    "Tribeca",
    "Astor Place",
    "Continental",
    "Mambo",
    "Fresno",
    "Clearview",
    "Monte Carlo",
    "Regal",
    "Allied Brass",
    "Shower Rods",
    "Vanity Top",
    "Countertop",
    "Bolero",
    "Prestige",
    "Marine",
    "Beach",
    "Island",
    "Pacific Beach",
    "Que New",
    "Foxtrot",
    "Washington Square",
]


@dataclass
class ExtractionResult:
    """Result of attribute extraction from a search query."""

    matched_attributes: dict[str, str | list[str]] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)

    @property
    def has_model_number(self) -> bool:
        return "model_number" in self.matched_attributes

    def score(self) -> float:
        """Compute weighted attribute score, capped at 1.0."""
        if self.has_model_number:
            return 1.0
        total = sum(self.weights.values())
        return min(total, 1.0)


class AttributeExtractor:
    """Extracts product catalog attributes from search queries.

    Uses fuzzy matching (rapidfuzz) for finishes and collections,
    regex for model numbers and dimensions, and exact matching for
    product types and brand terms.
    """

    # Attribute weights for scoring
    WEIGHTS = {
        "model_number": 1.0,  # short-circuit
        "collection": 0.30,
        "finish": 0.25,
        "dimension": 0.25,
        "product_type": 0.15,
        "brand": 0.10,
    }

    # Regex patterns
    MODEL_PATTERN = re.compile(
        r"\b[A-Za-z]{2,4}[-/]\d+(?:[-/]\d+[A-Za-z]*)*\b"
    )
    DIMENSION_PATTERN = re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:inch|inches|in|\"|\u2033|cm|mm)\b",
        re.IGNORECASE,
    )

    # Fuzzy match threshold
    FUZZY_THRESHOLD = 85

    def __init__(
        self,
        finishes: dict[str, list[str]] | None = None,
        collections: list[str] | None = None,
        product_types: set[str] | None = None,
        brand_terms: set[str] | None = None,
    ):
        self.finishes = finishes or dict(KNOWN_FINISHES)
        self.collections = collections or list(KNOWN_COLLECTIONS)
        self.product_types = product_types or set()
        self.brand_terms = brand_terms or {"allied brass", "allied"}

        # Build lowercase lookup for finish codes
        self._finish_codes: dict[str, str] = {}
        for name, codes in self.finishes.items():
            for code in codes:
                self._finish_codes[code.lower()] = name

        # Build lowercase finish name set for fuzzy matching
        self._finish_names_lower = {
            name.lower(): name for name in self.finishes
        }

        # Build lowercase collection set for fuzzy matching
        self._collection_names_lower = {
            c.lower(): c for c in self.collections
        }

        # Build lowercase product types for matching
        self._product_types_lower = {
            pt.lower(): pt for pt in self.product_types
        }

    @classmethod
    def from_supabase(cls, client=None) -> "AttributeExtractor":
        """Load attribute dictionaries from Supabase product_catalog.

        Args:
            client: Supabase client. If None, uses get_client().

        Returns:
            Initialized AttributeExtractor with catalog data.
        """
        if client is None:
            from feedops.db.supabase_client import get_client
            client = get_client()

        product_types: set[str] = set()

        try:
            # Load custom_label_0 values as product types
            result = client.table("product_catalog").select(
                "custom_label_0"
            ).execute()
            for row in result.data or []:
                val = row.get("custom_label_0")
                if val and isinstance(val, str) and val.strip():
                    product_types.add(val.strip())

            logger.info(
                "Loaded %d product types from product_catalog",
                len(product_types),
            )
        except Exception as e:
            logger.warning("Failed to load product types from Supabase: %s", e)

        return cls(
            finishes=dict(KNOWN_FINISHES),
            collections=list(KNOWN_COLLECTIONS),
            product_types=product_types,
            brand_terms={"allied brass", "allied"},
        )

    def extract(self, query: str) -> ExtractionResult:
        """Extract matched attributes from a search query.

        Args:
            query: The search query text.

        Returns:
            ExtractionResult with matched attributes and weights.
        """
        result = ExtractionResult()

        # Edge cases: empty, single-char, all-numeric
        if not query or len(query.strip()) <= 1:
            return result

        query_clean = query.strip()

        # 1. Model number detection (short-circuit to 1.0)
        model_match = self.MODEL_PATTERN.search(query_clean)
        if model_match:
            result.matched_attributes["model_number"] = model_match.group()
            result.weights["model_number"] = self.WEIGHTS["model_number"]
            return result

        query_lower = query_clean.lower()

        # 2. Collection matching (fuzzy)
        matched_collection = self._match_collection(query_lower)
        if matched_collection:
            result.matched_attributes["collection"] = matched_collection
            result.weights["collection"] = self.WEIGHTS["collection"]

        # 3. Finish matching (fuzzy names + exact codes)
        matched_finish = self._match_finish(query_lower)
        if matched_finish:
            result.matched_attributes["finish"] = matched_finish
            result.weights["finish"] = self.WEIGHTS["finish"]

        # 4. Dimension matching (regex)
        dim_match = self.DIMENSION_PATTERN.search(query_clean)
        if dim_match:
            result.matched_attributes["dimension"] = dim_match.group()
            result.weights["dimension"] = self.WEIGHTS["dimension"]

        # 5. Product type matching
        matched_type = self._match_product_type(query_lower)
        if matched_type:
            result.matched_attributes["product_type"] = matched_type
            result.weights["product_type"] = self.WEIGHTS["product_type"]

        # 6. Brand matching
        for brand in self.brand_terms:
            if brand.lower() in query_lower:
                result.matched_attributes["brand"] = brand
                result.weights["brand"] = self.WEIGHTS["brand"]
                break

        return result

    def score(self, query: str) -> float:
        """Return weighted attribute score for a query (0-1)."""
        return self.extract(query).score()

    def _match_finish(self, query_lower: str) -> str | None:
        """Match finish name or code in query."""
        # First: check short codes with word-boundary matching
        words = set(re.split(r"[\s\-/]+", query_lower))
        for code_lower, name in self._finish_codes.items():
            if code_lower in words:
                return name

        # Second: fuzzy match finish names
        best_score = 0
        best_name = None
        for name_lower, name in self._finish_names_lower.items():
            # Check substring containment first for multi-word finishes
            if name_lower in query_lower:
                return name
            ratio = fuzz.token_set_ratio(name_lower, query_lower)
            if ratio >= self.FUZZY_THRESHOLD and ratio > best_score:
                best_score = ratio
                best_name = name

        return best_name

    def _match_collection(self, query_lower: str) -> str | None:
        """Match collection name in query using fuzzy matching."""
        best_score = 0
        best_name = None

        for name_lower, name in self._collection_names_lower.items():
            # Exact substring match (prioritize)
            if name_lower in query_lower:
                return name

            # Fuzzy match for multi-word collection names
            if len(name_lower.split()) >= 2:
                ratio = fuzz.token_set_ratio(name_lower, query_lower)
                if ratio >= self.FUZZY_THRESHOLD and ratio > best_score:
                    best_score = ratio
                    best_name = name

        return best_name

    def _match_product_type(self, query_lower: str) -> str | None:
        """Match product type (custom_label_0) in query."""
        best_match = None
        best_len = 0

        for type_lower, type_name in self._product_types_lower.items():
            if type_lower in query_lower and len(type_lower) > best_len:
                best_match = type_name
                best_len = len(type_lower)

        return best_match
