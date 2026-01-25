"""On-the-fly product enrichment for design-intent detection.

This module detects unique product features and design context at runtime,
enabling the LLM to generate more differentiated, brand-appropriate content.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Optional

from feedops.models import ParentSKU


# Evidence dataclass - shared with evidence.py (avoid circular import)
from dataclasses import dataclass as _dataclass

@_dataclass
class Evidence:
    """A single evidence row for the LLM prompt."""
    field: str
    value: str
    source: str


# Load collection metadata at module import
_COLLECTION_METADATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "collection-metadata.json"
_COLLECTION_METADATA: dict = {}
_COLLECTIONS: dict = {}
_GROUPS: dict = {}
_SUBGROUPS: dict = {}

def _load_collection_metadata() -> None:
    """Load collection metadata from JSON file."""
    global _COLLECTION_METADATA, _COLLECTIONS, _GROUPS, _SUBGROUPS
    if _COLLECTION_METADATA:
        return  # Already loaded
    
    try:
        with open(_COLLECTION_METADATA_PATH) as f:
            _COLLECTION_METADATA = json.load(f)
            _COLLECTIONS = _COLLECTION_METADATA.get("collections", {})
            _GROUPS = _COLLECTION_METADATA.get("groups", {})
            _SUBGROUPS = _COLLECTION_METADATA.get("subgroups", {})
    except FileNotFoundError:
        pass  # Graceful degradation if file not found


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CollectionContext:
    """Context about product's collection membership."""
    name: str
    group: str  # Contemporary/Modern, Traditional/Classic, etc.
    subgroup: Optional[str]  # Designer Statement, Coastal Modern, etc.
    aesthetic: str
    design_language: str
    tone_keywords: list[str]
    coordination_keywords: list[str]
    ideal_for: list[str]
    is_collection_member: bool = True


@dataclass
class DesignStyleContext:
    """Design style classification for tone guidance."""
    style: str  # "modern", "traditional", "transitional", "industrial", "coastal"
    tone_guidance: str
    style_keywords: list[str]


@dataclass
class FunctionalFeature:
    """A detected functional feature with title keyword, benefit, and search keywords."""
    feature_id: str
    title_keyword: Optional[str]  # Short term for titles (e.g., "Reeded Grip", "ADA Compliant")
    benefit: str  # Value proposition for descriptions
    keywords: list[str]  # Search terms for keyword targeting


@dataclass
class FinishVarietyContext:
    """Analysis of available finish options."""
    total_count: int
    variety_level: str  # "exceptional", "extensive", "good", "standard"
    variety_message: Optional[str]
    has_statement_finishes: bool
    statement_finishes: dict[str, str]  # {finish: description}
    finish_keywords: list[str]


@dataclass
class CompetitiveContext:
    """Competitive positioning analysis."""
    edge_level: str  # "high", "moderate", "standard"
    edge_statement: str
    unique_differentiators: list[str]
    competitor_gap_keywords: list[str]


