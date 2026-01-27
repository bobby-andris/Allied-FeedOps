#!/usr/bin/env python3
"""Test customer-focused lifestyle image improvements.

This script tests the enhanced context system with 5 representative products:
1. Paper towel holder (should show KITCHEN, not bathroom)
2. Four-tier towel bar (should show 4+ towels, not 1-2)
3. Three-tier corner shelf (should show 8-12 shower products)
4. Glass shelf (should show toiletries ON shelf, not towels draped over)
5. Heated towel rack (should show multiple folded towels)
"""

import asyncio
import os
from pathlib import Path

# Set environment variables
os.environ["LIFESTYLE_IMAGES_ENABLED"] = "true"
os.environ["LIFESTYLE_IMAGES_NUM_VARIATIONS"] = "3"
os.environ["LIFESTYLE_IMAGES_OUTPUT_DIR"] = "data/lifestyle_images_customer_focused"
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "")

from feedops.pipeline.optimize import optimize_parent_sku


# Test products representing key improvements
TEST_PRODUCTS = {
    "1051": {
        "name": "Paper Towel Holder (Countertop)",
        "expected": "KITCHEN context with cooking/food prep visible",
        "check": "Should be in kitchen, NOT bathroom. Look for counter, sink, cooking area"
    },
    "1052": {
        "name": "Paper Towel Holder (Countertop)",
        "expected": "KITCHEN context with cooking/food prep visible",
        "check": "Should be in kitchen, NOT bathroom. Look for counter, sink, cooking area"
    },
    # Note: Need to find actual SKUs for these products
    # "TD-22": {
    #     "name": "Four-Tier Heated Towel Rack",
    #     "expected": "4-5 towels showing full capacity, family bathroom context",
    #     "check": "Should show ALL FOUR bars with towels, different colors for family members"
    # },
    # "RC-5-16TB": {
    #     "name": "Three-Tier Corner Shelf",
    #     "expected": "8-12 shower products organized across shelves",
    #     "check": "Should show full shower storage with bottles, soaps, razors, loofahs"
    # },
}


async def test_product(master_sku: str, product_info: dict):
    """Test single product with customer-focused improvements."""

    print(f"\n{'='*80}")
    print(f"Testing: {product_info['name']} (SKU: {master_sku})")
    print(f"{'='*80}")
    print(f"Expected: {product_info['expected']}")
    print(f"Check: {product_info['check']}")
    print()

    catalog_path = Path("data/catalog/Product Catalog.csv")

    try:
        result = await optimize_parent_sku(
            master_sku=master_sku,
            catalog_path=catalog_path,
            dry_run=False,
            output_dir="reports/customer_focused",
            exports_dir="exports/customer_focused",
        )

        print(f"\n{'='*70}")
        print("✅ Generation Complete")
        print(f"{'='*70}")

        print(f"\nProduct: {result.master_sku}")
        print(f"Quality Score: {result.candidate.final_score.composite}%")

        # Check lifestyle images
        if result.candidate.lifestyle_images:
            successful = [img for img in result.candidate.lifestyle_images if img.generation_success]
            print(f"\n🖼️  Lifestyle Images: {len(successful)}/{len(result.candidate.lifestyle_images)} successful")

            for img in successful:
                print(f"\n  ✅ Variation {img.variation_num}:")
                print(f"     Path: {img.image_path}")
                if Path(img.image_path).exists():
                    print(f"     Size: {Path(img.image_path).stat().st_size // 1024} KB")
                print(f"     Timestamp: {img.timestamp}")

            # Show validation prompt for user
            print(f"\n📋 VALIDATION CHECKLIST:")
            print(f"   □ {product_info['check']}")
            print(f"   □ Product detail accuracy 90%+")
            print(f"   □ Scene matches customer use case")
            print(f"   □ Capacity properly demonstrated")

            print(f"\n💡 View images:")
            print(f"   open {Path(img.image_path).parent}")

        else:
            print("\n⚠️  No lifestyle images generated")

        return result

    except Exception as e:
        print(f"\n❌ Error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run tests for all products."""

    print(f"\n{'='*80}")
    print("Customer-Focused Lifestyle Image Improvements Test")
    print(f"{'='*80}")

    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set")
        return

    catalog_path = Path("data/catalog/Product Catalog.csv")
    if not catalog_path.exists():
        print(f"❌ Catalog not found: {catalog_path}")
        return

    print(f"\n📊 Testing {len(TEST_PRODUCTS)} products")
    print(f"Output directory: data/lifestyle_images_customer_focused/")
    print()

    results = {}
    for master_sku, product_info in TEST_PRODUCTS.items():
        result = await test_product(master_sku, product_info)
        results[master_sku] = result

        # Pause between products
        await asyncio.sleep(2)

    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")

    successful = sum(1 for r in results.values() if r is not None)
    print(f"\nProducts processed: {successful}/{len(TEST_PRODUCTS)}")

    total_images = sum(
        len([img for img in r.candidate.lifestyle_images if img.generation_success])
        for r in results.values()
        if r and r.candidate.lifestyle_images
    )
    print(f"Total images generated: {total_images}")

    print(f"\n📂 Review all images:")
    print(f"   open data/lifestyle_images_customer_focused/")

    print(f"\n🎯 Next Steps:")
    print(f"   1. Review generated images against validation checklists")
    print(f"   2. Compare to previous images in dashboard_data/lifestyle-eval-candidate-new/images")
    print(f"   3. Verify improvements:")
    print(f"      - Paper towel holders in KITCHEN (not bathroom)")
    print(f"      - Multi-tier products showing FULL capacity")
    print(f"      - Corner shelves with 8-12 products (not empty)")
    print(f"   4. If improvements confirmed, run full batch for all eval SKUs")


if __name__ == "__main__":
    asyncio.run(main())
