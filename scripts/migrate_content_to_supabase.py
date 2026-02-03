#!/usr/bin/env python3
"""
Migrate generated content from JSON files to Supabase.

This script migrates:
1. Title and description content from *-patch-*.json files to generated_content table
2. Lifestyle images to Supabase Storage and generated_images table
3. Quality scores and metadata

Usage:
    PYTHONPATH=./src .venv/bin/python scripts/migrate_content_to_supabase.py --dry-run
    PYTHONPATH=./src .venv/bin/python scripts/migrate_content_to_supabase.py --execute

Requires:
    - SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables
    - Or .env file with these values
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add src to path for imports
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


# Configuration
DASHBOARD_DATA_DIR = Path("dashboard_data")
BASELINE_DIR = DASHBOARD_DATA_DIR / "lifestyle-eval"
CANDIDATE_DIR = DASHBOARD_DATA_DIR / "lifestyle-eval-candidate"
STORAGE_BUCKET = "lifestyle-images"


def get_supabase_client() -> Client:
    """Create Supabase client from environment variables."""
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        raise ValueError(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_SERVICE_KEY "
            "environment variables or add them to .env file."
        )
    
    return create_client(url, key)


def parse_platform_from_filename(filename: str) -> str:
    """Extract platform from patch filename."""
    if filename.startswith("google-patch-"):
        return "google"
    elif filename.startswith("bing-patch-"):
        return "bing"
    elif filename.startswith("shopify-patch-"):
        return "shopify"
    else:
        raise ValueError(f"Unknown platform in filename: {filename}")


def parse_sku_from_filename(filename: str) -> str:
    """Extract SKU from patch filename."""
    # Format: {platform}-patch-{sku}.json
    parts = filename.replace(".json", "").split("-patch-")
    if len(parts) == 2:
        return parts[1]
    raise ValueError(f"Cannot parse SKU from filename: {filename}")


def load_patch_files(directory: Path) -> dict[str, list[dict]]:
    """Load all patch files from a directory, grouped by SKU."""
    patches_by_sku: dict[str, list[dict]] = {}
    
    for json_file in directory.glob("*-patch-*.json"):
        try:
            platform = parse_platform_from_filename(json_file.name)
            sku = parse_sku_from_filename(json_file.name)
            
            with open(json_file, "r") as f:
                data = json.load(f)
            
            data["_source_file"] = str(json_file)
            data["_platform"] = platform
            data["_sku"] = sku
            
            if sku not in patches_by_sku:
                patches_by_sku[sku] = []
            patches_by_sku[sku].append(data)
            
        except Exception as e:
            print(f"Warning: Failed to load {json_file}: {e}")
    
    return patches_by_sku


def extract_content_records(patch: dict, is_candidate: bool) -> list[dict]:
    """Extract generated_content records from a patch file."""
    records = []
    platform = patch.get("_platform")
    sku = patch.get("_sku")
    meta = patch.get("_meta", {})
    previous = patch.get("_previous", {})
    
    # Extract title
    title_record = {
        "master_sku": sku,
        "platform": platform,
        "content_type": "title",
        "quality_score": meta.get("quality_score"),
        "quality_breakdown": meta.get("quality_breakdown") or meta.get("heuristic_score_breakdown"),
        "generation_timestamp": meta.get("generated_at"),
    }
    
    if is_candidate:
        title_record["candidate_content"] = patch.get("title")
        title_record["baseline_content"] = previous.get("title")
    else:
        title_record["baseline_content"] = patch.get("title")
    
    if title_record.get("candidate_content") or title_record.get("baseline_content"):
        records.append(title_record)
    
    # Extract description
    desc_key = "body_html" if platform == "shopify" else "description"
    desc_record = {
        "master_sku": sku,
        "platform": platform,
        "content_type": "description",
        "quality_score": meta.get("quality_score"),
        "quality_breakdown": meta.get("quality_breakdown") or meta.get("heuristic_score_breakdown"),
        "generation_timestamp": meta.get("generated_at"),
    }
    
    if is_candidate:
        desc_record["candidate_content"] = patch.get(desc_key)
        desc_record["baseline_content"] = previous.get("description")
    else:
        desc_record["baseline_content"] = patch.get(desc_key)
    
    if desc_record.get("candidate_content") or desc_record.get("baseline_content"):
        records.append(desc_record)
    
    return records


def extract_image_records(patch: dict) -> list[dict]:
    """Extract generated_images records from a patch file."""
    records = []
    sku = patch.get("_sku")
    lifestyle_images = patch.get("lifestyle_images", [])
    selected_index = patch.get("selected_lifestyle_image")
    
    for img in lifestyle_images:
        if not img.get("generation_success"):
            continue
            
        variation_num = img.get("variation_num", 0)
        records.append({
            "master_sku": sku,
            "variation_index": variation_num - 1 if variation_num > 0 else 0,  # Convert to 0-indexed
            "image_url": img.get("image_path"),  # Will be updated with Storage URL
            "prompt": img.get("prompt_used"),
            "score": img.get("score"),
            "selected": selected_index == variation_num if selected_index else False,
            "generation_model": "gemini-3-pro-image-preview",
            "generation_timestamp": img.get("timestamp"),
        })
    
    return records


def upload_image_to_storage(
    client: Client, 
    local_path: str, 
    sku: str, 
    variation_index: int,
    dry_run: bool = True
) -> Optional[str]:
    """Upload image to Supabase Storage and return public URL."""
    full_path = Path(local_path)
    if not full_path.exists():
        # Try relative to project root
        full_path = Path(__file__).parent.parent / local_path
    
    if not full_path.exists():
        print(f"  Warning: Image not found: {local_path}")
        return None
    
    # Storage path: lifestyle-images/{sku}/{sku}_var{index}.png
    storage_path = f"{sku}/{sku}_var{variation_index}.png"
    
    if dry_run:
        print(f"  [DRY RUN] Would upload {full_path} to {STORAGE_BUCKET}/{storage_path}")
        return f"https://storage.supabase.co/{STORAGE_BUCKET}/{storage_path}"
    
    try:
        with open(full_path, "rb") as f:
            client.storage.from_(STORAGE_BUCKET).upload(
                storage_path,
                f,
                file_options={"content-type": "image/png", "upsert": "true"}
            )
        
        # Get public URL
        url = client.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)
        print(f"  Uploaded: {storage_path}")
        return url
    except Exception as e:
        print(f"  Error uploading {storage_path}: {e}")
        return None


def migrate_content(client: Client, dry_run: bool = True):
    """Migrate all content to Supabase."""
    print("=" * 60)
    print("FeedOps Content Migration to Supabase")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"Baseline dir: {BASELINE_DIR}")
    print(f"Candidate dir: {CANDIDATE_DIR}")
    print()
    
    # Load baseline patches
    print("Loading baseline patches...")
    baseline_patches = load_patch_files(BASELINE_DIR)
    print(f"  Found {len(baseline_patches)} SKUs with baseline data")
    
    # Load candidate patches
    print("Loading candidate patches...")
    candidate_patches = load_patch_files(CANDIDATE_DIR)
    print(f"  Found {len(candidate_patches)} SKUs with candidate data")
    
    # Combine all SKUs
    all_skus = set(baseline_patches.keys()) | set(candidate_patches.keys())
    print(f"\nTotal unique SKUs: {len(all_skus)}")
    print()
    
    # Collect all content records
    content_records: dict[tuple, dict] = {}  # (sku, platform, content_type) -> record
    image_records: dict[tuple, dict] = {}    # (sku, variation_index) -> record
    
    # Process baseline patches
    print("Processing baseline patches...")
    for sku, patches in baseline_patches.items():
        for patch in patches:
            for record in extract_content_records(patch, is_candidate=False):
                key = (record["master_sku"], record["platform"], record["content_type"])
                if key not in content_records:
                    content_records[key] = record
                else:
                    content_records[key]["baseline_content"] = record.get("baseline_content")
    
    # Process candidate patches (may overwrite/merge with baseline)
    print("Processing candidate patches...")
    for sku, patches in candidate_patches.items():
        for patch in patches:
            # Content records
            for record in extract_content_records(patch, is_candidate=True):
                key = (record["master_sku"], record["platform"], record["content_type"])
                if key not in content_records:
                    content_records[key] = record
                else:
                    # Merge candidate data into existing record
                    content_records[key]["candidate_content"] = record.get("candidate_content")
                    content_records[key]["quality_score"] = record.get("quality_score")
                    content_records[key]["quality_breakdown"] = record.get("quality_breakdown")
                    content_records[key]["generation_timestamp"] = record.get("generation_timestamp")
            
            # Image records (only from candidate patches)
            for record in extract_image_records(patch):
                key = (record["master_sku"], record["variation_index"])
                image_records[key] = record
    
    print(f"\nContent records to migrate: {len(content_records)}")
    print(f"Image records to migrate: {len(image_records)}")
    print()
    
    # Migrate content
    print("Migrating content records...")
    content_success = 0
    content_failed = 0
    
    for key, record in content_records.items():
        try:
            if dry_run:
                print(f"  [DRY RUN] Would upsert: {key}")
                content_success += 1
            else:
                client.table("generated_content").upsert(
                    record,
                    on_conflict="master_sku,platform,content_type"
                ).execute()
                content_success += 1
        except Exception as e:
            print(f"  Error migrating {key}: {e}")
            content_failed += 1
    
    print(f"  Content: {content_success} success, {content_failed} failed")
    print()
    
    # Migrate images
    print("Migrating image records...")
    image_success = 0
    image_failed = 0
    
    for key, record in image_records.items():
        sku, variation_index = key
        try:
            # Upload image to storage
            local_path = record.get("image_url", "")
            if local_path:
                storage_url = upload_image_to_storage(
                    client, local_path, sku, variation_index, dry_run
                )
                if storage_url:
                    record["image_url"] = storage_url
            
            if dry_run:
                print(f"  [DRY RUN] Would upsert: {key}")
                image_success += 1
            else:
                client.table("generated_images").upsert(
                    record,
                    on_conflict="master_sku,variation_index"
                ).execute()
                image_success += 1
        except Exception as e:
            print(f"  Error migrating {key}: {e}")
            image_failed += 1
    
    print(f"  Images: {image_success} success, {image_failed} failed")
    print()
    
    # Summary
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Content records: {content_success} migrated, {content_failed} failed")
    print(f"Image records: {image_success} migrated, {image_failed} failed")
    
    if dry_run:
        print("\nThis was a DRY RUN. No data was actually modified.")
        print("Run with --execute to perform the actual migration.")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate FeedOps content from JSON files to Supabase"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be migrated without making changes (default)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the migration"
    )
    
    args = parser.parse_args()
    dry_run = not args.execute
    
    try:
        client = get_supabase_client()
        migrate_content(client, dry_run=dry_run)
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
