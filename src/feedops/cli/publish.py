"""Publish commands for pushing content to platforms."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from feedops.cli.defaults import CANDIDATE_EXPORTS_DIR
from feedops.db import get_publish_history, init_db, log_publish_event

console = Console()

# Create a sub-app for publish-related commands
# These will be merged into the main app
publish_app = typer.Typer(help="Content publishing commands")


def _get_db_path() -> Path:
    return Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))


def _get_patches_dir(patches_dir: str | None) -> Path:
    if patches_dir:
        return Path(patches_dir)
    return CANDIDATE_EXPORTS_DIR


def _load_patch(patches_dir: Path, sku: str, platform: str) -> dict | None:
    """Load a patch file for a specific SKU and platform."""
    safe_sku = sku.replace("/", "-")
    patch_file = patches_dir / f"{platform}-patch-{safe_sku}.json"
    if not patch_file.exists():
        return None
    try:
        with open(patch_file) as f:
            patch = json.load(f)
        patch["_source_file"] = str(patch_file)
        return patch
    except (json.JSONDecodeError, OSError):
        return None


def _validate_patch(
    patch: dict,
    require_approval: bool,
    min_score: float | None,
) -> tuple[bool, str | None]:
    """Validate a patch against approval and score requirements."""
    meta = patch.get("_meta", {})
    approval_status = meta.get("approval_status", "pending")
    quality_score = meta.get("quality_score", 0)

    if require_approval and approval_status != "approved":
        return False, f"Not approved (status: {approval_status})"

    if min_score is not None and quality_score < min_score:
        return False, f"Below minimum score ({quality_score:.1f} < {min_score})"

    return True, None


def _display_diff(
    sku: str,
    platform: str,
    current_title: str,
    new_title: str,
    current_desc: str | None,
    new_desc: str | None,
    quality_score: float,
    approval_status: str,
    environment: str,
    dry_run: bool,
):
    """Display a side-by-side diff of content changes."""
    # Truncate long descriptions for display
    max_desc_len = 200

    def truncate(text: str | None, max_len: int = max_desc_len) -> str:
        if not text:
            return "(empty)"
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text

    content = f"""[bold]Current Title:[/bold]
  {truncate(current_title, 100)}

[bold]New Title:[/bold]
  [green]{truncate(new_title, 100)}[/green]

[bold]Current Description:[/bold]
  {truncate(current_desc)}

[bold]New Description:[/bold]
  [green]{truncate(new_desc)}[/green]

