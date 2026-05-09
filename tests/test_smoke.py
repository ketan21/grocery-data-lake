"""Phase 1 smoke tests for the current SQLAlchemy runtime."""

from __future__ import annotations

import subprocess

from sqlalchemy import inspect


def test_cli_imports_and_help_works() -> None:
    result = subprocess.run(
        ["grocery", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0
    assert "Albert Heijn product data lake" in result.stdout


def test_api_app_creation_works(tmp_path, monkeypatch) -> None:
    from grocery import db
    from grocery.api.app import create_app

    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api.db")

    app = create_app()

    assert app.title == "Grocery Data Lake"


def test_database_connection_and_table_listing_works(tmp_path, monkeypatch) -> None:
    from grocery import db

    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "smoke.db")

    db.init_db()
    tables = set(inspect(db.get_engine()).get_table_names())

    assert {
        "products",
        "categories",
        "nutrition",
        "allergens",
        "ingredients",
        "images",
        "price_history",
        "scrape_runs",
        "raw_json",
    }.issubset(tables)


def test_auth_token_generation_works() -> None:
    from grocery.auth import auth_headers, get_token

    token = get_token()
    headers = auth_headers()

    assert len(token) > 10
    assert headers["Authorization"] == f"Bearer {token}"


def test_product_data_parsing_works() -> None:
    from grocery.models import Product

    product = Product(
        webshopId=123,
        hqId=456,
        title="Smoke Test Product",
        brand="AH",
        currentPrice=1.99,
        salesUnitSize="250 g",
    )

    assert product.webshop_id == 123
    assert product.hq_id == 456
    assert product.current_price == 1.99
    assert product.sales_unit_size == "250 g"


def test_api_client_search_works() -> None:
    from grocery.client import AHClient
    from grocery.models import Product

    client = AHClient(search_delay=0, detail_delay=0)
    products = client.search_products(query="chocolate", page=0, size=3)

    assert products
    assert all(isinstance(product, Product) for product in products)
    assert all(product.webshop_id for product in products)
