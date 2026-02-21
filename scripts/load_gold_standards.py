#!/usr/bin/env python3
"""Load gold standard examples into prompt_templates and run batch evaluation.

Usage:
    # Load gold standards into Supabase (requires env vars):
    python scripts/load_gold_standards.py

    # Dry run (print what would be loaded, no DB writes):
    python scripts/load_gold_standards.py --dry-run

    # Evaluate recent generated content against the new rubric:
    python scripts/load_gold_standards.py --evaluate

    # Evaluate a specific SKU:
    python scripts/load_gold_standards.py --evaluate --sku WP-2/16-GAL

Environment:
    SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL
    SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Gold standard examples — copied verbatim from .claude/skills/google-shopping-content/SKILL.md
# ---------------------------------------------------------------------------

GOLD_STANDARD_EXAMPLES: list[dict[str, Any]] = [
    # 1. Paper Towel Holder — Skyline Collection (from google-shopping-content SKILL.md)
    {
        "index": 1,
        "category": "Paper Towel Holders",
        "master_sku": "1025U",
        "gold_standard_content": {
            "google_title": "Solid Brass Wall Mounted Paper Towel Holder - Skyline Collection Kitchen Hardware - Allied Brass",
            "google_short_title": "Solid Brass Wall Mounted Paper Towel Holder - Skyline",
            "google_description": (
                "Free up counter space and keep a full roll at tearing height — this wall-mounted paper towel holder "
                "is constructed of solid brass, not the hollow zinc tubing that loosens after a few months of "
                "one-handed pulls. {FINISH_SENTENCE} The 5-inch projection holds standard and jumbo rolls without "
                "crowding your backsplash, while concealed screw mounting keeps the wall clean with no visible "
                "hardware. Solid brass construction means this holder won't corrode, wobble, or need replacing — "
                "even mounted next to the sink where steam and splashes are constant. Part of the Skyline "
                "Collection, so it coordinates with matching towel bars, soap dishes, and hooks across 28 finishes "
                "for a kitchen or bathroom where every detail speaks the same design language. One of the "
                "most-searched categories in bathroom hardware — and the difference between solid brass and plated "
                "zinc is something you feel every time you tear off a sheet."
            ),
            "quality_score": 89,
            "why_it_works": (
                "Opens with a benefit scenario (counter space, tearing height) matching the #1 search intent. "
                "Differentiates immediately against zinc competitors with a tactile contrast. Naturally integrates: "
                "'wall mounted paper towel holder,' 'solid brass,' 'kitchen hardware.' {FINISH_SENTENCE} sits after "
                "the hook and before construction details."
            ),
        },
    },
    # 2. Freestanding Toilet Paper Holder — Carolina Crystal (from google-shopping-content SKILL.md)
    {
        "index": 2,
        "category": "Toilet Paper Holders",
        "master_sku": "CC-29",
        "gold_standard_content": {
            "google_title": "Freestanding Euro Style Toilet Paper Holder - Crystal Accents Solid Brass Stand - Carolina Crystal - Allied Brass",
            "google_short_title": "Freestanding Euro Style Solid Brass Toilet Paper Stand",
            "google_description": (
                "No drilling, no wall damage, and no compromising on style — this freestanding toilet paper holder "
                "stands on a weighted solid brass base that stays put on tile, marble, or hardwood without tipping. "
                "The European-style hook lets you swap rolls with one hand, while Carolina Crystal's signature "
                "crystal accents turn a purely functional fixture into a bathroom statement piece. {FINISH_SENTENCE} "
                "The heavy weighted base provides anti-tipping stability that cheap plastic stands can't match — "
                "solid brass construction means this holder won't corrode, crack, or wobble after years beside the "
                "toilet where humidity is highest. Ideal for renters who cannot drill walls, powder rooms where wall "
                "space is limited, or anyone who wants a unique freestanding toilet paper holder that guests "
                "actually notice. Coordinates with Carolina Crystal towel bars, soap dishes, and robe hooks in 28 "
                "finishes for a bathroom where every accessory shares the same crystal-accented design language."
            ),
            "quality_score": 90,
            "why_it_works": (
                "Opens with the three biggest objections to wall-mounted holders and resolves all three immediately. "
                "Euro-style hook is a genuine differentiator. Three distinct buyer scenarios (renters, powder rooms, "
                "design-conscious). 893 characters using the full budget."
            ),
        },
    },
    # 3. Decorative Reeded Grab Bar — Cube Design 18-Inch (from google-shopping-content SKILL.md)
    {
        "index": 3,
        "category": "Grab Bars",
        "master_sku": "CU-GRR-18",
        "gold_standard_content": {
            "google_title": "Decorative 18-Inch Reeded Solid Brass Grab Bar - ADA Compliant 250 lb Capacity - Cube Design Contemporary - Allied Brass",
            "google_short_title": "Decorative 18-Inch Reeded Solid Brass Grab Bar, ADA Compliant",
            "google_description": (
                "A grab bar that looks like it belongs in a contemporary renovation, not a hospital hallway — the "
                "Cube Design Reeded Grab Bar brings ADA-compliant safety to bathrooms without the institutional "
                "aesthetic that makes most grab bars an eyesore. The reeded texture provides secure grip even with "
                "wet or soapy hands, while solid brass construction supports 250 lb and resists the corrosion that "
                "destroys chrome-plated steel bars in wet shower environments. {FINISH_SENTENCE} The 18-inch length "
                "fits beside a shower entry, along a tub wall, or next to a toilet — mounting vertically, "
                "horizontally, or diagonally depending on where you need the grip most. Corrosion-free solid brass "
                "means this bar performs in the exact humid conditions that cause cheaper metals to pit and weaken. "
                "Whether you are outfitting an aging parent's bathroom or adding safety to your own shower, the "
                "Cube Design proves that ADA compliance and contemporary style belong in the same sentence. "
                "Coordinates with Cube Design accessories in 28 finishes."
            ),
            "quality_score": 92,
            "why_it_works": (
                "Opens by naming the core objection ('hospital hallway') and resolving it with contemporary aesthetic. "
                "'Decorative' in both title and description captures search terms current listings miss. Reeded "
                "texture as both design and function. Two buyer personas (aging parent, own shower). Highest-scoring "
                "example at 92/100."
            ),
        },
    },
    # 4. Cabinet Knob (from google-shopping-content SKILL.md)
    {
        "index": 4,
        "category": "Cabinet Hardware",
        "master_sku": "101",
        "gold_standard_content": {
            "google_title": "Solid Brass 1-1/2 Inch Round Cabinet Knob - 28 Designer Finishes - Kitchen and Bathroom Hardware - Allied Brass",
            "google_short_title": "Solid Brass 1-1/2 Inch Round Cabinet Knob",
            "google_description": (
                "You touch a cabinet knob dozens of times a day — this 1-1/2 inch solid brass knob has the weight "
                "and smooth action of quality hardware, not the hollow rattle of die-cast zinc that loosens in its "
                "socket after a year. {FINISH_SENTENCE} The round profile sits comfortably under your fingers and "
                "the standard mounting bolt fits most cabinet doors and drawer fronts without modification. Solid "
                "brass won't crack, corrode, or strip its threads the way plated zinc alternatives do — and at "
                "1-1/2 inches, it is sized for both bathroom vanity drawers and kitchen cabinetry. Available in 28 "
                "finishes, from Matte Black and Polished Chrome to Antique Copper and Satin Brass, so you can match "
                "your cabinet hardware to the bathroom fixtures or kitchen faucet you have already chosen. Swap out "
                "a roomful of knobs in an afternoon for a finish that ties the whole space together."
            ),
            "quality_score": 87,
            "why_it_works": (
                "The 'simple product' gold standard — demonstrates that even a basic cabinet knob can have "
                "compelling content. Sensory hook (you touch it dozens of times) elevates a commodity product. "
                "Differentiates on tactile quality (weight vs hollow rattle). Dual-room applicability "
                "(bathroom + kitchen)."
            ),
        },
    },
    # 5. Ceiling Hung Mirror (from google-shopping-content SKILL.md)
    {
        "index": 5,
        "category": "Mirrors",
        "master_sku": "CH-90",
        "gold_standard_content": {
            "google_title": "22-Inch Frameless Round Ceiling Hung Mirror - Beveled Edge Solid Brass Hardware - Adjustable Height - Allied Brass",
            "google_short_title": "22-Inch Frameless Round Ceiling Hung Mirror, Beveled Edge",
            "google_description": (
                "A mirror that floats from the ceiling and becomes the room's focal point — this 22-inch round "
                "frameless mirror hangs from solid brass hardware at an adjustable height, creating the kind of "
                "statement that wall-mounted mirrors simply cannot make. The beveled edge adds visual depth around "
                "the perimeter without the weight of a frame, and at 28 lb, this is real glass with genuine optical "
                "clarity, not a lightweight acrylic imitation. {FINISH_SENTENCE} The adjustable-length hardware "
                "adapts to different ceiling heights, making this mirror work in a primary bathroom vanity area, a "
                "dressing room, or a retail fitting room where overhead mounting keeps floor and wall space "
                "completely open. Solid brass mounting hardware carries the full 28 lb securely — engineered for "
                "the weight, not adapted from wall-mount brackets. The ceiling-hung design creates a dramatic "
                "floating effect that draws the eye and gives any room a sense of architectural intention that fixed "
                "wall mirrors cannot replicate. Available in 28 finishes to match existing fixtures."
            ),
            "quality_score": 91,
            "why_it_works": (
                "Opens with a visual image ('floats from the ceiling') that immediately communicates uniqueness. "
                "28 lb weight positioned as quality proof (real glass, not acrylic). Three specific spaces "
                "(bathroom, dressing room, retail). Addresses installation anxiety. 900 characters using the full "
                "budget."
            ),
        },
    },
    # 6. Height Adjustable Makeup Mirror 2X (from google-shopping-content SKILL.md)
    {
        "index": 6,
        "category": "Makeup Mirrors",
        "master_sku": "DM-1/2X",
        "gold_standard_content": {
            "google_title": "8-Inch 2X Magnifying Makeup Mirror - Height Adjustable 17-23 Inch Countertop - Solid Brass - Allied Brass",
            "google_short_title": "8-Inch 2X Magnifying Makeup Mirror, Height Adjustable",
            "google_description": (
                "See every detail at your own height — this 8-inch countertop makeup mirror adjusts from 17 to 23 "
                "inches, so it works whether you are sitting at a vanity, standing at a bathroom counter, or sharing "
                "the space with someone a foot taller. The 2X magnification provides clear, natural detail for "
                "daily makeup application and grooming without the distortion that higher magnifications create at "
                "normal viewing distance. {FINISH_SENTENCE} The solid brass construction gives this mirror real "
                "weight on the countertop — it stays where you position it instead of sliding or tipping when you "
                "lean in close. The pivoting head tilts to any angle, locking into position so you are not "
                "readjusting mid-application. Unlike lightweight mirrors with plastic gears that strip after months "
                "of daily tilting, the solid brass pivot mechanism maintains smooth, precise tension for the life "
                "of the mirror. Available in 28 finishes to coordinate with your faucet, towel bar, and other "
                "bathroom fixtures from any Allied Brass collection."
            ),
            "quality_score": 90,
            "why_it_works": (
                "Opens with the defining feature (height adjustability) framed as a personal benefit. Three use "
                "scenarios (sitting, standing, sharing). 2X magnification positioned as the practical daily-use "
                "choice vs higher magnification distortion. Pivot mechanism contrasted with plastic gears."
            ),
        },
    },
    # 7. Glass Shelf — Skyline Collection 18-Inch (from google-shopping-content SKILL.md)
    {
        "index": 7,
        "category": "Glass Shelves",
        "master_sku": "1033/18",
        "gold_standard_content": {
            "google_title": "18-Inch Tempered Glass Shelf with Solid Brass Wall Mount Brackets - Skyline Collection - Allied Brass",
            "google_short_title": "18-Inch Tempered Glass Shelf, Solid Brass Brackets",
            "google_description": (
                "Add bathroom storage without closing in a small room — this 18-inch tempered glass shelf holds "
                "your heaviest bottles and jars while keeping the visual openness that wire racks and wooden shelves "
                "block. The 1/4-inch thick tempered glass is stronger and safer than standard glass — if ever "
                "broken, it crumbles into small pieces instead of dangerous shards. {FINISH_SENTENCE} Solid brass "
                "wall-mount brackets carry the weight without the flex or corrosion you get from chrome-plated "
                "plastic brackets after a year of bathroom humidity. The Skyline Collection's clean contemporary "
                "lines mean these brackets complement the shelf rather than competing with it — and they coordinate "
                "with Skyline towel bars, robe hooks, and toilet paper holders for a bathroom where every piece of "
                "hardware shares the same design language. Glass shelves are the most-searched bathroom storage "
                "category after towel bars, and the combination of tempered glass with solid brass brackets is a "
                "quality level most competitors at this price point cannot match."
            ),
            "quality_score": 88,
            "why_it_works": (
                "Opens with the visual-openness benefit — the primary reason shoppers choose glass over wood/wire. "
                "Tempered glass safety (crumbles vs shards) addresses a real concern. Bracket material "
                "differentiation (solid brass vs chrome-plated plastic)."
            ),
        },
    },
    # 8. Multi Hook — Skyline Collection 2-Position (from google-shopping-content SKILL.md)
    {
        "index": 8,
        "category": "Multi Hooks",
        "master_sku": "1020-2",
        "gold_standard_content": {
            "google_title": "Solid Brass 2-Position Wall Hook - Robe, Towel, and Coat Hook - Skyline Collection - Allied Brass",
            "google_short_title": "Solid Brass 2-Position Multi Hook, Wall Mount",
            "google_description": (
                "Two hooks on a single mount — hang a robe and a towel, or a coat and a bag, without drilling "
                "twice. This Skyline Collection wall hook is constructed of solid brass, so each hook holds its "
                "shape under the daily weight of wet bath towels and heavy winter coats without bending or loosening "
                "the way die-cast zinc hooks do. {FINISH_SENTENCE} The compact 2-position design fits spaces where "
                "a hook strip looks cluttered and a single hook is not enough — behind a bathroom door, inside a "
                "closet, beside the shower, or in an entryway. Concealed screw mounting keeps the wall clean, with "
                "no visible hardware to interrupt the Skyline Collection's contemporary lines. Coordinates with "
                "Skyline towel bars, glass shelves, and toilet paper holders in 28 finishes for a bathroom, closet, "
                "or mudroom where every piece of hardware matches. Solid brass means these hooks carry real weight "
                "— the kind of hooks you grab without thinking and they never let you down."
            ),
            "quality_score": 88,
            "why_it_works": (
                "Opens with the core value proposition (two hooks, one mount, fewer holes). Naturally uses 'robe "
                "hook,' 'towel hook,' 'coat hook,' 'wall hook' — capturing multiple search intents. Four placement "
                "scenarios expand perceived use cases."
            ),
        },
    },
    # 9. Guest Towel Holder — Freestanding 2-Ring (from google-shopping-content SKILL.md)
    {
        "index": 9,
        "category": "Guest Towel Holders",
        "master_sku": "953",
        "gold_standard_content": {
            "google_title": "Freestanding 2-Ring Guest Towel Holder - Countertop Solid Brass Hand Towel Stand - Allied Brass",
            "google_short_title": "Freestanding 2-Ring Solid Brass Guest Towel Holder",
            "google_description": (
                "Display a hand towel and a guest towel side by side without mounting a single bracket — this "
                "countertop towel holder stands on a heavy weighted solid brass base that stays put on marble, "
                "granite, or quartz vanity tops without scratching or tipping. The two-ring design solves a problem "
                "single towel rings cannot: keeping an everyday hand towel and a decorative guest towel both "
                "accessible and beautifully presented. {FINISH_SENTENCE} Contemporary styling sets this holder "
                "apart from the traditional towel stands that dominate the category — clean lines and a sleek "
                "silhouette that suits modern and transitional bathrooms equally. The heavy weighted base means no "
                "wobble even on wet countertops, and the solid brass construction will not corrode beside the sink "
                "where water contact is constant. Ideal for powder rooms where wall space is limited, guest "
                "bathrooms where presentation matters, or rental homes where drilling walls is not an option. "
                "Available in 28 finishes to match your faucet and other bathroom hardware — from Polished Nickel "
                "to Matte Black to Satin Brass."
            ),
            "quality_score": 89,
            "why_it_works": (
                "Opens with dual-display benefit and no-drilling advantage. Two-ring design positioned as solving "
                "a real problem. Three buyer scenarios (powder rooms, guest bathrooms, rentals). Contemporary "
                "styling as a within-catalog differentiator. Specific finish names in closing."
            ),
        },
    },
    # 10. Corner Shower Basket (from google-shopping-content SKILL.md)
    {
        "index": 10,
        "category": "Shower Accessories",
        "master_sku": "BSK-10ST",
        "gold_standard_content": {
            "google_title": "Solid Brass Corner Shower Basket - Wall Mount Soap and Shampoo Caddy - Open Drain Design - Allied Brass",
            "google_short_title": "Solid Brass Corner Shower Basket, Wall Mount",
            "google_description": (
                "Reclaim dead corner space in your shower — this solid brass corner basket turns the unused angle "
                "between two walls into organized storage for soap, shampoo, and conditioner without taking up any "
                "wall or floor area. The open basket design lets water drain through so you never get the "
                "standing-water soap scum that collects in solid-bottom caddies. {FINISH_SENTENCE} Solid brass "
                "construction means this basket will not rust — the single biggest reason cheap chrome-plated steel "
                "and plastic shower caddies end up in the trash after one season. Wall-mounted with concealed "
                "hardware, this corner basket stays where you install it permanently. No suction cups that release "
                "at 3 AM, no adhesive strips that peel in steam, no tension poles that slip on wet tile. The "
                "corner-specific design maximizes shower real estate in small bathrooms and tiled showers where "
                "every inch of wall space counts. Available in 28 finishes to match your showerhead, faucet handle, "
                "and bathroom hardware — because even shower storage should look like it belongs in the room."
            ),
            "quality_score": 91,
            "why_it_works": (
                "Opens with spatial benefit (dead corner space). Open-drain design solves soap scum problem. Three "
                "competitor alternatives dismissed in one punchy sentence (suction cups, adhesive strips, tension "
                "poles) — strongest competitive differentiation in the set. 'Will not rust' addresses the #1 "
                "complaint in shower caddy reviews."
            ),
        },
    },
    # 11-15: Improved versions from quality-evaluation SKILL.md bad-to-good examples
    # 11. Towel Ring (from quality-evaluation SKILL.md Example 1 improved version)
    {
        "index": 11,
        "category": "Towel Rings",
        "master_sku": "1016",
        "gold_standard_content": {
            "google_title": "Solid Brass 6-Inch Towel Ring - Wall Mount Hand Towel Holder - Skyline Collection - Allied Brass",
            "google_short_title": "Solid Brass 6-Inch Towel Ring, Wall Mount",
            "google_description": (
                "Keep a fresh hand towel within arm's reach of the vanity without cluttering the counter — this "
                "6-inch solid brass towel ring projects just 1.5 inches from the wall, holding up to 10 lb while "
                "taking up almost no visual space. {FINISH_SENTENCE} Unlike die-cast zinc rings that corrode in "
                "humid bathrooms, solid brass keeps its finish and strength for the long haul, backed by a limited "
                "lifetime warranty. Part of the Skyline Collection, so it coordinates with towel bars, robe hooks, "
                "and tissue holders in the same finish across your bathroom."
            ),
            "quality_score": 78,
            "why_it_works": (
                "Opens with a use scenario (hand towel by the vanity). Leads with the compact size as a benefit, "
                "not a spec. Differentiates against zinc competitors naturally. Collection coordination framed as "
                "a practical benefit."
            ),
        },
    },
    # 12. Cabinet Knob (from quality-evaluation SKILL.md Example 2 improved version)
    {
        "index": 12,
        "category": "Cabinet Knobs",
        "master_sku": "102",
        "gold_standard_content": {
            "google_title": "Solid Brass 1-1/2 Inch Cabinet Knob - Round Profile Kitchen and Bathroom Hardware - Allied Brass",
            "google_short_title": "Solid Brass 1-1/2 Inch Round Cabinet Knob",
            "google_description": (
                "You notice a cabinet knob every time you open a drawer — this 1-1/2 inch solid brass knob has the "
                "weight and resistance of quality hardware, not the hollow rattle of plated zinc. {FINISH_SENTENCE} "
                "The round profile fits comfortably under your fingers with 2.25 inches of projection for a clean "
                "pull on cabinet doors and drawers. Single-bolt installation takes five minutes per knob, and the "
                "solid brass won't loosen over years of daily use the way lightweight alternatives do. Swap out a "
                "kitchen's worth of knobs in an afternoon for a finish that coordinates across your entire room."
            ),
            "quality_score": 75,
            "why_it_works": (
                "Opens with a sensory hook (you notice it every time). Differentiates on tactile quality (weight vs "
                "hollow rattle). Frames installation as easy weekend project. Practical coordination benefit."
            ),
        },
    },
    # 13. Robe Hook (from quality-evaluation SKILL.md Example 3 improved version)
    {
        "index": 13,
        "category": "Robe Hooks",
        "master_sku": "1020",
        "gold_standard_content": {
            "google_title": "Solid Brass Wall Robe Hook - Skyline Collection Bathroom and Closet Hook - Allied Brass",
            "google_short_title": "Solid Brass Wall Robe Hook, Skyline Collection",
            "google_description": (
                "Hang your robe where you'll actually reach for it — beside the shower, behind the bathroom door, "
                "or next to the vanity. {FINISH_SENTENCE} This Skyline Collection robe hook holds up to 2 lb on a "
                "compact 2.3-inch projection that won't crowd narrow spaces. Solid brass means the hook keeps its "
                "shape even with a heavy terry robe, and concealed screw mounting gives you a clean wall with no "
                "visible hardware. Coordinates with Skyline towel bars, tissue holders, and towel rings for a "
                "pulled-together bathroom. Lifetime warranty included."
            ),
            "quality_score": 76,
            "why_it_works": (
                "Opens with a use scenario (where you'd put it). Leads with the benefit of compact size. Weight "
                "capacity framed practically (heavy robe). Collection as coordination benefit."
            ),
        },
    },
    # 14. 3-Position Multi Hook (from quality-evaluation SKILL.md Example 4 improved version)
    {
        "index": 14,
        "category": "Multi Hooks 3-Position",
        "master_sku": "1020-3",
        "gold_standard_content": {
            "google_title": "Solid Brass 3-Position Multi Hook - Bathroom Robe and Towel Hook - Skyline Collection - Allied Brass",
            "google_short_title": "Solid Brass 3-Position Multi Hook, Wall Mount",
            "google_description": (
                "Three solid brass hooks on a single 3-inch mount — hang a robe, a towel, and a washcloth without "
                "drilling three separate holes. {FINISH_SENTENCE} The Skyline Collection multi hook works in the "
                "bathroom, but also doubles as a tie and belt organizer inside a closet door. At just 3 inches wide, "
                "it fits spaces where individual hooks won't — between a door frame and a light switch, beside the "
                "shower in a narrow bath, or on the back of a cabinet door. Concealed screws, solid brass that won't "
                "corrode, and a lifetime warranty. Coordinates with the full Skyline Collection lineup."
            ),
            "quality_score": 79,
            "why_it_works": (
                "Opens with the key value proposition (3 hooks, 1 mount, fewer holes). Dual-use framed concretely "
                "(closet door). Narrow-space benefit made vivid with real locations."
            ),
        },
    },
    # 15. Toilet Paper Holder (from quality-evaluation SKILL.md Example 5 improved version)
    {
        "index": 15,
        "category": "Toilet Paper Holders Wall Mount",
        "master_sku": "1024",
        "gold_standard_content": {
            "google_title": "Solid Brass Two-Post Toilet Paper Holder - Wall Mount - Skyline Collection - Allied Brass",
            "google_short_title": "Solid Brass Two-Post Toilet Paper Holder",
            "google_description": (
                "No more fumbling with a spring-loaded roller — this two-post toilet paper holder lets you swap "
                "rolls with one hand. {FINISH_SENTENCE} Solid brass construction means the posts stay rigid (no "
                "wobble after six months like plastic-core holders), and concealed screw mounting keeps the wall "
                "clean. Part of the Skyline Collection, so it matches your towel bar, robe hook, and shower "
                "accessories in the same finish. Wall-mounted to keep your bathroom surfaces clear. Lifetime "
                "warranty included."
            ),
            "quality_score": 77,
            "why_it_works": (
                "Opens with the product's actual UX advantage (no spring roller). Differentiates against "
                "plastic-core competitors. Practical one-hand scenario. Collection coordination as practical "
                "matching benefit."
            ),
        },
    },
]


# ---------------------------------------------------------------------------
# Category guidance (serialized from prompts.py _CATEGORY_GUIDANCE)
# ---------------------------------------------------------------------------

CATEGORY_GUIDANCE = {
    "niche_functional": {
        "categories": [
            "retractable",
            "garment rod",
            "cabinet pull",
            "cabinet knob",
            "squeegee",
            "door pull",
            "shower door",
        ],
        "guidance": (
            "CATEGORY NOTE: This is a niche/functional product. Shoppers searching "
            "for this product type already know what they want — focus on the concrete fit for this use case "
            "(material quality, dimensions, mounting system) rather than generic bathroom upgrade hooks. "
            "For Google/Bing: lead with exact product type and differentiating specs. "
            "For Shopify: open with the specific problem this product solves, not a generic bathroom hook."
        ),
    },
    "towel_storage": {
        "categories": [
            "towel bar",
            "towel ring",
            "towel holder",
            "towel stand",
            "towel valet",
            "towel shelf",
            "guest towel",
        ],
        "guidance": (
            "CATEGORY NOTE: High-competition category. Differentiate on construction "
            "(solid brass vs die-cast zinc), finish variety, and collection coordination. "
            "For Google/Bing: include towel bar/rack/holder synonyms and exact dimensions early. "
            "For Shopify: address the common frustration (flimsy bars, mismatched finishes) in opening."
        ),
    },
    "safety_ada": {
        "categories": ["grab bar", "ada"],
        "guidance": (
            "CATEGORY NOTE: Safety-critical product. Lead with functional assurance "
            "(weight capacity, ADA compliance, mounting security). Trust signals matter more than aesthetics. "
            "For Google/Bing: include 'ADA compliant', weight capacity, mounting type as primary attributes. "
            "For Shopify: open with safety/accessibility benefit, then mention that it doesn't sacrifice style."
        ),
    },
}


# ---------------------------------------------------------------------------
# Rubric weights (from quality_rubric.yaml)
# ---------------------------------------------------------------------------

RUBRIC_WEIGHTS = {
    "hook_quality": 0.15,
    "product_specificity": 0.15,
    "competitive_diff": 0.12,
    "keyword_integration": 0.10,
    "customer_scenario": 0.10,
    "emotional_resonance": 0.10,
    "factual_accuracy": 0.10,
    "platform_compliance": 0.08,
    "finish_integration": 0.05,
    "variety_score": 0.05,
}

RUBRIC_GRADE_THRESHOLDS = {
    "excellent": 95,
    "good": 85,
    "acceptable": 75,
    "needs_work": 60,
    "reject": 0,
}


def get_grade(score: float) -> str:
    """Return grade label for a weighted score."""
    if score >= RUBRIC_GRADE_THRESHOLDS["excellent"]:
        return "Excellent"
    elif score >= RUBRIC_GRADE_THRESHOLDS["good"]:
        return "Good"
    elif score >= RUBRIC_GRADE_THRESHOLDS["acceptable"]:
        return "Acceptable"
    elif score >= RUBRIC_GRADE_THRESHOLDS["needs_work"]:
        return "Needs Work"
    else:
        return "Reject"


def compute_weighted_score(scores: dict[str, int | float]) -> float:
    """Compute weighted score from criterion scores."""
    total = 0.0
    for criterion, weight in RUBRIC_WEIGHTS.items():
        criterion_score = scores.get(criterion, 0)
        total += criterion_score * weight * 10  # Convert to 0-100 scale
    return round(total, 1)


def get_supabase_client():
    """Get Supabase client using environment variables."""
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: supabase-py not installed. Run: pip install supabase")
        sys.exit(1)

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )

    if not url:
        print("ERROR: SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL not set")
        sys.exit(1)
    if not key:
        print("ERROR: SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, or NEXT_PUBLIC_SUPABASE_ANON_KEY not set")
        sys.exit(1)

    return create_client(url, key)


def build_template_payload() -> dict[str, Any]:
    """Build the prompt_templates row payload."""
    gold_standard_data = {
        "version": "3.0",
        "examples": GOLD_STANDARD_EXAMPLES,
    }

    return {
        "name": "feedops_v3",
        "version": 3,
        "is_active": True,
        "system_prompt": (
            "System prompt is code-owned in feedops.pipeline.prompts — "
            "this field is for rollback only"
        ),
        "gold_standard_examples": gold_standard_data,
        "category_guidance": CATEGORY_GUIDANCE,
        "description": (
            "v3.0 gold standards (Feb 2026): 15 examples across 10+ product categories. "
            "10-criterion quality rubric replaces 6-criterion self_score. "
            "All examples drawn from google-shopping-content and quality-evaluation skills."
        ),
        "created_by": "load_gold_standards.py",
    }


def print_dry_run_summary(payload: dict[str, Any]) -> None:
    """Print what would be loaded without writing to DB."""
    examples = payload["gold_standard_examples"]["examples"]
    categories = sorted({ex["category"] for ex in examples})
    avg_score = sum(
        ex["gold_standard_content"]["quality_score"] for ex in examples
    ) / len(examples)

    print("\n=== DRY RUN: Gold Standards that would be loaded ===\n")
    print(f"Template name: {payload['name']} (version {payload['version']})")
    print(f"Total examples: {len(examples)}")
    print(f"Categories covered ({len(categories)}): {', '.join(categories)}")
    print(f"Average quality score: {avg_score:.1f}/100")
    print()

    print("Examples:")
    for ex in examples:
        content = ex["gold_standard_content"]
        title = content.get("google_title", "")
        score = content.get("quality_score", 0)
        why = content.get("why_it_works", "")[:80]
        print(f"  {ex['index']:2d}. [{ex['category']}] SKU:{ex['master_sku']}")
        print(f"      Title: {title[:80]}")
        print(f"      Score: {score}/100  |  {why}...")
        print()

    print(f"Category guidance groups: {list(CATEGORY_GUIDANCE.keys())}")
    print()
    print("=== END DRY RUN ===")


def load_into_supabase(payload: dict[str, Any]) -> None:
    """Deactivate all active templates, then upsert the feedops_v3 template."""
    supabase = get_supabase_client()

    print("Deactivating existing active templates...")
    supabase.table("prompt_templates").update({"is_active": False}).eq(
        "is_active", True
    ).execute()

    print(f"Upserting template '{payload['name']}'...")
    # Use upsert on the name unique constraint
    result = (
        supabase.table("prompt_templates")
        .upsert(payload, on_conflict="name")
        .execute()
    )

    if result.data:
        print(f"SUCCESS: Template '{payload['name']}' loaded.")
        examples = payload["gold_standard_examples"]["examples"]
        categories = sorted({ex["category"] for ex in examples})
        avg_score = sum(
            ex["gold_standard_content"]["quality_score"] for ex in examples
        ) / len(examples)
        print(f"  Examples loaded: {len(examples)}")
        print(f"  Categories: {len(categories)} ({', '.join(categories)})")
        print(f"  Average score: {avg_score:.1f}/100")
    else:
        print("WARNING: Upsert returned no data. Check Supabase logs.")


def evaluate_recent_content(sku: str | None = None, limit: int = 10) -> None:
    """Query generated_content and score using the new 10-criterion rubric.

    Looks for quality_breakdown JSONB with self_score criteria.
    Falls back to quality_score numeric if breakdown not available.
    """
    supabase = get_supabase_client()

    print(f"\n=== Batch Evaluation (new 10-criterion rubric) ===")
    print(f"Rubric weights: {', '.join(f'{k}: {v*100:.0f}%' for k, v in RUBRIC_WEIGHTS.items())}\n")

    query = (
        supabase.table("generated_content")
        .select(
            "master_sku, platform, content_type, quality_score, quality_breakdown, "
            "candidate_content, generation_timestamp"
        )
        .not_.is_("candidate_content", "null")
        .order("generation_timestamp", desc=True)
    )

    if sku:
        query = query.eq("master_sku", sku)
    else:
        query = query.limit(limit)

    result = query.execute()

    if not result.data:
        print(f"No generated content found{f' for SKU {sku}' if sku else ''}.")
        return

    rows = result.data
    print(f"Found {len(rows)} content records.\n")

    # Table header
    header = f"{'SKU':<16} {'Platform':<10} {'Type':<14} {'OldScore':>9} {'NewScore':>9} {'Grade':<12} {'Top Criterion'}"
    print(header)
    print("-" * len(header))

    for row in rows:
        master_sku = row.get("master_sku", "?")
        platform = row.get("platform", "?")
        content_type = row.get("content_type", "?")
        old_score = row.get("quality_score")
        breakdown = row.get("quality_breakdown") or {}

        # Try to extract self_score from quality_breakdown
        self_score = breakdown.get("self_score") if isinstance(breakdown, dict) else None

        if self_score and isinstance(self_score, dict):
            # Check if it uses the new 10-criterion rubric
            new_criteria = set(RUBRIC_WEIGHTS.keys())
            score_criteria = set(self_score.keys())
            has_new_rubric = bool(new_criteria & score_criteria)

            if has_new_rubric:
                new_score = compute_weighted_score(self_score)
                grade = get_grade(new_score)
                # Find weakest criterion
                weakest = min(
                    ((c, self_score.get(c, 0)) for c in RUBRIC_WEIGHTS),
                    key=lambda x: x[1] * RUBRIC_WEIGHTS.get(x[0], 1),
                )
                top_criterion = f"weak: {weakest[0]} ({weakest[1]}/10)"
            else:
                # Old rubric — report only old score
                new_score = None
                grade = "N/A (old rubric)"
                top_criterion = f"old criteria: {list(score_criteria)[:3]}..."
        else:
            new_score = None
            grade = "No breakdown"
            top_criterion = "quality_breakdown missing"

        old_str = f"{old_score:.0f}" if old_score is not None else "N/A"
        new_str = f"{new_score:.1f}" if new_score is not None else "N/A"

        print(
            f"{master_sku:<16} {platform:<10} {content_type:<14} "
            f"{old_str:>9} {new_str:>9} {grade:<12} {top_criterion}"
        )

    print()
    print(
        "NOTE: 'NewScore' uses the 10-criterion rubric only when quality_breakdown contains "
        "new-rubric keys (hook_quality, product_specificity, etc.).\n"
        "Newly generated content with the updated pipeline will show new scores automatically."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load gold standard examples into prompt_templates and/or evaluate content."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be loaded without writing to Supabase",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Evaluate recent generated_content using the new 10-criterion rubric",
    )
    parser.add_argument(
        "--sku",
        type=str,
        default=None,
        help="Specific master_sku to evaluate (use with --evaluate)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent records to evaluate (default: 10)",
    )
    args = parser.parse_args()

    payload = build_template_payload()

    if args.dry_run:
        print_dry_run_summary(payload)
        return

    if args.evaluate:
        evaluate_recent_content(sku=args.sku, limit=args.limit)
        return

    # Default: load gold standards into Supabase
    load_into_supabase(payload)


if __name__ == "__main__":
    main()
