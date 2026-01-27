"""
Lifestyle Image Generation Module
Generates AI lifestyle images for Allied Brass products using Gemini Imagen API
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from PIL import Image
import requests
from io import BytesIO


class LifestyleImageResult(BaseModel):
    """Result of lifestyle image generation"""
    image_path: str
    variation_num: int
    generation_success: bool
    prompt_used: str
    timestamp: str
    error_message: Optional[str] = None


class LifestyleImageGenerator:
    """Generates lifestyle images using Gemini Imagen API"""

    def __init__(self, api_key: str, output_dir: Path):
        """
        Initialize lifestyle image generator

        Args:
            api_key: Google Gemini API key
            output_dir: Directory to save generated images
        """
        self.client = genai.Client(api_key=api_key)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_image(self, url: str) -> Optional[Image.Image]:
        """Download product reference image from URL"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        except Exception as e:
            print(f"Error downloading image from {url}: {e}")
            return None

    def build_reference_images_text(self, image_urls: list[str]) -> str:
        """Build reference image list for prompt."""
        if not image_urls:
            return "Reference Images: None available"
        labels = ["Primary", "Detail", "Alternate", "Alternate 2", "Alternate 3"]
        lines = []
        for idx, url in enumerate(image_urls):
            label = labels[idx] if idx < len(labels) else f"Alternate {idx + 1}"
            lines.append(f"Reference Image {idx + 1} ({label}): {url}")
        return "\n".join(lines)

    def build_prompt(
        self,
        inventory: str,
        scene: str,
        technical: str,
        reference_images_text: str,
        usage_constraints: str,
    ) -> str:
        """
        Build product-first prompt using proven template

        Args:
            inventory: Product component description
            scene: Scene context narrative
            technical: Photography technical specs
            reference_images_text: Reference image list for prompt
            usage_constraints: Product usage validation rules

        Returns:
            Complete prompt for image generation
        """
        return f"""CRITICAL: This is PRODUCT PHOTOGRAPHY with lifestyle context. REPLICATE the exact product shown in the reference images - do not interpret or redesign.

REFERENCE IMAGES:
{reference_images_text}

If any reference image includes staging elements (towels, toilet paper) that obscure product details,
prioritize the clearest image for component fidelity.

PRODUCT VISUAL INVENTORY:
{inventory}

SCENE CONTEXT (narrative description):
{scene}

{usage_constraints}

TECHNICAL SPECIFICATIONS:
{technical}

Remember: The product must be an EXACT REPLICA of the reference. Study every detail carefully."""

    def generate_single_variation(
        self,
        prompt: str,
        ref_images: list[Image.Image],
        master_sku: str,
        variation_num: int
    ) -> LifestyleImageResult:
        """
        Generate single lifestyle image variation

        Args:
            prompt: Complete generation prompt
            ref_images: Reference product images
            master_sku: Product SKU for filename
            variation_num: Which variation this is (1-3)

        Returns:
            LifestyleImageResult with generation status
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            print(f"  Generating variation {variation_num}...")

            try:
                response = self.client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=[prompt, *ref_images],
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE']
                    )
                )
            except Exception:
                if len(ref_images) == 1:
                    raise
                print("  ⚠️  Multi-image input failed, retrying with primary image only.")
                response = self.client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=[prompt, ref_images[0]],
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE']
                    )
                )

            # Extract and save image
            safe_sku = master_sku.replace("/", "-")
            for part in response.parts:
                if image := part.as_image():
                    filename = f"{safe_sku}_var{variation_num}_{timestamp}.png"
                    output_path = self.output_dir / filename
                    image.save(str(output_path))

                    print(f"  ✅ Saved: {filename}")

                    return LifestyleImageResult(
                        image_path=str(output_path),
                        variation_num=variation_num,
                        generation_success=True,
                        prompt_used=prompt,
                        timestamp=timestamp
                    )

            # No image in response
            return LifestyleImageResult(
                image_path="",
                variation_num=variation_num,
                generation_success=False,
                prompt_used=prompt,
                timestamp=timestamp,
                error_message="No image in API response"
            )

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return LifestyleImageResult(
                image_path="",
                variation_num=variation_num,
                generation_success=False,
                prompt_used=prompt,
                timestamp=timestamp,
                error_message=str(e)
            )

    def generate_for_product(
        self,
        product_image_urls: list[str],
        master_sku: str,
        inventory: str,
        scene: str,
        technical: str,
        category: str,
        num_variations: int = 3
    ) -> list[LifestyleImageResult]:
        """
        Generate lifestyle images for a product

        Args:
            product_image_urls: URLs to product reference images
            master_sku: Product identifier
            inventory: Product component description
            scene: Scene context description
            technical: Technical photography specs
            category: Product category for usage validation
            num_variations: Number of variations to generate (default: 3)

        Returns:
            List of LifestyleImageResult
        """
        print(f"\n{'='*70}")
        print(f"Generating lifestyle images for {master_sku}...")
        print(f"{'='*70}")

        if not product_image_urls:
            print("❌ No product image URLs provided")
            return []

        reference_images = []
        reference_urls = []
        seen_urls = set()
        for url in product_image_urls:
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            image = self.download_image(url)
            if image is None:
                continue
            reference_images.append(image)
            reference_urls.append(url)

        if not reference_images:
            print("❌ Failed to download reference images")
            return []

        # Build prompt
        reference_images_text = self.build_reference_images_text(reference_urls)
        usage_constraints = get_usage_constraints(category)
        prompt = self.build_prompt(
            inventory=inventory,
            scene=scene,
            technical=technical,
            reference_images_text=reference_images_text,
            usage_constraints=usage_constraints,
        )
        print(f"Prompt length: {len(prompt)} characters")
        print(f"Reference images used: {len(reference_images)}")

        # Generate variations
        results = []
        for i in range(1, num_variations + 1):
            result = self.generate_single_variation(
                prompt, reference_images, master_sku, variation_num=i
            )
            results.append(result)

        successful = sum(1 for r in results if r.generation_success)
        print(f"\n✅ Generated {successful}/{num_variations} variations")

        return results


# Template helpers for building prompts

def get_product_inventory(category: str, product_title: str = "") -> str:
    """
    Get product component description template based on category and title.

    Now considers product features like tier count, mounting type, and special features
    to provide more accurate component descriptions.

    Args:
        category: Product category (e.g., "Towel Bar", "Cabinet Knob")
        product_title: Product title (used to detect features)

    Returns:
        Product component inventory description
    """
    category_lower = category.lower()
    title_lower = product_title.lower()

    # Paper towel holders
    if "paper towel" in category_lower or "paper towel" in title_lower:
        if any(x in title_lower for x in ["under cabinet", "under-cabinet", "wall mount"]):
            return """UNDER-CABINET PAPER TOWEL HOLDER:
