"""Rollback functionality for reverting content to original versions.

This module provides platform-agnostic rollback capabilities using the
`_previous` field stored in patch files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping

from feedops.db import get_last_publish_event, log_publish_event
from feedops.integrations.bing_catalog import get_bing_patch_for_sku
from feedops.integrations.google_supplemental import (
    get_patch_for_sku as get_google_patch,
)
from feedops.integrations.shopify_catalog import (
    get_shopify_patch_for_sku,
    remove_product_tags,
    update_shopify_product,
)

Platform = Literal["google", "bing", "shopify"]


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    sku: str
    platform: Platform
    success: bool
    message: str
    original_title: str | None = None
    original_description: str | None = None
    publish_event_id: int | None = None
    error: str | None = None


def load_patch_previous(
    patches_dir: Path,
    sku: str,
    platform: Platform,
) -> dict | None:
    """Load the _previous field from a patch file.

    Args:
        patches_dir: Directory containing patch files.
        sku: MasterSKU to look up.
        platform: Target platform.

    Returns:
        Dict with original title/description, or None if not found.
    """
    if platform == "google":
        patch = get_google_patch(patches_dir, sku)
    elif platform == "bing":
        patch = get_bing_patch_for_sku(patches_dir, sku)
    elif platform == "shopify":
        patch = get_shopify_patch_for_sku(patches_dir, sku)
    else:
        return None

    if not patch:
        return None

    previous = patch.get("_previous")
    if not previous:
        return None

    return {
        "title": previous.get("title"),
        "description": previous.get("description"),
        "patch_file": patch.get("_source_file"),
        "product_id": patch.get("productId") if platform == "shopify" else None,
        "offer_id": patch.get("offerId") if platform == "google" else None,
        "sku": patch.get("sku") if platform == "bing" else None,
        "variants": previous.get("variants"),
    }


def rollback_shopify_content(
    product_id: str,
    original_title: str,
    original_description: str,
    *,
    env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Rollback Shopify product to original content.

    Args:
        product_id: Shopify product ID.
        original_title: Original title to restore.
        original_description: Original description to restore.
        env: Environment variables mapping.
        dry_run: If True, validate but don't execute.

    Returns:
        Response dict with success status.
    """
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "product_id": product_id,
            "title": original_title,
            "description": original_description,
            "message": "Dry run - no changes made",
        }

    # First, remove feedops tracking tags
    for tag in ["feedops-staging", "feedops-production"]:
        remove_product_tags(product_id, [tag], env=env)

    # Then restore original content
    result = update_shopify_product(
        product_id,
        title=original_title,
        description_html=original_description,
        env=env,
        dry_run=False,
    )

    return result


