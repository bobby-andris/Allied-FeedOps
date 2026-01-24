"""FeedOps CLI entry point."""
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file before any other imports that depend on env vars
load_dotenv()

import typer
from rich.console import Console

import feedops

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
    catalog_path = os.environ.get("CATALOG_PATH", "data/catalog/Product Catalog.csv")
    if Path(catalog_path).exists():
        console.print(f"[green]✓[/green] Catalog: {catalog_path}")
    else:
        console.print(f"[red]✗[/red] Catalog not found: {catalog_path}")
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
    for dir_name in ["reports", "exports"]:
        dir_path = Path(dir_name)
        if dir_path.exists():
            console.print(f"[green]✓[/green] Directory: {dir_name}/")
        else:
            console.print(f"[yellow]![/yellow] Directory missing: {dir_name}/ (will be created)")

    # Summary
    console.print()
    if all_ok:
        console.print("[bold green]All critical checks passed![/bold green]")
    else:
        console.print("[bold red]Some checks failed. Fix issues before running optimize.[/bold red]")
        raise typer.Exit(1)


@app.command()
def optimize(
    parent_sku: str = typer.Option(..., "--parent-sku", "-p", help="MasterSKU to optimize"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Preview only, no updates"),
    output_dir: str = typer.Option("reports", "--output-dir", "-o", help="Output directory"),
    catalog: Optional[str] = typer.Option(None, "--catalog", "-c", help="Path to catalog CSV"),
):
    """Optimize title and description for a parent SKU."""
    from feedops.pipeline.optimize import optimize_parent_sku

    catalog_path = catalog or os.environ.get("CATALOG_PATH", "data/catalog/Product Catalog.csv")

    console.print(f"\n[bold]Optimizing: {parent_sku}[/bold]")
    console.print(f"Catalog: {catalog_path}")
    console.print(f"Dry run: {dry_run}\n")

    try:
        result = asyncio.run(optimize_parent_sku(
            master_sku=parent_sku,
            catalog_path=catalog_path,
            dry_run=dry_run,
            output_dir=output_dir,
        ))

        score = result.candidate.final_score
        console.print(f"[bold]Quality Score: {score.composite}%[/bold]")
        console.print(f"Status: {score.approval_status.upper()}")
        safe_sku = parent_sku.replace("/", "-")
        console.print(f"\nReport saved to: {output_dir}/sku-{safe_sku}-*.md")
        console.print("Patch previews:")
        console.print(f"  Google:  exports/google-patch-{safe_sku}.json")
        console.print(f"  Bing:    exports/bing-patch-{safe_sku}.json")
        console.print(f"  Shopify: exports/shopify-patch-{safe_sku}.json")

        if score.approval_status == "approved":
            console.print("\n[bold green]Content approved for publication![/bold green]")
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
    catalog: Optional[str] = typer.Option(None, "--catalog", "-c", help="Path to catalog CSV"),
):
    """List available MasterSKUs in catalog."""
    from feedops.loaders import load_catalog, list_master_skus

    catalog_path = catalog or os.environ.get("CATALOG_PATH", "data/catalog/Product Catalog.csv")

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


@app.command(name="evaluate-exports")
def evaluate_exports(
    exports_dir: str = typer.Option("exports", "--exports-dir", help="Directory of export patches"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Write markdown report to this path (default: reports/)"
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


@app.command(name="compare-runs")
def compare_runs(
    baseline_exports_dir: str = typer.Option(..., "--baseline-exports-dir", help="Baseline exports dir"),
    candidate_exports_dir: str = typer.Option(..., "--candidate-exports-dir", help="Candidate exports dir"),
    baseline_reports_dir: Optional[str] = typer.Option(
        None, "--baseline-reports-dir", help="Baseline reports dir (for prompts/evidence)"
    ),
    candidate_reports_dir: Optional[str] = typer.Option(
        None, "--candidate-reports-dir", help="Candidate reports dir (for prompts/evidence)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Write HTML report to this path (default: reports/)"
    ),
):
    """Generate an HTML dashboard comparing two runs."""
    from feedops.quality.dashboard import compare_runs_to_html

    html_report = compare_runs_to_html(
        baseline_exports_dir=Path(baseline_exports_dir),
        candidate_exports_dir=Path(candidate_exports_dir),
        baseline_reports_dir=Path(baseline_reports_dir) if baseline_reports_dir else None,
        candidate_reports_dir=Path(candidate_reports_dir) if candidate_reports_dir else None,
    )

    if output is None:
        output = f"reports/compare-runs-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_report)
    console.print(f"\n[bold]Comparison dashboard saved to:[/bold] {output_path}")


if __name__ == "__main__":
    app()
