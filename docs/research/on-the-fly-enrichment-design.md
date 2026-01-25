# On-the-Fly Product Enrichment Design
## Dynamic Feature Detection for Allied Brass Content Generation

**Date:** January 24, 2026  
**Status:** Design Proposal  
**Author:** FeedOps Research Agent

---

## Overview

Allied Brass's competitive advantage lies in **design variety + functional innovation + finish options**. Generic product templates miss this differentiation. This document outlines an on-the-fly enrichment system that dynamically detects and surfaces product uniqueness during content generation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ON-THE-FLY ENRICHMENT PIPELINE                      │
│                                                                             │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────────────┐│
│  │             │    │                  │    │                             ││
│  │  Product    │───▶│   ENRICHMENT     │───▶│    ENRICHED EVIDENCE       ││
│  │  Catalog    │    │   ENGINE         │    │    + DESIGN CONTEXT        ││
│  │  (CSV)      │    │                  │    │                             ││
│  └─────────────┘    └──────────────────┘    └─────────────────────────────┘│
│                              │                             │                │
│                              ▼                             ▼                │
│                     ┌──────────────────┐          ┌───────────────────────┐│
│                     │  FEATURE         │          │  PROMPT INJECTION     ││
│                     │  DETECTORS       │          │                       ││
│                     │  • Collection    │          │  • Design signals     ││
│                     │  • Design Style  │          │  • Intent keywords    ││
│                     │  • Grip Type     │          │  • Competitive edge   ││
│                     │  • Configuration │          │  • Tone guidance      ││
│                     │  • Finish Count  │          │                       ││
│                     │  • Unique Features│         │                       ││
│                     └──────────────────┘          └───────────────────────┘│
│                                                                             │
│  OPTIONAL EXTERNAL ENRICHMENT (async, cached):                             │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────────────┐│
│  │ GA4 MCP     │    │ Google Ads MCP   │    │ Competitor Cache            ││
│  │ SKU perf    │    │ Search queries   │    │ (Apify, 24h TTL)           ││
│  └─────────────┘    └──────────────────┘    └─────────────────────────────┘│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Detectors

### 1. Collection Detector

**Purpose:** Identify if product belongs to a named design collection and surface collection-specific context.

**Input:** `parent_sku.collection` field + product title/description

**Detection Logic:**
```python
ALLIED_BRASS_COLLECTIONS = {
    "Waverly Place": {
        "aesthetic": "traditional elegance",
        "design_language": "classic curves with refined details",
        "coordination_keywords": ["waverly place collection", "matching waverly place"],
    },
    "Dottingham": {
        "aesthetic": "timeless sophistication",
        "design_language": "dotted accents with traditional base",
        "coordination_keywords": ["dottingham collection", "coordinating dottingham"],
    },
    "Pipeline": {
        "aesthetic": "industrial modern",
        "design_language": "clean lines with exposed pipe aesthetic",
        "coordination_keywords": ["pipeline collection", "industrial bathroom"],
    },
    "Monte Carlo": {
        "aesthetic": "luxury classic",
        "design_language": "ornate detailing with premium presence",
        "coordination_keywords": ["monte carlo collection", "luxury bathroom set"],
    },
    "Prestige Regal": {
        "aesthetic": "stately elegance",
        "design_language": "regal proportions with distinguished finish",
        "coordination_keywords": ["prestige regal collection", "elegant bathroom hardware"],
    },
    "Skyline": {
        "aesthetic": "contemporary minimalist",
        "design_language": "sleek geometric forms",
        "coordination_keywords": ["skyline collection", "modern bathroom accessories"],
    },
    "Soho": {
        "aesthetic": "urban modern",
        "design_language": "loft-inspired with artistic flair",
        "coordination_keywords": ["soho collection", "urban bathroom design"],
    },
    # ... 40+ collections
}

def detect_collection(parent_sku: ParentSKU) -> CollectionContext | None:
    collection_name = parent_sku.collection
    if not collection_name:
        return None
    
    # Fuzzy match against known collections
    for name, metadata in ALLIED_BRASS_COLLECTIONS.items():
        if name.lower() in collection_name.lower():
            return CollectionContext(
                name=name,
                aesthetic=metadata["aesthetic"],
                design_language=metadata["design_language"],
                coordination_keywords=metadata["coordination_keywords"],
                is_collection_member=True,
            )
    
    # Unknown collection - still flag as collection member
    return CollectionContext(
        name=collection_name,
        aesthetic="distinctive design",
        design_language="coordinated collection piece",
        coordination_keywords=[f"{collection_name.lower()} collection"],
        is_collection_member=True,
    )
```

