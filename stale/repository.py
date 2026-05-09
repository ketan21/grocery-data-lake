"""Repository layer — CRUD operations backed by SQLite.

Provides typed methods for all entities, handling upserts,
batch inserts, and query logic.
"""

import logging
from datetime import datetime, timezone

import aiosqlite

from grocery.database import db
from grocery.models import (
    Allergen,
    BonusPeriod,
    BonusProduct,
    Category,
    Nutrient,
    Price,
    Product,
    ProductProperty,
    ScrapeLog,
    SubCategory,
)

logger = logging.getLogger(__name__)


class Repository:
    """All database operations for the grocery data lake."""

    # ── Categories ──────────────────────────────────────────────

    async def upsert_category(self, cat: Category) -> None:
        """Insert or update a top-level category."""
        conn = await db.connect()
        await conn.execute(
            """INSERT INTO categories (id, name, image_url, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name,
                   image_url=excluded.image_url,
                   updated_at=CURRENT_TIMESTAMP""",
            (cat.id, cat.name, cat.image_url, datetime.now(timezone.utc).isoformat()),
        )

    async def upsert_categories(self, cats: list[Category]) -> int:
        """Batch upsert categories. Returns count."""
        conn = await db.connect()
        now = datetime.now(timezone.utc).isoformat()
        await conn.executemany(
            """INSERT INTO categories (id, name, image_url, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name,
                   image_url=excluded.image_url,
                   updated_at=excluded.updated_at""",
            [(c.id, c.name, c.image_url, now) for c in cats],
        )
        await conn.commit()
        return len(cats)

    async def get_categories(self) -> list[Category]:
        """Return all categories."""
        conn = await db.connect()
        async with conn.execute(
            "SELECT id, name, image_url FROM categories ORDER BY id"
        ) as cur:
            rows = await cur.fetchall()
        return [Category(id=r[0], name=r[1], image_url=r[2]) for r in rows]

    # ── Sub-categories ──────────────────────────────────────────

    async def upsert_subcategory(self, sub: SubCategory) -> None:
        conn = await db.connect()
        await conn.execute(
            """INSERT INTO subcategories (id, parent_id, name, image_url, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name,
                   image_url=excluded.image_url,
                   updated_at=CURRENT_TIMESTAMP""",
            (sub.id, sub.parent_id, sub.name, sub.image_url,
             datetime.now(timezone.utc).isoformat()),
        )

    async def upsert_subcategories(self, subs: list[SubCategory]) -> int:
        conn = await db.connect()
        now = datetime.now(timezone.utc).isoformat()
        await conn.executemany(
            """INSERT INTO subcategories (id, parent_id, name, image_url, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name,
                   image_url=excluded.image_url,
                   updated_at=excluded.updated_at""",
            [(s.id, s.parent_id, s.name, s.image_url, now) for s in subs],
        )
        await conn.commit()
        return len(subs)

    async def get_subcategories(self, parent_id: int) -> list[SubCategory]:
        conn = await db.connect()
        async with conn.execute(
            "SELECT id, parent_id, name, image_url FROM subcategories WHERE parent_id = ?",
            (parent_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [SubCategory(id=r[0], parent_id=r[1], name=r[2], image_url=r[3]) for r in rows]

    # ── Products ────────────────────────────────────────────────

    def _extract_dietary_flags(self, properties: dict | None) -> dict:
        """Extract boolean dietary flags from AH product properties."""
        if not properties:
            return {}
        flags = {}
        flags["is_vegan"] = bool(properties.get("sp_include_dieet_veganistisch"))
        flags["is_vegetarian"] = bool(properties.get("sp_include_dieet_vegetarisch"))
        flags["is_gluten_free"] = bool(properties.get("sp_include_dieet_glutenvrij"))
        flags["is_low_sugar"] = bool(properties.get("sp_include_dieet_laag_suiker"))
        flags["is_low_fat"] = bool(properties.get("sp_include_dieet_laag_vet"))
        flags["is_low_salt"] = bool(properties.get("sp_include_dieet_laag_zout"))
        ns = properties.get("nutriscore", [])
        flags["nutriscore"] = ns[0] if ns else None
        return flags

    def _get_best_image(self, images: list[dict] | None) -> str | None:
        """Extract the best (800x800) image URL from API response."""
        if not images:
            return None
        for img in images:
            if img.get("width") == 800:
                return img.get("url")
        return images[0].get("url") if images else None

    async def upsert_product(self, product: Product) -> None:
        """Insert or update a single product."""
        conn = await db.connect()
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """INSERT INTO products (
                webshop_id, hq_id, title, brand, sales_unit_size,
                unit_price_description, image_url, main_category, sub_category,
                sub_category_id, shop_type, available_online,
                description_highlights, order_availability_status,
                nutriscore, is_vegan, is_vegetarian, is_gluten_free,
                is_low_sugar, is_low_fat, is_low_salt, gtin, gln, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(webshop_id) DO UPDATE SET
                title=excluded.title,
                brand=excluded.brand,
                sales_unit_size=excluded.sales_unit_size,
                unit_price_description=excluded.unit_price_description,
                image_url=excluded.image_url,
                main_category=excluded.main_category,
                sub_category=excluded.sub_category,
                sub_category_id=excluded.sub_category_id,
                nutriscore=excluded.nutriscore,
                is_vegan=excluded.is_vegan,
                is_vegetarian=excluded.is_vegetarian,
                is_gluten_free=excluded.is_gluten_free,
                is_low_sugar=excluded.is_low_sugar,
                is_low_fat=excluded.is_low_fat,
                is_low_salt=excluded.is_low_salt,
                updated_at=excluded.updated_at""",
            (
                product.webshop_id, product.hq_id, product.title, product.brand,
                product.sales_unit_size, product.unit_price_description,
                product.image_url, product.main_category, product.sub_category,
                product.sub_category_id, product.shop_type,
                1 if product.available_online else 0,
                product.description_highlights,
                product.order_availability_status,
                product.nutriscore,
                1 if product.is_vegan else 0,
                1 if product.is_vegetarian else 0,
                1 if product.is_gluten_free else 0,
                1 if product.is_low_sugar else 0,
                1 if product.is_low_fat else 0,
                1 if product.is_low_salt else 0,
                product.gtin, product.gln, now,
            ),
        )

    async def upsert_products(self, products: list[Product]) -> int:
        """Batch upsert products. Returns count."""
        conn = await db.connect()
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for p in products:
            rows.append((
                p.webshop_id, p.hq_id, p.title, p.brand, p.sales_unit_size,
                p.unit_price_description, p.image_url, p.main_category,
                p.sub_category, p.sub_category_id, p.shop_type,
                1 if p.available_online else 0,
                p.description_highlights, p.order_availability_status,
                p.nutriscore,
                1 if p.is_vegan else 0, 1 if p.is_vegetarian else 0,
                1 if p.is_gluten_free else 0, 1 if p.is_low_sugar else 0,
                1 if p.is_low_fat else 0, 1 if p.is_low_salt else 0,
                p.gtin, p.gln, now,
            ))
        await conn.executemany(
            """INSERT INTO products (
                webshop_id, hq_id, title, brand, sales_unit_size,
                unit_price_description, image_url, main_category, sub_category,
                sub_category_id, shop_type, available_online,
                description_highlights, order_availability_status,
                nutriscore, is_vegan, is_vegetarian, is_gluten_free,
                is_low_sugar, is_low_fat, is_low_salt, gtin, gln, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(webshop_id) DO UPDATE SET
                title=excluded.title, brand=excluded.brand,
                sales_unit_size=excluded.sales_unit_size,
                unit_price_description=excluded.unit_price_description,
                image_url=excluded.image_url,
                main_category=excluded.main_category,
                sub_category=excluded.sub_category,
                sub_category_id=excluded.sub_category_id,
                nutriscore=excluded.nutriscore,
                is_vegan=excluded.is_vegan,
                is_vegetarian=excluded.is_vegetarian,
                is_gluten_free=excluded.is_gluten_free,
                is_low_sugar=excluded.is_low_sugar,
                is_low_fat=excluded.is_low_fat,
                is_low_salt=excluded.is_low_salt,
                updated_at=excluded.updated_at""",
            rows,
        )
        await conn.commit()
        return len(products)

    async def get_product(self, webshop_id: int) -> Product | None:
        conn = await db.connect()
        async with conn.execute(
            "SELECT * FROM products WHERE webshop_id = ?", (webshop_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return Product(
            webshop_id=row[0], hq_id=row[1], title=row[2], brand=row[3],
            sales_unit_size=row[4], unit_price_description=row[5],
            image_url=row[6], main_category=row[7], sub_category=row[8],
            sub_category_id=row[9], shop_type=row[10],
            available_online=bool(row[11]), description_highlights=row[12],
            order_availability_status=row[13], nutriscore=row[14],
            is_vegan=bool(row[15]), is_vegetarian=bool(row[16]),
            is_gluten_free=bool(row[17]), is_low_sugar=bool(row[18]),
            is_low_fat=bool(row[19]), is_low_salt=bool(row[20]),
            gtin=row[21], gln=row[22],
        )

    async def get_product_count(self) -> int:
        conn = await db.connect()
        async with conn.execute("SELECT COUNT(*) FROM products") as cur:
            row = await cur.fetchone()
        return row[0]

    async def search_products(
        self, query: str | None = None, brand: str | None = None,
        nutriscore: str | None = None, vegan: bool | None = None,
        limit: int = 50
    ) -> list[Product]:
        """Search products in the local database."""
        conditions = []
        params = []
        if query:
            conditions.append("(title LIKE ? OR brand LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if brand:
            conditions.append("brand LIKE ?")
            params.append(f"%{brand}%")
        if nutriscore:
            conditions.append("nutriscore = ?")
            params.append(nutriscore)
        if vegan is not None:
            conditions.append("is_vegan = ?")
            params.append(1 if vegan else 0)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        conn = await db.connect()
        async with conn.execute(f"SELECT * FROM products{where} LIMIT ?", params) as cur:
            rows = await cur.fetchall()
        results = []
        for row in rows:
            results.append(Product(
                webshop_id=row[0], hq_id=row[1], title=row[2], brand=row[3],
                sales_unit_size=row[4], unit_price_description=row[5],
                image_url=row[6], main_category=row[7], sub_category=row[8],
                sub_category_id=row[9], shop_type=row[10],
                available_online=bool(row[11]), description_highlights=row[12],
                order_availability_status=row[13], nutriscore=row[14],
                is_vegan=bool(row[15]), is_vegetarian=bool(row[16]),
                is_gluten_free=bool(row[17]), is_low_sugar=bool(row[18]),
                is_low_fat=bool(row[19]), is_low_salt=bool(row[20]),
                gtin=row[21], gln=row[22],
            ))
        return results

    # ── Product Properties ──────────────────────────────────────

    async def upsert_properties(self, props: list[ProductProperty]) -> int:
        conn = await db.connect()
        await conn.executemany(
            """INSERT INTO product_properties (webshop_id, property_key, property_value)
               VALUES (?, ?, ?)
               ON CONFLICT(webshop_id, property_key) DO UPDATE SET
                   property_value=excluded.property_value""",
            [(p.webshop_id, p.property_key, p.property_value) for p in props],
        )
        await conn.commit()
        return len(props)

    # ── Prices ──────────────────────────────────────────────────

    async def record_price(self, price: Price) -> int:
        """Record a price entry. Returns the new row ID."""
        conn = await db.connect()
        async with conn.execute(
            """INSERT INTO prices (webshop_id, price, price_before_bonus,
               is_bonus, bonus_start_date, bonus_end_date, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                price.webshop_id, price.price, price.price_before_bonus,
                1 if price.is_bonus else 0,
                price.bonus_start_date, price.bonus_end_date,
                datetime.now(timezone.utc).isoformat(),
            ),
        ) as cur:
            return cur.lastrowid

    async def record_prices(self, prices: list[Price]) -> int:
        """Batch record prices. Returns count."""
        conn = await db.connect()
        now = datetime.now(timezone.utc).isoformat()
        await conn.executemany(
            """INSERT INTO prices (webshop_id, price, price_before_bonus,
               is_bonus, bonus_start_date, bonus_end_date, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (p.webshop_id, p.price, p.price_before_bonus,
                 1 if p.is_bonus else 0, p.bonus_start_date,
                 p.bonus_end_date, now)
                for p in prices
            ],
        )
        await conn.commit()
        return len(prices)

    async def get_latest_price(self, webshop_id: int) -> Price | None:
        conn = await db.connect()
        async with conn.execute(
            "SELECT * FROM prices WHERE webshop_id = ? ORDER BY recorded_at DESC LIMIT 1",
            (webshop_id,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return Price(
            id=row[0], webshop_id=row[1], price=row[2],
            price_before_bonus=row[3], is_bonus=bool(row[4]),
            bonus_start_date=row[5], bonus_end_date=row[6],
        )

    # ── Nutrition ───────────────────────────────────────────────

    async def upsert_nutrition(self, nutrients: list[Nutrient]) -> int:
        conn = await db.connect()
        await conn.executemany(
            """INSERT OR REPLACE INTO nutrition
               (webshop_id, nutrient, value, unit, basis)
               VALUES (?, ?, ?, ?, ?)""",
            [(n.webshop_id, n.nutrient, n.value, n.unit, n.basis) for n in nutrients],
        )
        await conn.commit()
        return len(nutrients)

    async def get_nutrition(self, webshop_id: int) -> list[Nutrient]:
        conn = await db.connect()
        async with conn.execute(
            "SELECT * FROM nutrition WHERE webshop_id = ? ORDER BY rowid", (webshop_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [Nutrient(webshop_id=r[0], nutrient=r[1], value=r[2], unit=r[3], basis=r[4])
                for r in rows]

    # ── Allergens ───────────────────────────────────────────────

    async def upsert_allergens(self, allergens: list[Allergen]) -> int:
        conn = await db.connect()
        await conn.executemany(
            """INSERT OR REPLACE INTO allergens (webshop_id, allergen, level)
               VALUES (?, ?, ?)""",
            [(a.webshop_id, a.allergen, a.level) for a in allergens],
        )
        await conn.commit()
        return len(allergens)

    async def get_allergens(self, webshop_id: int) -> list[Allergen]:
        conn = await db.connect()
        async with conn.execute(
            "SELECT * FROM allergens WHERE webshop_id = ?", (webshop_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [Allergen(webshop_id=r[0], allergen=r[1], level=r[2]) for r in rows]

    # ── Bonus ───────────────────────────────────────────────────

    async def upsert_bonus_period(self, period: BonusPeriod) -> int:
        conn = await db.connect()
        async with conn.execute(
            """INSERT INTO bonus_periods (start_date, end_date, segment_id)
               VALUES (?, ?, ?)""",
            (period.start_date, period.end_date, period.segment_id),
        ) as cur:
            rid = cur.lastrowid
        await conn.commit()
        return rid

    async def upsert_bonus_product(self, bp: BonusProduct) -> int:
        conn = await db.connect()
        async with conn.execute(
            """INSERT INTO bonus_products
               (webshop_id, bonus_period_id, original_price, bonus_price, start_date, end_date)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(webshop_id, start_date, end_date) DO UPDATE SET
                   bonus_price=excluded.bonus_price,
                   bonus_period_id=excluded.bonus_period_id,
                   original_price=excluded.original_price""",
            (bp.webshop_id, bp.bonus_period_id, bp.original_price,
             bp.bonus_price, bp.start_date, bp.end_date),
        ) as cur:
            rid = cur.lastrowid
        await conn.commit()
        return rid

    async def get_active_bonus_products(self) -> list:
        """Get products currently in a bonus period."""
        now = datetime.now().strftime("%Y-%m-%d")
        conn = await db.connect()
        async with conn.execute(
            """SELECT bp.*, p.title, p.brand, p.price
               FROM bonus_products bp
               JOIN products p ON p.webshop_id = bp.webshop_id
               WHERE bp.start_date <= ? AND bp.end_date >= ?""",
            (now, now),
        ) as cur:
            rows = await cur.fetchall()
        return rows

    # ── Scrape Log ──────────────────────────────────────────────

    async def log_scrape(self, entity_type: str, entity_id: str, count: int = 0) -> None:
        conn = await db.connect()
        await conn.execute(
            "INSERT INTO scrape_log (entity_type, entity_id, record_count) VALUES (?, ?, ?)",
            (entity_type, entity_id, count),
        )
        await conn.commit()


# Singleton
repo = Repository()
