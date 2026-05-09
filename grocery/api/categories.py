"""Category API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ..db import CategoryRow, ProductRow, get_session

router = APIRouter()


@router.get("/categories")
def list_categories():
    """List all categories with product counts."""
    session = get_session()
    categories = session.query(CategoryRow).order_by(CategoryRow.name).all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "productCount": session.query(ProductRow).filter(
                ProductRow.main_category == c.name
            ).count(),
        }
        for c in categories
    ]
