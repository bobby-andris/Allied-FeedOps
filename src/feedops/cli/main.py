"""FeedOps CLI entry point."""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file before any other imports that depend on env vars
load_dotenv()

import typer
from rich.console import Console

import feedops
from feedops.cli.defaults import (
    BASELINE_EXPORTS_DIR,
    BASELINE_REPORTS_DIR,
    CANDIDATE_EXPORTS_DIR,
    CANDIDATE_REPORTS_DIR,
)
from feedops.loaders.catalog_resolver import resolve_catalog_path

app = typer.Typer(
    name="feedops",
    help="Allied FeedOps - Merchant Center feed optimization",
    add_completion=False,
)
console = Console()


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
            )
        )

        score = result.candidate.final_score
        console.print(f"[bold]Quality Score: {score.composite}%[/bold]")
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
