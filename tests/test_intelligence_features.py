"""Tests for grocery intelligence analytics features."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from typer.testing import CliRunner


def test_unit_price_parser_supports_ah_formats() -> None:
    from grocery.unit_price import parse_unit_price

    slash_format = parse_unit_price("€2,50/100g")
    assert slash_format is not None
    assert slash_format.base_unit == "g"
    assert slash_format.normalized_price == 0.025

    per_format = parse_unit_price("normale prijs per kg €1.16")
    assert per_format is not None
    assert per_format.base_unit == "g"
    assert round(per_format.normalized_price, 6) == 0.00116


def test_analytics_api_routes_work(tmp_path, monkeypatch) -> None:
    from grocery import db
    from grocery.api.app import create_app
    from grocery.analytics import compute_price_metrics
    from grocery.unit_price import normalize_unit_prices

    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "analytics.db")
    db.init_db()

    session = db.get_session()
    product = db.ProductRow(
        webshop_id=1,
        title="Test Product",
        brand="AH",
        main_category="Zuivel",
        current_price=1.50,
        price_before_bonus=2.00,
        is_bonus=True,
        unit_price_description="normale prijs per kg €1.50",
    )
    session.add(product)
    session.add_all(
        [
            db.PriceHistoryRow(
                product_id=1,
                recorded_at=datetime(2026, 5, 1, 9, 0),
                current_price=2.00,
            ),
            db.PriceHistoryRow(
                product_id=1,
                recorded_at=datetime(2026, 5, 2, 9, 0),
                current_price=1.50,
            ),
        ]
    )
    compute_price_metrics(session)
    normalize_unit_prices(session)
    session.commit()
    session.close()

    client = TestClient(create_app())
    assert client.get("/api/analytics/price-metrics").status_code == 200
    assert client.get("/api/analytics/unit-prices?unit=g").json()["total"] == 1
    assert client.get("/api/analytics/category-inflation").json()["categories"][0]["category"] == "Zuivel"
    assert client.get("/api/analytics/brand-inflation").json()["brands"][0]["brand"] == "AH"
    assert client.get("/api/analytics/bonus?group_by=brand").json()["items"][0]["brand"] == "AH"


def test_bonus_analytics_discount_depth_uses_bonus_products_only(tmp_path, monkeypatch) -> None:
    from grocery import db
    from grocery.bonus_analytics import compute_bonus_analytics

    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "bonus.db")
    db.init_db()

    session = db.get_session()
    session.add_all(
        [
            db.ProductRow(
                webshop_id=1,
                title="Bonus Product",
                brand="AH",
                current_price=1.00,
                price_before_bonus=2.00,
                is_bonus=True,
            ),
            db.ProductRow(
                webshop_id=2,
                title="Regular Product",
                brand="AH",
                current_price=8.00,
                price_before_bonus=10.00,
                is_bonus=False,
            ),
        ]
    )
    session.commit()

    result = compute_bonus_analytics(session)
    item = result["items"][0]

    assert item["brand"] == "AH"
    assert item["productCount"] == 2
    assert item["bonusCount"] == 1
    assert item["bonusSharePct"] == 50
    assert item["avgDiscountDepthPct"] == 50
    assert item["maxDiscountDepthPct"] == 50


def test_health_quality_checks_are_testable(tmp_path, monkeypatch) -> None:
    from grocery import db
    from grocery.health import get_health_summary, run_quality_checks

    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "health.db")
    db.init_db()

    session = db.get_session()
    session.add(db.CategoryRow(id=1, name="Zuivel", product_count=1))
    session.add(
        db.ProductRow(
            webshop_id=1,
            title="Milk",
            current_price=1.50,
            main_category="Zuivel",
            is_bonus=False,
        )
    )
    session.add(db.RawJson(product_id=1, source="search", raw_data="{}"))
    session.add(db.ScrapeRun(status="completed", products_scraped=1, categories_scraped=1))
    session.add(
        db.PriceHistoryRow(
            product_id=1,
            recorded_at=datetime(2026, 5, 2, 9, 0),
            current_price=1.50,
        )
    )
    session.commit()

    summary = get_health_summary(session)
    checks = run_quality_checks(session)

    assert summary["products"] == 1
    assert all(check.passed for check in checks)


def test_new_query_commands_are_registered() -> None:
    from grocery.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["query", "--help"])

    assert result.exit_code == 0
    assert "bonus-analytics" in result.stdout
    assert "health" in result.stdout


def test_jobs_command_is_registered() -> None:
    from grocery.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["jobs", "--help"])

    assert result.exit_code == 0
    assert "rebuild-derived" in result.stdout
