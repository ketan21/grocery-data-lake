"""Tests for Task 2: Database Schema + Repository layer."""

import asyncio
import pytest
from pathlib import Path

from grocery.config import Settings
from grocery.database import Database, db
from grocery.repository import Repository, repo
from grocery.models import (
    Allergen,
    BonusPeriod,
    BonusProduct,
    Category,
    Nutrient,
    Price,
    Product,
    ProductProperty,
    SubCategory,
)


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_grocery.db")


@pytest.fixture
def test_settings(test_db_path):
    return Settings(
        api_base="https://api.ah.nl",
        auth_client_id="appie",
        app_header="AHWEBSHOP",
        request_delay=0.1,
        workers=2,
        max_retries=1,
        timeout=10,
        db_path=test_db_path,
    )


@pytest.fixture(autouse=True)
async def repo(test_settings):
    """Provide a fresh repository + database for each test."""
    import grocery.database as db_mod
    import grocery.repository as repo_mod
    import grocery.config as cfg_mod

    old_db = db_mod.db
    old_repo = repo_mod.repo
    old_settings = cfg_mod.settings
    # repo_mod imports `db` directly via `from grocery.database import db`
    # so we must patch BOTH the module attribute AND the local name
    old_repo_mod_db = getattr(repo_mod, "db", None)

    cfg_mod.settings = test_settings
    test_db = Database()
    db_mod.db = test_db
    repo_mod.db = test_db  # Patch the local binding too
    repo_mod.repo = Repository()

    await test_db.connect()
    await test_db.init_schema()

    yield repo_mod.repo

    try:
        conn = await test_db.connect()
        # Use executescript for atomic FK-disable + DROP (avoids FK constraint errors)
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cur:
            tables = [r[0] for r in await cur.fetchall() if r[0] != "sqlite_sequence"]
        if tables:
            drop_sql = "PRAGMA foreign_keys=OFF;\n" + "\n".join(f"DROP TABLE IF EXISTS {t};" for t in tables) + "\nPRAGMA foreign_keys=ON;"
            await conn.executescript(drop_sql)
    finally:
        await test_db.close()
        db_mod.db = old_db
        repo_mod.repo = old_repo
        cfg_mod.settings = old_settings
        if old_repo_mod_db is not None:
            repo_mod.db = old_repo_mod_db


@pytest.mark.asyncio
async def test_schema_created(repo):
    """All tables exist after init_schema."""
    conn = await db.connect()
    async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") as cur:
        tables = [r[0] for r in await cur.fetchall()]

    expected = [
        "allergens", "bonus_periods", "bonus_products", "categories",
        "nutrition", "prices", "product_properties", "products",
        "schema_migrations", "scrape_log", "subcategories",
    ]
    for t in expected:
        assert t in tables, f"Missing table: {t}"


@pytest.mark.asyncio
async def test_schema_version(repo):
    """Schema version is recorded."""
    conn = await db.connect()
    async with conn.execute("SELECT version FROM schema_migrations") as cur:
        row = await cur.fetchone()
    assert row["version"] >= 1


@pytest.mark.asyncio
async def test_category_roundtrip(repo):
    """Upsert and retrieve categories."""
    cats = [
        Category(id=1, name="Groente, aardappelen"),
        Category(id=2, name="Vlees, vis"),
        Category(id=3, name="Dagboodschappen"),
    ]
    count = await repo.upsert_categories(cats)
    assert count == 3

    fetched = await repo.get_categories()
    assert len(fetched) == 3
    assert fetched[0].name == "Groente, aardappelen"

    # Upsert again (idempotent)
    cats[0].name = "Groente & Aardappelen"
    await repo.upsert_category(cats[0])
    fetched = await repo.get_categories()
    assert fetched[0].name == "Groente & Aardappelen"


@pytest.mark.asyncio
async def test_subcategory_roundtrip(repo):
    """Upsert and retrieve sub-categories."""
    await repo.upsert_category(Category(id=1, name="Groente"))

    subs = [
        SubCategory(id=100, parent_id=1, name="Snoepgroente"),
        SubCategory(id=101, parent_id=1, name="Spinazie, andijvie"),
    ]
    count = await repo.upsert_subcategories(subs)
    assert count == 2

    fetched = await repo.get_subcategories(1)
    assert len(fetched) == 2
    assert fetched[0].name == "Snoepgroente"


@pytest.mark.asyncio
async def test_product_roundtrip(repo):
    """Upsert and retrieve products."""
    products = [
        Product(
            webshop_id=12345, title="Milka Chocolate", brand="Milka",
            sales_unit_size="100 g", nutriscore="D",
            is_vegetarian=True, is_vegan=False,
        ),
        Product(
            webshop_id=67890, title="Chocoapels", brand="Lindt",
            sales_unit_size="100 g", nutriscore="D",
            is_vegan=False, is_vegetarian=True,
        ),
    ]
    count = await repo.upsert_products(products)
    assert count == 2

    total = await repo.get_product_count()
    assert total == 2

    fetched = await repo.get_product(12345)
    assert fetched is not None
    assert fetched.title == "Milka Chocolate"
    assert fetched.is_vegetarian is True
    assert fetched.is_vegan is False


