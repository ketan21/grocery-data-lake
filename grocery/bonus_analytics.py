"""Promotion analytics shared by CLI and API."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import Integer, case, cast, func
from sqlalchemy.orm import Session

from .db import ProductRow


GroupBy = Literal["brand", "product"]


def compute_bonus_analytics(
    session: Session,
    group_by: GroupBy = "brand",
    limit: int = 20,
) -> dict:
    """Compute active promotion frequency and discount depth.

    Discount depth is calculated only for active bonus products with valid
    current and pre-bonus prices, so non-promoted products do not dilute the
    average.
    """
    if group_by not in {"brand", "product"}:
        raise ValueError("group_by must be 'brand' or 'product'")

    group_col = ProductRow.webshop_id if group_by == "product" else ProductRow.brand
    label = "webshopId" if group_by == "product" else "brand"
    bonus_flag = cast(ProductRow.is_bonus, Integer)
    discount_pct = (
        (ProductRow.price_before_bonus - ProductRow.current_price)
        / ProductRow.price_before_bonus
        * 100
    )
    valid_discount = (
        (ProductRow.is_bonus == True)  # noqa: E712
        & ProductRow.current_price.isnot(None)
        & ProductRow.price_before_bonus.isnot(None)
        & (ProductRow.price_before_bonus > 0)
        & (ProductRow.current_price >= 0)
    )
    bonus_discount_pct = case((valid_discount, discount_pct), else_=None)

    rows = (
        session.query(
            group_col,
            func.count(ProductRow.webshop_id),
            func.sum(bonus_flag),
            func.avg(bonus_discount_pct),
            func.max(bonus_discount_pct),
        )
        .filter(group_col.isnot(None))
        .group_by(group_col)
        .order_by(func.sum(bonus_flag).desc())
        .limit(limit)
        .all()
    )

    return {
        "groupBy": group_by,
        "items": [
            {
                label: row[0],
                "productCount": row[1],
                "bonusCount": row[2] or 0,
                "bonusSharePct": round(((row[2] or 0) / row[1]) * 100, 2) if row[1] else 0,
                "avgDiscountDepthPct": round(row[3], 2) if row[3] is not None else None,
                "maxDiscountDepthPct": round(row[4], 2) if row[4] is not None else None,
            }
            for row in rows
        ],
    }
