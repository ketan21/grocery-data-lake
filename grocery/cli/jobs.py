"""Operational job commands."""

from __future__ import annotations

import typer
from rich.console import Console

from ..analytics import compute_price_metrics
from ..db import get_session, init_db
from ..unit_price import normalize_unit_prices

app = typer.Typer(add_completion=False)
console = Console()


@app.command("rebuild-derived")
def rebuild_derived():
    """Rebuild deterministic derived tables from stored product and price data."""
    init_db()
    session = get_session()

    unit_prices = normalize_unit_prices(session)
    price_metrics = compute_price_metrics(session)
    session.commit()

    console.print("[green]Rebuilt derived tables.[/]")
    console.print(f"  Unit prices: {unit_prices}")
    console.print(f"  Price metrics: {price_metrics}")
