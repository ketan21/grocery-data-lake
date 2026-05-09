"""CLI commands for bonus/promotion scraping."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="bonus",
    help="Scrape bonus/promotion data",
)


@app.command("scrape")
def bonus_scrape():
    """Scrape current bonus/promotion data and store raw JSON."""
    from ..bonus_scraper import scrape_bonus

    summary = scrape_bonus()

    if summary.get("status") == "completed":
        typer.echo(f"\n✅ Bonus scrape complete: {summary.get('bonus_products', 0)} products on bonus")
    else:
        typer.echo(f"\n⚠️ Bonus scrape: {summary}")
