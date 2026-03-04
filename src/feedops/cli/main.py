"""FeedOps CLI entry point."""

import asyncio
import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _resolve_primary_checkout_root(repo_root: Path) -> Path | None:
    """Resolve the primary checkout root when running from a git worktree."""
    git_ref = repo_root / ".git"
    if not git_ref.exists() or not git_ref.is_file():
        return None
    try:
        content = git_ref.read_text(encoding="utf-8").strip()
        if not content.startswith("gitdir:"):
            return None
        gitdir_path = Path(content.split(":", 1)[1].strip()).expanduser()
        # In worktrees: <main>/.git/worktrees/<name>
        if len(gitdir_path.parts) >= 3 and gitdir_path.parts[-2] == "worktrees":
            return gitdir_path.parents[2]
    except Exception:
        return None
    return None


def _load_environment_files() -> None:
    """Load env files with worktree-aware fallback to primary checkout root."""
    repo_root = Path(__file__).resolve().parents[3]
    roots = [repo_root]
    primary_root = _resolve_primary_checkout_root(repo_root)
    if primary_root and primary_root not in roots:
        roots.append(primary_root)

    # Priority (last wins): .env -> .env.local -> .env.vercel
    # Across roots: worktree first, primary checkout second.
    for root in roots:
        load_dotenv(root / ".env", override=False)
        load_dotenv(root / ".env.local", override=True)
        load_dotenv(root / ".env.vercel", override=True)


_load_environment_files()

import typer
from rich.console import Console

import feedops
from feedops.cli.defaults import (
    BASELINE_EXPORTS_DIR,
    BASELINE_REPORTS_DIR,
    CANDIDATE_EXPORTS_DIR,
    CANDIDATE_REPORTS_DIR,
)
from feedops.cli.performance import performance_app
from feedops.cli.publish import publish_app
from feedops.loaders.catalog_resolver import resolve_catalog_path
from feedops.utils.offer_id import normalize_offer_id as _normalize_offer_id_canonical
from feedops.loaders.unified_loader import (
    get_cached_shopify_age_hours,
    load_parent_sku_unified,
)

app = typer.Typer(
    name="feedops",
    help="Allied FeedOps - Merchant Center feed optimization",
    add_completion=False,
)
console = Console()

# Register publish-related commands
for command in publish_app.registered_commands:
    app.registered_commands.append(command)

# Register performance monitoring commands
for command in performance_app.registered_commands:
    app.registered_commands.append(command)