MOUNTING BRACKET:
- Metal mounting bracket attaching to underside of cabinet
- Visible screws or tension mechanism
- Compact profile maximizing clearance below cabinet

PAPER TOWEL ARM:
- Horizontal rod holding paper towel roll
- Spring-loaded or friction-hold mechanism
- Allows one-handed tearing motion

PAPER TOWEL ROLL:
- Standard kitchen paper towel roll (11 inches tall)
- Positioned for easy access from counter
- Bottom edge at comfortable reach height (24-26 inches from counter)

CONFIGURATION: Under-cabinet mount for space-saving kitchen storage"""
        else:
            return """COUNTERTOP PAPER TOWEL HOLDER:
WEIGHTED BASE:
- Wide or weighted base for stability
- Prevents tipping when pulling paper towels
- Decorative finish matching kitchen hardware

VERTICAL POST:
- Center post extending 12-14 inches tall
- Holds paper towel roll vertically
- Smooth polished finish

TOP FINIAL/CAP:
- Decorative top piece preventing roll from sliding off
- May have spring-loaded or friction mechanism for roll security

PAPER TOWEL ROLL:
- Standard kitchen paper towel roll installed on post
- Positioned upright for easy one-handed tearing

CONFIGURATION: Freestanding countertop model, easily moved to where needed"""

    # Four-tier towel bars
    if "towel bar" in category_lower or "towel bar" in title_lower:
        if any(x in title_lower for x in ["four tier", "4-tier", "4 tier", "ladder", "quad"]):
            return """FOUR-TIER LADDER TOWEL BAR:
MOUNTING BRACKETS (2 total - top and bottom):
- Wall-mount plates securing the ladder structure to wall
- Decorative finish matching the horizontal bars
- Vertical mounting for maximum space efficiency

FOUR HORIZONTAL BARS (from top to bottom):
- Bar 1 (Top): Full-size bath towel hanging space (24-30 inches wide)
- Bar 2 (Second): Full-size bath towel hanging space
- Bar 3 (Third): Bath towel or hand towel space
- Bar 4 (Bottom): Hand towel or washcloth space
- Each bar independently holds one full towel

