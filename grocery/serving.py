"""Build materialized serving tables for dashboard-ready metrics."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .bonus_analytics import compute_bonus_analytics
from .category_analytics import compute_brand_inflation, compute_category_inflation
from .db import (
    DashboardBonusMetricRow,
    DashboardBrandMetricRow,
    DashboardCategoryMetricRow,
)


def refresh_serving_metrics(session: Session) -> dict[str, int]:
    """Rebuild materialized dashboard metrics from normalized and derived data."""
    computed_at = datetime.utcnow()

    session.query(DashboardCategoryMetricRow).delete()
    category_rows = 0
    for metric in compute_category_inflation(session):
        session.add(
            DashboardCategoryMetricRow(
                category=metric["category"],
                avg_price_change_pct=metric["avg_price_change_pct"],
                median_price_change_pct=metric["median_price_change_pct"],
                products_with_increases=metric["products_with_increases"],
                products_with_decreases=metric["products_with_decreases"],
                products_unchanged=metric["products_unchanged"],
                total_products_tracked=metric["total_products_tracked"],
                computed_at=computed_at,
            )
        )
        category_rows += 1

    session.query(DashboardBrandMetricRow).delete()
    brand_rows = 0
    for metric in compute_brand_inflation(session):
        session.add(
            DashboardBrandMetricRow(
                brand=metric["brand"],
                avg_price_change_pct=metric["avg_price_change_pct"],
                products_with_increases=metric["products_with_increases"],
                products_with_decreases=metric["products_with_decreases"],
                products_unchanged=metric["products_unchanged"],
                total_products_tracked=metric["total_products_tracked"],
                computed_at=computed_at,
            )
        )
        brand_rows += 1

    session.query(DashboardBonusMetricRow).delete()
    bonus_rows = 0
    for group_by in ("brand", "product"):
        result = compute_bonus_analytics(session, group_by=group_by, limit=None)
        label = "webshopId" if group_by == "product" else "brand"
        for metric in result["items"]:
            session.add(
                DashboardBonusMetricRow(
                    group_by=group_by,
                    group_key=str(metric[label]),
                    product_count=metric["productCount"],
                    bonus_count=metric["bonusCount"],
                    bonus_share_pct=metric["bonusSharePct"],
                    avg_discount_depth_pct=metric["avgDiscountDepthPct"],
                    max_discount_depth_pct=metric["maxDiscountDepthPct"],
                    computed_at=computed_at,
                )
            )
            bonus_rows += 1

    return {
        "categoryMetrics": category_rows,
        "brandMetrics": brand_rows,
        "bonusMetrics": bonus_rows,
    }
