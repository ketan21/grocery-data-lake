"""Raw JSON API endpoints — grocery intelligence data."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..db import (
    ProductRow, RawJson, get_session, init_db,
)

router = APIRouter(prefix="/api/raw", tags=["raw-json"])


class RawJsonResponse(BaseModel):
    product_id: Optional[int] = Field(None, description="Product webshopId (null for non-product data)")
    source: str = Field(..., description="Source type: search, detail, bonus, bonus_metadata, graphql, category")
    sub_source: Optional[str] = Field(None, description="Sub-endpoint identifier")
    fetched_at: str = Field(..., description="ISO timestamp")
    size_bytes: int = Field(..., description="Raw JSON size in bytes")
    data: dict = Field(..., description="Raw API response")


class RawJsonStats(BaseModel):
    total_records: int
    search_responses: int
    detail_responses: int
    bonus_responses: int
    bonus_metadata_responses: int
    avg_size_bytes: float
    avg_search_size_bytes: float
    avg_detail_size_bytes: float
    avg_bonus_size_bytes: float


@router.get("/search/{product_id}", response_model=RawJsonResponse)
def get_raw_search(product_id: int):
    """Get raw search API response for a product."""
    session = get_session()
    row = (
        session.query(RawJson)
        .filter(RawJson.product_id == product_id, RawJson.source == "search")
        .order_by(RawJson.fetched_at.desc())
        .first()
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    product = session.query(ProductRow).filter(ProductRow.webshop_id == product_id).first()
    return RawJsonResponse(
        product_id=row.product_id,
        source=row.source,
        sub_source=row.sub_source,
        fetched_at=row.fetched_at.isoformat(),
        size_bytes=len(row.raw_data),
        data=json.loads(row.raw_data),
    )


@router.get("/detail/{product_id}", response_model=RawJsonResponse)
def get_raw_detail(product_id: int):
    """Get raw detail API response for a product."""
    session = get_session()
    row = (
        session.query(RawJson)
        .filter(RawJson.product_id == product_id, RawJson.source == "detail")
        .order_by(RawJson.fetched_at.desc())
        .first()
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    return RawJsonResponse(
        product_id=row.product_id,
        source=row.source,
        sub_source=row.sub_source,
        fetched_at=row.fetched_at.isoformat(),
        size_bytes=len(row.raw_data),
        data=json.loads(row.raw_data),
    )


@router.get("/bonus/{product_id}", response_model=RawJsonResponse)
def get_raw_bonus(product_id: int):
    """Get raw bonus/promotion data for a product."""
    session = get_session()
    row = (
        session.query(RawJson)
        .filter(RawJson.product_id == product_id, RawJson.source == "bonus")
        .order_by(RawJson.fetched_at.desc())
        .first()
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No bonus data for product {product_id}")

    return RawJsonResponse(
        product_id=row.product_id,
        source=row.source,
        sub_source=row.sub_source,
        fetched_at=row.fetched_at.isoformat(),
        size_bytes=len(row.raw_data),
        data=json.loads(row.raw_data),
    )


@router.get("/bonus-metadata")
def get_bonus_metadata():
    """Get latest bonus metadata (weekly periods, categories, dates)."""
    session = get_session()
    row = (
        session.query(RawJson)
        .filter(RawJson.source == "bonus_metadata")
        .order_by(RawJson.fetched_at.desc())
        .first()
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No bonus metadata stored")

    return RawJsonResponse(
        product_id=None,
        source=row.source,
        sub_source=row.sub_source,
        fetched_at=row.fetched_at.isoformat(),
        size_bytes=len(row.raw_data),
        data=json.loads(row.raw_data),
    )


@router.get("/stats", response_model=RawJsonStats)
def get_raw_stats():
    """Get raw JSON storage statistics."""
    from sqlalchemy import func

    session = get_session()
    init_db()

    total = session.query(RawJson).count()
    search_count = session.query(RawJson).filter(RawJson.source == "search").count()
    detail_count = session.query(RawJson).filter(RawJson.source == "detail").count()
    bonus_count = session.query(RawJson).filter(RawJson.source == "bonus").count()
    bonus_meta_count = session.query(RawJson).filter(RawJson.source == "bonus_metadata").count()

    avg_size = session.query(func.avg(func.length(RawJson.raw_data))).scalar() or 0
    avg_search = (
        session.query(func.avg(func.length(RawJson.raw_data)))
        .filter(RawJson.source == "search")
        .scalar()
    ) or 0
    avg_detail = (
        session.query(func.avg(func.length(RawJson.raw_data)))
        .filter(RawJson.source == "detail")
        .scalar()
    ) or 0
    avg_bonus = (
        session.query(func.avg(func.length(RawJson.raw_data)))
        .filter(RawJson.source == "bonus")
        .scalar()
    ) or 0

    return RawJsonStats(
        total_records=total,
        search_responses=search_count,
        detail_responses=detail_count,
        bonus_responses=bonus_count,
        bonus_metadata_responses=bonus_meta_count,
        avg_size_bytes=round(avg_size, 1),
        avg_search_size_bytes=round(avg_search, 1),
        avg_detail_size_bytes=round(avg_detail, 1),
        avg_bonus_size_bytes=round(avg_bonus, 1),
    )