VERTICAL SUPPORT RAILS:
- Two vertical rails connecting all four horizontal bars
- Ladder-style construction allowing towels to hang without touching
- Maintains spacing between bars for air circulation

CONFIGURATION: Four independent bars provide organized towel storage for 4+ people
This is a FAMILY SOLUTION - each person gets their own designated bar"""
        else:
            return """SINGLE TOWEL BAR:
BACKPLATE (2 total - one at each end):
- Shape: Perfect SQUARE or CIRCLE (depends on design)
- Surface: Flat with decorative detail or pattern
- This is a single flat surface - not layered or stepped

END CAP:
- Small projection extending from backplate center
- Clean geometric shape

BAR:
- Cylindrical round bar connecting the two end caps
- Smooth, polished finish
- Holds 1-2 full-size bath towels

CONFIGURATION: Two mounting points (left and right ends), standard single-bar design"""

    elif "cabinet knob" in category_lower or "knob" in category_lower:
        return """BACKPLATE/ROSETTE:
- Circular decorative base
- May have decorative pattern or smooth surface
- Diameter approximately 1-2 inches

KNOB:
- Spherical or decorative shaped handle
- Projects from backplate
- Smooth polished finish

MOUNTING: Single center screw through backplate"""

    # Corner shelves
    if "corner" in title_lower and ("shelf" in category_lower or "shelf" in title_lower):
        from feedops.pipeline.product_usage_context import extract_tier_count
        tier_count = extract_tier_count(title_lower)
        tier_num = {"two": 2, "three": 3, "four": 4, "five": 5}.get(tier_count, 3)

        return f"""CORNER SHELF (MULTI-TIER):
MOUNTING BRACKETS (per shelf):
- Corner-specific triangular or L-shaped brackets
- Secure to both walls meeting at corner
- Chrome/brass finish visible from front
- Each shelf has independent mounting hardware

GLASS OR METAL SHELVES ({tier_num} total, from top to bottom):
- Top Shelf: Positioned 6-8 inches below shower head, holds 3-5 bottles
- Middle Shelf(ves): Spaced 10-12 inches apart, each holds 3-5 bottles
- Bottom Shelf: 12-15 inches above tub edge, holds 3-5 bottles
- Clear tempered glass or metal construction
- Typical capacity: {tier_num * 3}-{tier_num * 5} full-size shower products total

CORNER GUARDS/RAILS (if present):
- Small raised edge preventing items from sliding off
- Wire or metal guard visible at shelf edge

CONFIGURATION: Corner-mounted maximizing unused corner space in shower
This is a SHOWER STORAGE SOLUTION - designed to organize all shower products off the floor"""

    elif "hook" in category_lower:
        return """ROBE HOOK:
BACKPLATE:
- Mounting plate (circular or square)
- Decorative pattern or smooth surface
- Secured to wall with screws

HOOK PROJECTION:
- Curved or straight projection extending from wall
- Single or double hook design
- Smooth polished finish
- Designed for hanging robes or towels

CONFIGURATION: Simple hook for quick hang-up of robes and towels"""

    # Default generic template
    return """COMPONENTS (as visible in reference image):
- Primary mounting hardware
- Decorative elements as shown
- Finish details matching reference

Study the reference image carefully and replicate exactly."""


def get_customer_focused_scene(
    category: str,
    style: str,
    product_title: str,
) -> str:
    """
    Generate customer-focused scene based on actual usage patterns.

    This function creates scenes that demonstrate:
    - HOW customers use the product
    - WHERE they use it (correct room)
    - WHAT capacity it serves (full usage demonstration)
    - WHY it solves their problem

    Args:
        category: Product category
        style: Design style
        product_title: Product title (used to detect features like tier count)

    Returns:
        Customer-focused scene description
    """
    from feedops.pipeline.product_usage_context import get_product_usage_context

    # Get usage context from database
    usage_context = get_product_usage_context(category, product_title)

    if not usage_context:
        # Fallback to current generic scene
        return get_scene_context(style, category)

    # Build base environment for target room
    if usage_context.target_room == "kitchen":
        base_env = get_kitchen_environment(style)
    elif "guest" in usage_context.target_room:
        base_env = get_guest_bathroom_environment(style)
    elif usage_context.target_room == "shower":
        base_env = get_shower_environment(style)
    else:
        base_env = get_bathroom_environment(style)

    # Build item list for display
    items_list = build_item_list(usage_context.typical_items, usage_context.capacity_min)

    # Build context requirements
    context_items = build_context_items(usage_context.required_context_items)

    # Build customer-focused scene narrative
    scene = f"""{base_env}

