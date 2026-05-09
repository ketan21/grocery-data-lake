"""Enrich existing products with nutrition/allergen/ingredient detail data."""

from __future__ import annotations

import time
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .client import AHClient
from .db import (
    ProductRow, NutritionRow, AllergenRow, IngredientRow,
    get_session, init_db,
    _store_nutrition, _store_allergens, _store_ingredients, _store_extra_fields,
    store_raw_json,
)

console = Console()


def enrich_products(client: AHClient, batch_size: int = 100) -> dict:
    """
    Fetch product details for all products in the DB.
    Stores nutrition, allergens, ingredients, and extra fields.

    Args:
        client: AH API client
        batch_size: Commit to DB every N products

    Returns:
        Stats dict with enriched/skipped/failed counts
    """
    init_db()
    session = get_session()

    # Get all products
    all_products = session.query(ProductRow).all()
    console.print(f"[bold blue]Found {len(all_products)} products to enrich[/]")

    stats = {"enriched": 0, "skipped": 0, "failed": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Fetching product details...", total=len(all_products))

        for i, row in enumerate(all_products):
            try:
                detail = client.get_product_detail(row.webshop_id)
                if detail:
                    # Always store raw detail response
                    store_raw_json(session, row.webshop_id, "detail", detail)

                    # Check if there's actual data worth storing
                    ti = detail.get("tradeItem", {})
                    has_nutrition = bool(ti.get("nutritionalInformation"))
                    has_allergens = bool(ti.get("allergenInformation"))
                    has_ingredients = bool(ti.get("foodAndBeverageIngredientStatement"))
                    has_extra = bool(ti.get("foodName") or ti.get("barcode") or ti.get("manufacturer"))

                    if has_nutrition or has_allergens or has_ingredients or has_extra:
                        _store_nutrition(session, row.webshop_id, detail)
                        _store_allergens(session, row.webshop_id, detail)
                        _store_ingredients(session, row.webshop_id, detail)
                        _store_extra_fields(session, row.webshop_id, detail)
                        stats["enriched"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    stats["failed"] += 1

            except Exception as e:
                stats["failed"] += 1
                if stats["failed"] <= 5:
                    console.print(f"[red]Error on product {row.webshop_id} ({row.title[:40]}): {e}[/]")

            progress.update(task, completed=i + 1)

            # Rate limiting — ~6.6 req/sec
            time.sleep(0.15)

            # Periodic commit
            if (i + 1) % batch_size == 0:
                session.commit()
                console.print(f"  [dim]Committed batch {i+1}/{len(all_products)} — enriched: {stats['enriched']}, skipped: {stats['skipped']}, failed: {stats['failed']}[/]")

    session.commit()
    return stats