@dataclass
class ProductEnrichment:
    """Complete on-the-fly enrichment for a product."""
    collection: Optional[CollectionContext]
    design_style: DesignStyleContext
    functional_features: list[FunctionalFeature]
    finish_variety: FinishVarietyContext
    competitive: CompetitiveContext
    design_intent_keywords: list[str] = field(default_factory=list)
    tone_guidance: str = ""
    key_differentiators: list[str] = field(default_factory=list)
    
    def to_evidence_rows(self) -> list[Evidence]:
        """Convert enrichment to evidence table rows for prompt injection."""
        rows = []
        
        if self.collection:
            rows.append(Evidence(
                field="collection_context",
                value=f"{self.collection.name} ({self.collection.group}) - {self.collection.aesthetic}",
                source="enrichment_collection",
            ))
            if self.collection.subgroup:
                rows.append(Evidence(
                    field="collection_subgroup",
                    value=self.collection.subgroup,
                    source="enrichment_collection",
                ))
        
        rows.append(Evidence(
            field="design_style",
            value=f"{self.design_style.style} ({self.design_style.tone_guidance})",
            source="enrichment_style",
        ))
        
        # SEPARATE: title_keywords (for titles) vs functional_benefits (for descriptions)
        if self.functional_features:
            # Title keywords - short search terms like "Reeded Grip", "ADA Compliant", "Tilting"
            title_keywords = [f.title_keyword for f in self.functional_features if f.title_keyword]
            if title_keywords:
                rows.append(Evidence(
                    field="feature_title_keywords",
                    value=", ".join(title_keywords),
                    source="enrichment_features",
                ))
            
            # Benefits for descriptions - longer value propositions
            benefits = [f.benefit for f in self.functional_features]
            if benefits:
                rows.append(Evidence(
                    field="feature_benefits",
                    value="; ".join(benefits),
                    source="enrichment_features",
                ))
        
        if self.finish_variety.variety_message:
            rows.append(Evidence(
                field="finish_variety",
                value="Multiple designer finish options available",
                source="enrichment_finishes",
            ))
        
        if self.competitive.edge_level in ("high", "moderate"):
            rows.append(Evidence(
                field="competitive_edge",
                value=self.competitive.edge_statement,
                source="enrichment_competitive",
            ))
        
        if self.key_differentiators:
            rows.append(Evidence(
                field="key_differentiators",
                value="; ".join(self.key_differentiators[:3]),
                source="enrichment_competitive",
            ))
        
        if self.design_intent_keywords:
            rows.append(Evidence(
                field="design_intent_keywords",
                value=", ".join(self.design_intent_keywords[:10]),
                source="enrichment_keywords",
            ))
        
        return rows


# =============================================================================
# Feature Detectors
# =============================================================================

def detect_collection(parent_sku: ParentSKU) -> Optional[CollectionContext]:
    """Identify if product belongs to a named design collection."""
    _load_collection_metadata()
    
    collection_name = parent_sku.collection
    if not collection_name:
        return None
    
    # Try exact match first
    if collection_name in _COLLECTIONS:
        meta = _COLLECTIONS[collection_name]
        return CollectionContext(
            name=collection_name,
            group=meta.get("group", ""),
            subgroup=meta.get("subgroup"),
            aesthetic=meta.get("aesthetic", ""),
            design_language=meta.get("design_language", ""),
            tone_keywords=meta.get("tone_keywords", []),
            coordination_keywords=meta.get("coordination_keywords", []),
            ideal_for=meta.get("ideal_for", []),
        )
    
    # Try fuzzy match (case-insensitive, partial)
    collection_lower = collection_name.lower()
    for name, meta in _COLLECTIONS.items():
        if name.lower() in collection_lower or collection_lower in name.lower():
            return CollectionContext(
                name=name,
                group=meta.get("group", ""),
                subgroup=meta.get("subgroup"),
                aesthetic=meta.get("aesthetic", ""),
                design_language=meta.get("design_language", ""),
                tone_keywords=meta.get("tone_keywords", []),
                coordination_keywords=meta.get("coordination_keywords", []),
                ideal_for=meta.get("ideal_for", []),
            )
    
    # Unknown collection - still flag as collection member
    return CollectionContext(
        name=collection_name,
        group="Unknown",
        subgroup=None,
        aesthetic="distinctive design",
        design_language="coordinated collection piece",
        tone_keywords=["refined", "coordinated"],
        coordination_keywords=[f"{collection_name.lower()} collection"],
        ideal_for=["coordinated bathroom design"],
    )


