"""Unit price normalization for AH product data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from .db import ProductRow, UnitPriceRow


_PRICE_RE = re.compile(
    r"€\s*(?P<price>\d+(?:[,.]\d+)?)\s*/\s*(?P<quantity>\d+(?:[,.]\d+)?)?\s*(?P<unit>[^\s]+)",
    re.IGNORECASE,
)
_PRICE_PER_RE = re.compile(
    r"\bper\s+(?P<unit>[a-zA-Z0-9²]+)\s+€\s*(?P<price>\d+(?:[,.]\d+)?)",
    re.IGNORECASE,
)

_UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "kg": "kg",
    "kilo": "kg",
    "ml": "ml",
    "cl": "ml",
    "l": "l",
    "liter": "l",
    "ltr": "l",
    "m": "m",
    "meter": "m",
    "m2": "m2",
    "m²": "m2",
    "stuk": "stuk",
    "st": "stuk",
    "stuks": "stuk",
    "piece": "stuk",
}

_CONVERSIONS = {
    "g": ("g", 1.0),
    "kg": ("g", 1000.0),
    "ml": ("ml", 1.0),
    "l": ("ml", 1000.0),
    "m": ("m", 1.0),
    "m2": ("m2", 1.0),
    "stuk": ("stuk", 1.0),
}


@dataclass(frozen=True)
class ParsedUnitPrice:
    normalized_price: float
    base_unit: str
    original_price: float
    original_quantity: float
    original_description: str


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def _normalize_unit(unit: str) -> str | None:
    cleaned = unit.lower().strip().rstrip(".")
    return _UNIT_ALIASES.get(cleaned)


def parse_unit_price(description: str | None) -> ParsedUnitPrice | None:
    """Parse AH unitPriceDescription such as ``€2,50/100g``.

    Prices are normalized to the smallest comparable unit for mass and volume:
    grams for g/kg and milliliters for ml/l.
    """
    if not description:
        return None

    match = _PRICE_RE.search(description.strip())
    if match:
        unit = _normalize_unit(match.group("unit"))
        original_price = _to_float(match.group("price"))
        original_quantity = _to_float(match.group("quantity") or "1")
    else:
        match = _PRICE_PER_RE.search(description.strip())
        if not match:
            return None
        unit = _normalize_unit(match.group("unit"))
        original_price = _to_float(match.group("price"))
        original_quantity = 1.0

    if unit is None or unit not in _CONVERSIONS:
        return None

    if original_quantity <= 0:
        return None

    base_unit, multiplier = _CONVERSIONS[unit]
    base_quantity = original_quantity * multiplier
    normalized_price = original_price / base_quantity

    return ParsedUnitPrice(
        normalized_price=normalized_price,
        base_unit=base_unit,
        original_price=original_price,
        original_quantity=original_quantity,
        original_description=description,
    )


def upsert_unit_price(
    session: Session,
    product_id: int,
    description: str | None,
) -> UnitPriceRow | None:
    """Parse and upsert one product's normalized unit price."""
    parsed = parse_unit_price(description)
    if parsed is None:
        return None

    now = datetime.utcnow()
    row = session.query(UnitPriceRow).filter(UnitPriceRow.product_id == product_id).first()
    if row is None:
        row = UnitPriceRow(product_id=product_id, created_at=now)
        session.add(row)

    row.normalized_price_eur_per_unit = parsed.normalized_price
    row.base_unit = parsed.base_unit
    row.original_description = parsed.original_description
    row.raw_quantity = parsed.original_quantity
    row.updated_at = now
    return row


def normalize_unit_prices(session: Session) -> int:
    """Normalize unit prices for all products that have a stored description."""
    products = (
        session.query(ProductRow)
        .filter(ProductRow.unit_price_description.isnot(None))
        .all()
    )

    updated = 0
    for product in products:
        if upsert_unit_price(
            session,
            product.webshop_id,
            product.unit_price_description,
        ):
            updated += 1
    return updated
