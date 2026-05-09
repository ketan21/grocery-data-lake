"""Derived grocery intelligence API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..analytics import compute_price_metrics
from ..bonus_analytics import compute_bonus_analytics
from ..category_analytics import compute_brand_inflation, compute_category_inflation
from ..db import PriceMetricsRow, ProductRow, UnitPriceRow, get_session

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/price-metrics")
def price_metrics(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    recompute: bool = Query(False, description="Recompute metrics before returning results"),
):
    """Return stored price-history metrics joined to product metadata."""
    session = get_session()
    if recompute:
        compute_price_metrics(session)
        session.commit()

    query = (
        session.query(ProductRow, PriceMetricsRow)
        .join(PriceMetricsRow, PriceMetricsRow.product_id == ProductRow.webshop_id)
        .filter(PriceMetricsRow.cheapest_price.isnot(None))
    )
    total = query.count()
    rows = (
        query.order_by(PriceMetricsRow.cheapest_price.asc(), ProductRow.title.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "products": [
            {
                "webshopId": product.webshop_id,
                "title": product.title,
                "brand": product.brand,
                "mainCategory": product.main_category,
                "currentPrice": product.current_price,
                "cheapestPrice": metrics.cheapest_price,
                "cheapestDate": metrics.cheapest_date.isoformat() if metrics.cheapest_date else None,
                "mostExpensivePrice": metrics.most_expensive_price,
                "avgPrice": round(metrics.avg_price, 4) if metrics.avg_price is not None else None,
                "priceVolatility": round(metrics.price_volatility, 6) if metrics.price_volatility is not None else None,
                "totalChanges": metrics.total_changes,
                "firstSeen": metrics.first_seen.isoformat() if metrics.first_seen else None,
                "lastUpdated": metrics.last_updated.isoformat() if metrics.last_updated else None,
            }
            for product, metrics in rows
        ],
    }


@router.get("/unit-prices")
def unit_prices(
    unit: str | None = Query(None, description="Filter by base unit: g, ml, m, m2, stuk"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return normalized unit prices joined to product metadata."""
    session = get_session()
    query = session.query(ProductRow, UnitPriceRow).join(
        UnitPriceRow, UnitPriceRow.product_id == ProductRow.webshop_id
    )
    if unit:
        query = query.filter(UnitPriceRow.base_unit == unit.lower().strip().replace("m²", "m2"))

    total = query.count()
    rows = (
        query.order_by(UnitPriceRow.normalized_price_eur_per_unit.asc(), ProductRow.title.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "products": [
            {
                "webshopId": product.webshop_id,
                "title": product.title,
                "brand": product.brand,
                "mainCategory": product.main_category,
                "currentPrice": product.current_price,
                "normalizedPriceEurPerUnit": unit_price.normalized_price_eur_per_unit,
                "baseUnit": unit_price.base_unit,
                "originalDescription": unit_price.original_description,
            }
            for product, unit_price in rows
        ],
    }


@router.get("/category-inflation")
def category_inflation(limit: int = Query(20, ge=1, le=200)):
    """Return category-level price change metrics."""
    session = get_session()
    return {"categories": compute_category_inflation(session)[:limit]}


@router.get("/brand-inflation")
def brand_inflation(limit: int = Query(20, ge=1, le=200)):
    """Return brand-level price change metrics."""
    session = get_session()
    return {"brands": compute_brand_inflation(session)[:limit]}


@router.get("/bonus")
def bonus_analytics(
    group_by: str = Query("brand", pattern="^(brand|product)$"),
    limit: int = Query(20, ge=1, le=200),
):
    """Return promotion frequency and discount-depth metrics by brand or product."""
    session = get_session()
    return compute_bonus_analytics(session, group_by=group_by, limit=limit)
