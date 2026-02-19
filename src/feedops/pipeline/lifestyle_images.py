"""
Lifestyle Image Generation Module
Generates AI lifestyle images for Allied Brass products using Gemini Imagen API

Includes IPTC/XMP metadata tagging for AI disclosure compliance with Google Merchant Center.
"""

import shutil
import subprocess
import os
import random
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from google import genai
from google.genai import types
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from pydantic import BaseModel

# IPTC Digital Source Type URI for AI-generated content
IPTC_TRAINED_ALGORITHMIC_MEDIA = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
)

# AI System identifier for metadata
AI_SYSTEM_USED = "Google Gemini Imagen"
AI_SYSTEM_VERSION = "gemini-3-pro-image-preview"


def add_ai_metadata_to_image(
    image_path: Path,
    prompt: str,
    ai_system: str = AI_SYSTEM_USED,
    ai_version: str = AI_SYSTEM_VERSION,
) -> bool:
    """
    Add IPTC/XMP metadata to AI-generated image for Google Merchant Center compliance.

    Google requires trainedAlgorithmicMedia IPTC metadata tag on all AI-generated
    images used in lifestyle_image_link, image_link, or additional_image_link.

    Args:
        image_path: Path to the image file
        prompt: The AI prompt used to generate the image (truncated to 500 chars)
        ai_system: Name of the AI system used
        ai_version: Version of the AI model

    Returns:
        True if metadata was successfully added, False otherwise
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return False

    # Try exiftool first (most comprehensive IPTC/XMP support)
    if _add_metadata_with_exiftool(image_path, prompt, ai_system, ai_version):
        return True

    # Fallback: Re-save PNG with text metadata chunks
    if image_path.suffix.lower() == ".png":
        return _add_metadata_to_png(image_path, prompt, ai_system, ai_version)

    return False


def _add_metadata_with_exiftool(
    image_path: Path,
    prompt: str,
    ai_system: str,
    ai_version: str,
) -> bool:
    """Add IPTC/XMP metadata using exiftool if available."""
    exiftool = shutil.which("exiftool")
    if not exiftool:
        return False

    # Truncate prompt to 500 chars for IPTC field limits
    truncated_prompt = prompt[:500] if len(prompt) > 500 else prompt

    try:
        # Build exiftool command with IPTC and XMP tags
        # XMP-plus:DigitalSourceType is the standard field for AI disclosure
        cmd = [
            exiftool,
            "-overwrite_original",
            f"-XMP-plus:DigitalSourceType={IPTC_TRAINED_ALGORITHMIC_MEDIA}",
            f"-XMP-iptcExt:DigitalSourceType={IPTC_TRAINED_ALGORITHMIC_MEDIA}",
            f"-XMP:Creator={ai_system}",
            f"-XMP:CreatorTool={ai_system} {ai_version}",
            f"-XMP:Description=AI-generated lifestyle image. {truncated_prompt[:200]}",
            f"-IPTC:Caption-Abstract=AI-generated image using {ai_system}",
            str(image_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print(f"    ✓ IPTC metadata added via exiftool")
            return True
        else:
            # Silently fall back to PNG method
            return False

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _add_metadata_to_png(
    image_path: Path,
    prompt: str,
    ai_system: str,
    ai_version: str,
) -> bool:
    """Add metadata to PNG using PIL PngInfo text chunks."""
    try:
        # Load the image
        img = Image.open(image_path)

        # Create metadata
        metadata = PngInfo()

        # Add AI disclosure metadata as text chunks
        # These are readable by image viewers and can be extracted programmatically
        metadata.add_text("DigitalSourceType", IPTC_TRAINED_ALGORITHMIC_MEDIA)
        metadata.add_text("AISystemUsed", ai_system)
        metadata.add_text("AISystemVersion", ai_version)
        metadata.add_text("AIPromptInformation", prompt[:500])
        metadata.add_text(
            "GeneratedBy", "Allied FeedOps - AI Lifestyle Image Generator"
        )
        metadata.add_text(
            "AIDisclosure", "This image was generated using trained AI algorithms"
        )

        # Re-save with metadata
        img.save(str(image_path), "PNG", pnginfo=metadata)
        print(f"    ✓ AI metadata added via PNG text chunks")
        return True

    except Exception as e:
        print(f"    ⚠️ Failed to add PNG metadata: {e}")
        return False


def validate_ai_metadata(image_path: Path) -> dict:
    """
    Validate that AI disclosure metadata is present on an image.

    Args:
        image_path: Path to the image file

    Returns:
        Dict with 'valid' boolean and 'fields' dict of found metadata
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return {"valid": False, "fields": {}, "error": "File not found"}

    fields = {}

    # Try reading PNG text chunks
    if image_path.suffix.lower() == ".png":
        try:
            img = Image.open(image_path)
            if hasattr(img, "text"):
                fields = dict(img.text)
        except Exception:
            pass

    # Check for required AI disclosure field
    has_disclosure = (
        "DigitalSourceType" in fields
        or "AISystemUsed" in fields
        or "AIDisclosure" in fields
    )

    return {
        "valid": has_disclosure,
        "fields": fields,
        "has_digital_source_type": "DigitalSourceType" in fields,
        "has_ai_system": "AISystemUsed" in fields,
    }


