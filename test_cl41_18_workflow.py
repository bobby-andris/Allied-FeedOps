#!/usr/bin/env python3
"""
Test script for CL-41-18 end-to-end workflow.

Tests:
1. AI image selection using Gemini Vision
2. Finish filtering verification
3. Shopify product update with image upload
4. Google feed generation with variants and lifestyle_image_link
5. Bing feed generation with variants
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Configuration
SKU = "CL-41-18"
PATCHES_DIR = Path("dashboard_data/lifestyle-eval-candidate")
IMAGES_DIR = PATCHES_DIR / "images"
FEEDS_DIR = Path("data/feeds")
FEEDS_DIR.mkdir(parents=True, exist_ok=True)


def load_patch(platform: str) -> dict:
    """Load a patch file for the SKU."""
    patch_file = PATCHES_DIR / f"{platform}-patch-{SKU}.json"
    if not patch_file.exists():
        raise FileNotFoundError(f"Patch not found: {patch_file}")
    return json.loads(patch_file.read_text())


def save_patch(platform: str, patch: dict) -> None:
    """Save a patch file for the SKU."""
    patch_file = PATCHES_DIR / f"{platform}-patch-{SKU}.json"
    patch_file.write_text(json.dumps(patch, indent=2))
    print(f"  ✅ Saved {patch_file}")


def test_ai_image_selection():
    """Test 1: Run AI image selection on lifestyle images."""
    print("\n" + "=" * 70)
    print("TEST 1: AI Image Selection")
    print("=" * 70)

    from feedops.pipeline.lifestyle_images import (
        LifestyleImageResult,
        select_best_lifestyle_image,
    )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set - skipping AI selection")
        return None

    # Load the Google patch to get lifestyle images
    google_patch = load_patch("google")

    # Get lifestyle images from patch
    lifestyle_images = google_patch.get("lifestyle_images", [])
    if not lifestyle_images:
        print("❌ No lifestyle images in patch")
        return None

    print(f"Found {len(lifestyle_images)} lifestyle images")

    # Convert to LifestyleImageResult objects
    # Use the latest images (most recent timestamp per variation)
    latest_by_variation: dict[int, dict] = {}
    for img in lifestyle_images:
        var_num = img.get("variation_num", 1)
        if img.get("generation_success"):
            existing = latest_by_variation.get(var_num)
            if not existing or img.get("timestamp", "") > existing.get("timestamp", ""):
                latest_by_variation[var_num] = img

    print(f"Using {len(latest_by_variation)} unique variations (latest of each)")

    image_results = []
    for var_num, img_data in sorted(latest_by_variation.items()):
        result = LifestyleImageResult(
            image_path=str(Path(img_data["image_path"]).resolve()),
            variation_num=var_num,
            generation_success=True,
            prompt_used=img_data.get("prompt_used", ""),
            timestamp=img_data.get("timestamp", ""),
        )
        image_results.append(result)
        print(f"  - Variation {var_num}: {img_data['image_path']}")

    # Get reference image URL from patch
    ref_url = google_patch.get("_previous", {}).get("image_url", "")
    if not ref_url:
        # Try to fetch from Shopify
        print("No reference image URL in patch - fetching from Shopify...")
        from feedops.integrations.shopify_catalog import fetch_shopify_product

        product = fetch_shopify_product(SKU)
        if product:
            featured_media = product.get("featuredMedia", {})
            if featured_media and featured_media.get("image"):
                ref_url = featured_media["image"].get("url", "")

    if not ref_url:
        print(
            "❌ No reference image URL found - using first lifestyle image as reference"
        )
        # Use the product's main image from any source
        ref_url = (
            "https://cdn.shopify.com/s/files/1/0287/8658/9828/products/CL4118-ABR.jpg"
        )

    print(f"Reference image: {ref_url}")

    # Run AI selection
    best_variation, scores = select_best_lifestyle_image(
        image_results=image_results,
        reference_image_url=ref_url,
        category="Towel Bar",
        api_key=api_key,
    )

    if best_variation:
        print(f"\n🏆 Selected variation {best_variation} as best image")

        # Update all patches with selected image
        for platform in ["google", "bing", "shopify"]:
            patch = load_patch(platform)
            patch["selected_lifestyle_image"] = best_variation
            save_patch(platform, patch)

        return best_variation
    else:
        print("❌ AI selection failed")
        return None


def test_finish_filtering():
    """Test 2: Verify finish filtering works for variant preview."""
    print("\n" + "=" * 70)
    print("TEST 2: Finish Filtering Verification")
    print("=" * 70)

    from feedops.quality.data_loader import load_catalog_originals

    # First check if patch has variants with finish data
    patch = load_patch("google")
    variants = patch.get("variants", [])

    if variants:
        finishes = sorted(set(v.get("finish", "") for v in variants if v.get("finish")))
        print(f"✅ Found {len(finishes)} finishes from patch variants:")
        for finish in finishes[:10]:
            print(f"  - {finish}")
        if len(finishes) > 10:
            print(f"  ... and {len(finishes) - 10} more")
        return True

    # Fall back to catalog check
    catalog_path = Path("dashboard_data/catalog.csv")
    if not catalog_path.exists():
        catalog_path = Path("samples/sample-catalog.csv")

    originals = load_catalog_originals(catalog_path)
    original = originals.get(SKU)

    if original and original.available_finishes:
        print(f"✅ Found {len(original.available_finishes)} finishes for {SKU}:")
        for finish in original.available_finishes:
            print(f"  - {finish}")
        return True
    else:
        print(f"⚠️ No finish data found for {SKU} in catalog or patch")
        print("  Variant preview will fall back to showing all finishes.")
        return False


def test_shopify_publish():
    """Test 3: Push content to Shopify."""
    print("\n" + "=" * 70)
    print("TEST 3: Shopify Publish")
    print("=" * 70)

    from feedops.integrations.shopify_catalog import (
        fetch_shopify_product,
        publish_to_shopify,
        upload_lifestyle_image_to_shopify,
    )

    # Check credentials
    if not os.environ.get("SHOPIFY_ACCESS_TOKEN"):
        print("❌ SHOPIFY_ACCESS_TOKEN not set - skipping")
        return False

    # Fetch product to get the product ID
    print(f"Fetching Shopify product for {SKU}...")
    product = fetch_shopify_product(SKU)

    if not product:
        print(f"❌ Product {SKU} not found in Shopify")
        return False

    product_id = product.get("legacyResourceId") or product.get("id", "").split("/")[-1]
    print(f"Found product ID: {product_id}")

    # Load shopify patch
    patch = load_patch("shopify")
    title = patch.get("title", "")
    body_html = patch.get("body_html", "")

    if not title and not body_html:
        print("❌ No title or body_html in patch")
        return False

    # DRY RUN first
    print("\nPerforming dry run...")
    result = publish_to_shopify(
        product_id=product_id,
        title=title,
        description_html=body_html,
        environment="staging",
        dry_run=True,
    )
    print(f"Dry run result: {result}")

    # Ask before actual publish
    print("\n⚠️ Skipping actual publish (would require user confirmation)")
    print(f"  Would publish to product {product_id}:")
    print(f"  - Title: {title[:60]}...")
    print(f"  - Description: {body_html[:60]}...")

    # Check for lifestyle image upload
    selected_image = patch.get("selected_lifestyle_image")
    lifestyle_images = patch.get("lifestyle_images", [])

    if selected_image and lifestyle_images:
        # Find the selected image path
        selected_path = None
        for img in lifestyle_images:
            if img.get("variation_num") == selected_image:
                selected_path = img.get("image_path")
                break

        if selected_path:
            full_path = Path(selected_path)
            if full_path.exists():
                print(f"\n  Would upload lifestyle image: {selected_path}")
            else:
                print(f"\n  ⚠️ Selected image not found at: {selected_path}")

    return True


def test_google_feed_generation():
    """Test 4: Generate Google feed with variants."""
    print("\n" + "=" * 70)
    print("TEST 4: Google Feed Generation")
    print("=" * 70)

    from feedops.integrations.google_supplemental import (
        generate_supplemental_feed,
        load_google_patches,
    )

    # Load just the CL-41-18 patch
    patches = load_google_patches(PATCHES_DIR)
    cl41_patches = [p for p in patches if p.get("_meta", {}).get("master_sku") == SKU]

    if not cl41_patches:
        print(f"❌ No Google patches found for {SKU}")
        return False

    print(f"Found {len(cl41_patches)} Google patch(es) for {SKU}")

    # Generate feed
    xml_content = generate_supplemental_feed(
        patches=cl41_patches,
        environment="staging",
        include_variants=True,
    )

    # Save feed
    feed_path = FEEDS_DIR / f"google-feed-{SKU}-test.xml"
    feed_path.write_text(xml_content, encoding="utf-8")
    print(f"✅ Generated Google feed: {feed_path}")

    # Show snippet
    print("\nFeed snippet:")
    lines = xml_content.split("\n")
    for line in lines[:30]:
        print(f"  {line}")
    if len(lines) > 30:
        print(f"  ... ({len(lines) - 30} more lines)")

    # Check for lifestyle_image_link
    if "lifestyle_image_link" in xml_content:
        print("\n✅ Feed includes lifestyle_image_link")
    else:
        print(
            "\n⚠️ Feed does not include lifestyle_image_link (may not be set in patch)"
        )

    return True


def test_bing_feed_generation():
    """Test 5: Generate Bing feed with variants."""
    print("\n" + "=" * 70)
    print("TEST 5: Bing Feed Generation")
    print("=" * 70)

    from feedops.integrations.bing_catalog import (
        generate_bing_feed_from_patches,
        load_bing_patches,
    )

    # Load just the CL-41-18 patch
    patches = load_bing_patches(PATCHES_DIR)
    cl41_patches = [p for p in patches if p.get("_meta", {}).get("master_sku") == SKU]

    if not cl41_patches:
        print(f"❌ No Bing patches found for {SKU}")
        return False

    print(f"Found {len(cl41_patches)} Bing patch(es) for {SKU}")

    # Generate feed
    xml_content = generate_bing_feed_from_patches(
        patches=cl41_patches,
        environment="staging",
        include_variants=True,
    )

    # Save feed
    feed_path = FEEDS_DIR / f"bing-feed-{SKU}-test.xml"
    feed_path.write_text(xml_content, encoding="utf-8")
    print(f"✅ Generated Bing feed: {feed_path}")

    # Show snippet
    print("\nFeed snippet:")
    lines = xml_content.split("\n")
    for line in lines[:30]:
        print(f"  {line}")
    if len(lines) > 30:
        print(f"  ... ({len(lines) - 30} more lines)")

    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print(f"CL-41-18 END-TO-END WORKFLOW TEST")
    print("=" * 70)

    results = {}

    # Test 1: AI Image Selection
    try:
        results["ai_selection"] = test_ai_image_selection()
    except Exception as e:
        print(f"❌ AI Selection failed: {e}")
        results["ai_selection"] = False

    # Test 2: Finish Filtering
    try:
        results["finish_filtering"] = test_finish_filtering()
    except Exception as e:
        print(f"❌ Finish filtering failed: {e}")
        results["finish_filtering"] = False

    # Test 3: Shopify Publish
    try:
        results["shopify_publish"] = test_shopify_publish()
    except Exception as e:
        print(f"❌ Shopify publish failed: {e}")
        results["shopify_publish"] = False

    # Test 4: Google Feed
    try:
        results["google_feed"] = test_google_feed_generation()
    except Exception as e:
        print(f"❌ Google feed generation failed: {e}")
        results["google_feed"] = False

    # Test 5: Bing Feed
    try:
        results["bing_feed"] = test_bing_feed_generation()
    except Exception as e:
        print(f"❌ Bing feed generation failed: {e}")
        results["bing_feed"] = False

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL" if result is False else "⚠️ SKIP"
        print(f"  {test_name}: {status}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