CUSTOMER USE CASE: {usage_context.primary_use_case}
The scene demonstrates how a {usage_context.customer_persona} uses this product daily.

PROBLEM SOLVED: {usage_context.customer_problem_solved}

ITEMS TO SHOW ({usage_context.capacity_min}-{usage_context.capacity_max} items):
{items_list}

CONTEXT REQUIREMENTS:
{context_items}

VALUE DEMONSTRATION: {usage_context.unique_value}
The image must clearly show: {usage_context.capacity_description}

SCENE TYPE: {usage_context.scene_type}
{'Show the product in active use during ' + usage_context.primary_use_case if usage_context.scene_type == 'in-use' else 'Show lifestyle staging that demonstrates practical use'}

This is not just product photography - this shows customers HOW they will use this product and WHY they need it."""

    return scene


def get_kitchen_environment(style: str) -> str:
    """Generate kitchen base environment based on style."""
    if style.lower() in ["modern", "contemporary"]:
        return "Modern kitchen with white quartz countertops, stainless steel sink, and subway tile backsplash. Bright natural lighting."
    elif style.lower() in ["traditional", "classic"]:
        return "Traditional kitchen with granite countertops, farmhouse sink, and classic cabinetry. Warm ambient lighting."
    else:
        return "Kitchen with clean countertops and sink area visible. Natural lighting."


def get_guest_bathroom_environment(style: str) -> str:
    """Generate guest/family bathroom environment."""
    if style.lower() in ["modern", "contemporary"]:
        return "Modern guest bathroom with white walls, chrome fixtures, and clean lines. Multiple personal care items visible suggesting family use."
    else:
        return "Guest bathroom with neutral walls and organized family items visible. Warm welcoming atmosphere."


def get_shower_environment(style: str) -> str:
    """Generate shower/tub area environment."""
    return "Shower area with white tile walls, chrome shower head visible, and water droplets suggesting recent use. Glass enclosure partially visible."


def get_bathroom_environment(style: str) -> str:
    """Generate standard bathroom environment."""
    if style.lower() in ["modern", "contemporary"]:
        return "Modern bathroom with white large-format porcelain tiles, chrome fixtures. Clean, minimal aesthetic."
    elif style.lower() in ["traditional", "classic"]:
        return "Traditional bathroom with cream subway tiles, warm brass fixtures. Classic elegant styling."
    else:
        return "Bathroom with neutral tiles and clean finishes."


def build_item_list(items: list[str], min_items: int) -> str:
    """Build formatted item list for prompt."""
    item_descriptions = []
    for i, item in enumerate(items[:min_items], 1):
        item_descriptions.append(f"{i}. {item}")
    return "\n".join(item_descriptions)


def build_context_items(context_items: list[str]) -> str:
    """Build formatted context requirements for prompt."""
    return "\n".join(f"- {item}" for item in context_items)


def get_scene_context(style: str = "modern", category: str = "") -> str:
    """
    Get scene description based on style and product category.

    NOTE: This is the legacy function. New code should use get_customer_focused_scene().

    Args:
        style: Design style (modern, traditional, transitional, industrial)
        category: Product category (e.g., "Towel Bar", "Glass Shelf")

    Returns:
        Scene context narrative description
    """
    style_lower = (style or "modern").lower()
    category_lower = (category or "").lower()

    if "contemporary" in style_lower or "modern" in style_lower:
        base_env = "Modern bathroom with white large-format porcelain tiles, chrome fixtures. "
    elif "traditional" in style_lower or "classic" in style_lower:
        base_env = "Traditional bathroom with cream subway tiles, warm brass fixtures. "
    elif "transitional" in style_lower:
        base_env = "Transitional bathroom with soft gray walls, classic white tile, mixed metal accents. "
    elif "industrial" in style_lower:
        base_env = "Industrial bathroom with exposed concrete, blackened metal accents. "
    else:
        base_env = "Bathroom with neutral tiles and clean finishes. "

    if "glass shelf" in category_lower:
        return (
            f"{base_env}"
            "The glass shelf is mounted above a floating vanity.\n"
            "Premium toiletries are organized ON the shelf: amber glass serum bottles, "
            "a white ceramic soap dispenser, and a small potted succulent.\n"
            "The shelf holds decorative bathroom items, NOT towels or fabric.\n"
            "Soft lighting creates subtle reflections in the glass.\n"
            "The vanity area below is clean and uncluttered."
        )

    if "towel bar" in category_lower:
        return (
            f"{base_env}"
            "The towel bar is mounted on the wall outside a glass shower enclosure.\n"
            "A single plush bath towel hangs naturally FROM the bar, showing natural drape.\n"
            "The towel is a neutral color (white, gray, or taupe).\n"
            "The bar is positioned at standard 48-inch height.\n"
            "Negative space emphasizes the architectural lines of the fixture."
        )

    if "toilet paper holder" in category_lower or "paper holder" in category_lower:
        return (
            f"{base_env}"
            "The toilet paper holder is mounted on the wall next to the toilet.\n"
            "A premium white toilet paper roll is installed ON the holder.\n"
            "The holder is positioned at standard 26-inch height from the floor.\n"
            "The surrounding wall area is clean and minimal.\n"
            "A partial view of the toilet edge provides context without distracting."
        )

    if "robe hook" in category_lower or ("hook" in category_lower and "multi hook" not in category_lower):
        return (
            f"{base_env}"
            "The robe hook is mounted on the wall near the shower entry.\n"
            "A plush white bathrobe or premium hand towel hangs FROM the hook.\n"
            "The fabric shows natural drape and weight from the hook.\n"
            "A single item hangs from the hook (not multiple items piled).\n"
            "The wall area around the hook is clean and uncluttered."
        )

    if "towel ring" in category_lower:
        return (
            f"{base_env}"
            "The towel ring is mounted on the wall near the sink.\n"
            "A hand towel is pulled THROUGH the ring and hangs naturally.\n"
            "The towel shows a single pass through the ring, not wrapped around it.\n"
            "The ring is positioned at a comfortable reach height.\n"
            "The wall area emphasizes the fixture's design."
        )

    return (
        f"{base_env}"
        "The bathroom fixture is mounted at standard height.\n"
        "Clean, professional installation in an uncluttered setting.\n"
        "Soft, even lighting highlights the product's finish and details."
    )


PRODUCT_USAGE_RULES = {
    "paper towel": {
        "correct": "Kitchen counter or cabinet area with paper towel roll installed, suggesting cooking/food prep context",
        "forbidden": "Bathroom setting (unless specifically bathroom paper towels), empty holder",
        "critical": "CRITICAL: Must show KITCHEN context with cooking or sink area visible. Paper towel holders are primarily KITCHEN products used during meal preparation.",
        "capacity": "Single paper towel roll properly mounted and accessible for one-handed use",
    },
    "four tier towel bar": {
        "correct": "4-5 towels hanging from different bars, showing full multi-person use. Different colors/styles to indicate family members.",
        "forbidden": "Only 1-2 towels shown, empty bars, towels folded instead of hanging, all same color",
        "critical": "CRITICAL: Must show at least 4 towels demonstrating FULL FAMILY USE. Each bar should have a towel. This is a MULTI-PERSON storage solution - showing only 1-2 towels completely misrepresents its purpose.",
        "capacity": "Minimum 4 towels (one per bar), ideally 4-5 in different colors showing family bathroom use",
    },
    "corner shelf": {
        "correct": "8-12 shower products (bottles, soaps, razors, loofahs) distributed across all shelves. Shows active shower storage use.",
        "forbidden": "Empty shelves, only 1-2 items total, decorative items only, towels on shelves",
        "critical": "CRITICAL: Must show 8-12 shower/bath products to demonstrate STORAGE CAPACITY. Customers buy this to ORGANIZE shower clutter - empty shelves don't show the value.",
        "capacity": "Minimum 8 items total (2-4 per shelf), maximum 12 items, showing realistic shower product organization",
    },
    "glass shelf": {
        "correct": "toiletries, skincare products, small decorative items stored ON the shelf surface, may include rolled hand towels on bottom shelf",
        "forbidden": "towels draped OVER or hanging FROM the shelf, empty shelves",
        "critical": "CRITICAL CONSTRAINT: Items must be PLACED ON the shelf, not draped over it. Glass shelves are for elegant storage and display, not hanging fabric.",
        "capacity": "4-8 items including toiletries and accessories, may include folded/rolled towels ON bottom shelf",
    },
    "towel bar": {
        "correct": "bath towel hanging FROM the horizontal bar, showing natural drape and weight",
        "forbidden": "towels folded and stacked on top of the bar, towels wrapped around",
        "critical": "CRITICAL CONSTRAINT: Towel must HANG from the bar, not folded on top of it.",
        "capacity": "1-2 full-size bath towels hanging naturally",
    },
    "heated towel rack": {
        "correct": "Multiple folded towels positioned for warming, luxurious bathroom context",
        "forbidden": "Hanging towels (reduces warming efficiency), empty rack, single towel",
        "critical": "CRITICAL: Show 3-5 folded towels positioned for warming. This is a HEATED product - demonstrate the luxury warming feature with multiple towels.",
        "capacity": "3-5 folded towels showing full rack utilization and warming capability",
    },
    "toilet paper holder": {
        "correct": "toilet paper roll installed ON the holder, showing the paper ready to use",
        "forbidden": "empty holder with no toilet paper, towels on the holder, decorative items",
        "critical": "CRITICAL CONSTRAINT: Toilet paper must be visible and installed on the holder.",
        "capacity": "Single toilet paper roll properly installed",
    },
    "paper holder": {
        "correct": "toilet paper roll installed ON the holder, showing the paper ready to use",
        "forbidden": "empty holder with no toilet paper, towels on the holder, decorative items",
        "critical": "CRITICAL CONSTRAINT: Toilet paper must be visible and installed on the holder.",
        "capacity": "Single toilet paper roll properly installed",
    },
    "robe hook": {
        "correct": "bathrobe or towel hanging FROM the hook, showing natural drape downward",
        "forbidden": "multiple items piled on hook, items placed ON TOP of hook, items wrapped around hook",
        "critical": "CRITICAL CONSTRAINT: Single item must HANG from hook, not stacked or wrapped.",
        "capacity": "Single bathrobe or towel hanging naturally",
    },
    "hook": {
        "correct": "bathrobe or towel hanging FROM the hook, showing natural drape downward",
        "forbidden": "multiple items piled on hook, items placed ON TOP of hook, items wrapped around hook",
        "critical": "CRITICAL CONSTRAINT: Single item must HANG from hook, not stacked or wrapped.",
        "capacity": "Single item hanging naturally",
    },
    "towel ring": {
        "correct": "hand towel pulled THROUGH the ring and hanging naturally",
        "forbidden": "towel wrapped AROUND the ring multiple times, towel folded on the ring",
        "critical": "CRITICAL CONSTRAINT: Towel passes THROUGH ring once, hangs naturally.",
        "capacity": "Single hand towel threaded through ring",
    },
}


def get_usage_constraints(category: str) -> str:
    """Get strict usage validation rules for product category."""
    category_lower = (category or "").lower()

    if "multi hook" in category_lower:
        return """PRODUCT USAGE VALIDATION:
