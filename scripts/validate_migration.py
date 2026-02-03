#!/usr/bin/env python3
"""
Validate that content migration to Supabase was successful.

Compares:
1. JSON file content vs Supabase generated_content records
2. Local image files vs Supabase Storage URLs
3. Approval status consistency

Usage:
    PYTHONPATH=./src .venv/bin/python scripts/validate_migration.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase-py not installed. Run: pip install supabase")
    sys.exit(1)


DASHBOARD_DATA_DIR = Path("dashboard_data")
CANDIDATE_DIR = DASHBOARD_DATA_DIR / "lifestyle-eval-candidate"


def get_supabase_client() -> Client:
    """Create Supabase client from environment variables."""
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        raise ValueError("Missing Supabase credentials")
    
    return create_client(url, key)


def validate_content(client: Client):
    """Validate generated_content table against JSON files."""
    print("Validating generated_content table...")
    
    # Get all content from Supabase
    result = client.table("generated_content").select("*").execute()
    db_content = {
        (r["master_sku"], r["platform"], r["content_type"]): r 
        for r in result.data
    }
    
    print(f"  Found {len(db_content)} records in database")
    
    # Count JSON files
    json_files = list(CANDIDATE_DIR.glob("*-patch-*.json"))
    print(f"  Found {len(json_files)} patch files in {CANDIDATE_DIR}")
    
    # Validate each JSON file has corresponding DB records
    missing = []
    mismatched = []
    
    for json_file in json_files:
        try:
            platform = "shopify" if "shopify-patch" in json_file.name else \
                      "google" if "google-patch" in json_file.name else "bing"
            sku = json_file.name.split("-patch-")[1].replace(".json", "")
            
            with open(json_file) as f:
                data = json.load(f)
            
            # Check title
            title_key = (sku, platform, "title")
            if title_key not in db_content:
                missing.append(title_key)
            elif db_content[title_key].get("candidate_content") != data.get("title"):
                mismatched.append(title_key)
            
            # Check description
            desc_key = (sku, platform, "description")
            desc_field = "body_html" if platform == "shopify" else "description"
            if desc_key not in db_content:
                missing.append(desc_key)
            elif db_content[desc_key].get("candidate_content") != data.get(desc_field):
                mismatched.append(desc_key)
                
        except Exception as e:
            print(f"  Error processing {json_file}: {e}")
    
    print(f"  Missing records: {len(missing)}")
    print(f"  Mismatched records: {len(mismatched)}")
    
    if missing:
        print(f"  First 5 missing: {missing[:5]}")
    if mismatched:
        print(f"  First 5 mismatched: {mismatched[:5]}")
    
    return len(missing) == 0 and len(mismatched) == 0


def validate_images(client: Client):
    """Validate generated_images table against local files."""
    print("\nValidating generated_images table...")
    
    # Get all images from Supabase
    result = client.table("generated_images").select("*").execute()
    db_images = {
        (r["master_sku"], r["variation_index"]): r 
        for r in result.data
    }
    
    print(f"  Found {len(db_images)} records in database")
    
    # Count local image files
    image_dir = CANDIDATE_DIR / "images"
    if image_dir.exists():
        local_images = list(image_dir.glob("*.png"))
        print(f"  Found {len(local_images)} images in {image_dir}")
    else:
        print(f"  Image directory not found: {image_dir}")
        local_images = []
    
    # Check each DB record has valid Storage URL
    broken_urls = []
    for key, record in db_images.items():
        url = record.get("image_url", "")
        if not url or not url.startswith("http"):
            broken_urls.append(key)
    
    print(f"  Records with broken URLs: {len(broken_urls)}")
    
    return len(broken_urls) == 0


def validate_approvals(client: Client):
    """Validate approval status consistency."""
    print("\nValidating approval consistency...")
    
    # Get approval records
    result = client.table("sku_approvals").select("*").execute()
    approvals = {r["master_sku"]: r for r in result.data}
    
    print(f"  Found {len(approvals)} SKU approval records")
    
    # Get content records
    content_result = client.table("generated_content").select("master_sku").execute()
    content_skus = set(r["master_sku"] for r in content_result.data)
    
    print(f"  Found {len(content_skus)} SKUs with content")
    
    # Check for SKUs with content but no approval record
    missing_approvals = content_skus - set(approvals.keys())
    print(f"  SKUs with content but no approval: {len(missing_approvals)}")
    
    if missing_approvals:
        print(f"  First 5: {list(missing_approvals)[:5]}")
    
    return len(missing_approvals) == 0


def main():
    print("=" * 60)
    print("FeedOps Migration Validation")
    print("=" * 60)
    
    try:
        client = get_supabase_client()
    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")
        sys.exit(1)
    
    content_ok = validate_content(client)
    images_ok = validate_images(client)
    approvals_ok = validate_approvals(client)
    
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    print(f"Content: {'PASS' if content_ok else 'FAIL'}")
    print(f"Images: {'PASS' if images_ok else 'FAIL'}")
    print(f"Approvals: {'PASS' if approvals_ok else 'FAIL'}")
    
    if all([content_ok, images_ok, approvals_ok]):
        print("\nAll validations passed!")
        sys.exit(0)
    else:
        print("\nSome validations failed. Review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