# =============================================================================
# Lifestyle Image Compliance Validation
# =============================================================================

# Google Merchant Center supported image formats
SUPPORTED_IMAGE_FORMATS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif"}

# Maximum file size for Google Merchant Center (16MB)
MAX_FILE_SIZE_BYTES = 16 * 1024 * 1024

# Minimum image dimensions for quality
MIN_IMAGE_DIMENSION = 100

# Recommended minimum for lifestyle images
RECOMMENDED_MIN_DIMENSION = 800


class LifestyleImageValidationResult(BaseModel):
    """Result of lifestyle image compliance validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]

    # Technical details
    file_exists: bool
    file_format_valid: bool
    file_size_bytes: Optional[int] = None
    file_size_valid: bool = False

    # Image properties
    width: Optional[int] = None
    height: Optional[int] = None
    dimensions_valid: bool = False

    # AI metadata compliance
    has_ai_metadata: bool = False
    ai_metadata_fields: dict = {}


def validate_lifestyle_image(
    image_path: str | Path,
    require_ai_metadata: bool = True,
) -> LifestyleImageValidationResult:
    """
    Validate a lifestyle image for Google Merchant Center compliance.

    Checks:
    - File exists and is accessible
    - File format is supported (PNG, JPG, JPEG, GIF, BMP, TIFF)
    - File size is within limits (< 16MB)
    - Image dimensions meet minimum requirements
    - AI disclosure metadata is present (for compliance)

    Args:
        image_path: Path to the image file
        require_ai_metadata: Whether to require AI metadata (default True)

    Returns:
        LifestyleImageValidationResult with validation details
    """
    import os

    image_path = Path(image_path)
    errors: list[str] = []
    warnings: list[str] = []

    # Initialize result
    result_data = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "file_exists": False,
        "file_format_valid": False,
        "file_size_bytes": None,
        "file_size_valid": False,
        "width": None,
        "height": None,
        "dimensions_valid": False,
        "has_ai_metadata": False,
        "ai_metadata_fields": {},
    }

    # Check file exists
    if not image_path.exists():
        errors.append(f"Image file not found: {image_path}")
        result_data["errors"] = errors
        result_data["valid"] = False
        return LifestyleImageValidationResult(**result_data)

    result_data["file_exists"] = True

    # Check file format
    suffix = image_path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_FORMATS:
        errors.append(
            f"Unsupported image format: {suffix}. "
            f"Supported formats: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
        )
        result_data["file_format_valid"] = False
    else:
        result_data["file_format_valid"] = True

    # Check file size
    try:
        file_size = os.path.getsize(image_path)
        result_data["file_size_bytes"] = file_size

        if file_size > MAX_FILE_SIZE_BYTES:
            errors.append(
                f"Image file too large: {file_size / (1024*1024):.1f}MB. "
                f"Maximum allowed: {MAX_FILE_SIZE_BYTES / (1024*1024):.0f}MB"
            )
            result_data["file_size_valid"] = False
        else:
            result_data["file_size_valid"] = True

        # Warn if file is very large (>5MB)
        if file_size > 5 * 1024 * 1024:
            warnings.append(
                f"Large image file ({file_size / (1024*1024):.1f}MB). "
                "Consider optimizing for faster load times."
            )
    except OSError as e:
        errors.append(f"Cannot read file size: {e}")

    # Check image dimensions
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            result_data["width"] = width
            result_data["height"] = height

            if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                errors.append(
                    f"Image dimensions too small: {width}x{height}. "
                    f"Minimum: {MIN_IMAGE_DIMENSION}x{MIN_IMAGE_DIMENSION}"
                )
                result_data["dimensions_valid"] = False
            else:
                result_data["dimensions_valid"] = True

            if width < RECOMMENDED_MIN_DIMENSION or height < RECOMMENDED_MIN_DIMENSION:
                warnings.append(
                    f"Image dimensions ({width}x{height}) below recommended "
                    f"minimum ({RECOMMENDED_MIN_DIMENSION}x{RECOMMENDED_MIN_DIMENSION}) "
                    "for high-quality lifestyle images."
                )
    except Exception as e:
        errors.append(f"Cannot read image dimensions: {e}")

    # Check AI metadata compliance
    metadata_result = validate_ai_metadata(image_path)
    result_data["has_ai_metadata"] = metadata_result.get("valid", False)
    result_data["ai_metadata_fields"] = metadata_result.get("fields", {})

    if require_ai_metadata and not result_data["has_ai_metadata"]:
        errors.append(
            "Missing AI disclosure metadata. "
            "Google Merchant Center requires trainedAlgorithmicMedia IPTC tag "
            "for AI-generated images."
        )

    # Set final validity
    result_data["errors"] = errors
    result_data["warnings"] = warnings
    result_data["valid"] = len(errors) == 0

    return LifestyleImageValidationResult(**result_data)


def validate_lifestyle_image_result(
    result: "LifestyleImageResult",
    require_ai_metadata: bool = True,
) -> LifestyleImageValidationResult:
    """
    Validate a LifestyleImageResult object for compliance.

    Convenience wrapper that handles failed generations.

    Args:
        result: LifestyleImageResult from image generation
        require_ai_metadata: Whether to require AI metadata

    Returns:
        LifestyleImageValidationResult with validation details
    """
    if not result.generation_success:
        return LifestyleImageValidationResult(
            valid=False,
            errors=[
                f"Image generation failed: {result.error_message or 'Unknown error'}"
            ],
            warnings=[],
            file_exists=False,
            file_format_valid=False,
        )

    if not result.image_path:
        return LifestyleImageValidationResult(
            valid=False,
            errors=["No image path in generation result"],
            warnings=[],
            file_exists=False,
            file_format_valid=False,
        )

    return validate_lifestyle_image(
        result.image_path,
        require_ai_metadata=require_ai_metadata,
    )


def validate_all_lifestyle_images(
    results: list["LifestyleImageResult"],
    require_ai_metadata: bool = True,
) -> dict:
    """
    Validate all lifestyle images from a generation batch.

    Args:
        results: List of LifestyleImageResult objects
        require_ai_metadata: Whether to require AI metadata

    Returns:
        Dict with summary and per-image validation results
    """
    validations = []
    all_valid = True
    total_errors = 0
    total_warnings = 0

    for result in results:
        validation = validate_lifestyle_image_result(
            result,
            require_ai_metadata=require_ai_metadata,
        )
        validations.append(
            {
                "variation_num": result.variation_num,
                "image_path": result.image_path,
                "validation": validation,
            }
        )

        if not validation.valid:
            all_valid = False
        total_errors += len(validation.errors)
        total_warnings += len(validation.warnings)

    return {
        "all_valid": all_valid,
        "total_images": len(results),
        "successful_generations": sum(1 for r in results if r.generation_success),
        "valid_images": sum(1 for v in validations if v["validation"].valid),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "validations": validations,
    }


class LifestyleImageScore(BaseModel):
    """Scores from AI evaluation of a lifestyle image."""

    variation_num: int
    product_accuracy: int  # 0-100: Does the product match the reference?
    composition_quality: int  # 0-100: Professional framing and lighting
    background_appropriateness: int  # 0-100: Correct setting for product type
    aesthetic_appeal: int  # 0-100: Overall visual appeal
    composite_score: float  # Weighted average
    evaluation_notes: str
    evaluation_success: bool
    error_message: Optional[str] = None


def _is_resource_exhausted_error(error: Exception) -> bool:
    text = str(error).lower()
    return "resource_exhausted" in text or "code': 429" in text or " 429" in text


def score_lifestyle_image(
    image_path: str | Path,
    reference_image_url: str,
    category: str,
    api_key: str,
) -> LifestyleImageScore:
    """
    Score a lifestyle image using Gemini Vision API.

    Evaluates:
    - Product accuracy (40%): Does the generated product match the reference?
    - Composition quality (25%): Professional framing, lighting, focus
    - Background appropriateness (20%): Correct setting for product category
    - Aesthetic appeal (15%): Overall visual attractiveness

    Args:
        image_path: Path to the generated lifestyle image
        reference_image_url: URL of the original product reference image
        category: Product category (e.g., "Towel Bar", "Glass Shelf")
        api_key: Gemini API key

    Returns:
        LifestyleImageScore with detailed scores
    """
    image_path = Path(image_path)

    # Extract variation number from filename
    variation_num = 1
    filename = image_path.stem
    if "_var" in filename:
        try:
            var_part = filename.split("_var")[1].split("_")[0]
            variation_num = int(var_part)
        except (IndexError, ValueError):
            pass

    if not image_path.exists():
        return LifestyleImageScore(
            variation_num=variation_num,
            product_accuracy=0,
            composition_quality=0,
            background_appropriateness=0,
            aesthetic_appeal=0,
            composite_score=0.0,
            evaluation_notes="",
            evaluation_success=False,
            error_message=f"Image file not found: {image_path}",
        )

    try:
        # Initialize Gemini client
        client = genai.Client(api_key=api_key)

        # Load the generated image
        generated_image = Image.open(image_path)

        # Download reference image
        response = requests.get(reference_image_url, timeout=10)
        response.raise_for_status()
        reference_image = Image.open(BytesIO(response.content))

        # Build evaluation prompt
        eval_prompt = f"""You are an expert product photography evaluator for e-commerce. 
