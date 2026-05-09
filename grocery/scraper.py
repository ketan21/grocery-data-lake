"""Main scraping logic — categories → products → details pipeline."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .client import AHClient
from .config import SEARCH_DELAY
from .db import (
    CategoryRow, ProductRow, ScrapeRun,
    get_session, init_db, upsert_product, record_price_snapshot, store_raw_json,
)
from .models import Category, Product

console = Console()

# Commit to SQLite every N products to keep transaction size small.
COMMIT_INTERVAL = 200


def scrape_categories(client: AHClient) -> list[Category]:
    """Fetch and store all categories."""
    console.print("[bold blue]Fetching categories...[/]")
    categories = client.get_categories()

    session = get_session()
    run = ScrapeRun(status="running", notes="categories")
    session.add(run)

    for cat in categories:
        row = session.get(CategoryRow, cat.id)
        if row:
            row.name = cat.name
        else:
            session.add(CategoryRow(id=cat.id, name=cat.name))

    run.categories_scraped = len(categories)
    session.commit()
    console.print(f"[green]Stored {len(categories)} categories[/]")
    return categories


def scrape_category_products(
    client: AHClient,
    category: Category,
    on_progress: Callable[[int, int], None] | None = None,
    fetch_details: bool = False,
) -> list[Product]:
    """Scrape all products in a category, optionally fetching details."""
    all_products: list[Product] = []
    page = 0

    while True:
        products = client.search_products(
            query="",
            page=page,
            taxonomy_id=category.id,
        )
        if not products:
            break

        all_products.extend(products)
        if on_progress:
            on_progress(len(all_products), page + 1)
        page += 1

    return all_products


def scrape_full_catalog(
    client: AHClient,
    category_ids: list[int] | None = None,
    fetch_details: bool = False,
    record_prices: bool = True,
) -> int:
    """
    Full catalog scrape: categories → products → (optional details) → DB.

    Args:
        client: AH API client
        category_ids: Optional list of category IDs to scrape (None = all)
        fetch_details: If True, also fetch nutrition/allergens for each product
        record_prices: If True, record price snapshots in price_history table

    Returns:
        Number of unique products scraped
    """
    init_db()
    session = get_session()

    # Create scrape run record
    run = ScrapeRun(status="running", notes=f"full_catalog, details={fetch_details}, prices={record_prices}")
    session.add(run)
    session.commit()

    run_id = run.id
    api_failures = 0
    total_products = 0
    new_products = 0
    updated_products = 0
    price_snapshots = 0

    try:
        # Get categories
        categories = client.get_categories()
        if category_ids:
            categories = [c for c in categories if c.id in category_ids]

        run.categories_scraped = len(categories)
        session.commit()

        # Progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Scraping products...", total=None)

            for cat in categories:
                cat_task = progress.add_task(
                    f"[blue]{cat.name}[/]", total=None
                )
                page = 0

                while True:
                    try:
                        products, raw_response = client.search_products_raw(
                            query="",
                            page=page,
                            taxonomy_id=cat.id,
                        )
                    except Exception as e:
                        api_failures += 1
                        # 400 on a paginated search = API says "no more pages" —
                        # treat it as end of results for this category and continue.
                        if "400" in str(e):
                            console.print(
                                f"[dim]Category {cat.id} page {page}: "
                                f"400 Bad Request — treating as end of results.[/]"
                            )
                            break
                        console.print(f"[red]API error on category {cat.id} page {page}: {e}[/]")
                        if api_failures > 10:
                            console.print("[red]Too many API failures — aborting.[/]")
                            raise
                        page += 1
                        time.sleep(SEARCH_DELAY)
                        continue

                    if not products:
                        break

                    # Build a lookup: webshopId -> raw product dict from this page
                    raw_lookup = {}
                    if raw_response and "products" in raw_response:
                        for rp in raw_response["products"]:
                            wid = rp.get("webshopId")
                            if wid is not None:
                                raw_lookup[wid] = rp

                    for product in products:
                        # Store raw search product data
                        if product.webshop_id in raw_lookup:
                            store_raw_json(session, product.webshop_id, "search", raw_lookup[product.webshop_id], run_id)

                        # Fetch detail if requested
                        detail = None
                        detail_raw = None
                        if fetch_details:
                            try:
                                detail_raw = client.get_product_detail(product.webshop_id)
                                detail = detail_raw
                            except Exception:
                                api_failures += 1

                        is_new = upsert_product(session, product, detail)
                        if is_new:
                            new_products += 1
                        else:
                            updated_products += 1

                        # Store raw detail response
                        if detail_raw:
                            store_raw_json(session, product.webshop_id, "detail", detail_raw, run_id)

                        # Record price snapshot (dedupe handled inside record_price_snapshot)
                        if record_prices:
                            price_data = {
                                "currentPrice": product.current_price,
                                "priceBeforeBonus": product.price_before_bonus,
                                "isBonus": product.is_bonus,
                                "bonusMechanism": product.bonus_mechanism,
                                "bonusStartDate": product.bonus_start_date,
                                "bonusEndDate": product.bonus_end_date,
                            }
                            record_price_snapshot(session, product.webshop_id, price_data, run_id)
                            price_snapshots += 1

                        total_products += 1
                        progress.update(cat_task, completed=total_products)

                        # Periodic commit every COMMIT_INTERVAL products
                        if total_products % COMMIT_INTERVAL == 0:
                            session.commit()
                            console.print(f"  [dim]Committed batch {total_products} products[/]")

                    page += 1
                    # Rate limiting between pages
                    time.sleep(SEARCH_DELAY)

                progress.remove_task(cat_task)

            progress.update(task, completed=total_products, visible=False)

        # Include retry stats from the client
        retry_info = client.retry_stats()

        # Update run record with detailed notes
        run.products_scraped = total_products
        run.completed_at = datetime.utcnow()
        run.status = "completed"
        notes_parts = [
            f"new={new_products}",
            f"updated={updated_products}",
            f"price_snapshots={price_snapshots}",
            f"api_failures={api_failures}",
            f"retried={retry_info.get('retried', 0)}",
        ]
        run.notes = ", ".join(notes_parts)
        session.commit()

        console.print(f"\n[bold green]Done![/]")
        console.print(f"  Total products processed: {total_products}")
        console.print(f"  New products: {new_products}")
        console.print(f"  Updated products: {updated_products}")
        console.print(f"  Price snapshots recorded: {price_snapshots}")
        console.print(f"  API failures (recovered): {api_failures}")
        console.print(f"  Retries: {retry_info.get('retried', 0)}")

        return total_products

    except Exception as e:
        retry_info = client.retry_stats()
        notes_parts = [
            f"failed: {e}",
            f"products_so_far={total_products}",
            f"api_failures={api_failures}",
            f"retried={retry_info.get('retried', 0)}",
        ]
        run.status = "failed"
        run.notes = ", ".join(notes_parts)
        session.commit()
        raise
