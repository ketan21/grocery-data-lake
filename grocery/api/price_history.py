"""Price history API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException

from ..db import ProductRow, PriceHistoryRow, ScrapeRun, get_session

router = APIRouter()


@router.get("/price-history")
def price_history_overview():
    """Overview of price tracking."""
    session = get_session()

    total_snapshots = session.query(PriceHistoryRow).count()
    total_runs = session.query(ScrapeRun).count()
    products_tracked = session.query(PriceHistoryRow.product_id).distinct().count()

    # Recent scrape runs
    runs = session.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(10).all()

    return {
        "total_snapshots": total_snapshots,
        "scrape_runs": total_runs,
        "products_tracked": products_tracked,
        "recent_runs": [
            {
                "id": r.id,
                "startedAt": r.started_at.isoformat() if r.started_at else None,
                "completedAt": r.completed_at.isoformat() if r.completed_at else None,
                "productsScraped": r.products_scraped,
                "status": r.status,
                "notes": r.notes,
            }
            for r in runs
        ],
    }


@router.get("/price-history/{product_id}")
def product_price_history(
    product_id: int,
    limit: int = Query(100, ge=1, le=1000, description="Max snapshots"),
):
    """Get price history for a specific product."""
    session = get_session()

    p = session.get(ProductRow, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")

    snapshots = (
        session.query(PriceHistoryRow)
        .filter(PriceHistoryRow.product_id == product_id)
        .order_by(PriceHistoryRow.recorded_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "webshopId": p.webshop_id,
        "title": p.title,
        "brand": p.brand,
        "currentPrice": p.current_price,
        "snapshots": [
            {
                "recordedAt": s.recorded_at.isoformat() if s.recorded_at else None,
                "currentPrice": s.current_price,
                "priceBeforeBonus": s.price_before_bonus,
                "isBonus": s.is_bonus,
                "bonusMechanism": s.bonus_mechanism,
                "bonusStartDate": s.bonus_start_date,
                "bonusEndDate": s.bonus_end_date,
                "scrapeRunId": s.scrape_run_id,
            }
            for s in snapshots
        ],
    }


@router.get("/price-history/{product_id}/inflation")
def product_inflation(product_id: int):
    """Calculate inflation metrics for a product."""
    session = get_session()

    p = session.get(ProductRow, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")

    snapshots = (
        session.query(PriceHistoryRow)
        .filter(PriceHistoryRow.product_id == product_id)
        .order_by(PriceHistoryRow.recorded_at.asc())
        .all()
    )

    if len(snapshots) < 2:
        return {
            "webshopId": p.webshop_id,
            "title": p.title,
            "message": "Need at least 2 price snapshots to calculate inflation",
            "snapshots": len(snapshots),
        }

    prices = [s.current_price for s in snapshots if s.current_price is not None]
    if len(prices) < 2:
        return {
            "webshopId": p.webshop_id,
            "title": p.title,
            "message": "Not enough valid prices",
            "snapshots": len(snapshots),
        }

    first_price = prices[0]
    last_price = prices[-1]
    price_change = last_price - first_price
    price_change_pct = (price_change / first_price * 100) if first_price else 0

    return {
        "webshopId": p.webshop_id,
        "title": p.title,
        "brand": p.brand,
        "firstPrice": first_price,
        "lastPrice": last_price,
        "priceChange": round(price_change, 2),
        "priceChangePercent": round(price_change_pct, 2),
        "totalSnapshots": len(snapshots),
        "minPrice": round(min(prices), 2),
        "maxPrice": round(max(prices), 2),
        "avgPrice": round(sum(prices) / len(prices), 2),
    }
