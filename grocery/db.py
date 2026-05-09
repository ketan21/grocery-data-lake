"""SQLite database setup with SQLAlchemy ORM."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, create_engine, event, text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from .config import DB_DIR, DB_PATH


class Base(DeclarativeBase):
    pass


class CategoryRow(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    product_count = Column(Integer, default=0)


class ProductRow(Base):
    __tablename__ = "products"

    webshop_id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    brand = Column(String(255))
    sales_unit_size = Column(String(100))
    current_price = Column(Float)
    price_before_bonus = Column(Float)
    main_category = Column(String(255))
    sub_category = Column(String(255))
    nutriscore = Column(String(10))
    is_bonus = Column(Boolean)
    bonus_mechanism = Column(String(255))
    bonus_start_date = Column(String(20))
    bonus_end_date = Column(String(20))
    available_online = Column(Boolean)
    description_highlights = Column(Text)
    image_url = Column(String(1000))  # primary image
    scraped_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    nutrition_rows = relationship("NutritionRow", back_populates="product", cascade="all, delete-orphan")
    allergen_rows = relationship("AllergenRow", back_populates="product", cascade="all, delete-orphan")
    ingredient_rows = relationship("IngredientRow", back_populates="product", cascade="all, delete-orphan")
    image_rows = relationship("ImageRow", back_populates="product", cascade="all, delete-orphan")
    price_history_rows = relationship("PriceHistoryRow", back_populates="product", cascade="all, delete-orphan")

    # Extra detail fields (populated from /detail/v4/fir)
    ingredients = Column(Text)  # JSON array
    food_name = Column(String(500))
    product_type = Column(String(255))
    origin_country = Column(String(100))
    barcode = Column(String(50))
    manufacturer = Column(String(255))


class NutritionRow(Base):
    __tablename__ = "nutrition"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.webshop_id"), nullable=False)
    nutrient_name = Column(String(100))
    value = Column(Float)
    unit = Column(String(50))
    basis = Column(String(50))  # e.g. "per 100g"

    product = relationship("ProductRow", back_populates="nutrition_rows")


class AllergenRow(Base):
    __tablename__ = "allergens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.webshop_id"), nullable=False)
    allergen_name = Column(String(100))
    level = Column(String(20))  # CONTAINS / MAY_CONTAIN

    product = relationship("ProductRow", back_populates="allergen_rows")


class IngredientRow(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.webshop_id"), nullable=False)
    ingredient_name = Column(Text)
    highlighted = Column(Boolean, default=False)

    product = relationship("ProductRow", back_populates="ingredient_rows")


class ImageRow(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.webshop_id"), nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    url = Column(String(1000))

    product = relationship("ProductRow", back_populates="image_rows")


class PriceHistoryRow(Base):
    """Time-series price tracking for inflation analysis."""
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.webshop_id"), nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    current_price = Column(Float)
    price_before_bonus = Column(Float)
    is_bonus = Column(Boolean)
    bonus_mechanism = Column(String(255))
    bonus_start_date = Column(String(20))
    bonus_end_date = Column(String(20))
    scrape_run_id = Column(Integer)  # links to scrape_runs

    product = relationship("ProductRow", back_populates="price_history_rows")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    products_scraped = Column(Integer, default=0)
    categories_scraped = Column(Integer, default=0)
    status = Column(String(20), default="running")  # running / completed / failed
    notes = Column(String(500))


class RawJson(Base):
    """Raw API response storage for grocery intelligence.

    Stores per-product and per-event raw data from all AH API endpoints:
    - source='search': individual product object from search API (~2.6KB)
    - source='detail': full /detail/v4/fir/{id} response (~7KB)
    - source='bonus': bonus/promotion item (per-product or per-group)
    - source='bonus_metadata': weekly bonus folder metadata (period-level)
    - source='graphql': GraphQL response (receipts, orders, etc.)
    - source='category': category metadata
    """
    __tablename__ = "raw_json"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.webshop_id"), nullable=True)  # NULL for non-product data
    source = Column(String(30), nullable=False)  # search, detail, bonus, bonus_metadata, graphql, category
    sub_source = Column(String(100), nullable=True)  # e.g., "bonuspage/v2/section", "bargainItems", "posReceiptsPage"
    raw_data = Column(Text, nullable=False)  # JSON string
    fetched_at = Column(DateTime, default=datetime.utcnow)
    scrape_run_id = Column(Integer)  # links to scrape_runs

    product = relationship("ProductRow")

    __table_args__ = (
        Index("ix_raw_json_product_source", "product_id", "source"),
        Index("ix_raw_json_source_fetched", "source", "fetched_at"),
    )


def get_engine():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    # Enable WAL mode for better concurrent read performance
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA journal_mode=WAL")
        dbapi_connection.execute("PRAGMA synchronous=NORMAL")
    return engine


def get_session():
    engine = get_engine()
    return sessionmaker(bind=engine)()


def init_db():
    """Create all tables if they don't exist."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def store_raw_json(session: Session, product_id: int | None, source: str, data: dict | list, scrape_run_id: int | None = None, sub_source: str | None = None):
    """Store a raw API response as JSON text for debugging/future-proofing.

    Args:
        session: SQLAlchemy session
        product_id: Product webshop_id (None for non-product data like bonus metadata)
        source: "search", "detail", "bonus", "bonus_metadata", "graphql", "category"
        data: Raw API response (dict or list)
        scrape_run_id: Optional scrape run ID
        sub_source: Optional sub-endpoint identifier
    """
    import json
    session.add(RawJson(
        product_id=product_id,
        source=source,
        raw_data=json.dumps(data, ensure_ascii=False, default=str),
        scrape_run_id=scrape_run_id,
        sub_source=sub_source,
    ))