**Output:**
```python
@dataclass
class CollectionContext:
    name: str
    aesthetic: str  # "traditional elegance", "industrial modern"
    design_language: str  # Description of design approach
    coordination_keywords: list[str]  # Keywords for collection-seekers
    is_collection_member: bool
```

---

### 2. Design Style Detector

**Purpose:** Classify product into design style categories for appropriate tone and keywords.

**Input:** Product title, collection, category, style field

**Detection Logic:**
```python
DESIGN_STYLE_PATTERNS = {
    "traditional": {
        "signals": ["traditional", "classic", "ornate", "regal", "victorian"],
        "tone": "timeless, refined, elegant",
        "keywords": ["traditional bathroom hardware", "classic bath accessories"],
    },
    "modern": {
        "signals": ["modern", "contemporary", "minimalist", "sleek", "cube"],
        "tone": "clean, sophisticated, streamlined",
        "keywords": ["modern bathroom accessories", "contemporary bath hardware"],
    },
    "transitional": {
        "signals": ["transitional", "blend", "versatile"],
        "tone": "balanced, adaptable, harmonious",
        "keywords": ["transitional bathroom hardware", "versatile bath accessories"],
    },
    "industrial": {
        "signals": ["industrial", "pipeline", "pipe", "exposed"],
        "tone": "bold, authentic, urban",
        "keywords": ["industrial bathroom hardware", "pipe-style accessories"],
    },
    "coastal": {
        "signals": ["beach", "coastal", "nautical", "marine"],
        "tone": "fresh, relaxed, breezy",
        "keywords": ["coastal bathroom accessories", "beach house hardware"],
    },
}

def detect_design_style(parent_sku: ParentSKU) -> DesignStyleContext:
    text_to_analyze = " ".join([
        parent_sku.current_title or "",
        parent_sku.collection or "",
        parent_sku.style or "",
    ]).lower()
    
    for style, config in DESIGN_STYLE_PATTERNS.items():
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
```

**Output:**
```python
@dataclass
class DesignStyleContext:
    style: str  # "traditional", "modern", "industrial"
    tone_guidance: str  # Adjectives for copy tone
    style_keywords: list[str]  # Style-specific search terms
```

---

### 3. Functional Feature Detector

**Purpose:** Identify unique functional features that differentiate the product.

**Input:** Product title, description, category, specific fields

