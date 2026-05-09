"""Enrich CLI commands."""

from __future__ import annotations

import typer

from ..client import AHClient
from ..enrich import enrich_products

app = typer.Typer(add_completion=False)


@app.command("all")
def enrich_all():
    """Fetch nutrition/allergen details for all products in the database."""
    client = AHClient()
    console = typer.echo
    console("Fetching product details for enrichment...")
    stats = enrich_products(client)
    console(f"\n[bold green]Enrichment complete![/bold green]")
    console(f"  Enriched: {stats['enriched']}")
    console(f"  Skipped (no data): {stats['skipped']}")
    console(f"  Failed: {stats['failed']}")
