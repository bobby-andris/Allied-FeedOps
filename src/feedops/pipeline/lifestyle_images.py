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

def get_product_inventory(category: str) -> str:
    """
    Get product component description template based on category

    Args:
        category: Product category (e.g., "Towel Bar", "Cabinet Knob")

    Returns:
        Product component inventory description
    """
    category_lower = category.lower()

    if "towel bar" in category_lower:
        return """BACKPLATE (2 total - one at each end):
- Shape: Perfect SQUARE or CIRCLE (depends on design)
- Surface: Flat with decorative detail or pattern
- This is a single flat surface - not layered or stepped

END CAP:
- Small projection extending from backplate center
- Clean geometric shape

BAR:
- Cylindrical round bar connecting the two end caps
- Smooth, polished finish

CONFIGURATION: Two mounting points (left and right ends)"""

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

    elif "hook" in category_lower:
        return """BACKPLATE:
- Mounting plate (circular or square)
- Decorative pattern or smooth
- Secured to wall

HOOK:
- Curved or straight projection
- Single or double hook design
- Smooth polished finish"""

    # Default generic template
    return """COMPONENTS (as visible in reference image):
- Primary mounting hardware
- Decorative elements as shown
- Finish details matching reference

Study the reference image carefully and replicate exactly."""


def get_scene_context(style: str = "modern", category: str = "") -> str:
    """
    Get scene description based on style and product category

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
    "glass shelf": {
        "correct": "toiletries, skincare products, small decorative items stored ON the shelf surface",
        "forbidden": "towels, robes, or any fabric items draped OVER or hanging FROM the shelf",
        "critical": "CRITICAL CONSTRAINT: Items must be PLACED ON the shelf, not draped over it. Glass shelves are for storage, not hanging fabric.",
    },
    "towel bar": {
        "correct": "bath towel hanging FROM the horizontal bar, showing natural drape and weight",
        "forbidden": "towels folded and stacked on top of the bar, multiple towels, towels wrapped around",
        "critical": "CRITICAL CONSTRAINT: Single towel must HANG from the bar, not folded on top of it.",
    },
    "toilet paper holder": {
        "correct": "toilet paper roll installed ON the holder, showing the paper ready to use",
        "forbidden": "empty holder with no toilet paper, towels on the holder, decorative items",
        "critical": "CRITICAL CONSTRAINT: Toilet paper must be visible and installed on the holder.",
    },
    "paper holder": {
        "correct": "toilet paper roll installed ON the holder, showing the paper ready to use",
        "forbidden": "empty holder with no toilet paper, towels on the holder, decorative items",
        "critical": "CRITICAL CONSTRAINT: Toilet paper must be visible and installed on the holder.",
    },
    "robe hook": {
        "correct": "bathrobe or towel hanging FROM the hook, showing natural drape downward",
        "forbidden": "multiple items piled on hook, items placed ON TOP of hook, items wrapped around hook",
        "critical": "CRITICAL CONSTRAINT: Single item must HANG from hook, not stacked or wrapped.",
    },
    "hook": {
        "correct": "bathrobe or towel hanging FROM the hook, showing natural drape downward",
        "forbidden": "multiple items piled on hook, items placed ON TOP of hook, items wrapped around hook",
        "critical": "CRITICAL CONSTRAINT: Single item must HANG from hook, not stacked or wrapped.",
    },
    "towel ring": {
        "correct": "hand towel pulled THROUGH the ring and hanging naturally",
        "forbidden": "towel wrapped AROUND the ring multiple times, towel folded on the ring",
        "critical": "CRITICAL CONSTRAINT: Towel passes THROUGH ring once, hangs naturally.",
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
