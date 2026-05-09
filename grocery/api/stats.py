"""Stats API endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func

from ..db import CategoryRow, ProductRow, ScrapeRun, get_session

router = APIRouter()


@router.get("/stats")
def get_stats():
    """Get catalog statistics."""
    session = get_session()

    total_products = session.query(ProductRow).count()
    total_categories = session.query(CategoryRow).count()
    bonus_count = session.query(ProductRow).filter(ProductRow.is_bonus == True).count()  # noqa: E712
    brands = session.query(ProductRow.brand).filter(
        ProductRow.brand.isnot(None)
    ).distinct().count()

    price_stats = session.query(
        func.min(ProductRow.current_price),
        func.max(ProductRow.current_price),
        func.avg(ProductRow.current_price),
    ).filter(ProductRow.current_price.isnot(None)).first()

    last_run = session.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).first()

    return {
        "totalProducts": total_products,
        "totalCategories": total_categories,
        "uniqueBrands": brands,
        "bonusProducts": bonus_count,
        "priceRange": {
            "min": price_stats[0],
            "max": price_stats[1],
            "avg": round(price_stats[2], 2) if price_stats[2] else None,
        },
        "lastScrapeRun": {
            "startedAt": last_run.started_at.isoformat() if last_run else None,
            "completedAt": last_run.completed_at.isoformat() if last_run and last_run.completed_at else None,
            "productsScraped": last_run.products_scraped if last_run else None,
            "status": last_run.status if last_run else None,
        },
    }
