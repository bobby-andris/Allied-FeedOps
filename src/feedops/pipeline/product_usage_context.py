"""Product usage context database for customer-focused image generation.

This module defines how customers actually use Allied Brass products, enabling
lifestyle images that demonstrate real-world usage patterns and value propositions.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProductUsageContext:
    """Defines how customers actually use this product.

    This context transforms generic product photography into customer-focused
    lifestyle images that answer: "How will I use this? What problem does it solve?"
    """

    # Core purpose
    primary_use_case: str
    """What customers primarily use this product for"""

    customer_problem_solved: str
    """The specific problem this product solves"""

    target_room: str
    """Primary room where product is used: kitchen, bathroom, guest bathroom, shower"""

    # Capacity and items
    typical_items: list[str]
    """List of items typically shown with this product"""

    capacity_min: int
    """Minimum number of items to show (demonstrates capacity)"""

    capacity_max: int
    """Maximum number of items to show"""

    capacity_description: str
    """Description of storage capacity for prompts"""

    # Scene requirements
    scene_type: str
    """Type of scene: 'in-use', 'staged', or 'lifestyle'"""

    required_context_items: list[str]
    """Items that must be visible in scene to show proper context"""

    customer_persona: str
    """Who uses this product (helps generate relatable scenes)"""

    # Value proposition
    unique_value: str
    """What makes this product special/valuable"""

    competitive_advantage: str
    """Why customer should choose this vs. alternatives"""


# Product Usage Database
PRODUCT_USAGE_DATABASE = {
    "paper towel holder countertop": ProductUsageContext(
        primary_use_case="Kitchen cleanup during cooking and food preparation",
        customer_problem_solved="Need quick, one-handed access to paper towels while hands are messy from cooking",
        target_room="kitchen",
        typical_items=["paper towel roll on holder"],
        capacity_min=1,
        capacity_max=1,
        capacity_description="Single roll ready for instant one-handed access",
        scene_type="in-use",
        required_context_items=[
            "kitchen counter with cooking activity",
            "cutting board with vegetables or ingredients",
            "sink visible in background",
            "stove or cooking area nearby"
        ],
        customer_persona="home cook preparing meals, parent cooking dinner",
        unique_value="Freestanding countertop placement for flexibility, weighted base prevents tipping during use",
        competitive_advantage="Countertop model allows placement exactly where needed, moves easily between prep areas"
    ),

    "paper towel holder under cabinet": ProductUsageContext(
        primary_use_case="Kitchen cleanup with space-saving under-cabinet mounting",
        customer_problem_solved="Need paper towels accessible but don't want to use counter space",
        target_room="kitchen",
        typical_items=["paper towel roll dispensing downward"],
        capacity_min=1,
        capacity_max=1,
        capacity_description="Under-cabinet mount saves valuable counter space",
        scene_type="in-use",
        required_context_items=[
            "kitchen cabinet above",
            "counter below with workspace visible",
            "sink area or prep zone",
            "paper towel at easy reach height (24-26 inches from counter)"
        ],
        customer_persona="home cook maximizing kitchen workspace",
        unique_value="Saves counter space while keeping paper towels within arm's reach",
        competitive_advantage="Wall-mount eliminates counter clutter, permanent placement near sink"
    ),

    "towel bar single": ProductUsageContext(
        primary_use_case="Bath towel storage for individual or couple",
        customer_problem_solved="Need convenient place to hang bath towel after shower",
        target_room="bathroom",
        typical_items=["single large bath towel (27x54 inches)"],
        capacity_min=1,
        capacity_max=2,
        capacity_description="Holds 1-2 full-size bath towels",
        scene_type="lifestyle",
        required_context_items=[
            "bathroom wall outside shower",
            "towel in neutral color (white, gray, taupe)",
            "towel showing natural drape",
            "shower door or enclosure partially visible"
        ],
        customer_persona="individual or couple using master bathroom",
        unique_value="Classic single-bar design for everyday bath towel storage",
        competitive_advantage="Simple, functional towel hanging at comfortable height"
    ),

    "towel bar four tier": ProductUsageContext(
        primary_use_case="Multi-person towel storage for families or guest bathrooms",
        customer_problem_solved="Not enough towel bar space for all family members - towels piling up or falling",
        target_room="guest bathroom, kids bathroom, family bathroom",
        typical_items=[
            "Dad's navy blue bath towel (top bar)",
            "Mom's white bath towel (second bar)",
            "Child's colorful character towel (third bar)",
            "Guest hand towels or washcloths (bottom bar)"
        ],
        capacity_min=4,
        capacity_max=5,
        capacity_description="4-5 full-size towels, one per family member - everyone has their own designated space",
        scene_type="lifestyle",
        required_context_items=[
            "family bathroom context",
            "multiple towels in different colors showing family use",
            "toothbrush holder or personal care items visible",
            "all four bars showing towels (demonstrating full capacity)"
        ],
        customer_persona="family of 4+ needing organized towel storage, or host with frequent guests",
        unique_value="Vertical ladder design provides 4x storage in same wall space as single bar",
        competitive_advantage="Solves the 'not enough towel space' problem - each person gets their own bar"
    ),

    "corner shelf three tier": ProductUsageContext(
        primary_use_case="Shower and bath product organization in corner space",
        customer_problem_solved="Shampoo bottles cluttering tub ledge or shower floor, items falling during shower",
        target_room="shower, bathtub area",
        typical_items=[
            "Large shampoo bottle (top shelf)",
            "Conditioner bottle (top shelf)",
            "Body wash pump bottle (middle shelf)",
            "Face wash (middle shelf)",
            "Shaving cream (bottom shelf)",
            "Razor (bottom shelf)",
            "Bar soap on dish (bottom shelf)",
            "Loofah or bath sponge (hanging or on shelf)"
        ],
        capacity_min=8,
        capacity_max=12,
        capacity_description="8-12 full-size shower products organized across 3 corner shelves",
        scene_type="in-use",
        required_context_items=[
            "shower corner with tile walls",
            "shower head visible",
            "water droplets on shelves (showing recent use)",
            "realistic product bottles and containers",
            "products arranged naturally (frequently used items at eye level)"
        ],
        customer_persona="shower user with complete bath routine (hair care, body care, shaving)",
        unique_value="Corner mounting maximizes unused space without intruding into shower area",
        competitive_advantage="3 tiers = 3x storage vs single shelf, keeps everything off floor and within reach"
    ),

    "glass shelf two tier": ProductUsageContext(
        primary_use_case="Bathroom vanity storage for toiletries and personal care products",
        customer_problem_solved="Need elegant storage for daily-use items without visible clutter",
        target_room="bathroom vanity area",
        typical_items=[
            "Amber glass serum bottles (top shelf)",
            "White ceramic soap dispenser (top shelf)",
            "Small succulent plant or decorative item (top shelf)",
            "Face cream jars (bottom shelf)",
            "Cotton pad container (bottom shelf)",
            "Hand soap (bottom shelf)"
        ],
        capacity_min=4,
        capacity_max=8,
        capacity_description="4-8 toiletry items displayed elegantly on glass shelving",
        scene_type="lifestyle",
        required_context_items=[
            "bathroom vanity with mirror above",
            "floating vanity or countertop below",
            "premium toiletries and skincare products ON shelves (not towels)",
            "soft lighting creating glass reflections",
            "organized, boutique hotel aesthetic"
        ],
        customer_persona="homeowner wanting spa-like bathroom organization",
        unique_value="Glass shelves create open, airy feel while displaying products elegantly",
        competitive_advantage="Transparent glass doesn't visually clutter space, shows off premium products"
    ),

    "glass shelf three tier": ProductUsageContext(
        primary_use_case="Extensive bathroom storage for toiletries, products, and decorative items",
        customer_problem_solved="Need significant bathroom storage while maintaining elegant, uncluttered appearance",
        target_room="bathroom vanity area, master bath",
        typical_items=[
            "Skincare products in premium bottles (top shelf)",
            "Face serums and treatments (top shelf)",
            "Body lotions and hand soaps (middle shelf)",
            "Cotton products and accessories (middle shelf)",
            "Rolled hand towels (bottom shelf)",
            "Decorative items like small plants or candles (bottom shelf)"
        ],
        capacity_min=6,
        capacity_max=12,
        capacity_description="6-12 items including toiletries, products, and decorative elements",
        scene_type="lifestyle",
        required_context_items=[
            "luxury bathroom vanity setting",
            "mirror above or behind shelf",
            "mixed use showing toiletries AND towels together",
            "boutique hotel or spa aesthetic",
            "items arranged by height and frequency of use"
        ],
        customer_persona="homeowner creating spa-like master bathroom experience",
        unique_value="Three tiers provide extensive storage while glass maintains open, elegant appearance",
        competitive_advantage="Can hold both daily products AND display items, creates visual focal point"
    ),

    "heated towel rack": ProductUsageContext(
        primary_use_case="Towel warming for luxury bathroom experience",
        customer_problem_solved="Cold, damp towels after shower - want warm, dry towels ready for use",
        target_room="master bathroom, luxury bathroom",
        typical_items=[
            "3-5 bath towels folded for warming (not hanging)",
            "White or neutral luxury towels",
            "Towels stacked to maximize warming surface contact"
        ],
        capacity_min=3,
        capacity_max=5,
        capacity_description="3-5 folded bath towels positioned for even heat distribution",
        scene_type="lifestyle",
        required_context_items=[
            "luxury master bathroom setting",
            "high-end fixtures visible (rainfall shower, soaking tub)",
            "folded towels showing warming feature (not hanging)",
            "spa-like atmosphere with premium finishes",
            "heated rack clearly showing multiple bars/rungs"
        ],
        customer_persona="luxury homeowner wanting spa experience at home",
        unique_value="Heated bars warm and dry towels between uses - stepping out of shower into warm towel",
        competitive_advantage="Dual function: towel storage AND warming - premium feature for master bath"
    ),

    "towel ring": ProductUsageContext(
        primary_use_case="Hand towel storage near sink for hand drying",
        customer_problem_solved="Need convenient hand towel placement for frequent handwashing",
        target_room="bathroom, powder room",
        typical_items=["Single hand towel (16x30 inches) pulled through ring"],
        capacity_min=1,
        capacity_max=1,
        capacity_description="Single hand towel threaded through ring, hanging naturally",
        scene_type="lifestyle",
        required_context_items=[
            "bathroom wall near sink",
            "sink or vanity partially visible",
            "hand towel in neutral or accent color",
            "towel passed THROUGH ring once (not wrapped around)",
            "ring at comfortable reach height (42-48 inches)"
        ],
        customer_persona="homeowner, guest bathroom host",
        unique_value="Compact ring design saves space while keeping hand towel accessible",
        competitive_advantage="Takes less wall space than towel bar, perfect for powder rooms"
    ),

    "robe hook": ProductUsageContext(
        primary_use_case="Bathrobe and towel hanging near shower entry",
        customer_problem_solved="Need convenient place to hang robe before shower and after bath",
        target_room="bathroom near shower",
        typical_items=["Plush white bathrobe or large bath towel hanging FROM hook"],
        capacity_min=1,
        capacity_max=1,
        capacity_description="Single bathrobe or oversized towel showing natural drape from hook",
        scene_type="lifestyle",
        required_context_items=[
            "bathroom wall near shower entry or door",
            "bathrobe hanging naturally showing hook function",
            "shower door or enclosure visible in background",
            "single item (not multiple items piled on hook)"
        ],
        customer_persona="homeowner using bathrobe in morning/evening routine",
        unique_value="Simple hook design for quick hang-up of robes and towels",
        competitive_advantage="Space-efficient, works in tight spaces where towel bars don't fit"
    ),

    "toilet paper holder": ProductUsageContext(
        primary_use_case="Toilet paper storage and dispensing in bathroom",
        customer_problem_solved="Need convenient toilet paper access at proper height",
        target_room="bathroom",
        typical_items=["White premium toilet paper roll installed on holder"],
        capacity_min=1,
        capacity_max=1,
        capacity_description="Single toilet paper roll ready for use",
        scene_type="lifestyle",
        required_context_items=[
            "bathroom wall next to toilet",
            "toilet edge partially visible for context",
            "holder at standard height (26 inches from floor)",
            "clean minimal wall area",
            "paper roll showing proper installation"
        ],
        customer_persona="homeowner, bathroom user",
        unique_value="Proper mounting height and reach for comfortable use",
        competitive_advantage="Decorative design elevates basic necessity into design element"
    ),
}


def get_product_usage_context(category: str, product_title: str) -> Optional[ProductUsageContext]:
    """
    Determine product usage context from category and title.

    Args:
        category: Product category from catalog
        product_title: Product title from catalog

    Returns:
        ProductUsageContext if match found, None otherwise
    """
    category_lower = category.lower()
    title_lower = product_title.lower()

    # Paper towel holders - check mounting type
    if "paper towel" in category_lower or "paper towel" in title_lower:
        if any(x in title_lower for x in ["under cabinet", "under-cabinet", "wall mount", "wall-mount"]):
            return PRODUCT_USAGE_DATABASE.get("paper towel holder under cabinet")
        else:
            return PRODUCT_USAGE_DATABASE.get("paper towel holder countertop")

    # Multi-tier towel bars - detect tier count
    if "towel bar" in category_lower or "towel bar" in title_lower:
        if any(x in title_lower for x in ["four tier", "4-tier", "4 tier", "ladder", "quad"]):
            return PRODUCT_USAGE_DATABASE.get("towel bar four tier")
        # Add other tier counts as needed
        return PRODUCT_USAGE_DATABASE.get("towel bar single")

    # Corner shelves
    if "corner" in title_lower and ("shelf" in category_lower or "shelf" in title_lower):
        if any(x in title_lower for x in ["three tier", "3-tier", "3 tier"]):
            return PRODUCT_USAGE_DATABASE.get("corner shelf three tier")
        # Default to three tier for corner shelves
        return PRODUCT_USAGE_DATABASE.get("corner shelf three tier")

    # Glass shelves - detect tier count
    if "glass shelf" in category_lower or ("glass" in title_lower and "shelf" in title_lower):
        if any(x in title_lower for x in ["three tier", "3-tier", "3 tier"]):
            return PRODUCT_USAGE_DATABASE.get("glass shelf three tier")
        elif any(x in title_lower for x in ["two tier", "2-tier", "2 tier"]):
            return PRODUCT_USAGE_DATABASE.get("glass shelf two tier")
        # Default to two tier
        return PRODUCT_USAGE_DATABASE.get("glass shelf two tier")

    # Heated towel racks
    if any(x in title_lower for x in ["heated", "warmer", "warming"]):
        return PRODUCT_USAGE_DATABASE.get("heated towel rack")

    # Towel rings
    if "towel ring" in category_lower or "towel ring" in title_lower:
        return PRODUCT_USAGE_DATABASE.get("towel ring")

    # Robe hooks
    if "robe hook" in category_lower or "robe hook" in title_lower:
        return PRODUCT_USAGE_DATABASE.get("robe hook")
    elif "hook" in category_lower and "multi" not in title_lower:
        return PRODUCT_USAGE_DATABASE.get("robe hook")

    # Toilet paper holders
    if "toilet paper" in category_lower or "toilet paper" in title_lower:
        return PRODUCT_USAGE_DATABASE.get("toilet paper holder")

    return None


def extract_tier_count(text: str) -> str:
    """Extract tier count from title text.

    Args:
        text: Product title text

    Returns:
        Tier count as word ('two', 'three', 'four') or 'single'
    """
    tier_patterns = {
        "two": ["two tier", "2-tier", "2 tier", "double"],
        "three": ["three tier", "3-tier", "3 tier", "triple"],
        "four": ["four tier", "4-tier", "4 tier", "quad", "ladder"],
        "five": ["five tier", "5-tier", "5 tier"],
    }

    text_lower = text.lower()
    for tier_word, patterns in tier_patterns.items():
        if any(pattern in text_lower for pattern in patterns):
            return tier_word

    return "single"