# Design style patterns for classification
_DESIGN_STYLE_PATTERNS = {
    "traditional": {
        "signals": ["traditional", "classic", "ornate", "regal", "victorian", "heritage", 
                    "engraved", "floral", "carolina", "essex", "monte carlo", "retro"],
        "tone": "elegant, timeless, refined, luxurious",
        "keywords": ["traditional bathroom hardware", "classic bath accessories", "heritage bathroom fixtures"],
    },
    "modern": {
        "signals": ["modern", "contemporary", "minimalist", "sleek", "cube", "geometric",
                    "argo", "dayton", "fresno", "montero", "venus", "southbeach", "tribecca", "remi"],
        "tone": "crisp, clean, sophisticated, architectural",
        "keywords": ["modern bathroom hardware", "contemporary bath accessories", "minimalist bathroom fixtures"],
    },
    "transitional": {
        "signals": ["transitional", "blend", "versatile", "dottingham", "waverly", "mercury",
                    "que new", "continental", "soho", "washington square", "astor place"],
        "tone": "balanced, versatile, sophisticated, adaptable",
        "keywords": ["transitional bathroom hardware", "versatile bath accessories"],
    },
    "industrial": {
        "signals": ["industrial", "pipeline", "pipe", "exposed", "loft", "shadwell", "urban"],
        "tone": "bold, authentic, urban, raw",
        "keywords": ["industrial bathroom hardware", "pipe-style accessories", "loft bathroom fixtures"],
    },
    "coastal": {
        "signals": ["beach", "coastal", "nautical", "marine", "pacific", "sag harbor", "malibu"],
        "tone": "fresh, light, relaxed, breezy",
        "keywords": ["coastal bathroom accessories", "beach house hardware", "maritime bath fixtures"],
    },
    "designer": {
        "signals": ["designer", "statement", "sculptural", "gallery", "bolero", "foxtrot",
                    "mambo", "satellite", "tango", "prestige skyline"],
        "tone": "bold, artistic, distinctive, gallery-worthy",
        "keywords": ["designer bathroom hardware", "statement bath accessories", "sculptural fixtures"],
    },
}


def detect_design_style(parent_sku: ParentSKU, collection: Optional[CollectionContext] = None) -> DesignStyleContext:
    """Classify product into design style categories for tone guidance."""
    
    # If we have collection context, use its group for primary classification
    if collection and collection.group:
        group_to_style = {
            "Contemporary/Modern": "modern",
            "Traditional/Classic": "traditional",
            "Transitional": "transitional",
            "Contemporary Specialty": "designer",
        }
        style = group_to_style.get(collection.group, "transitional")
        
        # Check for subgroup overrides
        if collection.subgroup == "Industrial Modern":
            style = "industrial"
        elif collection.subgroup == "Coastal Modern":
            style = "coastal"
        elif collection.subgroup == "Designer Statement":
            style = "designer"
        
        config = _DESIGN_STYLE_PATTERNS.get(style, _DESIGN_STYLE_PATTERNS["transitional"])
        return DesignStyleContext(
            style=style,
            tone_guidance=config["tone"],
            style_keywords=config["keywords"],
        )
    
    # Fall back to text analysis
    text_to_analyze = " ".join([
        parent_sku.current_title or "",
        parent_sku.collection or "",
        parent_sku.style or "",
    ]).lower()
    
    for style, config in _DESIGN_STYLE_PATTERNS.items():
        if any(signal in text_to_analyze for signal in config["signals"]):
            return DesignStyleContext(
                style=style,
                tone_guidance=config["tone"],
                style_keywords=config["keywords"],
            )
    
    # Default to transitional (versatile)
    return DesignStyleContext(
        style="transitional",
        tone_guidance="refined, versatile, quality-focused",
        style_keywords=["designer bathroom hardware", "quality bath accessories"],
    )