Evaluate this AI-generated lifestyle image against the reference product image.

PRODUCT CATEGORY: {category}

Score each dimension from 0-100:

1. PRODUCT ACCURACY (most important):
   - Does the generated product exactly match the reference product?
   - Are all components, proportions, and details correct?
   - Is the finish/material accurately represented?
   Score 90-100: Perfect match, indistinguishable from real product
   Score 70-89: Minor inaccuracies but clearly the same product
   Score 50-69: Noticeable differences but recognizable
   Score 0-49: Significant errors or wrong product

2. COMPOSITION QUALITY:
   - Professional framing and angles?
   - Proper lighting without harsh shadows?
   - Product in sharp focus?
   Score 90-100: Gallery-quality professional photography
   Score 70-89: Good commercial quality
   Score 50-69: Acceptable but could be improved
   Score 0-49: Poor composition

3. BACKGROUND APPROPRIATENESS:
   - Is this the correct room/setting for this product category?
   - For {category}: Is it in a bathroom/kitchen as appropriate?
   - Does the setting enhance the product presentation?
   Score 90-100: Perfect contextual setting
   Score 70-89: Appropriate setting
   Score 50-69: Acceptable but generic
   Score 0-49: Wrong setting or distracting

4. AESTHETIC APPEAL:
   - Overall visual attractiveness
   - Would this image help sell the product?
   - Professional, polished appearance?
   Score 90-100: Stunning, would feature prominently
   Score 70-89: Attractive, good for product listing
   Score 50-69: Acceptable
   Score 0-49: Unappealing