Show the product in its typical, correct usage scenario.
Avoid any atypical or incorrect usage that would confuse customers."""

    for key, rules in PRODUCT_USAGE_RULES.items():
        if key in category_lower:
            return f"""PRODUCT USAGE VALIDATION:
✅ CORRECT USAGE: {rules['correct']}
❌ FORBIDDEN: {rules['forbidden']}

{rules['critical']}

The AI must verify the scene shows CORRECT usage only.
Any forbidden usage will result in image rejection."""

    return """PRODUCT USAGE VALIDATION:
Show the product in its typical, correct usage scenario.
Avoid any atypical or incorrect usage that would confuse customers."""


def get_technical_specs(style: str = "modern") -> str:
    """
    Get photography technical specs based on style

    Args:
        style: Design style

    Returns:
        Technical photography specifications
    """
    style_lower = style.lower()

    if "modern" in style_lower or "contemporary" in style_lower:
        return """Lighting: Bright even 5500K illumination with directional spotlight for crisp shadows
Camera: 3/4 angle, product sharp focus, background soft
Mood: Clean, minimal, architectural precision"""

    elif "traditional" in style_lower or "classic" in style_lower:
        return """Lighting: Warm 3500K with natural light creating golden highlights
Camera: 3/4 angle showing dimensional details
Mood: Classic elegance, warm luxury, traditional sophistication"""

    # Default
    return """Lighting: Natural soft lighting with good product visibility
Camera: 3/4 angle, product in sharp focus
Mood: Professional, clean, lifestyle photography"""
