"""Scrape bonus/promotion data and store raw JSON for grocery intelligence."""

from __future__ import annotations

import json
from datetime import datetime, date as date_type

from rich.console import Console
from rich.progress import Progress

from .client import AHClient
from .db import (
    CategoryRow, ProductRow, ScrapeRun,
    get_session, init_db, store_raw_json,
)

console = Console()


def scrape_bonus() -> dict:
    """Scrape current bonus metadata + all category sections.

    Returns:
        Summary dict with counts.
    """
    init_db()
    client = AHClient()
    session = get_session()

    # Create scrape run
    run = ScrapeRun(status="running", started_at=datetime.utcnow())
    session.add(run)
    session.commit()
    run_id = run.id

    console.print(f"\n[bold]Scraping bonus/promotion data[/bold] (run {run_id})")

    # 1. Fetch bonus metadata (weekly periods, categories, dates)
    console.print("\n[yellow]Fetching bonus metadata...[/yellow]")
    metadata = client.get_bonus_metadata()
    store_raw_json(session, None, "bonus_metadata", metadata, run_id, "bonuspage/v3/metadata")
    console.print(f"  Stored bonus metadata: {len(json.dumps(metadata))} bytes")

    # 2. Extract active period
    periods = metadata.get("periods", [])
    if not periods:
        console.print("  [red]No bonus periods found[/red]")
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        session.commit()
        return {"status": "no_periods"}

    active_period = periods[0]
    bonus_start = active_period.get("bonusStartDate")
    bonus_end = active_period.get("bonusEndDate")
    console.print(f"  Active period: {bonus_start} → {bonus_end}")

    # 3. Extract all category URLs from tabs
    category_urls = []
    for tab in active_period.get("tabs", []):
        for meta in tab.get("urlMetadataList", []):
            bonus_type = meta.get("bonusType", "")
            description = meta.get("description", "")
            url = meta.get("url", "")
            count = meta.get("count", 0)
            category_urls.append({
                "url": url,
                "type": bonus_type,
                "description": description,
                "count": count,
            })

    console.print(f"  Found {len(category_urls)} bonus sections")

    # 4. Fetch each bonus section
    stored_items = 0
    bonus_products = {}  # webshopId -> bonus data

    with Progress() as progress:
        task = progress.add_task("[blue]Fetching bonus sections...", total=len(category_urls))

        for section_info in category_urls:
            url = section_info["url"]
            description = section_info["description"]
            count = section_info["count"]

            # Parse the URL to get params
            # URL format: bonuspage/v2/section?application=AHWEBSHOP&date=2026-05-04&promotionType=NATIONAL&category=Groente
            # or: bonuspage/v2/section/spotlight?application=AHWEBSHOP&date=2026-05-04
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(f"http://dummy/{url}")
            params = parse_qs(parsed.query)
            cat_name = params.get("category", [None])[0]

            try:
                bonus_data = client.get_bonus_section(date=bonus_start, category=cat_name)
                sub_source = f"bonuspage/v2/section{'/spotlight' if not cat_name else ''}"

                # Store the full section response
                store_raw_json(session, None, "bonus", bonus_data, run_id, sub_source)

                # Extract individual products/groups
                items = bonus_data.get("bonusGroupOrProducts", [])
                for item in items:
                    if "product" in item:
                        prod = item["product"]
                        wid = prod.get("webshopId")
                        if wid:
                            # Store per-product bonus data
                            store_raw_json(session, wid, "bonus", item, run_id, sub_source)
                            bonus_products[wid] = item
                            stored_items += 1
                    elif "bonusGroup" in item:
                        # Store bonus group (e.g., "2e gratis" on all apples)
                        store_raw_json(session, None, "bonus", item, run_id, sub_source)
                        stored_items += 1

                progress.update(task, advance=1, description=f"[blue]{description} ({count} items)[/]")

            except Exception as e:
                progress.update(task, advance=1, description=f"[red]{description} (ERROR: {e})[/]")
                console.print(f"  [red]Error fetching {description}: {e}[/red]")

    # Update scrape run
    run.status = "completed"
    run.completed_at = datetime.utcnow()
    run.products_scraped = len(bonus_products)
    session.commit()

    summary = {
        "status": "completed",
        "period": f"{bonus_start} → {bonus_end}",
        "sections_fetched": len(category_urls),
        "bonus_products": len(bonus_products),
        "total_items_stored": stored_items,
    }

    console.print(f"\n[bold green]Bonus scrape complete:[/bold green]")
    console.print(f"  Period: {bonus_start} → {bonus_end}")
    console.print(f"  Sections: {len(category_urls)}")
    console.print(f"  Bonus products: {len(bonus_products)}")
    console.print(f"  Total items stored: {stored_items}")

    return summary
