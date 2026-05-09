"""Price-history analytics for grocery products."""

from __future__ import annotations

from datetime import datetime
from math import sqrt

from sqlalchemy.orm import Session

from .db import PriceHistoryRow, PriceMetricsRow


def _std_dev(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _price_change_count(values: list[float]) -> int:
    if len(values) < 2:
        return 0
    return sum(1 for previous, current in zip(values, values[1:]) if current != previous)


def compute_price_metrics(session: Session) -> int:
    """Compute and upsert price metrics from all price_history snapshots."""
    product_ids = [
        row[0]
        for row in session.query(PriceHistoryRow.product_id).distinct().all()
    ]

    updated = 0
    now = datetime.utcnow()
    for product_id in product_ids:
        snapshots = (
            session.query(PriceHistoryRow)
            .filter(
                PriceHistoryRow.product_id == product_id,
                PriceHistoryRow.current_price.isnot(None),
            )
            .order_by(PriceHistoryRow.recorded_at.asc(), PriceHistoryRow.id.asc())
            .all()
        )
        if not snapshots:
            continue

        prices = [snapshot.current_price for snapshot in snapshots if snapshot.current_price is not None]
        cheapest = min(snapshots, key=lambda snapshot: snapshot.current_price)
        most_expensive = max(snapshots, key=lambda snapshot: snapshot.current_price)

        row = (
            session.query(PriceMetricsRow)
            .filter(PriceMetricsRow.product_id == product_id)
            .first()
        )
        if row is None:
            row = PriceMetricsRow(product_id=product_id)
            session.add(row)

        row.cheapest_price = cheapest.current_price
        row.cheapest_date = cheapest.recorded_at
        row.most_expensive_price = most_expensive.current_price
        row.most_expensive_date = most_expensive.recorded_at
        row.avg_price = sum(prices) / len(prices)
        row.price_volatility = _std_dev(prices)
        row.total_changes = _price_change_count(prices)
        row.first_seen = snapshots[0].recorded_at
        row.last_updated = now
        updated += 1

    return updated
