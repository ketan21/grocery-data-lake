"""Scrape commands."""

from __future__ import annotations

from typing import Annotated

import typer

from ..client import AHClient
from ..scraper import scrape_full_catalog

app = typer.Typer(add_completion=False)


@app.command("full")
def scrape_full(
    details: Annotated[bool, typer.Option("--details/--no-details", help="Also fetch nutrition/allergens")] = False,
    categories: Annotated[list[int] | None, typer.Option("--categories", "-c", help="Category IDs to scrape (comma-separated via multiple -c flags)")] = None,
):
    """Scrape the full AH product catalog."""
    client = AHClient()
    total = scrape_full_catalog(client, category_ids=categories or None, fetch_details=details)
    typer.echo(f"Scraped {total} products total.")


@app.command("category")
def scrape_category(
    category_id: Annotated[int, typer.Argument(help="Category ID to scrape")],
    details: Annotated[bool, typer.Option("--details/--no-details", help="Also fetch nutrition/allergens")] = False,
):
    """Scrape a single category."""
    client = AHClient()
    total = scrape_full_catalog(client, category_ids=[category_id], fetch_details=details)
    typer.echo(f"Scraped {total} products in category {category_id}.")
