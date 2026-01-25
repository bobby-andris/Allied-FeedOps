#!/usr/bin/env python3
"""Test lifestyle image integration with FeedOps pipeline."""

import asyncio
import os
from pathlib import Path

# Set environment variables for testing
os.environ["LIFESTYLE_IMAGES_ENABLED"] = "true"
os.environ["LIFESTYLE_IMAGES_NUM_VARIATIONS"] = "3"
os.environ["LIFESTYLE_IMAGES_OUTPUT_DIR"] = "data/lifestyle_images"
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "")

from feedops.pipeline.optimize import optimize_parent_sku


async def test_single_product():
    """Test lifestyle image generation for a single product."""

    print("="*80)
    print("Testing Lifestyle Image Integration")
    print("="*80)

    # Test with a known product (Argo collection, MasterSKU 101)
    master_sku = "101"  # Argo Towel Bar
    catalog_path = Path("data/catalog/Product Catalog.csv")

    if not catalog_path.exists():
        print(f"❌ Catalog not found: {catalog_path}")
        return

    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set")
        return

    print(f"\nOptimizing MasterSKU: {master_sku}")
    print(f"Catalog: {catalog_path}")
    print(f"Lifestyle images: Enabled")
    print()

    try:
        result = await optimize_parent_sku(
            master_sku=master_sku,
            catalog_path=catalog_path,
            dry_run=False,
            output_dir="reports",
            exports_dir="exports",
        )

        print("\n" + "="*80)
        print("✅ Optimization Complete")
        print("="*80)

        print(f"\nMasterSKU: {result.master_sku}")
        print(f"Quality Score: {result.candidate.final_score.composite}%")
        print(f"Status: {result.candidate.final_score.approval_status}")

        # Check lifestyle images
        if result.candidate.lifestyle_images:
            print(f"\n🖼️  Lifestyle Images: {len(result.candidate.lifestyle_images)} variations")
            for img in result.candidate.lifestyle_images:
                status = "✅" if img.generation_success else "❌"
                print(f"  {status} Variation {img.variation_num}: {img.image_path}")
                if not img.generation_success and img.error_message:
                    print(f"     Error: {img.error_message}")
        else:
            print("\n⚠️  No lifestyle images generated")

        # Check JSON exports
        print(f"\n📄 JSON Exports:")
        exports_dir = Path("exports")
        safe_sku = master_sku.replace("/", "-")

        for platform in ["google", "bing", "shopify"]:
            patch_path = exports_dir / f"{platform}-patch-{safe_sku}.json"
            if patch_path.exists():
                print(f"  ✅ {platform}: {patch_path}")

                # Check if lifestyle_images is in the JSON
                import json
                data = json.loads(patch_path.read_text())
                if "lifestyle_images" in data:
                    print(f"     └─ Contains lifestyle_images: {len(data['lifestyle_images'])} variations")
                else:
                    print(f"     └─ No lifestyle_images field")
            else:
                print(f"  ❌ {platform}: Not found")

        print(f"\n📊 Report: {exports_dir.parent / 'reports' / f'sku-{safe_sku}-{result.timestamp}.md'}")

        print("\n" + "="*80)
        print("Next steps:")
        print("1. Check that images exist in data/lifestyle_images/")
        print("2. Run the Streamlit dashboard to view them:")
        print("   streamlit run src/feedops/quality/review_dashboard.py")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Error during optimization:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_single_product())
