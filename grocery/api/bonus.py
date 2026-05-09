"""Bonus/promotion API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..db import init_db, get_session, RawJson

router = APIRouter()


@router.get("/api/bonus/overview")
def bonus_overview():
    """Overview of stored bonus data."""
    init_db()
    session = get_session()

    bonus_count = session.query(RawJson).filter(RawJson.source == "bonus").count()
    bonus_meta_count = session.query(RawJson).filter(RawJson.source == "bonus_metadata").count()

    # Get active period
    meta_record = (
        session.query(RawJson)
        .filter(RawJson.source == "bonus_metadata")
        .order_by(RawJson.fetched_at.desc())
        .first()
    )

    import json
    active_period = None
    if meta_record:
        try:
            data = json.loads(meta_record.raw_data)
            periods = data.get("periods", [])
            if periods:
                active_period = {
                    "startDate": periods[0].get("bonusStartDate"),
                    "endDate": periods[0].get("bonusEndDate"),
                }
        except (json.JSONDecodeError, KeyError):
            pass

    return {
        "bonus_records": bonus_count,
        "metadata_records": bonus_meta_count,
        "active_period": active_period,
    }


@router.get("/api/bonus/metadata")
def bonus_metadata(limit: int = Query(1, ge=1, le=10)):
    """Get stored bonus metadata (weekly folders, dates, categories)."""
    init_db()
    session = get_session()

    records = (
        session.query(RawJson)
        .filter(RawJson.source == "bonus_metadata")
        .order_by(RawJson.fetched_at.desc())
        .limit(limit)
        .all()
    )

    import json
    results = []
    for r in records:
        results.append({
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            "data": json.loads(r.raw_data),
        })

    return results


@router.get("/api/bonus/items")
def bonus_items(
    limit: int = Query(20, ge=1, le=100),
    product_id: Optional[int] = Query(None, description="Filter by product webshopId"),
):
    """Get stored bonus/promotion items."""
    init_db()
    session = get_session()

    q = session.query(RawJson).filter(RawJson.source == "bonus")
    if product_id is not None:
        q = q.filter(RawJson.product_id == product_id)
    q = q.order_by(RawJson.fetched_at.desc()).limit(limit)
    records = q.all()

    import json
    results = []
    for r in records:
        results.append({
            "product_id": r.product_id,
            "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            "sub_source": r.sub_source,
            "data": json.loads(r.raw_data),
        })

    return results