# Functional feature patterns by category
# NOTE: "title_keyword" is what goes in titles (search terms people use)
#       "benefit" is what goes in descriptions (value propositions)
#       These are DIFFERENT - don't mix them!
_FUNCTIONAL_FEATURES = {
    # Grab bar specific
    "reeded_grip": {
        "signals": ["reeded", "textured grip", "grooved grip"],
        "title_keyword": "Reeded Grip",  # Search term
        "benefit": "textured grip surface provides secure hold even with wet hands",  # Description
        "keywords": ["reeded grab bar", "textured grip grab bar"],
        "categories": ["Grab Bars"],
    },
    "smooth_grip": {
        "signals": ["smooth"],
        "title_keyword": "Smooth",  # Search term (grip style)
        "benefit": "smooth finish for a sleek look that's easy to maintain",  # Description
        "keywords": ["smooth grab bar"],
        "categories": ["Grab Bars"],
    },
    "l_shaped": {
        "signals": ["90 deg", "90-degree", "l-shaped", "left hand", "right hand", "angled"],
        "title_keyword": "L-Shaped",
        "benefit": "L-shaped configuration provides corner or transition support",
        "keywords": ["L-shaped grab bar", "corner grab bar", "angled grab bar"],
        "categories": ["Grab Bars"],
    },
    "three_post": {
        "signals": ["3 post", "3-post", "three post"],
        "title_keyword": "3-Post",
        "benefit": "three-post mounting configuration for enhanced stability",
        "keywords": ["3-post grab bar"],
        "categories": ["Grab Bars"],
    },
    "cube_design": {
        "signals": ["cube design", "cube style", "cubic"],
        "title_keyword": "Cube Design",
        "benefit": "modern cube-style mounts with clean geometric lines",
        "keywords": ["cube design bathroom hardware", "geometric bathroom accessories"],
        "categories": None,  # Applies to all
    },
    
    # Towel bar specific
    "double_bar": {
        "signals": ["double", "dual bar"],
        "title_keyword": "Double",
        "benefit": "double bar design provides twice the towel hanging capacity",
        "keywords": ["double towel bar", "dual towel bar"],
        "categories": ["Towel Bars"],
    },
    "with_shelf": {
        "signals": ["with shelf", "shelf combo", "integrated shelf"],
        "title_keyword": "with Shelf",
        "benefit": "integrated shelf provides additional storage space",
        "keywords": ["towel bar with shelf"],
        "categories": ["Towel Bars", "Glass Shelves"],
    },
    "train_rack": {
        "signals": ["train rack", "hotel rack", "hotel style"],
        "title_keyword": "Train Rack",
        "benefit": "hotel-style train rack with integrated shelf",
        "keywords": ["train rack", "hotel towel rack"],
        "categories": ["Towel Bars"],
    },
    
    # Mirror specific
    "tilting": {
        "signals": ["tilt", "tilting", "pivot", "pivoting", "adjustable angle"],
        "title_keyword": "Tilting",
        "benefit": "tilt-adjustable angle for personalized viewing",
        "keywords": ["tilting mirror", "pivot mirror", "tilt vanity mirror"],
        "categories": ["Wall Mirrors", "Make-Up Mirrors"],
    },
    "magnifying": {
        "signals": ["magnif", "2x", "3x", "4x", "5x", "8x", "magnification"],
        "title_keyword": None,  # Use the specific magnification (3X, 5X) from product data instead
        "benefit": "magnification for detailed grooming and makeup application",
        "keywords": ["magnifying mirror", "magnifying makeup mirror"],
        "categories": ["Make-Up Mirrors"],
    },
    "extendable": {
        "signals": ["extendable", "extending", "swing arm", "articulating"],
        "title_keyword": "Swing Arm",
        "benefit": "extendable swing arm brings mirror closer when needed",
        "keywords": ["swing arm mirror", "extendable mirror"],
        "categories": ["Make-Up Mirrors"],
    },
    "lighted": {
        "signals": ["lighted", "led", "illuminated", "backlit"],
        "title_keyword": "Lighted",
        "benefit": "built-in lighting for optimal visibility",
        "keywords": ["lighted mirror", "LED vanity mirror"],
        "categories": ["Make-Up Mirrors", "Wall Mirrors"],
    },
    
    # Toilet paper holder specific
    "recessed": {
        "signals": ["recessed", "in-wall"],
        "title_keyword": "Recessed",
        "benefit": "recessed design creates a streamlined, built-in appearance",
        "keywords": ["recessed toilet paper holder"],
        "categories": ["Toilet Paper Holders"],
    },
    "spring_loaded": {
        "signals": ["spring", "euro", "european"],
        "title_keyword": "Euro Style",
        "benefit": "European spring-loaded roller for easy roll changes",
        "keywords": ["euro toilet paper holder", "european tissue holder"],
        "categories": ["Toilet Paper Holders"],
    },
    "covered": {
        "signals": ["covered", "hooded", "lid"],
        "title_keyword": "Covered",
        "benefit": "covered design protects tissue from moisture and dust",
        "keywords": ["covered toilet paper holder"],
        "categories": ["Toilet Paper Holders"],
    },
    "with_cover": {
        "signals": ["with cover"],
        "title_keyword": "with Cover",
        "benefit": "protective cover keeps tissue clean and dry",
        "keywords": ["toilet paper holder with cover"],
        "categories": ["Toilet Paper Holders"],
    },
    
    # Universal features - these are modifiers, not title openers
    "concealed_mount": {
        "signals": ["concealed", "hidden screw", "hidden mount"],
        "title_keyword": None,  # Don't use in title - too common
        "benefit": "concealed mounting hardware creates a clean, finished appearance",
        "keywords": [],  # Not a search term
        "categories": None,  # Applies to all
    },
    "ada_compliant": {
        "signals": ["ada", "accessible", "compliant"],
        "title_keyword": "ADA Compliant",  # This IS a search term
        "benefit": "ADA-compliant design meets accessibility requirements",
        "keywords": ["ADA grab bar", "ADA compliant grab bar"],
        "categories": ["Grab Bars"],
    },
    "wall_mount": {
        "signals": ["wall mount", "wall-mount", "wall mounted"],
        "title_keyword": "Wall Mount",  # Common search modifier
        "benefit": "wall-mounted installation saves floor space",
        "keywords": ["wall mount"],
        "categories": None,
    },
    "freestanding": {
        "signals": ["freestanding", "free-standing", "floor stand"],
        "title_keyword": "Freestanding",
        "benefit": "freestanding design requires no wall mounting",
        "keywords": ["freestanding"],
        "categories": None,
    },
}