def upsert_product(session: Session, product: "Product", detail: dict | None = None) -> bool:  # type: ignore[name-defined]
    """Insert or update a product row. Returns True if new, False if updated."""
    row = session.get(ProductRow, product.webshop_id)
    is_new = row is None
    now = datetime.utcnow()

    base_data = {
        "title": product.title,
        "brand": product.brand,
        "sales_unit_size": product.sales_unit_size,
        "current_price": product.current_price,
        "price_before_bonus": product.price_before_bonus,
        "main_category": product.main_category,
        "sub_category": product.sub_category,
        "nutriscore": product.nutriscore,
        "is_bonus": product.is_bonus,
        "bonus_mechanism": product.bonus_mechanism,
        "bonus_start_date": product.bonus_start_date,
        "bonus_end_date": product.bonus_end_date,
        "available_online": product.available_online,
        "description_highlights": product.description_highlights,
        "scraped_at": now,
    }

    # Primary image
    if product.images:
        primary = max(product.images, key=lambda i: i.width)
        base_data["image_url"] = primary.url

    if row:
        for k, v in base_data.items():
            setattr(row, k, v)
    else:
        row = ProductRow(webshop_id=product.webshop_id, **base_data)
        session.add(row)

    # Store images
    if product.images:
        session.query(ImageRow).filter(ImageRow.product_id == product.webshop_id).delete()
        for img in product.images:
            session.add(ImageRow(product_id=product.webshop_id, width=img.width, height=img.height, url=img.url))

    # Parse nutrition/allergens/ingredients from detail
    if detail:
        _store_nutrition(session, product.webshop_id, detail)
        _store_allergens(session, product.webshop_id, detail)
        _store_ingredients(session, product.webshop_id, detail)
        _store_extra_fields(session, product.webshop_id, detail)

    return is_new


def record_price_snapshot(session: Session, product_id: int, price_data: dict, scrape_run_id: int | None = None):
    """Record a price snapshot in the price_history table for time-series tracking."""
    session.add(PriceHistoryRow(
        product_id=product_id,
        current_price=price_data.get("currentPrice"),
        price_before_bonus=price_data.get("priceBeforeBonus"),
        is_bonus=price_data.get("isBonus"),
        bonus_mechanism=price_data.get("bonusMechanism"),
        bonus_start_date=price_data.get("bonusStartDate"),
        bonus_end_date=price_data.get("bonusEndDate"),
        scrape_run_id=scrape_run_id,
    ))


