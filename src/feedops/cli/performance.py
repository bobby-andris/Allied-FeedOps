"""Performance monitoring CLI commands.

Commands for tracking, comparing, and reviewing performance of FeedOps-optimized content.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from feedops.db import (
    get_performance_baseline,
    get_performance_snapshots,
    init_db,
    save_performance_baseline,
    save_performance_snapshot,
)
from feedops.monitoring import (
    auto_review_performance,
    format_review_report,
    generate_review_summary,
    test_significance,
)

console = Console()

# Create sub-app for performance commands
performance_app = typer.Typer(help="Performance monitoring commands")


def _get_db_path() -> Path:
    return Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))


def _get_platform_fetcher(platform: str):
    """Get the appropriate performance fetcher for a platform."""
    if platform == "google":
        from feedops.integrations.google_ads_performance import (
            fetch_product_performance,
        )

        return fetch_product_performance
    elif platform == "bing":
        from feedops.integrations.bing_ads_performance import (
            fetch_bing_product_performance,
        )

        return fetch_bing_product_performance
    elif platform == "shopify":
        from feedops.integrations.shopify_analytics import (
            fetch_shopify_product_analytics,
        )

        return fetch_shopify_product_analytics
    else:
        raise ValueError(f"Unknown platform: {platform}")


@performance_app.command(name="baseline")
def capture_baseline(
    sku: str = typer.Option(
        ..., "--sku", "-s", help="Master SKU to capture baseline for"
    ),
    platform: str = typer.Option(
        ..., "--platform", "-p", help="Platform: google, bing, shopify"
    ),
    start_date: str = typer.Option(
        ..., "--start", help="Baseline start date (YYYY-MM-DD)"
    ),
    end_date: str = typer.Option(..., "--end", help="Baseline end date (YYYY-MM-DD)"),
    offer_id: Optional[str] = typer.Option(
        None, "--offer-id", help="Product offer ID (uses SKU if not provided)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only, don't save"),
):
    """Capture pre-FeedOps baseline metrics for a SKU.

    Fetches performance data for the baseline period and stores averaged
    metrics for later comparison.

    Examples:

        # Capture December baseline for Google Shopping
        feedops performance baseline --sku TD-22 --platform google \\
            --start 2025-12-01 --end 2025-12-31
    """
    console.print(f"\n[bold]Capturing Baseline: {sku}[/bold]")
    console.print(f"Platform: {platform}")
    console.print(f"Period: {start_date} to {end_date}\n")

    product_id = offer_id or sku
    db_path = _get_db_path()

    try:
        fetcher = _get_platform_fetcher(platform)

        console.print("[dim]Fetching metrics from API...[/dim]")
        metrics = fetcher(product_id, start_date, end_date)

        # Calculate period length for averaging
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end_dt - start_dt).days + 1

        # Display fetched metrics
        table = Table(title="Baseline Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Total", justify="right")
        table.add_column("Daily Avg", justify="right")

        impressions = metrics.get("impressions", 0)
        clicks = metrics.get("clicks", 0)
        conversions = metrics.get("conversions", 0)
        conversion_value = metrics.get("conversion_value", 0.0)
        cost = metrics.get("cost", 0.0)
        roas = metrics.get("roas", 0.0)
        ctr = metrics.get("ctr", 0.0)

        table.add_row("Impressions", f"{impressions:,}", f"{impressions / days:,.1f}")
        table.add_row("Clicks", f"{clicks:,}", f"{clicks / days:,.1f}")
        table.add_row("CTR", f"{ctr * 100:.2f}%", "-")
        table.add_row("Conversions", f"{conversions:,}", f"{conversions / days:,.2f}")
        table.add_row(
            "Conversion Value",
            f"${conversion_value:,.2f}",
            f"${conversion_value / days:,.2f}",
        )
        table.add_row("Cost", f"${cost:,.2f}", f"${cost / days:,.2f}")
        table.add_row("ROAS", f"{roas:.2f}", "-")

        console.print(table)

        if dry_run:
            console.print("\n[yellow][DRY RUN - Baseline not saved][/yellow]")
            return

        # Save baseline
        init_db(db_path)
        save_performance_baseline(
            db_path,
            master_sku=sku,
            platform=platform,
            baseline_start_date=start_date,
            baseline_end_date=end_date,
            avg_impressions=impressions / days,
            avg_clicks=clicks / days,
            avg_ctr=ctr,
            avg_conversions=conversions / days,
            avg_conversion_value=conversion_value / days,
            avg_cvr=conversions / clicks if clicks > 0 else 0.0,
            avg_cost=cost / days,
            avg_roas=roas,
        )

        console.print(f"\n[green]Baseline saved for {sku} ({platform})[/green]")

    except ValueError as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Error fetching metrics: {e}[/red]")
        raise typer.Exit(1)


@performance_app.command(name="fetch")
def fetch_current(
    sku: str = typer.Option(..., "--sku", "-s", help="Master SKU to fetch metrics for"),
    platform: str = typer.Option(
        ..., "--platform", "-p", help="Platform: google, bing, shopify"
    ),
    start_date: str = typer.Option(..., "--start", help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(..., "--end", help="End date (YYYY-MM-DD)"),
    offer_id: Optional[str] = typer.Option(
        None, "--offer-id", help="Product offer ID (uses SKU if not provided)"
    ),
    environment: str = typer.Option(
        "production", "--environment", "-e", help="Environment"
    ),
    save: bool = typer.Option(
        True, "--save/--no-save", help="Save snapshots to database"
    ),
):
    """Fetch current performance metrics for a SKU.

    Examples:

        # Fetch recent Google Shopping metrics
        feedops performance fetch --sku TD-22 --platform google \\
            --start 2026-01-15 --end 2026-01-27
    """
    console.print(f"\n[bold]Fetching Performance: {sku}[/bold]")
    console.print(f"Platform: {platform}")
    console.print(f"Period: {start_date} to {end_date}\n")

    product_id = offer_id or sku
    db_path = _get_db_path()

    try:
        fetcher = _get_platform_fetcher(platform)

        console.print("[dim]Fetching metrics from API...[/dim]")
        metrics = fetcher(product_id, start_date, end_date)

        # Display metrics
        table = Table(title="Current Performance")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        impressions = metrics.get("impressions", 0)
        clicks = metrics.get("clicks", 0)
        conversions = metrics.get("conversions", 0)
        conversion_value = metrics.get("conversion_value", 0.0)
        cost = metrics.get("cost", 0.0)
        roas = metrics.get("roas", 0.0)
        ctr = metrics.get("ctr", 0.0)

        table.add_row("Impressions", f"{impressions:,}")
        table.add_row("Clicks", f"{clicks:,}")
        table.add_row("CTR", f"{ctr * 100:.2f}%")
        table.add_row("Conversions", f"{conversions:,}")
        table.add_row("Conversion Value", f"${conversion_value:,.2f}")
        table.add_row("Cost", f"${cost:,.2f}")
        table.add_row("ROAS", f"{roas:.2f}")

        console.print(table)

        # Show daily breakdown if available
        daily_data = metrics.get("daily_data", [])
        if daily_data:
            console.print(
                f"\n[dim]Daily breakdown: {len(daily_data)} days of data[/dim]"
            )

        if save:
            init_db(db_path)

            # Save aggregate snapshot
            save_performance_snapshot(
                db_path,
                master_sku=sku,
                platform=platform,
                environment=environment,
                snapshot_date=end_date,
                impressions=impressions,
                clicks=clicks,
                ctr=ctr,
                conversions=conversions,
                conversion_value=conversion_value,
                cost=cost,
                roas=roas,
            )
            console.print(f"\n[green]Snapshot saved for {sku}[/green]")

    except ValueError as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Error fetching metrics: {e}[/red]")
        raise typer.Exit(1)


@performance_app.command(name="compare")
def compare_performance(
    sku: str = typer.Option(..., "--sku", "-s", help="Master SKU to compare"),
    platform: str = typer.Option(
        ..., "--platform", "-p", help="Platform: google, bing, shopify"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file (JSON)"
    ),
):
    """Compare baseline vs current performance for a SKU.

    Requires baseline to be captured first with `performance baseline`.

    Examples:

        feedops performance compare --sku TD-22 --platform google
    """
    console.print(f"\n[bold]Performance Comparison: {sku}[/bold]")
    console.print(f"Platform: {platform}\n")

    db_path = _get_db_path()

    # Get baseline
    baseline = get_performance_baseline(db_path, master_sku=sku, platform=platform)
    if not baseline:
        console.print(
            "[red]Error: No baseline found. Run `performance baseline` first.[/red]"
        )
        raise typer.Exit(1)

    # Get current snapshots
    snapshots = get_performance_snapshots(
        db_path,
        master_sku=sku,
        platform=platform,
        limit=30,
    )

    if not snapshots:
        console.print(
            "[red]Error: No current snapshots found. Run `performance fetch` first.[/red]"
        )
        raise typer.Exit(1)

    # Aggregate current metrics
    total_impressions = sum(s.get("impressions", 0) or 0 for s in snapshots)
    total_clicks = sum(s.get("clicks", 0) or 0 for s in snapshots)
    total_conversions = sum(s.get("conversions", 0) or 0 for s in snapshots)
    total_conversion_value = sum(
        s.get("conversion_value", 0.0) or 0.0 for s in snapshots
    )
    total_cost = sum(s.get("cost", 0.0) or 0.0 for s in snapshots)

    current_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
    current_roas = total_conversion_value / total_cost if total_cost > 0 else 0.0

    # Get baseline values
    baseline_ctr = baseline.get("avg_ctr", 0.0) or 0.0
    baseline_roas = baseline.get("avg_roas", 0.0) or 0.0
    baseline_impressions = int(baseline.get("avg_impressions", 0) or 0)
    baseline_conversions = int(baseline.get("avg_conversions", 0) or 0)

    # Calculate deltas
    delta_ctr = current_ctr - baseline_ctr
    delta_ctr_pct = delta_ctr / baseline_ctr * 100 if baseline_ctr > 0 else 0.0
    delta_roas = current_roas - baseline_roas
    delta_roas_pct = delta_roas / baseline_roas * 100 if baseline_roas > 0 else 0.0

    # Display comparison
    console.print(
        f"[bold]Baseline ({baseline['baseline_start_date']} to {baseline['baseline_end_date']}):[/bold]"
    )
    console.print(
        f"  Impressions: {baseline_impressions:,}/day  |  Clicks: {baseline.get('avg_clicks', 0):,.1f}/day  |  CTR: {baseline_ctr * 100:.2f}%"
    )
    console.print(
        f"  Conversions: {baseline_conversions:,.1f}/day  |  Value: ${baseline.get('avg_conversion_value', 0):,.2f}/day  |  ROAS: {baseline_roas:.2f}"
    )

    console.print(f"\n[bold]Current ({len(snapshots)} snapshots):[/bold]")
    console.print(
        f"  Impressions: {total_impressions:,}  |  Clicks: {total_clicks:,}  |  CTR: {current_ctr * 100:.2f}%"
    )
    console.print(
        f"  Conversions: {total_conversions:,}  |  Value: ${total_conversion_value:,.2f}  |  ROAS: {current_roas:.2f}"
    )

    # Display deltas with colors
    ctr_color = (
        "green" if delta_ctr_pct > 0 else "red" if delta_ctr_pct < 0 else "white"
    )
    roas_color = (
        "green" if delta_roas_pct > 0 else "red" if delta_roas_pct < 0 else "white"
    )

    console.print(f"\n[bold]Changes:[/bold]")
    console.print(f"  CTR:  [{ctr_color}]{delta_ctr_pct:+.1f}%[/{ctr_color}]")
    console.print(f"  ROAS: [{roas_color}]{delta_roas_pct:+.1f}%[/{roas_color}]")

    # Statistical significance test
    sig_result = test_significance(
        baseline_conversions=max(baseline_conversions, 1),
        baseline_impressions=max(baseline_impressions, 1),
        test_conversions=total_conversions,
        test_impressions=total_impressions,
        confidence_level=0.95,
    )

    if sig_result.get("sample_size_adequate"):
        sig_str = (
            "[green]Yes[/green]"
            if sig_result["is_significant"]
            else "[yellow]No[/yellow]"
        )
        p_val = sig_result.get("p_value", "N/A")
        console.print(
            f"\n[bold]Statistical Significance:[/bold] {sig_str} (p-value: {p_val})"
        )
    else:
        console.print(
            f"\n[yellow]Warning: {sig_result.get('warning', 'Insufficient sample size')}[/yellow]"
        )

    # Verdict
    if delta_roas_pct >= 0:
        verdict = (
            "[green]WINNER[/green]"
            if sig_result.get("is_significant")
            else "[green]POSITIVE[/green]"
        )
        recommendation = "Keep FeedOps content"
        if delta_roas_pct > 10:
            recommendation += ", consider expanding to similar SKUs"
    elif delta_roas_pct > -15:
        verdict = "[yellow]MONITOR[/yellow]"
        recommendation = "Continue monitoring - change may be within normal variance"
    else:
        verdict = "[red]UNDERPERFORMING[/red]"
        recommendation = "Consider rollback if decline persists"

    console.print(f"\n[bold]Verdict:[/bold] {verdict}")
    console.print(f"[bold]Recommendation:[/bold] {recommendation}")

    # Save to file if requested
    if output:
        result = {
            "sku": sku,
            "platform": platform,
            "baseline": baseline,
            "current": {
                "impressions": total_impressions,
                "clicks": total_clicks,
                "ctr": current_ctr,
                "conversions": total_conversions,
                "conversion_value": total_conversion_value,
                "cost": total_cost,
                "roas": current_roas,
            },
            "delta_ctr_pct": delta_ctr_pct,
            "delta_roas_pct": delta_roas_pct,
            "significance": sig_result,
        }
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        console.print(f"\n[dim]Results saved to {output}[/dim]")


@performance_app.command(name="report")
def batch_report(
    platform: str = typer.Option(
        ..., "--platform", "-p", help="Platform: google, bing, shopify"
    ),
    min_days: int = typer.Option(14, "--min-days", help="Minimum days since publish"),
    environment: Optional[str] = typer.Option(
        None, "--environment", "-e", help="Filter by environment"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file (JSON or TXT)"
    ),
):
    """Generate batch performance report for all published SKUs.

    Only includes SKUs that have been published for at least min-days
    to ensure statistical reliability.

    Examples:

        feedops performance report --platform google --min-days 14
    """
    console.print(f"\n[bold]Batch Performance Report[/bold]")
    console.print(f"Platform: {platform}")
    console.print(f"Minimum days: {min_days}")
    if environment:
        console.print(f"Environment: {environment}")
    console.print()

    db_path = _get_db_path()

    # Run auto-review
    try:
        reviews = auto_review_performance(
            platform=platform,
            min_days_since_publish=min_days,
            db_path=db_path,
            environment=environment,
        )
    except Exception as e:
        console.print(f"[red]Error running auto-review: {e}[/red]")
        raise typer.Exit(1)

    if not reviews:
        console.print("[yellow]No SKUs found matching criteria.[/yellow]")
        return

    summary = generate_review_summary(reviews)

    # Display summary
    console.print(f"[bold]Summary ({summary['total_reviewed']} SKUs reviewed):[/bold]")
    console.print(f"  Keep:     {summary['keep_count']} SKUs")
    console.print(f"  Monitor:  {summary['monitor_count']} SKUs")
    console.print(f"  Rollback: {summary['rollback_count']} SKUs")

    if summary["avg_roas_lift"] is not None:
        lift_color = "green" if summary["avg_roas_lift"] > 0 else "red"
        console.print(
            f"\n  Average ROAS Lift: [{lift_color}]{summary['avg_roas_lift'] * 100:+.1f}%[/{lift_color}]"
        )
    if summary["avg_ctr_lift"] is not None:
        lift_color = "green" if summary["avg_ctr_lift"] > 0 else "red"
        console.print(
            f"  Average CTR Lift:  [{lift_color}]{summary['avg_ctr_lift'] * 100:+.1f}%[/{lift_color}]"
        )

    # Display table of results
    table = Table(title=f"\nPerformance by SKU")
    table.add_column("SKU", style="cyan")
    table.add_column("Env", style="dim")
    table.add_column("Days", justify="right")
    table.add_column("ROAS Delta", justify="right")
    table.add_column("CTR Delta", justify="right")
    table.add_column("Sig?", justify="center")
    table.add_column("Recommendation")

    for r in reviews:
        roas_str = (
            f"{r['delta_roas_pct'] * 100:+.1f}%"
            if r["delta_roas_pct"] is not None
            else "N/A"
        )
        ctr_str = (
            f"{r['delta_ctr_pct'] * 100:+.1f}%"
            if r["delta_ctr_pct"] is not None
            else "N/A"
        )

        # Color code recommendation
        rec = r["recommendation"]
        if rec == "keep":
            rec_style = "[green]KEEP[/green]"
        elif rec == "rollback":
            rec_style = "[red]ROLLBACK[/red]"
        else:
            rec_style = "[yellow]MONITOR[/yellow]"

        sig_str = "Yes" if r["is_significant"] else "No"

        table.add_row(
            r["sku"],
            r["environment"][:4] if r["environment"] else "-",
            str(r["days_since_publish"]),
            roas_str,
            ctr_str,
            sig_str,
            rec_style,
        )

    console.print(table)

    # Save to file if requested
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output.endswith(".json"):
            with open(output_path, "w") as f:
                json.dump(
                    {"summary": summary, "reviews": reviews}, f, indent=2, default=str
                )
        else:
            report_text = format_review_report(reviews, summary)
            output_path.write_text(report_text)

        console.print(f"\n[dim]Report saved to {output}[/dim]")


@performance_app.command(name="auto-review")
def auto_review(
    platform: str = typer.Option(
        ..., "--platform", "-p", help="Platform: google, bing, shopify"
    ),
    rollback_threshold: float = typer.Option(
        -0.15,
        "--rollback-threshold",
        help="ROAS decline threshold for rollback (e.g., -0.20 for -20%)",
    ),
    min_days: int = typer.Option(14, "--min-days", help="Minimum days since publish"),
    environment: Optional[str] = typer.Option(
        None, "--environment", "-e", help="Filter by environment"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file (JSON)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Automatically review published SKUs and flag underperformers.

    Designed for automated/cron usage. Returns exit code 0 if all SKUs are
    healthy, 1 if any SKUs need attention (monitor/rollback).

    Examples:

        # Daily review with 20% rollback threshold
        feedops performance auto-review --platform google --rollback-threshold -0.20

        # Save results for processing
        feedops performance auto-review --platform google --output review-results.json
    """
    db_path = _get_db_path()

    try:
        reviews = auto_review_performance(
            platform=platform,
            min_days_since_publish=min_days,
            rollback_threshold=rollback_threshold,
            db_path=db_path,
            environment=environment,
        )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if not reviews:
        console.print(
            f"No SKUs ready for review (platform={platform}, min_days={min_days})"
        )
        return

    summary = generate_review_summary(reviews)

    # Output based on verbosity
    if verbose:
        report_text = format_review_report(reviews, summary)
        console.print(report_text)
    else:
        # Compact output for cron/logging
        console.print(
            f"Reviewed {summary['total_reviewed']} SKUs: "
            f"keep={summary['keep_count']}, "
            f"monitor={summary['monitor_count']}, "
            f"rollback={summary['rollback_count']}"
        )

        # List rollback candidates
        rollbacks = [r for r in reviews if r["recommendation"] == "rollback"]
        if rollbacks:
            console.print("\n[red]Rollback candidates:[/red]")
            for r in rollbacks:
                console.print(f"  - {r['sku']} ({r['platform']}): {r['reason']}")

    # Save results if requested
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(
                {"summary": summary, "reviews": reviews}, f, indent=2, default=str
            )
        console.print(f"\n[dim]Results saved to {output}[/dim]")

    # Exit with code 1 if any issues found
    if summary["rollback_count"] > 0:
        raise typer.Exit(1)