**Detection Logic:**
```python
FUNCTIONAL_FEATURES = {
    # Grab bar specific
    "reeded_grip": {
        "signals": ["reeded", "textured grip", "grooved"],
        "benefit": "enhanced grip texture for wet hands",
        "keywords": ["reeded grab bar", "textured grip safety bar"],
        "categories": ["Grab Bars"],
    },
    "smooth_grip": {
        "signals": ["smooth"],
        "benefit": "sleek smooth surface that's easy to clean",
        "keywords": ["smooth grab bar", "easy-clean safety bar"],
        "categories": ["Grab Bars"],
    },
    "l_shaped": {
        "signals": ["90 deg", "90-degree", "l-shaped", "left hand", "right hand", "angled"],
        "benefit": "L-shaped configuration for corner or transition support",
        "keywords": ["L-shaped grab bar", "corner grab bar", "angled safety bar"],
        "categories": ["Grab Bars"],
    },
    "three_post": {
        "signals": ["3 post", "3-post", "three post"],
        "benefit": "three-post mounting for maximum stability",
        "keywords": ["3-post grab bar", "heavy-duty grab bar"],
        "categories": ["Grab Bars"],
    },
    "cube_design": {
        "signals": ["cube design", "cube style"],
        "benefit": "modern cube-style mounts with clean geometric lines",
        "keywords": ["cube design bathroom hardware", "geometric bathroom accessories"],
        "categories": ["Grab Bars", "Towel Bars", "Toilet Paper Holders"],
    },
    
    # Towel bar specific
    "double_bar": {
        "signals": ["double", "dual"],
        "benefit": "double bar design for twice the hanging capacity",
        "keywords": ["double towel bar", "dual towel rack"],
        "categories": ["Towel Bars"],
    },
    "with_shelf": {
        "signals": ["with shelf", "shelf combo", "integrated shelf"],
        "benefit": "integrated shelf for additional storage",
        "keywords": ["towel bar with shelf", "combination towel rack"],
        "categories": ["Towel Bars", "Glass Shelves"],
    },
    
    # Mirror specific
    "tilting": {
        "signals": ["tilt", "tilting", "pivot", "pivoting", "adjustable angle"],
        "benefit": "tilt-adjustable for personalized viewing angles",
        "keywords": ["tilting mirror", "pivot mirror", "adjustable bathroom mirror"],
        "categories": ["Wall Mirrors", "Make-Up Mirrors"],
    },
    "magnifying": {
        "signals": ["magnif", "3x", "5x", "8x", "magnification"],
        "benefit": "magnification for detailed grooming tasks",
        "keywords": ["magnifying mirror", "makeup mirror with magnification"],
        "categories": ["Make-Up Mirrors"],
    },
    "extendable": {
        "signals": ["extendable", "extending", "swing arm", "articulating"],
        "benefit": "extendable arm brings mirror to you",
        "keywords": ["extendable makeup mirror", "swing arm mirror"],
        "categories": ["Make-Up Mirrors"],
    },
    
    # Toilet paper holder specific
    "recessed": {
        "signals": ["recessed", "in-wall"],
        "benefit": "recessed design for a streamlined built-in look",
        "keywords": ["recessed toilet paper holder", "in-wall tissue holder"],
        "categories": ["Toilet Paper Holders"],
    },
    "spring_loaded": {
        "signals": ["spring", "euro", "european"],
        "benefit": "spring-loaded roller for easy roll changes",
        "keywords": ["spring loaded toilet paper holder", "european style holder"],
        "categories": ["Toilet Paper Holders"],
    },
    "covered": {
        "signals": ["covered", "hooded", "lid"],
        "benefit": "covered design protects tissue from moisture",
        "keywords": ["covered toilet paper holder", "hooded tissue holder"],
        "categories": ["Toilet Paper Holders"],
    },
    
    # Universal features
    "concealed_mount": {
        "signals": ["concealed", "hidden screw", "hidden mount"],
        "benefit": "concealed mounting hardware for a clean, finished appearance",
        "keywords": ["concealed mount", "hidden screw bathroom hardware"],
        "categories": None,  # Applies to all
    },
    "ada_compliant": {
        "signals": ["ada", "accessible", "compliant"],
        "benefit": "ADA-compliant design meets accessibility standards",
        "keywords": ["ADA compliant", "accessible bathroom hardware"],
        "categories": ["Grab Bars"],
    },
}

def detect_functional_features(parent_sku: ParentSKU) -> list[FunctionalFeature]:
    text_to_analyze = " ".join([
        parent_sku.current_title or "",
        parent_sku.current_description or "",
        parent_sku.style or "",
    ]).lower()
    
    detected = []
    for feature_id, config in FUNCTIONAL_FEATURES.items():
        # Check category applicability
        if config["categories"] and parent_sku.category not in config["categories"]:
            continue
        
        # Check signals
        if any(signal in text_to_analyze for signal in config["signals"]):
            detected.append(FunctionalFeature(
                feature_id=feature_id,
                benefit=config["benefit"],
                keywords=config["keywords"],
            ))
    
    return detected
```

**Output:**
```python
@dataclass
class FunctionalFeature:
    feature_id: str  # "reeded_grip", "cube_design"
    benefit: str  # Benefit statement
    keywords: list[str]  # Feature-specific keywords
```

---

### 4. Finish Variety Analyzer

**Purpose:** Quantify finish options and identify unusual/statement finishes.

**Input:** `parent_sku.variants` finish values

**Detection Logic:**
```python
STANDARD_FINISHES = {
    "polished chrome", "brushed nickel", "satin nickel", 
    "oil rubbed bronze", "polished brass", "matte black",
}

STATEMENT_FINISHES = {
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
}

def analyze_finish_variety(parent_sku: ParentSKU) -> FinishVarietyContext:
    finishes = [v.finish.lower() for v in parent_sku.variants if v.finish]
    unique_finishes = set(finishes)
    
    # Categorize finishes
    standard = [f for f in unique_finishes if any(s in f for s in STANDARD_FINISHES)]
    statement = {f: STATEMENT_FINISHES[f] for f in unique_finishes if f in STATEMENT_FINISHES}
    
    # Determine variety level
    if len(unique_finishes) >= 20:
        variety_level = "exceptional"
        variety_message = f"Available in {len(unique_finishes)} designer finishes"
    elif len(unique_finishes) >= 10:
        variety_level = "extensive"
        variety_message = f"Available in {len(unique_finishes)} finish options"
    elif len(unique_finishes) >= 5:
        variety_level = "good"
        variety_message = f"Available in {len(unique_finishes)} finishes"
    else:
        variety_level = "standard"
        variety_message = None
    
    return FinishVarietyContext(
        total_count=len(unique_finishes),
        variety_level=variety_level,
        variety_message=variety_message,
        has_statement_finishes=bool(statement),
        statement_finishes=statement,
        finish_keywords=_generate_finish_keywords(unique_finishes),
    )

def _generate_finish_keywords(finishes: set[str]) -> list[str]:
    """Generate finish-specific keywords for high-intent searches."""
    keywords = []
    for finish in finishes:
        if finish in STATEMENT_FINISHES:
            # Statement finishes are search terms
            keywords.append(f"{finish} bathroom hardware")
            keywords.append(f"{finish} bath accessories")
    return keywords
```