Respond in this EXACT JSON format:
{{
  "product_accuracy": <number 0-100>,
  "composition_quality": <number 0-100>,
  "background_appropriateness": <number 0-100>,
  "aesthetic_appeal": <number 0-100>,
  "notes": "<brief evaluation notes>"
}}

The first image is the GENERATED lifestyle image to evaluate.
The second image is the REFERENCE product image to compare against."""

        # Call Gemini Vision API with bounded retry/backoff for quota bursts (429/RESOURCE_EXHAUSTED).
        max_attempts = int(os.environ.get("LIFESTYLE_SCORE_MAX_ATTEMPTS", "4"))
        base_sleep = float(os.environ.get("LIFESTYLE_SCORE_RETRY_BASE_SECONDS", "1.0"))

        response = None
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[eval_prompt, generated_image, reference_image],
                )
                last_error = None
                break
            except Exception as e:
                last_error = e
                if attempt >= max_attempts or not _is_resource_exhausted_error(e):
                    break
                delay = base_sleep * (2 ** (attempt - 1))
                delay += random.random() * 0.25 * delay
                time.sleep(delay)

        if response is None:
            raise last_error or RuntimeError("Image scoring failed")

        # Parse response
        response_text = response.text.strip()

        # Try to extract JSON from response
        import json
        import re

        # Find JSON object in response
        json_match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
        if json_match:
            scores = json.loads(json_match.group())
        else:
            raise ValueError(f"No JSON found in response: {response_text[:200]}")

        # Extract scores
        product_accuracy = int(scores.get("product_accuracy", 50))
        composition_quality = int(scores.get("composition_quality", 50))
        background_appropriateness = int(scores.get("background_appropriateness", 50))
        aesthetic_appeal = int(scores.get("aesthetic_appeal", 50))
        notes = scores.get("notes", "")

        # Calculate weighted composite score
        # Product accuracy is most important (40%), then composition (25%), background (20%), aesthetic (15%)
        composite_score = (
            product_accuracy * 0.40
            + composition_quality * 0.25
            + background_appropriateness * 0.20
            + aesthetic_appeal * 0.15
        )

        return LifestyleImageScore(
            variation_num=variation_num,
            product_accuracy=product_accuracy,
            composition_quality=composition_quality,
            background_appropriateness=background_appropriateness,
            aesthetic_appeal=aesthetic_appeal,
            composite_score=round(composite_score, 1),
            evaluation_notes=notes,
            evaluation_success=True,
        )

    except Exception as e:
        return LifestyleImageScore(
            variation_num=variation_num,
            product_accuracy=0,
            composition_quality=0,
            background_appropriateness=0,
            aesthetic_appeal=0,
            composite_score=0.0,
            evaluation_notes="",
            evaluation_success=False,
            error_message=str(e),
        )


def select_best_lifestyle_image(
    image_results: list["LifestyleImageResult"],
    reference_image_url: str,
    category: str,
    api_key: str,
) -> tuple[int | None, list[LifestyleImageScore]]:
    """
    Score all lifestyle images and select the best one.

    Args:
        image_results: List of LifestyleImageResult from generation
        reference_image_url: URL of the original product reference image
        category: Product category
        api_key: Gemini API key

    Returns:
        Tuple of (best_variation_num, list_of_all_scores)
        Returns (None, []) if no valid images to score
    """
    # Filter to only successful generations
    successful = [r for r in image_results if r.generation_success and r.image_path]

    if not successful:
        print("No successful images to score")
        return None, []

    print(f"\nScoring {len(successful)} lifestyle images...")

    scores: list[LifestyleImageScore] = []
    for result in successful:
        print(f"  Evaluating variation {result.variation_num}...")
        score = score_lifestyle_image(
            image_path=result.image_path,
            reference_image_url=reference_image_url,
            category=category,
            api_key=api_key,
        )
        scores.append(score)

        if score.evaluation_success:
            print(
                f"    ✅ Composite: {score.composite_score:.1f} "
                f"(Accuracy: {score.product_accuracy}, "
                f"Composition: {score.composition_quality}, "
                f"Background: {score.background_appropriateness}, "
                f"Aesthetic: {score.aesthetic_appeal})"
            )
        else:
            print(f"    ❌ Evaluation failed: {score.error_message}")

    # Find best scoring image
    valid_scores = [s for s in scores if s.evaluation_success]
    if not valid_scores:
        print("No images could be evaluated")
        return None, scores

    best = max(valid_scores, key=lambda s: s.composite_score)
    print(
        f"\n🏆 Best image: Variation {best.variation_num} (Score: {best.composite_score:.1f})"
    )

    return best.variation_num, scores


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
        variation_num: int,
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
                        response_modalities=["TEXT", "IMAGE"]
                    ),
                )
            except Exception:
                if len(ref_images) == 1:
                    raise
                print(
                    "  ⚠️  Multi-image input failed, retrying with primary image only."
                )
                response = self.client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=[prompt, ref_images[0]],
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"]
                    ),
                )

            # Extract and save image
            safe_sku = master_sku.replace("/", "-")
            for part in response.parts:
                if image := part.as_image():
                    filename = f"{safe_sku}_var{variation_num}_{timestamp}.png"
                    output_path = self.output_dir / filename
                    image.save(str(output_path))

                    print(f"  ✅ Saved: {filename}")

                    # Add IPTC/XMP metadata for AI disclosure compliance
                    # Required by Google Merchant Center for AI-generated images
                    add_ai_metadata_to_image(
                        image_path=output_path,
                        prompt=prompt,
                        ai_system=AI_SYSTEM_USED,
                        ai_version=AI_SYSTEM_VERSION,
                    )

                    return LifestyleImageResult(
                        image_path=str(output_path),
                        variation_num=variation_num,
                        generation_success=True,
                        prompt_used=prompt,
                        timestamp=timestamp,
                    )

            # No image in response
            return LifestyleImageResult(
                image_path="",
                variation_num=variation_num,
                generation_success=False,
                prompt_used=prompt,
                timestamp=timestamp,
                error_message="No image in API response",
            )

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return LifestyleImageResult(
                image_path="",
                variation_num=variation_num,
                generation_success=False,
                prompt_used=prompt,
                timestamp=timestamp,
                error_message=str(e),
            )

    def generate_for_product(
        self,
        product_image_urls: list[str],
        master_sku: str,
        inventory: str,
        scene: str,
        technical: str,
        category: str,
        num_variations: int = 3,
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
        if any(
            x in title_lower for x in ["under cabinet", "under-cabinet", "wall mount"]
        ):
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
        if any(
            x in title_lower
            for x in ["four tier", "4-tier", "4 tier", "ladder", "quad"]
        ):
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
    if "corner" in title_lower and (
        "shelf" in category_lower or "shelf" in title_lower
    ):
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
    items_list = build_item_list(
        usage_context.typical_items, usage_context.capacity_min
    )

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
        base_env = (
            "Modern bathroom with white large-format porcelain tiles, chrome fixtures. "
        )
    elif "traditional" in style_lower or "classic" in style_lower:
        base_env = "Traditional bathroom with cream subway tiles, warm brass fixtures. "
    elif "transitional" in style_lower:
        base_env = "Transitional bathroom with soft gray walls, classic white tile, mixed metal accents. "
    elif "industrial" in style_lower:
        base_env = (
            "Industrial bathroom with exposed concrete, blackened metal accents. "
        )
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

    if "robe hook" in category_lower or (
        "hook" in category_lower and "multi hook" not in category_lower
    ):
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


# =============================================================================
# Smart Finish Selection & Cloud Run Integration
# =============================================================================


def select_best_finish_for_generation(
    master_sku: str,
    supabase_client,
) -> tuple[str, str]:
    """Select best finish based on Google Ads performance data.

    Queries search_queries table (which has denormalized finish/finish_code)
    and aggregates clicks by finish to find the most popular one.

    Fallback order:
    1. Most clicks
    2. Most impressions (if clicks = 0)
    3. First finish alphabetically
    4. ABR as final fallback

    Args:
        master_sku: The master SKU to select finish for.
        supabase_client: Supabase client instance.

    Returns:
        (finish_name, finish_code) tuple.
    """
    # Query search_queries for this master_sku (finish/finish_code are denormalized)
    result = (
        supabase_client.table("search_queries")
        .select("finish, finish_code, clicks, impressions")
        .eq("master_sku", master_sku)
        .not_.is_("finish", "null")
        .not_.is_("finish_code", "null")
        .execute()
    )

    if result.data:
        # Aggregate clicks and impressions by finish
        finish_stats: dict[str, dict] = {}
        for row in result.data:
            fc = row["finish_code"]
            if fc not in finish_stats:
                finish_stats[fc] = {
                    "finish": row["finish"],
                    "finish_code": fc,
                    "total_clicks": 0,
                    "total_impressions": 0,
                }
            finish_stats[fc]["total_clicks"] += row.get("clicks") or 0
            finish_stats[fc]["total_impressions"] += row.get("impressions") or 0

        if finish_stats:
            # Sort by clicks desc, then impressions desc
            sorted_finishes = sorted(
                finish_stats.values(),
                key=lambda x: (x["total_clicks"], x["total_impressions"]),
                reverse=True,
            )
            best = sorted_finishes[0]
            if best["total_clicks"] > 0 or best["total_impressions"] > 0:
                print(
                    f"  Selected finish {best['finish']} ({best['finish_code']}) "
                    f"with {best['total_clicks']} clicks, {best['total_impressions']} impressions"
                )
                return best["finish"], best["finish_code"]

    # Fallback: get first finish alphabetically from variant_index
    vi_result = (
        supabase_client.table("variant_index")
        .select("finish, finish_code")
        .eq("master_sku", master_sku)
        .not_.is_("finish", "null")
        .not_.is_("finish_code", "null")
        .order("finish_code")
        .limit(1)
        .execute()
    )

    if vi_result.data:
        row = vi_result.data[0]
        print(f"  No search data, falling back to first finish: {row['finish']} ({row['finish_code']})")
        return row["finish"], row["finish_code"]

    # Final fallback
    print("  No finish data found, defaulting to ABR")
    return "Antique Brass", "ABR"


def upload_lifestyle_image_to_storage(
    image_path: Path,
    master_sku: str,
    variation_num: int,
    supabase_client,
) -> str:
    """Upload a lifestyle image to Supabase Storage.

    Args:
        image_path: Path to the local image file.
        master_sku: Master SKU identifier.
        variation_num: Variation number (1-N).
        supabase_client: Supabase client instance.

    Returns:
        Public URL of the uploaded image.
    """
    image_path = Path(image_path)
    safe_sku = master_sku.replace("/", "-")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    storage_path = f"{safe_sku}_var{variation_num}_{timestamp}.png"

    with open(image_path, "rb") as f:
        file_bytes = f.read()

    supabase_client.storage.from_("lifestyle-images").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "image/png"},
    )

    public_url = supabase_client.storage.from_("lifestyle-images").get_public_url(
        storage_path
    )
    print(f"  ✓ Uploaded to storage: {storage_path}")
    return public_url


def save_lifestyle_image_to_db(
    master_sku: str,
    shopify_product_id: str,
    finish: str,
    finish_code: str,
    gmc_offer_id: str,
    image_url: str,
    variation_num: int,
    ai_selected: bool,
    score: Optional[float],
    prompt: str,
    supabase_client,
) -> tuple[str, str]:
    """Insert records into product_lifestyle_images and variant_lifestyle_images.

    Args:
        master_sku: Master SKU identifier.
        shopify_product_id: Shopify product ID (required for product_lifestyle_images).
        finish: Full finish name.
        finish_code: Short finish code.
        gmc_offer_id: GMC offer ID for the variant.
        image_url: Supabase Storage public URL.
        variation_num: Variation number (1-N).
        ai_selected: Whether this is the AI-selected best image.
        score: Quality score (0-100) if available.
        prompt: Generation prompt used.
        supabase_client: Supabase client instance.

    Returns:
        (product_image_id, variant_image_id) tuple.
    """
    now = datetime.now().isoformat()

    # Upsert into product_lifestyle_images to keep generation idempotent on reruns.
    # Unique key: (master_sku, variation_index)
    product_result = (
        supabase_client.table("product_lifestyle_images")
        .upsert(
            {
                "master_sku": master_sku,
                "shopify_product_id": shopify_product_id,
                "variation_index": variation_num,
                "image_url": image_url,
                "approval_status": "pending",
                "ai_selected": ai_selected,
                "user_selected": False,
                "score": score,
                "prompt": prompt[:5000],
                "generation_model": AI_SYSTEM_VERSION,
                "generation_timestamp": now,
            },
            on_conflict="master_sku,variation_index",
            ignore_duplicates=False,
        )
        .execute()
    )
    product_image_id = product_result.data[0]["id"] if product_result.data else ""

    # Upsert into variant_lifestyle_images to keep generation idempotent on reruns.
    # Unique key: (gmc_offer_id, variation_index)
    variant_result = (
        supabase_client.table("variant_lifestyle_images")
        .upsert(
            {
                "master_sku": master_sku,
                "gmc_offer_id": gmc_offer_id,
                "finish": finish,
                "finish_code": finish_code,
                "variation_index": variation_num,
                "image_url": image_url,
                "approval_status": "pending",
                "ai_selected": ai_selected,
                "user_selected": False,
                "score": score,
                "prompt": prompt[:5000],
                "generation_model": AI_SYSTEM_VERSION,
                "generation_timestamp": now,
            },
            on_conflict="gmc_offer_id,variation_index",
            ignore_duplicates=False,
        )
        .execute()
    )
    variant_image_id = variant_result.data[0]["id"] if variant_result.data else ""

    print(f"  ✓ Saved to DB: product={product_image_id}, variant={variant_image_id}")
    return product_image_id, variant_image_id


def generate_lifestyle_images_for_sku(
    master_sku: str,
    num_variations: int = 3,
    dry_run: bool = False,
    force_finish_code: str | None = None,
) -> dict:
    """Generate lifestyle images for a SKU with smart finish selection.

    Steps:
    1. Load product data from Supabase
    2. Select best finish using Google Ads data (or use force_finish_code if provided)
    3. Generate images using LifestyleImageGenerator (existing code)
    4. Score images and select best variation
    5. Upload to Supabase Storage
    6. Insert into database tables

    Args:
        master_sku: Master SKU to generate images for.
        num_variations: Number of image variations to generate (1-5).
        dry_run: If True, generate images but don't upload/save.
        force_finish_code: If set, override auto-selection and use this finish_code directly.

    Returns:
        Dict with generation summary.
    """
    from feedops.db.supabase_client import get_client

    supabase = get_client()
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    print(f"\n{'='*70}")
    print(f"Smart Lifestyle Image Generation for {master_sku}")
    print(f"{'='*70}")

    # Step 1: Load product data
    product_rows = (
        supabase.table("product_catalog")
        .select("*")
        .eq("master_sku", master_sku)
        .order("position")
        .execute()
    )
    if not product_rows.data:
        raise ValueError(f"SKU not found in product_catalog: {master_sku}")

    first_row = product_rows.data[0]
    category = first_row["category"]
    title = first_row["title"]
    style = first_row.get("style") or "modern"

    print(f"  Category: {category}")
    print(f"  Title: {title}")

    # Step 2: Select best finish
    if force_finish_code:
        # User explicitly selected a finish — look it up in variant_index
        vi_forced = (
            supabase.table("variant_index")
            .select("finish, finish_code")
            .eq("master_sku", master_sku)
            .eq("finish_code", force_finish_code)
            .limit(1)
            .execute()
        )
        if vi_forced.data:
            selected_finish = vi_forced.data[0]["finish"]
            selected_finish_code = vi_forced.data[0]["finish_code"]
            print(f"  Using user-selected finish: {selected_finish} ({selected_finish_code})")
        else:
            print(f"  Forced finish_code {force_finish_code} not found, falling back to auto-select")
            print("\nSelecting best finish based on Google Ads data...")
            selected_finish, selected_finish_code = select_best_finish_for_generation(
                master_sku, supabase
            )
    else:
        print("\nSelecting best finish based on Google Ads data...")
        selected_finish, selected_finish_code = select_best_finish_for_generation(
            master_sku, supabase
        )

    # Step 3: Get variant info for selected finish
    vi_result = (
        supabase.table("variant_index")
        .select("gmc_offer_id, shopify_product_id, shopify_variant_id")
        .eq("master_sku", master_sku)
        .eq("finish_code", selected_finish_code)
        .limit(1)
        .execute()
    )
    if not vi_result.data:
        raise ValueError(
            f"No variant found for {master_sku} with finish {selected_finish_code}"
        )

    variant_info = vi_result.data[0]
    gmc_offer_id = variant_info["gmc_offer_id"]
    shopify_product_id = variant_info.get("shopify_product_id") or ""

    # Step 4: Get reference images for the selected finish
    finish_rows = [
        r for r in product_rows.data if r.get("finish_code") == selected_finish_code
    ]
    if not finish_rows:
        # Fallback to first variant's images
        finish_rows = [first_row]

    ref_row = finish_rows[0]
    product_image_urls = []
    for field in ["main_image_url", "alt_image_1", "alt_image_2", "alt_image_3", "alt_image_4"]:
        url = ref_row.get(field)
        if url and url not in product_image_urls:
            product_image_urls.append(url)

    if not product_image_urls:
        raise ValueError(f"No reference images found for {master_sku}")

    print(f"  Using {len(product_image_urls)} reference images from {selected_finish} finish")

    # Step 5: Build prompts using existing helpers
    inventory = get_product_inventory(category, title)
    scene = get_customer_focused_scene(
        category=category, style=style, product_title=title
    )
    technical = get_technical_specs(style)

    # Step 6: Generate images
    output_dir = Path(
        os.environ.get("LIFESTYLE_IMAGES_OUTPUT_DIR", "/tmp/lifestyle_images")
    )
    generator = LifestyleImageGenerator(api_key=gemini_api_key, output_dir=output_dir)
    lifestyle_results = generator.generate_for_product(
        product_image_urls=product_image_urls,
        master_sku=master_sku,
        inventory=inventory,
        scene=scene,
        technical=technical,
        category=category,
        num_variations=num_variations,
    )

    successful_results = [r for r in lifestyle_results if r.generation_success]
    if not successful_results:
        return {
            "master_sku": master_sku,
            "selected_finish": selected_finish,
            "selected_finish_code": selected_finish_code,
            "images_generated": 0,
            "image_ids": [],
            "best_variation_num": None,
            "message": "All image generation attempts failed",
        }

    # Step 7: Score images and select best
    best_variation_num = None
    scores_by_variation: dict[int, float] = {}

    ai_select_enabled = (
        os.environ.get("LIFESTYLE_IMAGE_AI_SELECT", "true").lower() == "true"
    )
    if ai_select_enabled and len(successful_results) > 1:
        best_variation_num, image_scores = select_best_lifestyle_image(
            image_results=lifestyle_results,
            reference_image_url=product_image_urls[0],
            category=category,
            api_key=gemini_api_key,
        )
        for s in image_scores:
            if s.evaluation_success:
                scores_by_variation[s.variation_num] = s.composite_score

    if best_variation_num is None:
        best_variation_num = successful_results[0].variation_num

    # Step 8: Upload and save (if not dry_run)
    image_ids = []
    if not dry_run:
        for result in successful_results:
            is_best = result.variation_num == best_variation_num
            score = scores_by_variation.get(result.variation_num)

            # Upload to Supabase Storage
            public_url = upload_lifestyle_image_to_storage(
                image_path=Path(result.image_path),
                master_sku=master_sku,
                variation_num=result.variation_num,
                supabase_client=supabase,
            )

            # Save to database
            product_id, variant_id = save_lifestyle_image_to_db(
                master_sku=master_sku,
                shopify_product_id=shopify_product_id,
                finish=selected_finish,
                finish_code=selected_finish_code,
                gmc_offer_id=gmc_offer_id,
                image_url=public_url,
                variation_num=result.variation_num,
                ai_selected=is_best,
                score=score,
                prompt=result.prompt_used,
                supabase_client=supabase,
            )
            image_ids.append(product_id)

    return {
        "master_sku": master_sku,
        "selected_finish": selected_finish,
        "selected_finish_code": selected_finish_code,
        "images_generated": len(successful_results),
        "image_ids": image_ids,
        "best_variation_num": best_variation_num,
        "message": f"Generated {len(successful_results)} images for {selected_finish} finish",
    }