def detect_functional_features(parent_sku: ParentSKU) -> list[FunctionalFeature]:
    """Identify unique functional features that differentiate the product."""
    text_to_analyze = " ".join([
        parent_sku.current_title or "",
        parent_sku.current_description or "",
        parent_sku.style or "",
        parent_sku.mounting_type or "",
    ]).lower()
    
    detected = []
    for feature_id, config in _FUNCTIONAL_FEATURES.items():
        # Check category applicability
        if config["categories"] and parent_sku.category not in config["categories"]:
            continue
        
        # Check signals
        if any(signal in text_to_analyze for signal in config["signals"]):
            detected.append(FunctionalFeature(
                feature_id=feature_id,
                title_keyword=config.get("title_keyword"),  # May be None
                benefit=config["benefit"],
                keywords=config.get("keywords", []),
            ))
    
    return detected


# Statement finishes that are distinctive/unusual
_STATEMENT_FINISHES = {
    "fire engine red": "bold statement color",
    "mediterranean blue": "distinctive coastal accent",
    "lavender": "soft contemporary accent",
    "pink": "playful modern accent",
    "glokzin teal": "unique designer color",
    "sea foam green": "fresh coastal tone",
    "golden yellow": "warm statement finish",
    "autumn sparkle": "rich seasonal accent",
    "spanish gold": "luxurious warm metallic",
    "unlacquered brass": "living finish that develops patina",
    "antique pewter": "vintage-inspired metallic",
    "venetian bronze": "rich Old World finish",
    "french gold": "refined European metallic",
    "tuscan brass": "warm Mediterranean tone",
}


def analyze_finish_variety(parent_sku: ParentSKU) -> FinishVarietyContext:
    """Quantify finish options and identify unusual/statement finishes."""
    finishes = [v.finish.lower() for v in parent_sku.variants if v.finish]
    unique_finishes = set(finishes)
    
    # Identify statement finishes
    statement = {}
    for finish in unique_finishes:
        for key, desc in _STATEMENT_FINISHES.items():
            if key in finish:
                statement[finish] = desc
                break
    
    # Determine variety level
    count = len(unique_finishes)
    if count >= 20:
        variety_level = "exceptional"
        variety_message = f"Available in {count} designer finishes"
    elif count >= 10:
        variety_level = "extensive"
        variety_message = f"Available in {count} finish options"
    elif count >= 5:
        variety_level = "good"
        variety_message = f"Available in {count} finishes"
    else:
        variety_level = "standard"
        variety_message = None
    
    # NOTE: finish_keywords intentionally left empty at parent level
    # Each variant should have keywords for its specific finish only
    finish_keywords = []
    
    return FinishVarietyContext(
        total_count=count,
        variety_level=variety_level,
        variety_message=variety_message,
        has_statement_finishes=bool(statement),
        statement_finishes=statement,
        finish_keywords=finish_keywords,
    )


