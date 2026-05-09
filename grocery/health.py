"""Operational health and data quality checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import CategoryRow, PriceHistoryRow, ProductRow, RawJson, ScrapeRun


@dataclass(frozen=True)
class QualityCheck:
    name: str
    passed: bool
    value: Any
    message: str


def get_health_summary(session: Session) -> dict[str, Any]:
    """Return operational health metrics for the local data lake."""
    latest_run = session.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).first()
    previous_run = (
        session.query(ScrapeRun)
        .order_by(ScrapeRun.started_at.desc())
        .offset(1)
        .limit(1)
        .first()
    )
    product_delta = None
    if latest_run and previous_run:
        product_delta = (latest_run.products_scraped or 0) - (previous_run.products_scraped or 0)

    return {
        "products": session.query(ProductRow).count(),
        "categories": session.query(CategoryRow).count(),
        "rawJsonRecords": session.query(RawJson).count(),
        "detailRawJsonRecords": session.query(RawJson).filter(RawJson.source == "detail").count(),
        "latestPriceSnapshot": session.query(func.max(PriceHistoryRow.recorded_at)).scalar(),
        "latestScrapeRun": latest_run,
        "productCountDeltaVsPreviousRun": product_delta,
    }


def run_quality_checks(session: Session) -> list[QualityCheck]:
    """Run lightweight data quality checks suitable for CLI/API health output."""
    product_count = session.query(ProductRow).count()
    category_count = session.query(CategoryRow).count()
    raw_count = session.query(RawJson).count()
    negative_prices = (
        session.query(ProductRow)
        .filter(ProductRow.current_price.isnot(None), ProductRow.current_price < 0)
        .count()
    )
    impossible_discounts = (
        session.query(ProductRow)
        .filter(
            ProductRow.is_bonus == True,  # noqa: E712
            ProductRow.current_price.isnot(None),
            ProductRow.price_before_bonus.isnot(None),
            ProductRow.price_before_bonus > 0,
            ProductRow.current_price > ProductRow.price_before_bonus,
        )
        .count()
    )
    latest_run = session.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).first()
    latest_snapshot = session.query(func.max(PriceHistoryRow.recorded_at)).scalar()

    return [
        QualityCheck("products_nonzero", product_count > 0, product_count, "product table is populated"),
        QualityCheck("categories_present", category_count > 0, category_count, "category table is populated"),
        QualityCheck("raw_json_nonzero", raw_count > 0, raw_count, "raw JSON table is populated"),
        QualityCheck("no_negative_prices", negative_prices == 0, negative_prices, "products have no negative current prices"),
        QualityCheck("no_impossible_bonus_prices", impossible_discounts == 0, impossible_discounts, "bonus products do not exceed pre-bonus price"),
        QualityCheck("latest_scrape_completed", bool(latest_run and latest_run.status == "completed"), latest_run.status if latest_run else None, "latest scrape run completed"),
        QualityCheck("latest_price_snapshot_present", latest_snapshot is not None, latest_snapshot, "price history has at least one snapshot"),
    ]