[bold]Quality Score:[/bold] {quality_score:.1f}%
[bold]Approval Status:[/bold] {approval_status}
[bold]Environment:[/bold] {environment}
"""

    if dry_run:
        content += "\n[yellow][DRY RUN - No changes made][/yellow]"

    panel = Panel(
        content,
        title=f"Publish Preview: {sku} → {platform}",
        border_style="blue" if dry_run else "green",
    )
    console.print(panel)


@publish_app.command(name="publish")
def publish(
    sku: Optional[str] = typer.Option(None, "--sku", help="Single SKU to publish"),
    platform: str = typer.Option(
        "all", "--platform", "-p", help="Target platform: google, bing, shopify, or all"
    ),
    environment: str = typer.Option(
        "staging", "--environment", "-e", help="Environment: staging or production"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only, no changes"),
    require_approval: bool = typer.Option(
        False, "--require-approval", help="Only publish if status is approved"
    ),
    batch: bool = typer.Option(
        False, "--batch", help="Batch publish all matching patches"
    ),
    min_score: Optional[float] = typer.Option(
        None, "--min-score", help="Minimum quality score for batch publish"
    ),
    patches_dir: Optional[str] = typer.Option(
        None, "--patches-dir", help="Directory containing patch files"
    ),
):
    """Publish optimized content to shopping platforms.

    Examples:

        # Dry run for a single SKU
        feedops publish --sku TD-22 --platform google --dry-run

        # Publish to staging
        feedops publish --sku TD-22 --platform google --environment staging

        # Publish to production (requires approval)
        feedops publish --sku TD-22 --platform google --environment production --require-approval

        # Batch publish all approved patches with score >= 80%
        feedops publish --platform google --batch --require-approval --min-score 80
    """
    # Validate inputs
    if environment == "production" and not require_approval:
        console.print(
            "[yellow]Warning: Publishing to production without --require-approval flag[/yellow]"
        )

    if not sku and not batch:
        console.print("[red]Error: Must specify --sku or use --batch mode[/red]")
        raise typer.Exit(1)

    valid_platforms = ["google", "bing", "shopify", "all"]
    if platform not in valid_platforms:
        console.print(
            f"[red]Error: Invalid platform. Choose from: {valid_platforms}[/red]"
        )
        raise typer.Exit(1)

    patches_path = _get_patches_dir(patches_dir)
    db_path = _get_db_path()
    init_db(db_path)

    platforms = ["google", "bing", "shopify"] if platform == "all" else [platform]

    if batch:
        _publish_batch(
            platforms=platforms,
            environment=environment,
            dry_run=dry_run,
            require_approval=require_approval,
            min_score=min_score,
            patches_dir=patches_path,
            db_path=db_path,
        )
    else:
        _publish_single(
            sku=sku,
            platforms=platforms,
            environment=environment,
            dry_run=dry_run,
            require_approval=require_approval,
            patches_dir=patches_path,
            db_path=db_path,
        )


def _publish_single(
    sku: str,
    platforms: list[str],
    environment: str,
    dry_run: bool,
    require_approval: bool,
    patches_dir: Path,
    db_path: Path,
):
    """Publish a single SKU to specified platforms."""
    console.print(f"\n[bold]Publishing: {sku}[/bold]")
    console.print(f"Environment: {environment}")
    console.print(f"Platforms: {', '.join(platforms)}\n")

    for plat in platforms:
        patch = _load_patch(patches_dir, sku, plat)
        if not patch:
            console.print(f"[yellow]No {plat} patch found for {sku}[/yellow]")
            continue

        meta = patch.get("_meta", {})
        previous = patch.get("_previous", {})

        # Validate
        valid, reason = _validate_patch(patch, require_approval, None)
        if not valid:
            console.print(f"[red]Skipping {plat}: {reason}[/red]")
            continue

        # Get content
        title = patch.get("title", "")
        description = patch.get("description") or patch.get("body_html", "")
        prev_title = previous.get("title", "")
        prev_desc = previous.get("description", "")

        # Display diff
        _display_diff(
            sku=sku,
            platform=plat,
            current_title=prev_title,
            new_title=title,
            current_desc=prev_desc,
            new_desc=description,
            quality_score=meta.get("quality_score", 0),
            approval_status=meta.get("approval_status", "unknown"),
            environment=environment,
            dry_run=dry_run,
        )

        if dry_run:
            continue

        # Execute publish
        success = False
        error_msg = None

        try:
            if plat == "shopify":
                from feedops.integrations.shopify_catalog import publish_to_shopify

                product_id = patch.get("productId")
                if not product_id:
                    console.print(f"[red]No productId in patch for {sku}[/red]")
                    continue

                result = publish_to_shopify(
                    product_id=product_id,
                    title=title,
                    description_html=description,
                    environment=environment,
                    dry_run=False,
                )
                success = result.get("success", False)
                if not success:
                    error_msg = "; ".join(result.get("errors", ["Unknown error"]))

            elif plat == "google":
                # Google: Generate supplemental feed (actual upload requires manual step)
                from feedops.integrations.google_supplemental import (
                    generate_supplemental_feed,
                )

                feed_xml = generate_supplemental_feed([patch], environment)
                output_path = (
                    Path("data/feeds") / f"feedops-supplemental-{environment}.xml"
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(feed_xml, encoding="utf-8")
                console.print(
                    f"[green]Supplemental feed written to: {output_path}[/green]"
                )
                success = True

            elif plat == "bing":
                # Bing: Generate feed (actual upload requires manual step)
                from feedops.integrations.bing_catalog import (
                    generate_bing_feed_from_patches,
                )

                feed_xml = generate_bing_feed_from_patches([patch], environment)
                output_path = Path("data/feeds") / f"bing-feedops-{environment}.xml"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(feed_xml, encoding="utf-8")
                console.print(f"[green]Bing feed written to: {output_path}[/green]")
                success = True

        except Exception as e:
            error_msg = str(e)
            console.print(f"[red]Error publishing to {plat}: {e}[/red]")

        # Log event
        log_publish_event(
            db_path,
            master_sku=sku,
            platform=plat,
            environment=environment,
            action="publish",
            patch_file=patch.get("_source_file", ""),
            status="success" if success else "failed",
            quality_score=meta.get("quality_score"),
            approval_status=meta.get("approval_status"),
            error_message=error_msg,
        )

        if success:
            console.print(f"[green]✓ Published {sku} to {plat}[/green]")
        else:
            console.print(
                f"[red]✗ Failed to publish {sku} to {plat}: {error_msg}[/red]"
            )


def _publish_batch(
    platforms: list[str],
    environment: str,
    dry_run: bool,
    require_approval: bool,
    min_score: float | None,
    patches_dir: Path,
    db_path: Path,
):
    """Batch publish all matching patches."""
    console.print(f"\n[bold]Batch Publish[/bold]")
    console.print(f"Environment: {environment}")
    console.print(f"Platforms: {', '.join(platforms)}")
    console.print(f"Require approval: {require_approval}")
    console.print(f"Minimum score: {min_score or 'None'}\n")

    total_published = 0
    total_skipped = 0

    for plat in platforms:
        # Load all patches for this platform
        pattern = f"{plat}-patch-*.json"
        patch_files = list(patches_dir.glob(pattern))

        console.print(
            f"\n[bold]Platform: {plat}[/bold] ({len(patch_files)} patches found)"
        )

        for patch_file in patch_files:
            try:
                with open(patch_file) as f:
                    patch = json.load(f)
                patch["_source_file"] = str(patch_file)
            except (json.JSONDecodeError, OSError):
                continue

            meta = patch.get("_meta", {})
            sku = meta.get("master_sku", patch_file.stem.replace(f"{plat}-patch-", ""))

            # Validate
            valid, reason = _validate_patch(patch, require_approval, min_score)
            if not valid:
                console.print(f"  [dim]Skipped {sku}: {reason}[/dim]")
                total_skipped += 1
                continue

            title = patch.get("title", "")
            description = patch.get("description") or patch.get("body_html", "")

            if dry_run:
                console.print(
                    f"  [yellow]Would publish {sku} "
                    f"(score: {meta.get('quality_score', 0):.1f}%)[/yellow]"
                )
                total_published += 1
                continue

            # Execute publish (simplified for batch)
            success = False
            error_msg = None

            try:
                if plat == "shopify":
                    from feedops.integrations.shopify_catalog import publish_to_shopify

                    product_id = patch.get("productId")
                    if product_id:
                        result = publish_to_shopify(
                            product_id=product_id,
                            title=title,
                            description_html=description,
                            environment=environment,
                            dry_run=False,
                        )
                        success = result.get("success", False)
                        if not success:
                            error_msg = "; ".join(result.get("errors", []))
                else:
                    # Google/Bing are handled by generating feeds at the end
                    success = True

            except Exception as e:
                error_msg = str(e)

            # Log event
            log_publish_event(
                db_path,
                master_sku=sku,
                platform=plat,
                environment=environment,
                action="publish",
                patch_file=str(patch_file),
                status="success" if success else "failed",
                quality_score=meta.get("quality_score"),
                approval_status=meta.get("approval_status"),
                error_message=error_msg,
            )

            if success:
                console.print(f"  [green]✓ {sku}[/green]")
                total_published += 1
            else:
                console.print(f"  [red]✗ {sku}: {error_msg}[/red]")

    # Generate batch feeds for Google and Bing
    if not dry_run and ("google" in platforms or "bing" in platforms):
        _generate_batch_feeds(
            platforms, environment, patches_dir, require_approval, min_score
        )

    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Published: {total_published}")
    console.print(f"  Skipped: {total_skipped}")


def _generate_batch_feeds(
    platforms: list[str],
    environment: str,
    patches_dir: Path,
    require_approval: bool,
    min_score: float | None,
):
    """Generate batch feeds for Google and Bing."""
    if "google" in platforms:
        from feedops.integrations.google_supplemental import (
            generate_supplemental_feed,
            load_google_patches,
        )

        patches = load_google_patches(
            patches_dir,
            min_score=min_score,
            require_approval=require_approval,
        )
        if patches:
            feed_xml = generate_supplemental_feed(patches, environment)
            output_path = Path("data/feeds") / f"feedops-supplemental-{environment}.xml"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(feed_xml, encoding="utf-8")
            console.print(
                f"\n[green]Google supplemental feed: {output_path} ({len(patches)} items)[/green]"
            )

    if "bing" in platforms:
        from feedops.integrations.bing_catalog import (
            generate_bing_feed_from_patches,
            load_bing_patches,
        )

        patches = load_bing_patches(
            patches_dir,
            min_score=min_score,
            require_approval=require_approval,
        )
        if patches:
            feed_xml = generate_bing_feed_from_patches(patches, environment)
            output_path = Path("data/feeds") / f"bing-feedops-{environment}.xml"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(feed_xml, encoding="utf-8")
            console.print(
                f"[green]Bing feed: {output_path} ({len(patches)} items)[/green]"
            )


@publish_app.command(name="rollback")
def rollback_command(
    sku: str = typer.Option(..., "--sku", help="SKU to rollback"),
    platform: str = typer.Option(
        "all", "--platform", "-p", help="Target platform: google, bing, shopify, or all"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only, no changes"),
    patches_dir: Optional[str] = typer.Option(
        None, "--patches-dir", help="Directory containing patch files"
    ),
):
    """Rollback content to original version.

    Examples:

        # Preview rollback
        feedops rollback --sku TD-22 --platform shopify --dry-run

        # Execute rollback
        feedops rollback --sku TD-22 --platform shopify
    """
    from feedops.rollback import get_rollback_preview, rollback_content

    patches_path = _get_patches_dir(patches_dir)
    db_path = _get_db_path()
    init_db(db_path)

    platforms = ["google", "bing", "shopify"] if platform == "all" else [platform]

    console.print(f"\n[bold]Rollback: {sku}[/bold]")
    console.print(f"Platforms: {', '.join(platforms)}\n")

    for plat in platforms:
        # Show preview
        preview = get_rollback_preview(sku, plat, patches_path)
        if not preview:
            console.print(f"[yellow]No patch found for {sku} on {plat}[/yellow]")
            continue

        current = preview.get("current", {})
        original = preview.get("original", {})

        console.print(f"[bold]{plat.upper()}[/bold]")
        console.print(f"  Current title: {current.get('title', '')[:60]}...")
        console.print(f"  Original title: {original.get('title', '')[:60]}...")

        if dry_run:
            console.print(f"  [yellow][DRY RUN - Would revert to original][/yellow]\n")
            continue

        # Execute rollback
        result = rollback_content(
            sku=sku,
            platform=plat,
            patches_dir=patches_path,
            db_path=db_path,
            dry_run=False,
        )

        if result.success:
            console.print(f"  [green]✓ Rolled back successfully[/green]\n")
        else:
            console.print(f"  [red]✗ Rollback failed: {result.error}[/red]\n")


@publish_app.command(name="publish-history")
def publish_history_command(
    sku: Optional[str] = typer.Option(None, "--sku", help="Filter by SKU"),
    platform: Optional[str] = typer.Option(
        None, "--platform", "-p", help="Filter by platform"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of records to show"),
):
    """View publish event history.

    Examples:

        # Show all recent events
        feedops publish-history

        # Filter by SKU
        feedops publish-history --sku TD-22

        # Filter by platform
        feedops publish-history --platform google --limit 50
    """
    db_path = _get_db_path()
    if not db_path.exists():
        console.print(
            "[yellow]No publish history found (database doesn't exist)[/yellow]"
        )
        raise typer.Exit(0)

    events = get_publish_history(
        db_path,
        master_sku=sku,
        platform=platform,
        limit=limit,
    )

    if not events:
        console.print("[yellow]No publish events found[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Publish History")
    table.add_column("Time", style="dim")
    table.add_column("SKU")
    table.add_column("Platform")
    table.add_column("Env")
    table.add_column("Action")
    table.add_column("Status")
    table.add_column("Score")

    for event in events:
        published_at = event.get("published_at", "")
        if published_at:
            try:
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                published_at = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

        status = event.get("status", "")
        status_style = "green" if status == "success" else "red"

        score = event.get("quality_score")
        score_str = f"{score:.1f}%" if score else "-"

        table.add_row(
            published_at,
            event.get("master_sku", ""),
            event.get("platform", ""),
            event.get("environment", ""),
            event.get("action", ""),
            f"[{status_style}]{status}[/{status_style}]",
            score_str,
        )

    console.print(table)


@publish_app.command(name="export-bing")
def export_bing_command(
    patches_dir: Optional[str] = typer.Option(
        None, "--patches-dir", help="Directory containing patch files"
    ),
    base_feed: Optional[str] = typer.Option(
        None, "--base-feed", help="Path to base Bing feed for merge mode"
    ),
    output: str = typer.Option(
        "data/feeds/bing-feedops.xml", "--output", "-o", help="Output file path"
    ),
    environment: str = typer.Option(
        "staging", "--environment", "-e", help="Environment: staging or production"
    ),
    min_score: Optional[float] = typer.Option(
        None, "--min-score", help="Minimum quality score filter"
    ),
    require_approval: bool = typer.Option(
        False, "--require-approval", help="Only include approved patches"
    ),
):
    """Export Bing Shopping feed with FeedOps content.

    This command generates a Bing Merchant Center feed containing optimized
    content with tracking labels (custom_label_4).

    Examples:

        # Generate standalone feed with optimized items
        feedops export-bing --output data/feeds/bing-staging.xml --environment staging

        # Merge into existing base feed
        feedops export-bing --base-feed data/feeds/bing-primary.xml --output data/feeds/bing-merged.xml

        # Only approved items with score >= 80%
        feedops export-bing --require-approval --min-score 80
    """
    from feedops.integrations.bing_catalog import (
        generate_bing_feed_from_patches,
        load_bing_patches,
        merge_feedops_into_bing_feed,
    )

    patches_path = _get_patches_dir(patches_dir)
    output_path = Path(output)

    patches = load_bing_patches(
        patches_path,
        min_score=min_score,
        require_approval=require_approval,
    )

    if not patches:
        console.print("[yellow]No matching patches found[/yellow]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Exporting Bing Feed[/bold]")
    console.print(f"Patches: {len(patches)} items")
    console.print(f"Environment: {environment}")

    if base_feed:
        base_path = Path(base_feed)
        if not base_path.exists():
            console.print(f"[red]Base feed not found: {base_path}[/red]")
            raise typer.Exit(1)

        console.print(f"Base feed: {base_path}")
        xml_content = merge_feedops_into_bing_feed(patches, base_path, environment)
    else:
        console.print("Mode: Standalone (no base feed)")
        xml_content = generate_bing_feed_from_patches(patches, environment)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml_content, encoding="utf-8")

    console.print(f"\n[green]✓ Feed written to: {output_path}[/green]")
    console.print(
        f"[dim]Upload this file to Bing Merchant Center via FTP or manual upload[/dim]"
    )


@publish_app.command(name="publish-google")
def publish_google_command(
    batch_id: Optional[str] = typer.Option(
        None, "--batch-id", "-b", help="Batch ID to publish"
    ),
    sku: Optional[str] = typer.Option(
        None, "--sku", help="Single SKU to publish (alternative to batch)"
    ),
    patches_dir: Optional[str] = typer.Option(
        None, "--patches-dir", help="Directory containing patch files"
    ),
    environment: str = typer.Option(
        "staging", "--environment", "-e", help="Environment: staging or production"
    ),
    spreadsheet_id: Optional[str] = typer.Option(
        None,
        "--spreadsheet-id",
        help="Google Sheets spreadsheet ID (uses env var if not set)",
    ),
    sheet_name: Optional[str] = typer.Option(
        None, "--sheet-name", help="Worksheet name (uses first sheet if not set)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview changes without writing to sheet"
    ),
):
    """Push optimized content to Google Merchant Center via Google Sheets.

    This command updates a Google Sheet that serves as a supplemental feed
    for Google Merchant Center. It supports upsert logic:
    - If an offer ID exists in the sheet, the row is updated
    - If the offer ID is new, a new row is appended

    Authentication (one of):
    - Local: GOOGLE_APPLICATION_CREDENTIALS env var pointing to service account JSON
    - Streamlit Cloud: st.secrets["gcp_service_account"] with service account fields

    Spreadsheet ID (one of):
    - st.secrets["GOOGLE_SHEETS_SPREADSHEET_ID"] (Streamlit Cloud)
    - GOOGLE_NEW_MERCHANT_CENTER_SHEETS_SPREADSHEET_ID env var
    - --spreadsheet-id parameter

    Examples:

        # Dry run for a batch
        feedops publish-google --batch-id Batch-2026-01-30-001 --dry-run

        # Publish a batch to staging
        feedops publish-google --batch-id Batch-2026-01-30-001 --environment staging

        # Publish a single SKU
        feedops publish-google --sku BSK-275LA --environment staging

        # Publish to production
        feedops publish-google --batch-id Batch-2026-01-30-001 --environment production
    """
    from feedops.integrations.google_sheets import (
        load_patches_for_batch,
        publish_batch_to_sheets,
        push_patches_to_sheet,
    )

    if not batch_id and not sku:
        console.print("[red]Error: Must specify --batch-id or --sku[/red]")
        raise typer.Exit(1)

    if batch_id and sku:
        console.print("[red]Error: Cannot specify both --batch-id and --sku[/red]")
        raise typer.Exit(1)

    patches_path = _get_patches_dir(patches_dir)
    db_path = _get_db_path()
    init_db(db_path)

    console.print(f"\n[bold]Publishing to Google Sheets[/bold]")
    console.print(f"Environment: {environment}")
    if batch_id:
        console.print(f"Batch: {batch_id}")
    else:
        console.print(f"SKU: {sku}")
    console.print(f"Dry run: {dry_run}\n")

    try:
        if batch_id:
            # Publish entire batch
            result = publish_batch_to_sheets(
                batch_id=batch_id,
                patches_dir=patches_path,
                environment=environment,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                dry_run=dry_run,
                db_path=db_path,
            )
        else:
            # Publish single SKU
            patches = load_patches_for_batch(patches_path, [sku], platform="google")
            if not patches:
                console.print(f"[red]No Google patch found for SKU: {sku}[/red]")
                raise typer.Exit(1)

            result = push_patches_to_sheet(
                patches=patches,
                environment=environment,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                dry_run=dry_run,
                include_variants=True,
            )

            # Log publish event for single SKU (if not dry run)
            if not dry_run and result.get("success"):
                patch = patches[0]
                meta = patch.get("_meta", {})
                log_publish_event(
                    db_path,
                    master_sku=sku,
                    platform="google",
                    environment=environment,
                    action="publish",
                    patch_file=patch.get("_source_file", ""),
                    status="success",
                    quality_score=meta.get("quality_score"),
                    approval_status=meta.get("approval_status"),
                )

        # Display results
        if result.get("success"):
            if dry_run:
                console.print("[yellow]DRY RUN - No changes made[/yellow]")

            console.print(f"\n[bold]Results:[/bold]")
            console.print(
                f"  Total variants processed: {result.get('total_variants', 0)}"
            )
            console.print(f"  Rows updated: {result.get('updated_count', 0)}")
            console.print(f"  Rows appended: {result.get('appended_count', 0)}")
            console.print(f"\n[green]✓ Successfully pushed to Google Sheets[/green]")
        else:
            errors = result.get("errors", ["Unknown error"])
            console.print(f"\n[red]✗ Failed to push to Google Sheets[/red]")
            for error in errors:
                console.print(f"  [red]• {error}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        raise typer.Exit(1)