**Output:**
```python
@dataclass
class FinishVarietyContext:
    total_count: int
    variety_level: str  # "exceptional", "extensive", "good", "standard"
    variety_message: str | None  # "Available in 26 designer finishes"
    has_statement_finishes: bool
    statement_finishes: dict[str, str]  # {"fire engine red": "bold statement color"}
    finish_keywords: list[str]  # Finish-specific search terms
```

---

### 5. Competitive Positioning Detector

**Purpose:** Determine product's competitive position and unique selling points.

**Input:** All detected features + category

**Detection Logic:**
```python
def detect_competitive_positioning(
    parent_sku: ParentSKU,
    collection: CollectionContext | None,
    design_style: DesignStyleContext,
    features: list[FunctionalFeature],
    finish_variety: FinishVarietyContext,
) -> CompetitiveContext:
    
    unique_differentiators = []
    
    # Collection coordination
    if collection and collection.is_collection_member:
        unique_differentiators.append(
            f"Part of coordinated {collection.name} collection"
        )
    
    # Exceptional finish variety
    if finish_variety.variety_level in ("exceptional", "extensive"):
        unique_differentiators.append(
            f"{finish_variety.total_count} finish options including statement colors"
        )
    
    # Functional innovations
    for feature in features:
        if feature.feature_id in ("cube_design", "reeded_grip", "l_shaped"):
            unique_differentiators.append(feature.benefit)
    
    # Safety + Design (grab bars)
    if parent_sku.category == "Grab Bars":
        has_ada = any(f.feature_id == "ada_compliant" for f in features)
        if has_ada and design_style.style != "industrial":
            unique_differentiators.append(
                "ADA-compliant safety meets designer aesthetics"
            )
    
    # Competitive edge statement
    if len(unique_differentiators) >= 2:
        edge = "high"
        edge_statement = "Unique combination of design and function not found in competitors"
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
        competitor_gap_keywords=_generate_gap_keywords(features, finish_variety),
    )

def _generate_gap_keywords(features, finish_variety) -> list[str]:
    """Keywords competitors likely don't target."""
    gap_keywords = []
    
    # Feature-specific gaps
    for f in features:
        if f.feature_id == "reeded_grip":
            gap_keywords.append("reeded grab bar")
        if f.feature_id == "cube_design":
            gap_keywords.append("cube design bathroom")
    
    # Statement finish gaps
    if finish_variety.has_statement_finishes:
        for finish in finish_variety.statement_finishes:
            gap_keywords.append(f"{finish} bathroom hardware")
    
    return gap_keywords
```

**Output:**
```python
@dataclass
class CompetitiveContext:
    edge_level: str  # "high", "moderate", "standard"
    edge_statement: str  # Summary of competitive advantage
    unique_differentiators: list[str]  # List of unique features
    competitor_gap_keywords: list[str]  # Keywords competitors don't target
```

---

## Enrichment Output Schema

The complete enrichment output that gets injected into the prompt:

```python
@dataclass
class ProductEnrichment:
    """Complete on-the-fly enrichment for a product."""
    
    # Core detections
    collection: CollectionContext | None
    design_style: DesignStyleContext
    functional_features: list[FunctionalFeature]
    finish_variety: FinishVarietyContext
    competitive: CompetitiveContext
    
    # Aggregated outputs for prompt
    design_intent_keywords: list[str]  # All design-related keywords
    tone_guidance: str  # How to write about this product
    key_differentiators: list[str]  # Top 3 unique selling points
    
    def to_evidence_rows(self) -> list[Evidence]:
        """Convert enrichment to evidence table rows."""
        rows = []
        
        if self.collection:
            rows.append(Evidence(
                field="collection_context",
                value=f"{self.collection.name} - {self.collection.aesthetic}",
                source="enrichment_collection",
            ))
        
        rows.append(Evidence(
            field="design_style",
            value=f"{self.design_style.style} ({self.design_style.tone_guidance})",
            source="enrichment_style",
        ))
        
        if self.functional_features:
            features_str = "; ".join(f.benefit for f in self.functional_features)
            rows.append(Evidence(
                field="functional_features",
                value=features_str,
                source="enrichment_features",
            ))
        
        if self.finish_variety.variety_message:
            rows.append(Evidence(
                field="finish_variety",
                value=self.finish_variety.variety_message,
                source="enrichment_finishes",
            ))
        
        if self.competitive.edge_level in ("high", "moderate"):
            rows.append(Evidence(
                field="competitive_edge",
                value=self.competitive.edge_statement,
                source="enrichment_competitive",
            ))
        
        if self.design_intent_keywords:
            rows.append(Evidence(
                field="design_intent_keywords",
                value=", ".join(self.design_intent_keywords[:10]),
                source="enrichment_keywords",
            ))
        
        return rows
```

---

## Integration with Existing Pipeline

### Modified `evidence.py`

```python
# Add to build_evidence_table()

from feedops.pipeline.enrichment import enrich_product

def build_evidence_table(parent_sku: ParentSKU) -> list[Evidence]:
    evidence = []
    
    # ... existing field extraction ...
    
    # NEW: On-the-fly enrichment
    enrichment = enrich_product(parent_sku)
    evidence.extend(enrichment.to_evidence_rows())
    
    # ... rest of existing code ...
    
    return evidence
```

### New `enrichment.py` Module

```python
"""On-the-fly product enrichment for design-intent detection."""

from feedops.models import ParentSKU
from feedops.pipeline.enrichment.detectors import (
    detect_collection,
    detect_design_style,
    detect_functional_features,
    analyze_finish_variety,
    detect_competitive_positioning,
)

def enrich_product(parent_sku: ParentSKU) -> ProductEnrichment:
    """Run all feature detectors and aggregate results."""
    
    # Run detectors
    collection = detect_collection(parent_sku)
    design_style = detect_design_style(parent_sku)
    features = detect_functional_features(parent_sku)
    finish_variety = analyze_finish_variety(parent_sku)
    competitive = detect_competitive_positioning(
        parent_sku, collection, design_style, features, finish_variety
    )
    
    # Aggregate keywords
    design_intent_keywords = []
    if collection:
        design_intent_keywords.extend(collection.coordination_keywords)
    design_intent_keywords.extend(design_style.style_keywords)
    for f in features:
        design_intent_keywords.extend(f.keywords)
    design_intent_keywords.extend(finish_variety.finish_keywords)
    design_intent_keywords.extend(competitive.competitor_gap_keywords)
    
    # Dedupe while preserving order
    seen = set()
    unique_keywords = []
    for kw in design_intent_keywords:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            unique_keywords.append(kw)
    
    # Aggregate differentiators (top 3)
    differentiators = competitive.unique_differentiators[:3]
    if not differentiators:
        differentiators = ["Solid brass construction", "Premium designer finishes"]
    
    return ProductEnrichment(
        collection=collection,
        design_style=design_style,
        functional_features=features,
        finish_variety=finish_variety,
        competitive=competitive,
        design_intent_keywords=unique_keywords,
        tone_guidance=design_style.tone_guidance,
        key_differentiators=differentiators,
    )
```

---

## Modified Prompt Template

Add a new section to the prompt that leverages enrichment:

```python
ENRICHMENT_PROMPT_SECTION = """
## Design Context (dynamically detected)

{enrichment_context}

Use this design context to:
1. **Tone**: Match the {design_style} aesthetic in word choice
2. **Keywords**: Prioritize design-intent keywords in first 70 characters when relevant
3. **Differentiators**: Highlight unique features that competitors don't offer
4. **Collection**: If part of a collection, mention coordination potential for buyers matching hardware

Do NOT invent features. Only use design context that maps to actual product evidence.
"""
```

---

## Example: Enrichment in Action

**Product:** DT-GRR-16 (Dottingham Collection Reeded Grab Bar - 16 inch)

### Raw Catalog Data:
```
MasterSKU: DT-GRR-16
Category: Grab Bars
Collection: Dottingham
Title: Dottingham Collection Reeded Grab Bar
Material: Solid Brass
Variants: 26 finishes
```

