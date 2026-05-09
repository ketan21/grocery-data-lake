"""Smoke tests for the current sync implementation.

Covers: auth, client, models, db, scraper, bonus_scraper.
All tests hit the real AH API (no mocks) — run sparingly.
"""

import json
import os
import sys
from datetime import datetime

import pytest

# Ensure the package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from grocery.config import BASE_URL, SEARCH_DELAY, DETAIL_DELAY, PAGE_SIZE
from grocery.auth import get_token, auth_headers
from grocery.client import AHClient
from grocery.models import Product, Category, Image
from grocery.db import (
    Base, get_engine, get_session, init_db,
    ProductRow, CategoryRow, NutritionRow, AllergenRow,
    IngredientRow, ImageRow, PriceHistoryRow, ScrapeRun, RawJson,
)


class TestConfig:
    def test_base_url(self):
        assert BASE_URL == "https://api.ah.nl"

    def test_delays(self):
        assert SEARCH_DELAY == 0.5
        assert DETAIL_DELAY == 0.2
        assert PAGE_SIZE == 200


class TestAuth:
    def test_get_token(self):
        token = get_token()
        assert token is not None
        assert len(token) > 10

    def test_auth_headers(self):
        headers = auth_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert "User-Agent" in headers

    def test_token_cached(self):
        t1 = get_token()
        t2 = get_token()
        assert t1 == t2


class TestClient:
    @pytest.fixture
    def client(self):
        return AHClient(search_delay=0.3, detail_delay=0.15)

    def test_categories(self, client):
        cats = client.get_categories()
        assert isinstance(cats, list)
        assert len(cats) > 0
        assert isinstance(cats[0], Category)
        assert hasattr(cats[0], "id")
        assert hasattr(cats[0], "name")

    def test_search_products(self, client):
        products = client.search_products(query="chocolate", page=0, size=5)
        assert isinstance(products, list)
        assert len(products) > 0
        assert isinstance(products[0], Product)
        assert hasattr(products[0], "webshop_id")
        assert hasattr(products[0], "title")

    def test_search_by_category(self, client):
        products = client.search_products(taxonomy_id=6401, page=0, size=5)
        assert isinstance(products, list)
        assert len(products) > 0

    def test_search_products_raw(self, client):
        products, raw = client.search_products_raw(query="chocolate", page=0, size=5)
        assert isinstance(products, list)
        assert isinstance(raw, dict)
        assert "products" in raw
        assert len(products) == len(raw["products"])

    def test_product_detail(self, client):
        products = client.search_products(query="chocolate", page=0, size=1)
        wid = products[0].webshop_id
        detail = client.get_product_detail(wid)
        assert isinstance(detail, dict)
        assert "productCard" in detail or "tradeItem" in detail

    def test_bonus_metadata(self, client):
        meta = client.get_bonus_metadata()
        assert isinstance(meta, dict)
        assert "periods" in meta

    def test_bonus_section(self, client):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        data = client.get_bonus_section(date=today, category="Groente, aardappelen")
        assert isinstance(data, dict)

    def test_bonus_spotlight(self, client):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        data = client.get_bonus_section(date=today)
        assert isinstance(data, dict)

    def test_bulk_lookup(self, client):
        products = client.search_products(query="chocolate", page=0, size=3)
        ids = [p.webshop_id for p in products]
        results = client.bulk_lookup(ids)
        assert isinstance(results, list)
        assert len(results) == len(ids)


class TestModels:
    def test_product_from_dict(self):
        data = {
            "webshopId": 12345,
            "hqId": 67890,
            "title": "Test Product",
            "brand": "TestBrand",
            "currentPrice": 1.99,
        }
        p = Product(**data)
        assert p.webshop_id == 12345
        assert p.title == "Test Product"
        assert p.current_price == 1.99
        assert p.brand == "TestBrand"

    def test_category_from_dict(self):
        c = Category(id=6401, name="Groente")
        assert c.id == 6401
        assert c.name == "Groente"

    def test_image_from_dict(self):
        img = Image(width=800, height=600, url="https://example.com/img.jpg")
        assert img.width == 800


class TestDB:
    @pytest.fixture
    def session(self):
        init_db()
        return get_session()

    def test_init_db(self):
        init_db()
        session = get_session()
        # All tables should exist
        from sqlalchemy import inspect
        inspector = inspect(get_engine())
        tables = inspector.get_table_names()
        assert "products" in tables
        assert "categories" in tables
        assert "nutrition" in tables
        assert "allergens" in tables
        assert "ingredients" in tables
        assert "images" in tables
        assert "price_history" in tables
        assert "scrape_runs" in tables
        assert "raw_json" in tables

    def test_upsert_product(self, session):
        from grocery.db import upsert_product
        from grocery.models import Product
        p = Product(
            webshopId=999999,
            hqId=1,
            title="Test Upsert",
            brand="Test",
            currentPrice=1.0,
        )
        is_new = upsert_product(session, p)
        assert is_new is True
        # Upsert again
        is_new2 = upsert_product(session, p)
        assert is_new2 is False
        session.rollback()

    def test_store_raw_json(self, session):
        from grocery.db import store_raw_json
        store_raw_json(session, 123, "test", {"key": "value"}, sub_source="test_sub")
        store_raw_json(session, None, "test", {"meta": True})
        records = session.query(RawJson).filter(RawJson.source == "test").all()
        assert len(records) >= 2
        session.rollback()

    def test_store_raw_json_roundtrip(self, session):
        from grocery.db import store_raw_json
        original = {"nested": {"data": [1, 2, 3]}, "unicode": "éàü"}
        store_raw_json(session, None, "roundtrip", original, sub_source="test")
        record = session.query(RawJson).filter(RawJson.source == "roundtrip").first()
        parsed = json.loads(record.raw_data)
        assert parsed == original
        session.rollback()

    def test_raw_json_nullable_product_id(self, session):
        from grocery.db import store_raw_json
        store_raw_json(session, None, "bonus_metadata", {"period": "W20"})
        record = session.query(RawJson).filter(RawJson.source == "bonus_metadata").first()
        assert record.product_id is None
        session.rollback()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
