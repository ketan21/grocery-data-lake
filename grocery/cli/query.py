"""Query commands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import (
    CategoryRow, ProductRow, PriceHistoryRow, ScrapeRun,
    NutritionRow, AllergenRow, IngredientRow, RawJson,
    get_session, init_db,
)

app = typer.Typer(add_completion=False)
console = Console()


def _session() -> Session:
    init_db()
    return get_session()


@app.command("search")
def search(
    term: Annotated[str, typer.Argument(help="Search term for title/brand")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
):
    """Search products by title or brand."""
    session = _session()

    results = (
        session.query(ProductRow)
        .filter(
            (ProductRow.title.ilike(f"%{term}%")) | (ProductRow.brand.ilike(f"%{term}%"))
        )
        .limit(limit)
        .all()
    )

    table = Table(title=f"Search results for '{term}' ({len(results)} found)")
    table.add_column("ID", style="dim")
    table.add_column("Title")
    table.add_column("Brand")
    table.add_column("Price")
    table.add_column("Bonus")
    table.add_column("Category")

    for p in results:
        table.add_row(
            str(p.webshop_id),
            p.title[:50] if p.title else "",
            p.brand or "",
            f"€{p.current_price:.2f}" if p.current_price else "",
            "✓" if p.is_bonus else "",
            (p.sub_category or p.main_category or "")[:30],
        )

    console.print(table)


@app.command("stats")
def stats():
    """Show database statistics."""
    session = _session()

    total_products = session.query(ProductRow).count()
    total_categories = session.query(CategoryRow).count()
    bonus_products = session.query(ProductRow).filter(ProductRow.is_bonus == True).count()  # noqa: E712
    brands = session.query(ProductRow.brand).filter(ProductRow.brand.isnot(None)).distinct().count()

    # Price range
    price_stats = session.query(
        func.min(ProductRow.current_price),
        func.max(ProductRow.current_price),
        func.avg(ProductRow.current_price),
    ).filter(ProductRow.current_price.isnot(None)).first()

    console.print("\n[bold]Database Statistics[/]")
    console.print(f"  Categories: {total_categories}")
    console.print(f"  Products: {total_products}")
    console.print(f"  Unique brands: {brands}")
    console.print(f"  Bonus products: {bonus_products}")
    if price_stats and price_stats[0] is not None:
        console.print(f"  Price range: €{price_stats[0]:.2f} - €{price_stats[1]:.2f} (avg €{price_stats[2]:.2f})")


@app.command("product")
def product_detail(
    webshop_id: Annotated[int, typer.Argument(help="Product webshopId")],
):
    """Show product details."""
    session = _session()

    p = session.get(ProductRow, webshop_id)
    if not p:
        console.print(f"[red]Product {webshop_id} not found[/]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{p.title}[/]")
    console.print(f"  ID: {p.webshop_id}")
    console.print(f"  Brand: {p.brand or 'N/A'}")
    console.print(f"  Price: {'€' + str(p.current_price) if p.current_price else 'N/A'}")
    console.print(f"  Regular price: {'€' + str(p.price_before_bonus) if p.price_before_bonus else 'N/A'}")
    console.print(f"  Category: {p.main_category or 'N/A'} > {p.sub_category or 'N/A'}")
    console.print(f"  Bonus: {'✓ ' + (p.bonus_mechanism or '') if p.is_bonus else 'No'}")
    console.print(f"  NutriScore: {p.nutriscore or 'N/A'}")
    console.print(f"  Unit size: {p.sales_unit_size or 'N/A'}")

    # Nutrition
    nutrition = [n for n in p.nutrition_rows]
    if nutrition:
        console.print("\n  [bold]Nutrition:[/]")
        for n in nutrition:
            console.print(f"    {n.nutrient_name}: {n.value} {n.unit} ({n.basis})")

    # Allergens
    allergens = [a for a in p.allergen_rows]
    if allergens:
        console.print("\n  [bold]Allergens:[/]")
        for a in allergens:
            console.print(f"    {a.allergen_name} ({a.level})")


@app.command("categories")
def list_categories():
    """List all categories."""
    session = _session()

    categories = session.query(CategoryRow).order_by(CategoryRow.name).all()

    table = Table(title=f"Categories ({len(categories)})")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Products", justify="right")

    for c in categories:
        count = session.query(ProductRow).filter(ProductRow.main_category == c.name).count()
        table.add_row(str(c.id), c.name, str(count))

    console.print(table)


@app.command("price-history")
def price_history(
    product_id: Annotated[int | None, typer.Argument(help="Product webshopId (omit for overview)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 20,
):
    """Show price history for a product, or overview of price tracking."""
    session = _session()

    if product_id is None:
        # Overview
        total_snapshots = session.query(PriceHistoryRow).count()
        total_runs = session.query(ScrapeRun).count()
        products_tracked = session.query(PriceHistoryRow.product_id).distinct().count()

        console.print("\n[bold]Price History Overview[/]")
        console.print(f"  Total price snapshots: {total_snapshots}")
        console.print(f"  Scrape runs recorded: {total_runs}")
        console.print(f"  Products tracked: {products_tracked}")

        # Latest scrape runs
        runs = session.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(5).all()
        if runs:
            console.print("\n  [bold]Recent scrape runs:[/bold]")
            for r in runs:
                console.print(f"    {r.started_at.strftime('%Y-%m-%d %H:%M')} — {r.products_scraped} products — {r.status} ({r.notes or ''})")
        return

    # Per-product history
    p = session.get(ProductRow, product_id)
    if not p:
        console.print(f"[red]Product {product_id} not found[/]")
        raise typer.Exit(1)

    snapshots = (
        session.query(PriceHistoryRow)
        .filter(PriceHistoryRow.product_id == product_id)
        .order_by(PriceHistoryRow.recorded_at.desc())
        .limit(limit)
        .all()
    )

    console.print(f"\n[bold]{p.title}[/] (ID: {product_id})")
    console.print(f"  Current price: {'€' + str(p.current_price) if p.current_price else 'N/A'}")
    console.print(f"  Price snapshots: {len(snapshots)}")

    if snapshots:
        table = Table(title=f"Price history for {p.title[:40]}")
        table.add_column("Date", style="dim")
        table.add_column("Price")
        table.add_column("Regular Price")
        table.add_column("Bonus")
        table.add_column("Mechanism")

        for s in snapshots:
            table.add_row(
                s.recorded_at.strftime("%Y-%m-%d %H:%M"),
                f"€{s.current_price:.2f}" if s.current_price else "",
                f"€{s.price_before_bonus:.2f}" if s.price_before_bonus else "",
                "✓" if s.is_bonus else "",
                (s.bonus_mechanism or "")[:30],
            )

        console.print(table)


@app.command("enrich-stats")
def enrich_stats():
    """Show enrichment statistics (nutrition, allergens, ingredients)."""
    session = _session()

    total_products = session.query(ProductRow).count()
    products_with_nutrition = session.query(NutritionRow.product_id).distinct().count()
    products_with_allergens = session.query(AllergenRow.product_id).distinct().count()
    products_with_ingredients = session.query(IngredientRow.product_id).distinct().count()

    total_nutrition = session.query(NutritionRow).count()
    total_allergens = session.query(AllergenRow).count()
    total_ingredients = session.query(IngredientRow).count()

    # Products with extra fields
    products_with_barcode = session.query(ProductRow).filter(ProductRow.barcode.isnot(None)).count()
    products_with_manufacturer = session.query(ProductRow).filter(ProductRow.manufacturer.isnot(None)).count()
    products_with_origin = session.query(ProductRow).filter(ProductRow.origin_country.isnot(None)).count()

    console.print("\n[bold]Enrichment Statistics[/]")
    console.print(f"  Total products: {total_products}")
    console.print(f"\n  Nutrition data: {products_with_nutrition}/{total_products} products ({total_nutrition} entries)")
    console.print(f"  Allergen data: {products_with_allergens}/{total_products} products ({total_allergens} entries)")
    console.print(f"  Ingredient data: {products_with_ingredients}/{total_products} products ({total_ingredients} entries)")
    console.print(f"\n  Extra fields:")
    console.print(f"    Barcode: {products_with_barcode}/{total_products}")
    console.print(f"    Manufacturer: {products_with_manufacturer}/{total_products}")
    console.print(f"    Origin country: {products_with_origin}/{total_products}")

    # Raw JSON stats
    raw_search = session.query(RawJson).filter(RawJson.source == "search").count()
    raw_detail = session.query(RawJson).filter(RawJson.source == "detail").count()
    raw_bonus = session.query(RawJson).filter(RawJson.source == "bonus").count()
    raw_bonus_meta = session.query(RawJson).filter(RawJson.source == "bonus_metadata").count()
    raw_total = session.query(RawJson).count()
    if raw_total:
        console.print(f"\n  Raw JSON storage:")
        console.print(f"    Search responses: {raw_search}")
        console.print(f"    Detail responses: {raw_detail}")
        console.print(f"    Bonus responses: {raw_bonus}")
        console.print(f"    Bonus metadata: {raw_bonus_meta}")
        console.print(f"    Total: {raw_total}")


@app.command("raw-json")
def raw_json(
    product_id: Annotated[int | None, typer.Argument(help="Product webshopId (omit for bonus-metadata)")] = None,
    source: Annotated[str, typer.Option("--source", "-s", help="Source: search, detail, bonus, bonus_metadata")] = "detail",
    pretty: Annotated[bool, typer.Option("--pretty", "-p", help="Pretty-print JSON")] = True,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 1,
):
    """Show raw API JSON response for a product or bonus data."""
    import json

    session = _session()

    if source == "bonus_metadata":
        records = (
            session.query(RawJson)
            .filter(RawJson.source == "bonus_metadata")
            .order_by(RawJson.fetched_at.desc())
            .limit(limit)
            .all()
        )
        if not records:
            console.print("[red]No bonus metadata stored. Run 'grocery bonus scrape' first.[/]")
            raise typer.Exit(1)
        console.print(f"\n[bold]Raw bonus metadata[/]")
    elif source == "bonus":
        records = (
            session.query(RawJson)
            .filter(RawJson.source == "bonus")
            .order_by(RawJson.fetched_at.desc())
            .limit(limit)
            .all()
        )
        if not records:
            console.print("[red]No bonus data stored. Run 'grocery bonus scrape' first.[/]")
            raise typer.Exit(1)
        console.print(f"\n[bold]Raw bonus data ({len(records)} records)[/]")
    else:
        if product_id is None:
            console.print("[red]Product ID required for search/detail sources.[/]")
            raise typer.Exit(1)

        p = session.get(ProductRow, product_id)
        if not p:
            console.print(f"[red]Product {product_id} not found[/]")
            raise typer.Exit(1)

        records = (
            session.query(RawJson)
            .filter(RawJson.product_id == product_id, RawJson.source == source)
            .order_by(RawJson.fetched_at.desc())
            .limit(limit)
            .all()
        )

        if not records:
            console.print(f"[red]No raw {source} JSON found for product {product_id}[/]")
            raise typer.Exit(1)

        console.print(f"\n[bold]Raw {source} JSON for {p.title}[/] (ID: {product_id})")

    console.print(f"  Fetched at: {records[0].fetched_at.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"  Size: {len(records[0].raw_data)} chars")
    console.print()

    for record in records:
        if pretty:
            parsed = json.loads(record.raw_data)
            console.print(json.dumps(parsed, indent=2, ensure_ascii=False, default=str))
        else:
            console.print(record.raw_data)
        console.print()