@pytest.mark.asyncio
async def test_product_search(repo):
    """Search products by query, brand, nutriscore, vegan."""
    products = [
        Product(webshop_id=1, title="Milka Chocolate", brand="Milka", nutriscore="D"),
        Product(webshop_id=2, title="Milka White", brand="Milka", nutriscore="E"),
        Product(webshop_id=3, title="Vegan Chips", brand="Lay's", nutriscore="C", is_vegan=True),
        Product(webshop_id=4, title="Apple Juice", brand="Ah", nutriscore="B"),
    ]
    await repo.upsert_products(products)

    # Search by query
    results = await repo.search_products(query="Milka")
    assert len(results) == 2

    # Search by brand
    results = await repo.search_products(brand="Lay's")
    assert len(results) == 1
    assert results[0].is_vegan

    # Search by nutriscore
    results = await repo.search_products(nutriscore="D")
    assert len(results) == 1

    # Search vegan only
    results = await repo.search_products(vegan=True)
    assert len(results) == 1

    # Search with limit
    results = await repo.search_products(limit=1)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_price_history(repo):
    """Record and retrieve price history."""
    await repo.upsert_product(Product(webshop_id=1, title="Test Product"))

    prices = [
        Price(webshop_id=1, price=2.49),
        Price(webshop_id=1, price=2.29, is_bonus=True,
              price_before_bonus=2.49, bonus_start_date="2026-05-01",
              bonus_end_date="2026-05-07"),
        Price(webshop_id=1, price=2.49),
    ]
    count = await repo.record_prices(prices)
    assert count == 3

    latest = await repo.get_latest_price(1)
    assert latest is not None
    assert latest.price == 2.49


@pytest.mark.asyncio
async def test_nutrition_roundtrip(repo):
    """Upsert and retrieve nutritional info."""
    await repo.upsert_product(Product(webshop_id=1, title="Test"))

    nutrients = [
        Nutrient(webshop_id=1, nutrient="Energie", value=504, unit="kcal", basis="100g"),
        Nutrient(webshop_id=1, nutrient="Vet", value=26.0, unit="g", basis="100g"),
        Nutrient(webshop_id=1, nutrient="Koolhydraten", value=60.0, unit="g", basis="100g"),
        Nutrient(webshop_id=1, nutrient="Eiwitten", value=4.0, unit="g", basis="100g"),
    ]
    count = await repo.upsert_nutrition(nutrients)
    assert count == 4

    fetched = await repo.get_nutrition(1)
    assert len(fetched) == 4
    assert fetched[0].nutrient == "Energie"
    assert fetched[0].value == 504


@pytest.mark.asyncio
async def test_allergen_roundtrip(repo):
    """Upsert and retrieve allergen info."""
    await repo.upsert_product(Product(webshop_id=1, title="Test"))

    allergens = [
        Allergen(webshop_id=1, allergen="Melk", level="CONTAINS"),
        Allergen(webshop_id=1, allergen="Soja", level="MAY_CONTAIN"),
    ]
    count = await repo.upsert_allergens(allergens)
    assert count == 2

    fetched = await repo.get_allergens(1)
    assert len(fetched) == 2
    assert any(a.allergen == "Melk" and a.level == "CONTAINS" for a in fetched)


@pytest.mark.asyncio
async def test_product_properties(repo):
    """Upsert and retrieve product properties."""
    await repo.upsert_product(Product(webshop_id=1, title="Test"))

    props = [
        ProductProperty(webshop_id=1, property_key="da_taste", property_value="Chocolade"),
        ProductProperty(webshop_id=1, property_key="da_store_department", property_value="Houdbaar"),
    ]
    count = await repo.upsert_properties(props)
    assert count == 2

    conn = await db.connect()
    async with conn.execute(
        "SELECT property_key, property_value FROM product_properties WHERE webshop_id = ?",
        (1,),
    ) as cur:
        rows = await cur.fetchall()
    assert len(rows) == 2
    keys = {r[0] for r in rows}
    assert "da_taste" in keys


@pytest.mark.asyncio
async def test_bonus_period(repo):
    """Upsert bonus period and bonus products."""
    await repo.upsert_product(Product(webshop_id=1, title="Test", brand="Test"))

    period = BonusPeriod(start_date="2026-05-01", end_date="2026-05-07", segment_id="seg1")
    pid = await repo.upsert_bonus_period(period)
    assert pid >= 1

    bp = BonusProduct(
        webshop_id=1, bonus_period_id=pid,
        original_price=2.99, bonus_price=1.99,
        start_date="2026-05-01", end_date="2026-05-07",
    )
    await repo.upsert_bonus_product(bp)

    # Verify it's stored
    conn = await db.connect()
    async with conn.execute(
        "SELECT bonus_price FROM bonus_products WHERE webshop_id = ?", (1,)
    ) as cur:
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == 1.99


@pytest.mark.asyncio
async def test_scrape_log(repo):
    """Record and verify scrape log entries."""
    await repo.log_scrape("category", "6401", count=15)
    await repo.log_scrape("product", "12345", count=1)

    conn = await db.connect()
    async with conn.execute("SELECT COUNT(*) FROM scrape_log") as cur:
        row = await cur.fetchone()
    assert row[0] == 2


@pytest.mark.asyncio
async def test_context_manager():
    """Database context manager works."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        test_settings = Settings(db_path=tf.name)
        import grocery.database as db_mod
        old_db = db_mod.db
        test_db = Database()
        db_mod.db = test_db
        try:
            async with test_db:
                async with test_db._db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ) as cur:
                    tables = [r[0] for r in await cur.fetchall()]
                assert "products" in tables
        finally:
            db_mod.db = old_db


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