def detect_competitive_positioning(
    parent_sku: ParentSKU,
    collection: Optional[CollectionContext],
    design_style: DesignStyleContext,
    features: list[FunctionalFeature],
    finish_variety: FinishVarietyContext,
) -> CompetitiveContext:
    """Determine product's competitive position and unique selling points."""
    
    unique_differentiators = []
    competitor_gap_keywords = []
    
    # Collection coordination
    if collection and collection.is_collection_member:
        unique_differentiators.append(
            f"Part of coordinated {collection.name} collection"
        )
        competitor_gap_keywords.extend(collection.coordination_keywords[:2])
    
    # Exceptional finish variety
    if finish_variety.variety_level in ("exceptional", "extensive"):
        unique_differentiators.append(
            f"{finish_variety.total_count} finish options including statement colors"
        )
    
    # Functional innovations
    for feature in features:
        if feature.feature_id in ("cube_design", "reeded_grip", "l_shaped", "three_post"):
            unique_differentiators.append(feature.benefit)
            competitor_gap_keywords.extend(feature.keywords[:2])
    
    # Safety + Design (grab bars)
    if parent_sku.category == "Grab Bars":
        has_ada = any(f.feature_id == "ada_compliant" for f in features)
        if has_ada and design_style.style != "industrial":
            unique_differentiators.append(
                "ADA-compliant safety meets designer aesthetics"
            )
            competitor_gap_keywords.append("designer ADA grab bar")
    
    # Designer statement pieces
    if design_style.style == "designer" or (collection and collection.subgroup == "Designer Statement"):
        unique_differentiators.append("Designer statement piece")
        competitor_gap_keywords.append("sculptural bathroom hardware")
    
    # Competitive edge statement
    if len(unique_differentiators) >= 3:
        edge = "high"
        edge_statement = "Unique combination of design variety, finish options, and function not found in competitors"
    elif len(unique_differentiators) >= 2:
        edge = "high"
        edge_statement = "Distinctive design and finish options set this apart from competitors"
    elif len(unique_differentiators) == 1:
        edge = "moderate"
        edge_statement = unique_differentiators[0]
    else:
        edge = "standard"
        edge_statement = "Quality solid brass construction with premium finishes"
    
    return CompetitiveContext(
        edge_level=edge,
        edge_statement=edge_statement,
        unique_differentiators=unique_differentiators,
        competitor_gap_keywords=competitor_gap_keywords,
    )


# =============================================================================
# Main Enrichment Function
# =============================================================================

def enrich_product(parent_sku: ParentSKU) -> ProductEnrichment:
    """Run all feature detectors and aggregate results.
    
    This is the main entry point for on-the-fly enrichment.
    
    Args:
        parent_sku: The parent SKU with all variants.
        
    Returns:
        ProductEnrichment with all detected features and context.
    """
    # Run detectors
    collection = detect_collection(parent_sku)
    design_style = detect_design_style(parent_sku, collection)
    features = detect_functional_features(parent_sku)
    finish_variety = analyze_finish_variety(parent_sku)
    competitive = detect_competitive_positioning(
        parent_sku, collection, design_style, features, finish_variety
    )
    
    # Aggregate keywords (prioritized order)
    design_intent_keywords = []
    
    # 1. Collection-specific keywords (highest priority)
    if collection:
        design_intent_keywords.extend(collection.coordination_keywords)
    
    # 2. Design style keywords
    design_intent_keywords.extend(design_style.style_keywords)
    
    # 3. Functional feature keywords
    for f in features:
        design_intent_keywords.extend(f.keywords)
    
    # 4. Competitor gap keywords (finish keywords excluded - variant-specific)
    design_intent_keywords.extend(competitive.competitor_gap_keywords)
    
    # Dedupe while preserving order
    seen = set()
    unique_keywords = []
    for kw in design_intent_keywords:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            unique_keywords.append(kw)
    
    # Aggregate differentiators (top 3)
    differentiators = competitive.unique_differentiators[:3]
    if not differentiators:
        differentiators = ["Solid brass construction", "Premium designer finishes"]
    
    # Build tone guidance
    tone_parts = [design_style.tone_guidance]
    if collection:
        tone_parts.append(collection.aesthetic)
    tone_guidance = "; ".join(tone_parts)
    
    return ProductEnrichment(
        collection=collection,
        design_style=design_style,
        functional_features=features,
        finish_variety=finish_variety,
        competitive=competitive,
        design_intent_keywords=unique_keywords,
        tone_guidance=tone_guidance,
        key_differentiators=differentiators,
    )
