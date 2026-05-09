"""Category-level inflation analytics for AH product data.

Computes per-category inflation metrics from price_history snapshots,
grouping products by their main_category field.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .db import PriceHistoryRow, ProductRow, get_session, init_db


def compute_category_inflation(session: Session) -> list[dict[str, Any]]:
    """Compute inflation metrics per category.

    For each category, calculates:
    - avg_price_change_pct: Mean % change from first to latest price
    - median_price_change_pct: Median % change
    - products_with_increases: Count of products that got more expensive
    - products_with_decreases: Count of products that got cheaper
    - products_unchanged: Count of products with no price change
    - total_products_tracked: Total products with >= 2 price snapshots

    Returns:
        List of category metric dicts sorted by avg_price_change_pct descending.
    """
    # Get all products with their category
    products = session.query(ProductRow).filter(
        ProductRow.main_category.isnot(None)
    ).all()

    # Build category -> product_id mapping
    cat_products: dict[str, list[int]] = defaultdict(list)
    for p in products:
        cat_products[p.main_category].append(p.webshop_id)

    results = []
    for category, product_ids in cat_products.items():
        price_changes: list[float] = []

        for pid in product_ids:
            snapshots = (
                session.query(PriceHistoryRow)
                .filter(
                    PriceHistoryRow.product_id == pid,
                    PriceHistoryRow.current_price.isnot(None),
                )
                .order_by(PriceHistoryRow.recorded_at.asc())
                .all()
            )

            if len(snapshots) < 2:
                continue

            first_price = snapshots[0].current_price
            last_price = snapshots[-1].current_price

            if first_price and first_price > 0:
                change_pct = ((last_price - first_price) / first_price) * 100
                price_changes.append(change_pct)

        if not price_changes:
            continue

        price_changes_sorted = sorted(price_changes)
        n = len(price_changes_sorted)
        median_idx = n // 2
        if n % 2 == 0 and n > 1:
            median_change = (price_changes_sorted[median_idx - 1] + price_changes_sorted[median_idx]) / 2
        else:
            median_change = price_changes_sorted[median_idx]

        results.append({
            "category": category,
            "avg_price_change_pct": round(sum(price_changes) / len(price_changes), 2),
            "median_price_change_pct": round(median_change, 2),
            "products_with_increases": sum(1 for c in price_changes if c > 0),
            "products_with_decreases": sum(1 for c in price_changes if c < 0),
            "products_unchanged": sum(1 for c in price_changes if c == 0),
            "total_products_tracked": len(price_changes),
        })

    # Sort by avg inflation descending
    results.sort(key=lambda x: x["avg_price_change_pct"], reverse=True)
    return results


def compute_brand_inflation(session: Session) -> list[dict[str, Any]]:
    """Compute inflation metrics per brand.

    Same logic as category inflation but grouped by brand.
    """
    products = session.query(ProductRow).filter(
        ProductRow.brand.isnot(None)
    ).all()

    brand_products: dict[str, list[int]] = defaultdict(list)
    for p in products:
        brand_products[p.brand].append(p.webshop_id)

    results = []
    for brand, product_ids in brand_products.items():
        price_changes: list[float] = []

        for pid in product_ids:
            snapshots = (
                session.query(PriceHistoryRow)
                .filter(
                    PriceHistoryRow.product_id == pid,
                    PriceHistoryRow.current_price.isnot(None),
                )
                .order_by(PriceHistoryRow.recorded_at.asc())
                .all()
            )

            if len(snapshots) < 2:
                continue

            first_price = snapshots[0].current_price
            last_price = snapshots[-1].current_price

            if first_price and first_price > 0:
                change_pct = ((last_price - first_price) / first_price) * 100
                price_changes.append(change_pct)

        if not price_changes:
            continue

        results.append({
            "brand": brand,
            "avg_price_change_pct": round(sum(price_changes) / len(price_changes), 2),
            "products_with_increases": sum(1 for c in price_changes if c > 0),
            "products_with_decreases": sum(1 for c in price_changes if c < 0),
            "products_unchanged": sum(1 for c in price_changes if c == 0),
            "total_products_tracked": len(price_changes),
        })

    results.sort(key=lambda x: x["avg_price_change_pct"], reverse=True)
    return results