def _store_nutrition(session: Session, product_id: int, detail: dict) -> None:
    """Extract and store nutrition data from detail response."""
    ti = detail.get("tradeItem", {})
    nutrition = ti.get("nutritionalInformation", {})
    if not nutrition:
        return

    session.query(NutritionRow).filter(NutritionRow.product_id == product_id).delete()

    for header in nutrition.get("nutrientHeaders", []):
        basis = ""
        basis_qty = header.get("nutrientBasisQuantity", {})
        if basis_qty:
            val = basis_qty.get("value", "")
            unit = basis_qty.get("measurementUnitCode", {}).get("label", "")
            basis = f"{val} {unit}".strip()

        for nutrient in header.get("nutrientDetail", []):
            tc = nutrient.get("nutrientTypeCode", {})
            name = tc.get("label", tc.get("value", "unknown"))

            for qty in nutrient.get("quantityContained", []):
                session.add(NutritionRow(
                    product_id=product_id,
                    nutrient_name=name,
                    value=qty.get("value"),
                    unit=qty.get("measurementUnitCode", {}).get("label", ""),
                    basis=basis,
                ))


def _store_allergens(session: Session, product_id: int, detail: dict) -> None:
    """Extract and store allergen data from detail response."""
    ti = detail.get("tradeItem", {})
    allergens = ti.get("allergenInformation", [])
    if not allergens:
        return

    session.query(AllergenRow).filter(AllergenRow.product_id == product_id).delete()

    for ag_group in allergens:
        for item in ag_group.get("items", []):
            tc = item.get("typeCode", {})
            name = tc.get("label", tc.get("value", "unknown"))
            level = "CONTAINS"  # default
            session.add(AllergenRow(product_id=product_id, allergen_name=name, level=level))


def _store_ingredients(session: Session, product_id: int, detail: dict) -> None:
    """Extract and store ingredient data from detail response."""
    ti = detail.get("tradeItem", {})

    # AH uses 'foodAndBeverageIngredientStatement' (plain text string)
    ingredient_text = ti.get("foodAndBeverageIngredientStatement", "")
    if not ingredient_text:
        # Fallback: check other possible fields
        ingredient_text = ti.get("ingredients", "") or ti.get("ingredientStatements", "")
    if not ingredient_text:
        return

    session.query(IngredientRow).filter(IngredientRow.product_id == product_id).delete()

    # Store the full ingredient string as a single row
    session.add(IngredientRow(
        product_id=product_id,
        ingredient_name=ingredient_text[:2048],  # truncate for safety
        highlighted=False,
    ))

    # Also store in the JSON ingredients field on ProductRow
    row = session.get(ProductRow, product_id)
    if row and ingredient_text:
        row.ingredients = ingredient_text


def _store_extra_fields(session: Session, product_id: int, detail: dict) -> None:
    """Store extra product detail fields."""
    row = session.get(ProductRow, product_id)
    if not row:
        return

    ti = detail.get("tradeItem", {})

    # Food name
    food_name = ti.get("foodName") or detail.get("foodName")
    if food_name:
        row.food_name = food_name

    # Product type
    product_type = ti.get("productType") or detail.get("productType")
    if product_type:
        row.product_type = product_type

    # Origin
    origin = ti.get("originCountry") or detail.get("originCountry")
    if origin:
        row.origin_country = origin

    # Barcode
    barcode = ti.get("barcode") or detail.get("barcode") or ti.get("gtin")
    if barcode:
        row.barcode = str(barcode)

    # Manufacturer
    manufacturer = ti.get("manufacturer") or detail.get("manufacturer")
    if manufacturer:
        row.manufacturer = manufacturer

    # Ingredients JSON
    ingredients = ti.get("ingredients", []) or ti.get("ingredientStatements", [])
    if ingredients:
        import json
        row.ingredients = json.dumps(ingredients, ensure_ascii=False)
