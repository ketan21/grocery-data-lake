"""Async SQLite database layer with aiosqlite.

Handles connection management, schema creation, and migrations.
"""

import logging
from pathlib import Path

import aiosqlite

from grocery.config import settings

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

CREATE_TABLES = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Top-level categories (28 total)
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    image_url TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sub-categories (children of top-level categories)
CREATE TABLE IF NOT EXISTS subcategories (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER NOT NULL REFERENCES categories(id),
    name TEXT NOT NULL,
    image_url TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products (deduplicated by webshopId)
CREATE TABLE IF NOT EXISTS products (
    webshop_id INTEGER PRIMARY KEY,
    hq_id INTEGER,
    title TEXT NOT NULL,
    brand TEXT,
    sales_unit_size TEXT,
    unit_price_description TEXT,
    image_url TEXT,
    main_category TEXT,
    sub_category TEXT,
    sub_category_id INTEGER,
    shop_type TEXT DEFAULT 'AH',
    available_online INTEGER DEFAULT 1,
    description_highlights TEXT,
    order_availability_status TEXT,
    nutriscore TEXT,
    is_vegan INTEGER DEFAULT 0,
    is_vegetarian INTEGER DEFAULT 0,
    is_gluten_free INTEGER DEFAULT 0,
    is_low_sugar INTEGER DEFAULT 0,
    is_low_fat INTEGER DEFAULT 0,
    is_low_salt INTEGER DEFAULT 0,
    gtin TEXT,
    gln TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product properties (key-value store for dietary/allergen flags)
CREATE TABLE IF NOT EXISTS product_properties (
    webshop_id INTEGER NOT NULL REFERENCES products(webshop_id),
    property_key TEXT NOT NULL,
    property_value TEXT,
    PRIMARY KEY (webshop_id, property_key)
);

-- Price history (one row per price change)
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webshop_id INTEGER NOT NULL REFERENCES products(webshop_id),
    price REAL NOT NULL,
    price_before_bonus REAL,
    is_bonus INTEGER DEFAULT 0,
    bonus_start_date TEXT,
    bonus_end_date TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Nutritional information (per 100g or per serving)
CREATE TABLE IF NOT EXISTS nutrition (
    webshop_id INTEGER NOT NULL REFERENCES products(webshop_id),
    nutrient TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    basis TEXT DEFAULT '100g',
    PRIMARY KEY (webshop_id, nutrient, unit, basis)
);

-- Allergen information
CREATE TABLE IF NOT EXISTS allergens (
    webshop_id INTEGER NOT NULL REFERENCES products(webshop_id),
    allergen TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'CONTAINS',
    PRIMARY KEY (webshop_id, allergen)
);

-- Bonus/promo periods metadata
CREATE TABLE IF NOT EXISTS bonus_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    segment_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bonus products (which products are on promo and when)
CREATE TABLE IF NOT EXISTS bonus_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webshop_id INTEGER NOT NULL REFERENCES products(webshop_id),
    bonus_period_id INTEGER REFERENCES bonus_periods(id),
    original_price REAL,
    bonus_price REAL NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    UNIQUE(webshop_id, start_date, end_date)
);

-- Scrape tracking (which categories/products have been scraped and when)
CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    record_count INTEGER DEFAULT 0
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(main_category);
CREATE INDEX IF NOT EXISTS idx_products_nutriscore ON products(nutriscore);
CREATE INDEX IF NOT EXISTS idx_products_vegan ON products(is_vegan);
CREATE INDEX IF NOT EXISTS idx_prices_webshop ON prices(webshop_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_bonus_products_webshop ON bonus_products(webshop_id);
CREATE INDEX IF NOT EXISTS idx_bonus_products_dates ON bonus_products(start_date, end_date);
"""


class Database:
    """Async SQLite database with connection management."""

    def __init__(self):
        self._db: aiosqlite.Connection | None = None
        self._closed = True

    async def connect(self) -> aiosqlite.Connection:
        """Open (or return existing) database connection."""
        if self._db is None or self._closed:
            db_path = Path(settings.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = await aiosqlite.connect(str(db_path))
            self._db.row_factory = aiosqlite.Row
            # Enable WAL mode for better concurrent read performance
            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._db.execute("PRAGMA foreign_keys=ON")
            await self._db.commit()
            self._closed = False
            logger.info("Connected to SQLite: %s", db_path)

        return self._db

    async def close(self) -> None:
        """Close the database connection."""
        if self._db and not self._closed:
            await self._db.close()
            self._closed = True
            self._db = None
            logger.info("Database closed")

    async def init_schema(self) -> None:
        """Create tables and record schema version if not already done."""
        conn = await self.connect()
        # First create all tables (IF NOT EXISTS is idempotent)
        await conn.executescript(CREATE_TABLES)
        await conn.commit()

        # Now check version
        async with conn.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1") as cur:
            row = await cur.fetchone()
            current = row["version"] if row else 0

        if current < SCHEMA_VERSION:
            logger.info("Recording schema version: %d → %d", current, SCHEMA_VERSION)
            await conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            await conn.commit()
            logger.info("Schema ready (v%d)", SCHEMA_VERSION)

    async def __aenter__(self):
        await self.connect()
        await self.init_schema()
        return self

    async def __aexit__(self, *exc):
        await self.close()


# Singleton
db = Database()