def _parse_bool_env(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_offer_id(value: str | None) -> str:
    """Normalize offer ID to canonical lowercase form. Delegates to canonical utility."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    return _normalize_offer_id_canonical(raw) or raw


def _extract_label0(custom_labels: object) -> str:
    if not isinstance(custom_labels, dict):
        return ""
    raw = custom_labels.get("customLabel0")
    if raw in (None, ""):
        raw = custom_labels.get("custom_label_0")
    return str(raw or "").strip()


def _classify_missing_label_queue(
    *,
    exists_in_gmc: bool | None,
    treat_gmc_blank_as_catchall: bool,
) -> str:
    if exists_in_gmc is True:
        return (
            "queue_b_expected_catchall_blank"
            if treat_gmc_blank_as_catchall
            else "queue_b_blank_label_upstream"
        )
    if exists_in_gmc is False:
        return "queue_a_missing_offer_mapping"
    return "queue_unknown_no_gmc_check"


def _compute_reconcile_coverage_metrics(
    *,
    offer_linked_total: int,
    missing_total: int,
    queue_a_missing_offer_mapping: int,
    queue_b_expected_catchall_blank: int,
    treat_gmc_blank_as_catchall: bool,
) -> dict[str, float]:
    if offer_linked_total <= 0:
        return {
            "strict_label_coverage_pct": 0.0,
            "actionable_coverage_pct": 0.0,
        }

    strict_label_coverage_pct = round(
        ((offer_linked_total - missing_total) / offer_linked_total) * 100.0,
        2,
    )
    actionable_missing = max(0, queue_a_missing_offer_mapping)
    if not treat_gmc_blank_as_catchall:
        actionable_missing += max(0, queue_b_expected_catchall_blank)
    actionable_coverage_pct = round(
        ((offer_linked_total - actionable_missing) / offer_linked_total) * 100.0,
        2,
    )
    return {
        "strict_label_coverage_pct": strict_label_coverage_pct,
        "actionable_coverage_pct": actionable_coverage_pct,
    }


def _fetch_variant_index_rows(supabase, page_size: int = 1000) -> list[dict]:
    """Fetch variant_index rows using Supabase-safe pagination.

    Supabase/PostgREST commonly caps response rows at 1000. Using a larger page
    size can cause false "last page" detection if only 1000 rows are returned.
    """
    rows: list[dict] = []
    start = 0
    while True:
        result = (
            supabase.table("variant_index")
            .select("master_sku,gmc_offer_id,custom_labels")
            .range(start, start + page_size - 1)
            .execute()
        )
        page = result.data or []
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _get_cache_ttl_hours() -> float:
    value = os.environ.get("CACHE_TTL_HOURS", "24")
    try:
        return float(value)
    except ValueError:
        return 24.0


def _should_auto_sync(master_sku: str, ttl_hours: float) -> tuple[bool, float | None]:
    age_hours = get_cached_shopify_age_hours(master_sku)
    if age_hours is None:
        return True, None
    if ttl_hours <= 0:
        return True, age_hours
    return age_hours > ttl_hours, age_hours


def version_callback(value: bool):
    if value:
        console.print(f"feedops version {feedops.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
):
    """Allied FeedOps - Merchant Center feed optimization."""
    pass


@app.command()
def healthcheck():
    """Check configuration and connectivity."""
    console.print("\n[bold]FeedOps Health Check[/bold]\n")

    all_ok = True

    # Check 1: Catalog file
    try:
        catalog_path = resolve_catalog_path(None)
        console.print(f"[green]✓[/green] Catalog: {catalog_path}")
    except FileNotFoundError as exc:
        console.print(f"[red]✗[/red] {exc}")
        all_ok = False

    # Check 2: LLM API keys
    openai_key = os.environ.get("OPENAI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if openai_key:
        console.print("[green]✓[/green] OpenAI API key configured")
    else:
        console.print("[yellow]![/yellow] OpenAI API key not set")

    if gemini_key:
        console.print("[green]✓[/green] Gemini API key configured")
    else:
        console.print("[yellow]![/yellow] Gemini API key not set")

    if not openai_key and not gemini_key:
        console.print("[red]✗[/red] No LLM provider configured")
        all_ok = False

    # Check 3: Output directories
    for dir_path in [CANDIDATE_REPORTS_DIR, CANDIDATE_EXPORTS_DIR]:
        if dir_path.exists():
            console.print(f"[green]✓[/green] Directory: {dir_path}/")
        else:
            console.print(
                f"[yellow]![/yellow] Directory missing: {dir_path}/ (will be created)"
            )

    # Summary
    console.print()
    if all_ok:
        console.print("[bold green]All critical checks passed![/bold green]")
    else:
        console.print(
            "[bold red]Some checks failed. Fix issues before running optimize.[/bold red]"
        )
        raise typer.Exit(1)


@app.command()
def optimize(
    parent_sku: str = typer.Option(
        ..., "--parent-sku", "-p", help="MasterSKU to optimize"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Preview only, no updates"
    ),
    output_dir: str = typer.Option(
        str(CANDIDATE_REPORTS_DIR), "--output-dir", "-o", help="Output directory"
    ),
    exports_dir: str = typer.Option(
        str(CANDIDATE_EXPORTS_DIR),
        "--exports-dir",
        help="Export directory for patch JSON",
    ),
    catalog: Optional[str] = typer.Option(
        None, "--catalog", "-c", help="Path to catalog CSV"
    ),
    force_refresh: bool = typer.Option(
        False, "--force-refresh", help="Bypass cache and fetch fresh data"
    ),
    no_sync: bool = typer.Option(False, "--no-sync", help="Skip automatic sync check"),
    candidates: Optional[int] = typer.Option(
        None, "--candidates", "-n", help="Number of candidates to generate"
    ),
    candidate_weights: Optional[str] = typer.Option(
        None,
        "--candidate-weights",
        help="Weights for selection scoring, e.g. google=0.7,bing=0.15,shopify=0.15",
    ),
):
    """Optimize title and description for a parent SKU."""
    from feedops.pipeline.optimize import optimize_parent_sku
    from feedops.pipeline.selection import parse_candidate_weights

    catalog_path = resolve_catalog_path(catalog)
    weights = (
        parse_candidate_weights(candidate_weights)
        if candidate_weights is not None
        else None
    )
    cache_ttl_hours = _get_cache_ttl_hours()
    auto_sync_enabled = _parse_bool_env("AUTO_SYNC_ENABLED", True)

    if not no_sync and auto_sync_enabled and not force_refresh:
        should_sync, age_hours = _should_auto_sync(parent_sku, cache_ttl_hours)
        if should_sync:
            if age_hours is None:
                console.print("Data is missing, syncing...")
            else:
                console.print(f"Data is {age_hours:.1f} hours old, syncing...")
            load_parent_sku_unified(
                parent_sku,
                force_refresh=True,
                catalog_path=str(catalog_path),
                cache_ttl_hours=cache_ttl_hours,
            )

    console.print(f"\n[bold]Optimizing: {parent_sku}[/bold]")
    console.print(f"Catalog: {catalog_path}")
    console.print(f"Dry run: {dry_run}\n")

    try:
        result = asyncio.run(
            optimize_parent_sku(
                master_sku=parent_sku,
                catalog_path=catalog_path,
                dry_run=dry_run,
                output_dir=output_dir,
                exports_dir=exports_dir,
                num_candidates=candidates,
                candidate_weights=weights,
                force_refresh=force_refresh,
            )
        )

        score = result.candidate.final_score
        data_source = getattr(result, "data_source", None)
        if data_source:
            console.print(f"Data source: {data_source}")
        if result.heuristic_score is not None:
            console.print(
                f"[bold]Quality Score: {result.heuristic_score:.1f}% (heuristic)[/bold]"
                f"  |  LLM Self-Score: {score.composite}%"
            )
        else:
            console.print(f"[bold]Quality Score: {score.composite}% (LLM self-score)[/bold]")
        if result.heuristic_score_breakdown:
            parts = [
                f"{platform}: {val:.1f}%"
                for platform, val in result.heuristic_score_breakdown.items()
            ]
            console.print(f"  Breakdown: {' | '.join(parts)}")
        console.print(f"Status: {score.approval_status.upper()}")
        safe_sku = parent_sku.replace("/", "-")
        console.print(f"\nReport saved to: {output_dir}/sku-{safe_sku}-*.md")
        console.print("Patch previews:")
        console.print(f"  Google:  {exports_dir}/google-patch-{safe_sku}.json")
        console.print(f"  Bing:    {exports_dir}/bing-patch-{safe_sku}.json")
        console.print(f"  Shopify: {exports_dir}/shopify-patch-{safe_sku}.json")

        if score.approval_status == "approved":
            console.print(
                "\n[bold green]Content approved for publication![/bold green]"
            )
        elif score.approval_status == "revise":
            console.print("\n[bold yellow]Content needs revision.[/bold yellow]")
        else:
            console.print("\n[bold red]Content rejected. Review errors.[/bold red]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="list-skus")
def list_skus(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum SKUs to list"),
    catalog: Optional[str] = typer.Option(
        None, "--catalog", "-c", help="Path to catalog CSV"
    ),
):
    """List available MasterSKUs in catalog."""
    from feedops.loaders import list_master_skus, load_catalog

    catalog_path = resolve_catalog_path(catalog)

    try:
        df = load_catalog(catalog_path)
        skus = list_master_skus(df)

        console.print(f"\n[bold]MasterSKUs in catalog ({len(skus)} total)[/bold]\n")
        for sku in skus[:limit]:
            console.print(f"  {sku}")

        if len(skus) > limit:
            console.print(f"\n  ... and {len(skus) - limit} more")
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="sync-catalog")
def sync_catalog_command(
    source: str = typer.Option(
        "auto", "--source", help="Which source to refresh: shopify, mapi, auto"
    ),
    output_catalog: Optional[str] = typer.Option(
        None,
        "--output-catalog",
        help="Output catalog path (default: CATALOG_PATH or cache)",
    ),
    output_mc_metadata: Optional[str] = typer.Option(
        None,
        "--output-mc-metadata",
        help="Output Merchant Center metadata path (default: cache)",
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Limit number of products fetched"
    ),
    force: bool = typer.Option(
        False, "--force", help="Force refresh even if caches are fresh"
    ),
    ttl_hours: Optional[float] = typer.Option(
        None, "--ttl-hours", help="Refresh caches older than this (hours)"
    ),
):
    """Sync Shopify catalog and Merchant Center metadata snapshots."""
    from feedops.cli.sync import sync_catalog

    try:
        result = sync_catalog(
            source=source,
            output_catalog=output_catalog,
            output_mc_metadata=output_mc_metadata,
            limit=limit,
            force=force,
            ttl_hours=ttl_hours,
        )
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    catalog_status = "refreshed" if result.refreshed_catalog else "cached"
    mc_status = "refreshed" if result.refreshed_mc_metadata else "cached"
    console.print(f"\n[bold]Catalog sync complete[/bold]")
    console.print(f"Shopify catalog: {result.catalog_path} ({catalog_status})")
    console.print(f"Merchant Center metadata: {result.mc_metadata_path} ({mc_status})")


@app.command(name="reconcile-custom-labels")
def reconcile_custom_labels(
    output_dir: str = typer.Option(
        "reports/merchant_center",
        "--output-dir",
        help="Directory where reconciliation CSVs are written",
    ),
    include_gmc_lookup: bool = typer.Option(
        True,
        "--include-gmc-lookup/--skip-gmc-lookup",
        help="Check each missing offer against live Merchant Center products",
    ),
    treat_gmc_blank_as_catchall: bool = typer.Option(
        True,
        "--treat-gmc-blank-as-catchall/--treat-gmc-blank-as-upstream-gap",
        help=(
            "When true, classify in-GMC blank custom_label_0 offers as expected catchall "
            "inventory (non-actionable for segmentation)."
        ),
    ),
):
    """Reconcile missing custom_label_0 coverage for offer-linked variants.

    Outputs:
    - Missing variants CSV (by gmc_offer_id)
    - Missing masters CSV (grouped by master_sku)
    - Queue split counts for exists_in_gmc=true/false
    """
    from feedops.db.supabase_client import get_client, is_supabase_available
    from feedops.integrations.merchant_center import fetch_merchant_center_items

    if not is_supabase_available():
        console.print("[red]Supabase is not configured. Cannot run reconciliation.[/red]")
        raise typer.Exit(1)

    supabase = get_client()
    rows = _fetch_variant_index_rows(supabase)
    offer_rows = [r for r in rows if str(r.get("gmc_offer_id") or "").strip()]
    missing_rows = [r for r in offer_rows if not _extract_label0(r.get("custom_labels"))]

    gmc_offers: set[str] = set()
    if include_gmc_lookup:
        console.print("Fetching Merchant Center products for existence checks...")
        items = fetch_merchant_center_items(limit=None)
        gmc_offers = {
            _normalize_offer_id(item.get("offerId"))
            for item in items
            if item.get("offerId")
        }

    missing_variants: list[dict] = []
    masters: dict[str, dict[str, object]] = {}
    for row in missing_rows:
        master_sku = str(row.get("master_sku") or "").strip()
        offer_id = str(row.get("gmc_offer_id") or "").strip()
        norm_offer = _normalize_offer_id(offer_id)
        exists_in_gmc = bool(norm_offer and norm_offer in gmc_offers) if include_gmc_lookup else None
        missing_variants.append(
            {
                "master_sku": master_sku,
                "gmc_offer_id": offer_id,
                "normalized_offer_id": norm_offer,
                "exists_in_gmc": exists_in_gmc,
                "queue": (
                    _classify_missing_label_queue(
                        exists_in_gmc=exists_in_gmc,
                        treat_gmc_blank_as_catchall=treat_gmc_blank_as_catchall,
                    )
                ),
            }
        )

        bucket = masters.setdefault(
            master_sku,
            {
                "master_sku": master_sku,
                "missing_variant_count": 0,
                "exists_true_count": 0,
                "exists_false_count": 0,
                "exists_unknown_count": 0,
            },
        )
        bucket["missing_variant_count"] = int(bucket["missing_variant_count"]) + 1
        if exists_in_gmc is True:
            bucket["exists_true_count"] = int(bucket["exists_true_count"]) + 1
        elif exists_in_gmc is False:
            bucket["exists_false_count"] = int(bucket["exists_false_count"]) + 1
        else:
            bucket["exists_unknown_count"] = int(bucket["exists_unknown_count"]) + 1

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    variants_path = out_dir / f"custom-label-no-match-variants-{ts}.csv"
    masters_path = out_dir / f"custom-label-no-match-master-skus-{ts}.csv"

    with variants_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "master_sku",
                "gmc_offer_id",
                "normalized_offer_id",
                "exists_in_gmc",
                "queue",
            ],
        )
        writer.writeheader()
        writer.writerows(missing_variants)

    master_rows = []
    for row in masters.values():
        total = int(row["missing_variant_count"])
        exists_false = int(row["exists_false_count"])
        all_missing = total > 0 and exists_false == total
        partial_missing = exists_false > 0 and exists_false < total
        master_rows.append(
            {
                **row,
                "all_missing_in_gmc": all_missing,
                "partially_missing_in_gmc": partial_missing,
            }
        )

    with masters_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "master_sku",
                "missing_variant_count",
                "exists_true_count",
                "exists_false_count",
                "exists_unknown_count",
                "all_missing_in_gmc",
                "partially_missing_in_gmc",
            ],
        )
        writer.writeheader()
        writer.writerows(sorted(master_rows, key=lambda r: (r["missing_variant_count"], r["master_sku"]), reverse=True))

    queue_a = sum(1 for row in missing_variants if row["exists_in_gmc"] is False)
    queue_b = sum(1 for row in missing_variants if row["exists_in_gmc"] is True)
    queue_unknown = sum(1 for row in missing_variants if row["exists_in_gmc"] is None)
    coverage = _compute_reconcile_coverage_metrics(
        offer_linked_total=len(offer_rows),
        missing_total=len(missing_rows),
        queue_a_missing_offer_mapping=queue_a,
        queue_b_expected_catchall_blank=queue_b,
        treat_gmc_blank_as_catchall=treat_gmc_blank_as_catchall,
    )

    console.print("\n[bold]Custom label reconciliation complete[/bold]")
    console.print(f"Timestamp: {ts}")
    console.print(f"Offer-linked variants scanned: {len(offer_rows)}")
    console.print(f"Missing custom_label_0 variants: {len(missing_rows)}")
    console.print(f"Strict label coverage: {coverage['strict_label_coverage_pct']}%")
    actionable_label = (
        "Actionable coverage (excluding expected catchall blanks)"
        if treat_gmc_blank_as_catchall
        else "Actionable coverage (Queue B treated as upstream gap)"
    )
    console.print(f"{actionable_label}: {coverage['actionable_coverage_pct']}%")
    console.print(f"Queue A (missing/stale offer mapping): {queue_a}")
    if treat_gmc_blank_as_catchall:
        console.print(f"Queue B (offer exists, expected catchall blank): {queue_b}")
    else:
        console.print(f"Queue B (offer exists, upstream label blank): {queue_b}")
    if queue_unknown:
        console.print(f"Queue unknown (no GMC existence check): {queue_unknown}")
    console.print(f"Missing variants CSV: {variants_path}")
    console.print(f"Missing masters CSV: {masters_path}")


@app.command(name="refresh-cache")
def refresh_cache(
    sku: str = typer.Option(..., "--sku", help="Master SKU to refresh"),
    source: str = typer.Option(
        "both",
        "--source",
        help="Which source to refresh: shopify, gmc, both",
    ),
):
    """Manually refresh cached data for a SKU."""
    from feedops.db import init_db, upsert_merchant_center_items
    from feedops.integrations.merchant_center import fetch_merchant_center_items

    cache_ttl_hours = _get_cache_ttl_hours()
    db_path = Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))
    source = source.strip().lower()
    if source not in {"shopify", "gmc", "both"}:
        console.print("[red]Error:[/red] --source must be one of: shopify, gmc, both")
        raise typer.Exit(1)

    if source in {"shopify", "both"}:
        console.print(f"Refreshing Shopify data for {sku}...")
        parent = load_parent_sku_unified(
            sku,
            force_refresh=True,
            cache_ttl_hours=cache_ttl_hours,
        )
        if parent is None:
            console.print(f"[yellow]No Shopify data found for {sku}[/yellow]")

    if source in {"gmc", "both"}:
        console.print(f"Refreshing Merchant Center data for {sku}...")
        init_db(db_path)
        items = fetch_merchant_center_items(limit=None)
        if items:
            upsert_merchant_center_items(db_path, items)
        console.print(f"Merchant Center items cached: {len(items)}")

    console.print("[green]✅ Cache refreshed[/green]")


@app.command(name="evaluate-exports")
def evaluate_exports(
    exports_dir: str = typer.Option(
        "exports", "--exports-dir", help="Directory of export patches"
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write markdown report to this path (default: reports/)",
    ),
):
    """Evaluate existing export patch JSON files with heuristic scoring."""
    from feedops.quality import evaluate_exports_dir
    from feedops.quality.evaluator import render_markdown

    results = evaluate_exports_dir(Path(exports_dir))
    report = render_markdown(results)

    if output is None:
        output = f"reports/quality-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    console.print(f"\n[bold]Quality evaluation saved to:[/bold] {output_path}")


@app.command(name="review-dashboard")
def review_dashboard(
    baseline_exports_dir: str = typer.Option(
        str(BASELINE_EXPORTS_DIR), "--baseline", "-b", help="Baseline exports directory"
    ),
    candidate_exports_dir: str = typer.Option(
        str(CANDIDATE_EXPORTS_DIR),
        "--candidate",
        "-c",
        help="Candidate exports directory",
    ),
    catalog: Optional[str] = typer.Option(
        None, "--catalog", help="Path to Product Catalog.csv"
    ),
    baseline_reports_dir: Optional[str] = typer.Option(
        str(BASELINE_REPORTS_DIR),
        "--baseline-reports",
        help="Baseline reports directory",
    ),
    candidate_reports_dir: Optional[str] = typer.Option(
        str(CANDIDATE_REPORTS_DIR),
        "--candidate-reports",
        help="Candidate reports directory",
    ),
    port: int = typer.Option(8501, "--port", "-p", help="Port for Streamlit server"),
):
    """Launch the interactive Streamlit review dashboard.

    This opens a browser-based dashboard for reviewing and comparing
    optimized product titles and descriptions, with:

    - Three-way comparison (Original / Baseline / Candidate)
    - Product images
    - Keyword and enrichment reasoning inputs
    - Quality score visualization
    - Filtering by category, collection, and score changes
    """
    import subprocess
    import sys

    # Build the streamlit command
    dashboard_module = "feedops.quality.review_dashboard"

    # Prepare environment variables for the dashboard
    env = os.environ.copy()
    env["FEEDOPS_BASELINE_DIR"] = baseline_exports_dir
    env["FEEDOPS_CANDIDATE_DIR"] = candidate_exports_dir
    try:
        resolved_catalog = resolve_catalog_path(catalog)
        env["FEEDOPS_CATALOG_PATH"] = str(resolved_catalog)
    except FileNotFoundError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)
    if baseline_reports_dir:
        env["FEEDOPS_BASELINE_REPORTS"] = baseline_reports_dir
    if candidate_reports_dir:
        env["FEEDOPS_CANDIDATE_REPORTS"] = candidate_reports_dir

    # Get the path to the dashboard module
    from feedops.quality import review_dashboard as dashboard_mod

    dashboard_path = Path(dashboard_mod.__file__)

    console.print(f"\n[bold]Launching Review Dashboard[/bold]")
    console.print(f"Baseline: {baseline_exports_dir}")
    console.print(f"Candidate: {candidate_exports_dir}")
    console.print(f"Port: {port}\n")

    # Launch streamlit
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard_path),
        "--server.port",
        str(port),
        "--server.headless",
        "false",
        "--",
        "--baseline",
        baseline_exports_dir,
        "--candidate",
        candidate_exports_dir,
    ]

    cmd.extend(["--catalog", str(resolved_catalog)])
    if baseline_reports_dir:
        cmd.extend(["--baseline-reports", baseline_reports_dir])
    if candidate_reports_dir:
        cmd.extend(["--candidate-reports", candidate_reports_dir])

    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error launching dashboard: {e}[/red]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")


if __name__ == "__main__":
    app()
