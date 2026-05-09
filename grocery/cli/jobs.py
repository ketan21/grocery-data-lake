"""Operational job commands."""

from __future__ import annotations

import typer
from rich.console import Console

from ..analytics import compute_price_metrics
from ..client import AHClient
from ..db import get_session, init_db
from ..health import run_quality_checks
from ..scraper import scrape_full_catalog
from ..serving import refresh_serving_metrics
from ..unit_price import normalize_unit_prices

app = typer.Typer(add_completion=False)
console = Console()


def _rebuild_derived_tables(session) -> dict:
    unit_prices = normalize_unit_prices(session)
    price_metrics = compute_price_metrics(session)
    serving_metrics = refresh_serving_metrics(session)
    session.commit()
    return {
        "unitPrices": unit_prices,
        "priceMetrics": price_metrics,
        **serving_metrics,
    }


@app.command("rebuild-derived")
def rebuild_derived():
    """Rebuild deterministic derived and serving tables from stored data."""
    init_db()
    session = get_session()
    result = _rebuild_derived_tables(session)

    console.print("[green]Rebuilt derived tables.[/]")
    console.print(f"  Unit prices: {result['unitPrices']}")
    console.print(f"  Price metrics: {result['priceMetrics']}")
    console.print(f"  Category serving metrics: {result['categoryMetrics']}")
    console.print(f"  Brand serving metrics: {result['brandMetrics']}")
    console.print(f"  Bonus serving metrics: {result['bonusMetrics']}")


@app.command("daily-snapshot")
def daily_snapshot(
    details: bool = typer.Option(False, "--details/--no-details", help="Fetch detail enrichment during scrape"),
    skip_scrape: bool = typer.Option(False, "--skip-scrape", help="Only rebuild derived/serving tables and run checks"),
    fail_on_quality: bool = typer.Option(False, "--fail-on-quality", help="Exit nonzero if any quality check fails"),
):
    """Run the daily scrape, rebuild, and health-check workflow."""
    init_db()
    if skip_scrape:
        console.print("[yellow]Skipping scrape; rebuilding from existing local data.[/]")
    else:
        console.print("[bold]Running full catalog scrape...[/]")
        total = scrape_full_catalog(AHClient(), fetch_details=details, record_prices=True)
        console.print(f"[green]Scrape completed: {total} products processed.[/]")

    session = get_session()
    result = _rebuild_derived_tables(session)
    checks = run_quality_checks(session)

    console.print("[green]Daily snapshot pipeline completed.[/]")
    console.print(f"  Unit prices: {result['unitPrices']}")
    console.print(f"  Price metrics: {result['priceMetrics']}")
    console.print(f"  Category serving metrics: {result['categoryMetrics']}")
    console.print(f"  Brand serving metrics: {result['brandMetrics']}")
    console.print(f"  Bonus serving metrics: {result['bonusMetrics']}")
    console.print("\n[bold]Quality checks:[/]")
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        console.print(f"  {marker} {check.name}: {check.value} ({check.message})")

    if fail_on_quality and any(not check.passed for check in checks):
        raise typer.Exit(1)