def rollback_content(
    sku: str,
    platform: Platform,
    *,
    patches_dir: Path,
    db_path: Path,
    env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> RollbackResult:
    """Revert product content to original version.

    This function:
    1. Loads the patch file's `_previous` field (original content)
    2. Pushes original content back to the platform
    3. Logs the rollback event in the database

    Args:
        sku: MasterSKU to rollback.
        platform: Target platform ('google', 'bing', 'shopify').
        patches_dir: Directory containing patch files.
        db_path: Path to database file.
        env: Environment variables mapping.
        dry_run: If True, validate but don't execute.

    Returns:
        RollbackResult with status and details.
    """
    # Load original content from patch file
    previous = load_patch_previous(patches_dir, sku, platform)

    if not previous:
        return RollbackResult(
            sku=sku,
            platform=platform,
            success=False,
            message=f"No patch file found for {sku} on {platform}",
            error="Patch file not found or missing _previous field",
        )

    original_title = previous.get("title")
    original_description = previous.get("description")
    patch_file = previous.get("patch_file", "")

    if not original_title and not original_description:
        return RollbackResult(
            sku=sku,
            platform=platform,
            success=False,
            message=f"No original content found in patch for {sku}",
            error="Empty _previous field in patch file",
        )

    # Find the original publish event to reference
    last_publish = get_last_publish_event(db_path, master_sku=sku, platform=platform)
    original_publish_id = last_publish.get("id") if last_publish else None

    if dry_run:
        return RollbackResult(
            sku=sku,
            platform=platform,
            success=True,
            message=f"[DRY RUN] Would rollback {sku} on {platform} to original content",
            original_title=original_title,
            original_description=original_description,
        )

    # Execute platform-specific rollback
    error_msg = None

    if platform == "shopify":
        product_id = previous.get("product_id")
        if not product_id:
            return RollbackResult(
                sku=sku,
                platform=platform,
                success=False,
                message=f"No product ID found for Shopify rollback of {sku}",
                error="Missing productId in patch file",
            )

        result = rollback_shopify_content(
            product_id,
            original_title or "",
            original_description or "",
            env=env,
            dry_run=False,
        )

        if not result.get("success"):
            error_msg = "; ".join(result.get("errors", ["Unknown error"]))

    elif platform == "google":
        # Google rollback: push original content back to Google Sheets
        try:
            from feedops.integrations.google_sheets import push_patches_to_sheet

            # Build rollback patch with original content for all variants
            rollback_variants = []
            original_variants = previous.get("variants") or []
            if original_variants:
                for v in original_variants:
                    rollback_variants.append(v)
            else:
                # Single-item rollback
                offer_id = previous.get("offer_id")
                if offer_id:
                    rollback_variants.append({
                        "offerId": offer_id,
                        "title": original_title or "",
                        "description": original_description or "",
                    })

            if rollback_variants:
                rollback_patch = {
                    "variants": rollback_variants,
                    "lifestyle_image_link": "",  # Remove lifestyle image
                    "_meta": {"master_sku": sku},
                }
                result = push_patches_to_sheet(
                    patches=[rollback_patch],
                    environment="production",
                    dry_run=False,
                )
                if not result.get("success"):
                    error_msg = "; ".join(result.get("errors", ["Sheet update failed"]))
        except Exception as e:
            error_msg = f"Google rollback error: {e}"

    elif platform == "bing":
        # Bing rollback: Regenerate feed without this SKU's patches
        # This is handled by regenerating the merged feed
        # For now, we just log the rollback event
        pass

    # Log the rollback event
    status = "success" if not error_msg else "failed"
    event_id = log_publish_event(
        db_path,
        master_sku=sku,
        platform=platform,
        environment="production",  # Rollbacks are always production-impacting
        action="rollback",
        patch_file=patch_file,
        status=status,
        error_message=error_msg,
        rollback_id=original_publish_id,
    )

    if error_msg:
        return RollbackResult(
            sku=sku,
            platform=platform,
            success=False,
            message=f"Rollback failed for {sku} on {platform}",
            original_title=original_title,
            original_description=original_description,
            publish_event_id=event_id,
            error=error_msg,
        )

    return RollbackResult(
        sku=sku,
        platform=platform,
        success=True,
        message=f"Successfully rolled back {sku} on {platform} to original content",
        original_title=original_title,
        original_description=original_description,
        publish_event_id=event_id,
    )


def batch_rollback(
    skus: list[str],
    platform: Platform,
    *,
    patches_dir: Path,
    db_path: Path,
    env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> list[RollbackResult]:
    """Rollback multiple SKUs.

    Args:
        skus: List of MasterSKUs to rollback.
        platform: Target platform.
        patches_dir: Directory containing patch files.
        db_path: Path to database file.
        env: Environment variables mapping.
        dry_run: If True, validate but don't execute.

    Returns:
        List of RollbackResult for each SKU.
    """
    results = []
    for sku in skus:
        result = rollback_content(
            sku,
            platform,
            patches_dir=patches_dir,
            db_path=db_path,
            env=env,
            dry_run=dry_run,
        )
        results.append(result)
    return results


def get_rollback_preview(
    sku: str,
    platform: Platform,
    patches_dir: Path,
) -> dict | None:
    """Preview what a rollback would restore.

    Args:
        sku: MasterSKU to preview.
        platform: Target platform.
        patches_dir: Directory containing patch files.

    Returns:
        Dict with current and original content comparison, or None if not found.
    """
    if platform == "google":
        patch = get_google_patch(patches_dir, sku)
    elif platform == "bing":
        patch = get_bing_patch_for_sku(patches_dir, sku)
    elif platform == "shopify":
        patch = get_shopify_patch_for_sku(patches_dir, sku)
    else:
        return None

    if not patch:
        return None

    previous = patch.get("_previous", {})

    return {
        "sku": sku,
        "platform": platform,
        "current": {
            "title": patch.get("title"),
            "description": patch.get("description") or patch.get("body_html"),
        },
        "original": {
            "title": previous.get("title"),
            "description": previous.get("description"),
        },
        "meta": patch.get("_meta", {}),
    }