### Enrichment Output:
```python
ProductEnrichment(
    collection=CollectionContext(
        name="Dottingham",
        aesthetic="timeless sophistication",
        design_language="dotted accents with traditional base",
        coordination_keywords=["dottingham collection", "coordinating dottingham"],
        is_collection_member=True,
    ),
    design_style=DesignStyleContext(
        style="traditional",
        tone_guidance="timeless, refined, elegant",
        style_keywords=["traditional bathroom hardware", "classic bath accessories"],
    ),
    functional_features=[
        FunctionalFeature(
            feature_id="reeded_grip",
            benefit="enhanced grip texture for wet hands",
            keywords=["reeded grab bar", "textured grip safety bar"],
        ),
    ],
    finish_variety=FinishVarietyContext(
        total_count=26,
        variety_level="exceptional",
        variety_message="Available in 26 designer finishes",
        has_statement_finishes=True,
        statement_finishes={"fire engine red": "bold statement color", ...},
        finish_keywords=["fire engine red bathroom hardware", ...],
    ),
    competitive=CompetitiveContext(
        edge_level="high",
        edge_statement="Unique combination of design and function not found in competitors",
        unique_differentiators=[
            "Part of coordinated Dottingham collection",
            "26 finish options including statement colors",
            "enhanced grip texture for wet hands",
        ],
        competitor_gap_keywords=["reeded grab bar", "dottingham collection"],
    ),
    design_intent_keywords=[
        "dottingham collection",
        "coordinating dottingham",
        "traditional bathroom hardware",
        "reeded grab bar",
        "textured grip safety bar",
        "fire engine red bathroom hardware",
    ],
    tone_guidance="timeless, refined, elegant",
    key_differentiators=[
        "Part of coordinated Dottingham collection",
        "26 finish options including statement colors", 
        "enhanced grip texture for wet hands",
    ],
)
```

### Evidence Table Additions:
```
| collection_context      | Dottingham - timeless sophistication              | enrichment_collection |
| design_style            | traditional (timeless, refined, elegant)           | enrichment_style      |
| functional_features     | enhanced grip texture for wet hands                | enrichment_features   |
| finish_variety          | Available in 26 designer finishes                  | enrichment_finishes   |
| competitive_edge        | Unique combination of design and function...       | enrichment_competitive|
| design_intent_keywords  | dottingham collection, reeded grab bar, ...        | enrichment_keywords   |
```

### Generated Title (with enrichment):
```
Reeded Grip 16-Inch Grab Bar | Dottingham Collection | Solid Brass | Allied Brass
```
vs. without enrichment:
```
16-Inch Grab Bar Solid Brass | Polished Chrome | Allied Brass
```

---

## Performance Considerations

| Operation | Expected Latency | Caching Strategy |
|-----------|------------------|------------------|
| Collection detection | <1ms | Pre-loaded dictionary |
| Design style detection | <1ms | Pattern matching |
| Functional feature detection | <5ms | Pattern matching |
| Finish variety analysis | <5ms | Computed from variants |
| Competitive positioning | <1ms | Aggregation only |
| **Total enrichment** | **<15ms** | No external calls |

### Optional External Enrichment (async)

| Operation | Expected Latency | Caching Strategy |
|-----------|------------------|------------------|
| GA4 SKU performance | 500-2000ms | 24h cache per SKU |
| Google Ads search queries | 1000-3000ms | 24h cache per category |
| Competitor scraping | 10-30s | 24h cache, batch prefetch |

---

## Implementation Priority

### Phase 1: Core Enrichment (Immediate)
- [ ] Collection detector with 40+ collection metadata
- [ ] Design style detector
- [ ] Functional feature detector
- [ ] Finish variety analyzer
- [ ] Integration with evidence.py

### Phase 2: Competitive Context (Next)
- [ ] Competitive positioning detector
- [ ] Competitor gap keyword generation
- [ ] Prompt template updates

### Phase 3: External Enrichment (Later)
- [ ] GA4 performance integration (async)
- [ ] Google Ads query integration (async)
- [ ] Caching layer for external data

---

## Next Steps

1. **You:** Finalize collection descriptions (provides metadata for collection detector)
2. **Me:** Implement Phase 1 enrichment module once collection data is ready
3. **Test:** Run enrichment on eval-skus to validate detection accuracy
4. **Iterate:** Refine patterns based on edge cases

---

*Design document prepared for Allied FeedOps*  
*Ready for implementation upon collection description completion*
