"""Product API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..db import ProductRow, get_session

router = APIRouter()


@router.get("/search")
def search_products(
    q: str = Query(..., description="Search term for title, brand, or category"),
    limit: int = Query(20, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Search products by title, brand, or category."""
    session = get_session()
    query = session.query(ProductRow).filter(
        (ProductRow.title.ilike(f"%{q}%"))
        | (ProductRow.brand.ilike(f"%{q}%"))
        | (ProductRow.main_category.ilike(f"%{q}%"))
    )

    total = query.count()
    products = query.order_by(ProductRow.title).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "products": [
            {
                "webshopId": p.webshop_id,
                "title": p.title,
                "brand": p.brand,
                "currentPrice": p.current_price,
                "priceBeforeBonus": p.price_before_bonus,
                "mainCategory": p.main_category,
                "subCategory": p.sub_category,
                "isBonus": p.is_bonus,
                "nutriscore": p.nutriscore,
                "imageUrl": p.image_url,
            }
            for p in products
        ],
    }


@router.get("/products")
def list_products(
    q: str | None = Query(None, description="Search in title/brand"),
    category: str | None = Query(None, description="Filter by main category"),
    brand: str | None = Query(None, description="Filter by brand"),
    bonus: bool | None = Query(None, description="Filter by bonus status"),
    nutriscore: str | None = Query(None, description="Filter by NutriScore (A-E)"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Search and filter products."""
    session = get_session()
    query = session.query(ProductRow)

    if q:
        query = query.filter(
            (ProductRow.title.ilike(f"%{q}%")) | (ProductRow.brand.ilike(f"%{q}%"))
        )
    if category:
        query = query.filter(ProductRow.main_category.ilike(f"%{category}%"))
    if brand:
        query = query.filter(ProductRow.brand.ilike(f"%{brand}%"))
    if bonus is not None:
        query = query.filter(ProductRow.is_bonus == bonus)
    if nutriscore:
        query = query.filter(ProductRow.nutriscore == nutriscore.upper())

    total = query.count()
    products = query.order_by(ProductRow.title).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "products": [
            {
                "webshopId": p.webshop_id,
                "title": p.title,
                "brand": p.brand,
                "currentPrice": p.current_price,
                "priceBeforeBonus": p.price_before_bonus,
                "mainCategory": p.main_category,
                "subCategory": p.sub_category,
                "isBonus": p.is_bonus,
                "nutriscore": p.nutriscore,
                "imageUrl": p.image_url,
            }
            for p in products
        ],
    }


@router.get("/products/{webshop_id}")
def get_product(webshop_id: int):
    """Get product detail with nutrition and allergens."""
    session = get_session()
    p = session.get(ProductRow, webshop_id)

    if not p:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "webshopId": p.webshop_id,
        "title": p.title,
        "brand": p.brand,
        "salesUnitSize": p.sales_unit_size,
        "currentPrice": p.current_price,
        "priceBeforeBonus": p.price_before_bonus,
        "mainCategory": p.main_category,
        "subCategory": p.sub_category,
        "nutriscore": p.nutriscore,
        "isBonus": p.is_bonus,
        "bonusMechanism": p.bonus_mechanism,
        "bonusStartDate": p.bonus_start_date,
        "bonusEndDate": p.bonus_end_date,
        "availableOnline": p.available_online,
        "descriptionHighlights": p.description_highlights,
        "imageUrl": p.image_url,
        "nutrition": [
            {
                "name": n.nutrient_name,
                "value": n.value,
                "unit": n.unit,
                "basis": n.basis,
            }
            for n in p.nutrition_rows
        ],
        "allergens": [
            {"name": a.allergen_name, "level": a.level}
            for a in p.allergen_rows
        ],
    }
