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

    def build_prompt(self, inventory: str, scene: str, technical: str) -> str:
        """
        Build product-first prompt using proven template

        Args:
            inventory: Product component description
            scene: Scene context narrative
            technical: Photography technical specs

        Returns:
            Complete prompt for image generation
        """
        return f"""CRITICAL: This is PRODUCT PHOTOGRAPHY with lifestyle context. REPLICATE the exact product shown in the reference image - do not interpret or redesign.

PRODUCT VISUAL INVENTORY:
{inventory}

SCENE CONTEXT (narrative description):
{scene}

TECHNICAL SPECIFICATIONS:
{technical}

Remember: The product must be an EXACT REPLICA of the reference. Study every detail carefully."""

    def generate_single_variation(
        self,
        prompt: str,
        ref_image: Image.Image,
        master_sku: str,
        variation_num: int
    ) -> LifestyleImageResult:
        """
        Generate single lifestyle image variation

        Args:
            prompt: Complete generation prompt
            ref_image: Reference product image
            master_sku: Product SKU for filename
            variation_num: Which variation this is (1-3)

        Returns:
            LifestyleImageResult with generation status
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            print(f"  Generating variation {variation_num}...")

            response = self.client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=[prompt, ref_image],
                config=types.GenerateContentConfig(
                    response_modalities=['TEXT', 'IMAGE']
                )
            )

            # Extract and save image
            for part in response.parts:
                if image := part.as_image():
                    filename = f"{master_sku}_var{variation_num}_{timestamp}.png"
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
        product_image_url: str,
        master_sku: str,
        inventory: str,
        scene: str,
        technical: str,
        num_variations: int = 3
    ) -> list[LifestyleImageResult]:
        """
        Generate lifestyle images for a product

        Args:
            product_image_url: URL to product reference image
            master_sku: Product identifier
            inventory: Product component description
            scene: Scene context description
            technical: Technical photography specs
            num_variations: Number of variations to generate (default: 3)

        Returns:
            List of LifestyleImageResult
        """
        print(f"\n{'='*70}")
        print(f"Generating lifestyle images for {master_sku}...")
        print(f"{'='*70}")

        # Download reference image
        ref_image = self.download_image(product_image_url)
        if ref_image is None:
            print("❌ Failed to download reference image")
            return []

        # Build prompt
        prompt = self.build_prompt(inventory, scene, technical)
        print(f"Prompt length: {len(prompt)} characters")

        # Generate variations
        results = []
        for i in range(1, num_variations + 1):
            result = self.generate_single_variation(
                prompt, ref_image, master_sku, variation_num=i
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


def get_scene_context(style: str = "modern") -> str:
    """
    Get scene description based on style

    Args:
        style: Design style (modern, traditional, transitional, industrial)

    Returns:
        Scene context narrative description
    """
    style_lower = style.lower()

    if "contemporary" in style_lower or "modern" in style_lower:
        return """A professional photographer captures a high-contrast modern bathroom.
Pristine white large-format porcelain walls create a minimalist canvas, while a
charcoal gray waffle-weave towel hangs with perfect draping. The edge of a floating
white vanity with a single black accent stripe anchors the composition."""

    elif "traditional" in style_lower or "classic" in style_lower:
        return """An interior designer photographs a classic luxury bathroom bathed in
afternoon light. Warm cream marble walls with delicate gold veining provide an elegant
backdrop, while a soft ivory hand towel hangs gracefully. The edge of a hand-carved
wood vanity with marble top suggests old-world craftsmanship."""

    elif "transitional" in style_lower:
        return """A lifestyle photographer captures an elegant transitional bathroom.
Soft gray painted walls with subtle texture provide a sophisticated backdrop, while
a plush white towel hangs perfectly. Classic white subway tile wainscoting meets
contemporary clean lines."""

    elif "industrial" in style_lower:
        return """An architectural photographer captures an industrial loft bathroom.
Exposed concrete walls with raw texture create an urban backdrop, while a textured
gray towel adds warmth. The edge of a floating concrete vanity extends into frame."""

    # Default modern scene
    return """A clean modern bathroom with white walls, contemporary styling, and
minimalist aesthetic. Professional lifestyle photography showing the product in use."""


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
