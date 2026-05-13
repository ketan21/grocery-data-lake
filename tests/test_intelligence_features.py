"""Tests for grocery intelligence features — Steps 1-2 of mvp_next.md.

Tests cover:
- Category price rankings (cheapest, most expensive, cheapest unit, cheapest healthy, best deal)
- Deal quality scores (scoring algorithm, label assignment)
- Nutrition scores (health score computation, risk levels, nutrient normalization)
- Health value rankings (health value score, category ranking)
"""

import pytest
from sqlalchemy import inspect, text

from grocery.db import (
    CategoryPriceRankingRow,
    DealQualityScoreRow,
    HealthValueRankingRow,
    NutritionRow,
    NutritionScoreRow,
    PriceHistoryRow,
    PriceMetricsRow,
    ProductRow,
    ScrapeRun,
    UnitPriceRow,
    get_session,
    init_db,
)
from grocery.intelligence import (
    _compute_health_score,
    _effective_price,
    _normalize_nutrient_name,
    _risk_level,
    compute_all_intelligence,
    compute_category_price_rankings,
    compute_deal_quality_scores,
    compute_health_value_rankings,
    compute_nutrition_scores,
)


def _seed_products(temp_db, products):
    """Insert products and return their IDs."""
    ids = []
    for p in products:
        row = ProductRow(**p)
        temp_db.add(row)
        ids.append(p["webshop_id"])
    return ids


def _seed_price_history(temp_db, product_id, prices):
    """Insert price history entries for a product."""
    for price_data in prices:
        temp_db.add(PriceHistoryRow(product_id=product_id, **price_data))


def _seed_price_metrics(temp_db, product_id, metrics):
    """Insert price metrics for a product."""
    temp_db.add(PriceMetricsRow(product_id=product_id, **metrics))


def _seed_scrape_run(temp_db):
    """Insert a completed scrape run."""
    temp_db.add(ScrapeRun(id=1, status="completed"))


def _seed_unit_price(temp_db, product_id, normalized_price, base_unit="g", original_description=None, raw_quantity=1.0):
    """Insert a unit price entry."""
    temp_db.add(UnitPriceRow(
        product_id=product_id,
        normalized_price_eur_per_unit=normalized_price,
        base_unit=base_unit,
        original_description=original_description or f"per {base_unit}",
        raw_quantity=raw_quantity,
    ))


def _seed_nutrition(temp_db, product_id, nutrients):
    """Insert nutrition entries. nutrients: list of (name, value, basis, unit)."""
    for name, value, basis, unit in nutrients:
        temp_db.add(NutritionRow(
            product_id=product_id,
            nutrient_name=name,
            value=value,
            basis=basis,
            unit=unit,
        ))


class TestHelperFunctions:
    def test_effective_price_prefers_current(self, temp_db):
        p = ProductRow(current_price=2.5, price_before_bonus=3.0)
        assert _effective_price(p) == 2.5

    def test_effective_price_falls_back_to_bonus(self):
        p = ProductRow(current_price=None, price_before_bonus=3.0)
        assert _effective_price(p) == 3.0

    def test_effective_price_returns_none(self):
        p = ProductRow(current_price=None, price_before_bonus=None)
        assert _effective_price(p) is None

    def test_effective_price_zero_is_none(self):
        p = ProductRow(current_price=0, price_before_bonus=0)
        assert _effective_price(p) is None

    def test_normalize_nutrient_name_dutch(self):
        assert _normalize_nutrient_name("suikers") == "sugar"
        assert _normalize_nutrient_name("zout") == "salt"
        assert _normalize_nutrient_name("eiwitten") == "protein"
        assert _normalize_nutrient_name("vezels") == "fiber"
        assert _normalize_nutrient_name("verzadigde vetten") == "saturated_fat"
        assert _normalize_nutrient_name("energie (kcal)") == "calories"

    def test_normalize_nutrient_name_english(self):
        assert _normalize_nutrient_name("sugars") == "sugar"
        assert _normalize_nutrient_name("salt") == "salt"
        assert _normalize_nutrient_name("protein") == "protein"
        assert _normalize_nutrient_name("fibre") == "fiber"
        assert _normalize_nutrient_name("saturated fat") == "saturated_fat"
        assert _normalize_nutrient_name("calories") == "calories"

    def test_normalize_nutrient_name_unknown(self):
        assert _normalize_nutrient_name("cholesterol") == "cholesterol"

    def test_risk_level(self):
        assert _risk_level(2.0, {"low": 5.0, "medium": 15.0}) == "low"
        assert _risk_level(8.0, {"low": 5.0, "medium": 15.0}) == "medium"
        assert _risk_level(20.0, {"low": 5.0, "medium": 15.0}) == "high"
        assert _risk_level(None, {"low": 5.0, "medium": 15.0}) == "unknown"

    def test_health_score_healthy_product(self):
        """A product with high protein, fiber, Nutri-Score A should score high."""
        score = _compute_health_score(
            calories=150, sugar=2, salt=0.1, sat_fat=1,
            protein=20, fiber=8, nutriscore="A"
        )
        assert score >= 80

    def test_health_score_unhealthy_product(self):
        """A product with high sugar, salt, saturated fat, Nutri-Score E should score low."""
        score = _compute_health_score(
            calories=400, sugar=30, salt=2.0, sat_fat=15,
            protein=1, fiber=0.5, nutriscore="E"
        )
        assert score <= 30

    def test_health_score_neutral(self):
        """A product with no data should be around 50."""
        score = _compute_health_score(None, None, None, None, None, None, None)
        assert score == 50.0


class TestCategoryPriceRankings:
    @pytest.fixture(autouse=True)
    def setup(self, temp_db):
        init_db()
        _seed_scrape_run(temp_db)
        _seed_products(temp_db, [
            {"webshop_id": 1, "title": "Cheap Milk", "brand": "Brand A",
             "main_category": "Dairy", "sub_category": "Milk",
             "current_price": 0.99, "price_before_bonus": None},
            {"webshop_id": 2, "title": "Expensive Milk", "brand": "Brand B",
             "main_category": "Dairy", "sub_category": "Milk",
             "current_price": 2.50, "price_before_bonus": None},
            {"webshop_id": 3, "title": "Mid Cheese", "brand": "Brand C",
             "main_category": "Dairy", "sub_category": "Cheese",
             "current_price": 1.50, "price_before_bonus": None, "nutriscore": "A"},
            {"webshop_id": 4, "title": "Cheap Cheese", "brand": "Brand D",
             "main_category": "Dairy", "sub_category": "Cheese",
             "current_price": 1.20, "price_before_bonus": None, "nutriscore": "B"},
            {"webshop_id": 5, "title": "Expensive Cheese", "brand": "Brand E",
             "main_category": "Dairy", "sub_category": "Cheese",
             "current_price": 3.00, "price_before_bonus": None, "nutriscore": "D"},
            {"webshop_id": 6, "title": "Bread", "brand": "Brand F",
             "main_category": "Bakery", "sub_category": "Bread",
             "current_price": 1.10, "price_before_bonus": None},
        ])
        _seed_unit_price(temp_db, 1, 0.99, "l")
        _seed_unit_price(temp_db, 2, 2.50, "l")
        _seed_unit_price(temp_db, 3, 1.50, "g")
        _seed_unit_price(temp_db, 4, 1.20, "g")
        temp_db.commit()

    def test_cheapest_price_ranking(self, temp_db):
        rows = compute_category_price_rankings(temp_db)
        temp_db.commit()

        cheapest = temp_db.query(CategoryPriceRankingRow).filter_by(
            ranking_type="cheapest_price",
            main_category="Dairy",
            rank=1,
        ).first()
        assert cheapest is not None
        assert cheapest.product_id == 1  # Cheap Milk at 0.99

    def test_most_expensive_ranking(self, temp_db):
        compute_category_price_rankings(temp_db)
        temp_db.commit()

        most_expensive = temp_db.query(CategoryPriceRankingRow).filter_by(
            ranking_type="most_expensive_price",
            main_category="Dairy",
            rank=1,
        ).first()
        assert most_expensive is not None
        assert most_expensive.product_id == 5  # Expensive Cheese at 3.00

    def test_cheapest_unit_price_ranking(self, temp_db):
        compute_category_price_rankings(temp_db)
        temp_db.commit()

        cheapest_unit = temp_db.query(CategoryPriceRankingRow).filter_by(
            ranking_type="cheapest_unit_price",
            main_category="Dairy",
            rank=1,
        ).first()
        assert cheapest_unit is not None
        assert cheapest_unit.product_id == 1  # Milk at 0.99/l

    def test_cheapest_healthy_ranking(self, temp_db):
        compute_category_price_rankings(temp_db)
        temp_db.commit()

        # Only products with Nutri-Score A/B qualify
        healthy = temp_db.query(CategoryPriceRankingRow).filter_by(
            ranking_type="cheapest_healthy",
            main_category="Dairy",
            sub_category="Cheese",
            rank=1,
        ).first()
        assert healthy is not None
        assert healthy.product_id == 4  # Cheap Cheese (B) at 1.20

    def test_rankings_included_product_count(self, temp_db):
        compute_category_price_rankings(temp_db)
        temp_db.commit()

        row = temp_db.query(CategoryPriceRankingRow).filter_by(
            ranking_type="cheapest_price",
            main_category="Dairy",
            rank=1,
        ).first()
        assert row.product_count == 5  # All 5 dairy products


class TestDealQualityScores:
    @pytest.fixture(autouse=True)
    def setup(self, temp_db):
        init_db()
        _seed_scrape_run(temp_db)
        _seed_products(temp_db, [
            # Product at historical low
            {"webshop_id": 10, "title": "Historical Low Product", "brand": "Brand A",
             "main_category": "Test", "current_price": 1.00, "price_before_bonus": None},
            # Product with big discount
            {"webshop_id": 11, "title": "Big Discount", "brand": "Brand B",
             "main_category": "Test", "current_price": 1.50,
             "price_before_bonus": 3.00, "is_bonus": True},
            # Product at average price
            {"webshop_id": 12, "title": "Average Price", "brand": "Brand C",
             "main_category": "Test", "current_price": 2.00, "price_before_bonus": None},
        ])
        _seed_price_metrics(temp_db, 10, {
            "avg_price": 2.00, "cheapest_price": 1.00, "price_volatility": 0.1,
        })
        _seed_price_metrics(temp_db, 11, {
            "avg_price": 2.50, "cheapest_price": 1.80, "price_volatility": 0.2,
        })
        _seed_price_metrics(temp_db, 12, {
            "avg_price": 2.00, "cheapest_price": 1.50, "price_volatility": 0.05,
        })
        temp_db.commit()

    def test_historical_low_label(self, temp_db):
        rows = compute_deal_quality_scores(temp_db)
        temp_db.commit()

        deal = temp_db.query(DealQualityScoreRow).filter_by(product_id=10).first()
        assert deal is not None
        assert deal.deal_label == "historical_low"
        assert deal.deal_score >= 85

    def test_discount_calculated(self, temp_db):
        compute_deal_quality_scores(temp_db)
        temp_db.commit()

        deal = temp_db.query(DealQualityScoreRow).filter_by(product_id=11).first()
        assert deal is not None
        assert deal.discount_pct == 50.0  # (3.00 - 1.50) / 3.00 * 100

    def test_vs_avg_calculated(self, temp_db):
        compute_deal_quality_scores(temp_db)
        temp_db.commit()

        deal = temp_db.query(DealQualityScoreRow).filter_by(product_id=10).first()
        assert deal.current_vs_avg_pct == -50.0  # (1.00 - 2.00) / 2.00 * 100

    def test_score_clamped_to_range(self, temp_db):
        compute_deal_quality_scores(temp_db)
        temp_db.commit()

        all_deals = temp_db.query(DealQualityScoreRow).all()
        for deal in all_deals:
            assert 0 <= deal.deal_score <= 100


class TestNutritionScores:
    @pytest.fixture(autouse=True)
    def setup(self, temp_db):
        init_db()
        _seed_scrape_run(temp_db)
        _seed_products(temp_db, [
            {"webshop_id": 20, "title": "Healthy Product", "brand": "Brand A",
             "main_category": "Test", "current_price": 2.00, "nutriscore": "A"},
            {"webshop_id": 21, "title": "Unhealthy Product", "brand": "Brand B",
             "main_category": "Test", "current_price": 1.50, "nutriscore": "E"},
            {"webshop_id": 22, "title": "No Nutrition", "brand": "Brand C",
             "main_category": "Test", "current_price": 1.00},
        ])
        # Healthy product nutrition
        _seed_nutrition(temp_db, 20, [
            ("energie (kcal)", 150, "per 100g", "kcal"),
            ("suikers", 2, "per 100g", "g"),
            ("zout", 0.1, "per 100g", "g"),
            ("verzadigde vetten", 1, "per 100g", "g"),
            ("eiwitten", 20, "per 100g", "g"),
            ("vezels", 8, "per 100g", "g"),
        ])
        # Unhealthy product nutrition
        _seed_nutrition(temp_db, 21, [
            ("sugars", 30, "per 100g", "g"),
            ("salt", 2.0, "per 100g", "g"),
            ("saturated fat", 15, "per 100g", "g"),
            ("calories", 400, "per 100g", "kcal"),
            ("protein", 1, "per 100g", "g"),
        ])
        temp_db.commit()

    def test_nutrition_scores_computed(self, temp_db):
        rows = compute_nutrition_scores(temp_db)
        temp_db.commit()

        healthy = temp_db.query(NutritionScoreRow).filter_by(product_id=20).first()
        unhealthy = temp_db.query(NutritionScoreRow).filter_by(product_id=21).first()

        assert healthy is not None
        assert unhealthy is not None
        assert healthy.health_score > unhealthy.health_score

    def test_risk_levels(self, temp_db):
        compute_nutrition_scores(temp_db)
        temp_db.commit()

        unhealthy = temp_db.query(NutritionScoreRow).filter_by(product_id=21).first()
        assert unhealthy.sugar_risk_level == "high"
        assert unhealthy.salt_risk_level == "high"
        assert unhealthy.saturated_fat_risk_level == "high"

    def test_protein_per_euro(self, temp_db):
        compute_nutrition_scores(temp_db)
        temp_db.commit()

        healthy = temp_db.query(NutritionScoreRow).filter_by(product_id=20).first()
        assert healthy.protein_per_euro == 10.0  # 20g / 2.00 EUR

    def test_no_nutrition_skipped(self, temp_db):
        compute_nutrition_scores(temp_db)
        temp_db.commit()

        no_nutr = temp_db.query(NutritionScoreRow).filter_by(product_id=22).first()
        assert no_nutr is None


class TestHealthValueRankings:
    @pytest.fixture(autouse=True)
    def setup(self, temp_db):
        init_db()
        _seed_scrape_run(temp_db)
        _seed_products(temp_db, [
            {"webshop_id": 30, "title": "Cheap Healthy", "brand": "Brand A",
             "main_category": "Test", "current_price": 1.00, "nutriscore": "A"},
            {"webshop_id": 31, "title": "Expensive Healthy", "brand": "Brand B",
             "main_category": "Test", "current_price": 5.00, "nutriscore": "A"},
            {"webshop_id": 32, "title": "Cheap Unhealthy", "brand": "Brand C",
             "main_category": "Test", "current_price": 1.00, "nutriscore": "E"},
        ])
        _seed_nutrition(temp_db, 30, [
            ("eiwitten", 15, "per 100g", "g"),
            ("vezels", 5, "per 100g", "g"),
        ])
        _seed_nutrition(temp_db, 31, [
            ("eiwitten", 15, "per 100g", "g"),
            ("vezels", 5, "per 100g", "g"),
        ])
        _seed_nutrition(temp_db, 32, [
            ("suikers", 25, "per 100g", "g"),
            ("zout", 1.5, "per 100g", "g"),
        ])
        temp_db.commit()

    def test_health_value_rankings(self, temp_db):
        # Must compute nutrition scores first
        compute_nutrition_scores(temp_db)
        temp_db.flush()

        rows = compute_health_value_rankings(temp_db)
        temp_db.commit()

        assert rows == 3

        # Cheap healthy should rank highest
        rankings = temp_db.query(HealthValueRankingRow).order_by(
            HealthValueRankingRow.rank_in_category.asc()
        ).all()

        assert rankings[0].product_id == 30  # Cheap healthy
        assert rankings[0].rank_in_category == 1

    def test_health_value_score_formula(self, temp_db):
        compute_nutrition_scores(temp_db)
        temp_db.flush()
        compute_health_value_rankings(temp_db)
        temp_db.commit()

        cheap = temp_db.query(HealthValueRankingRow).filter_by(product_id=30).first()
        expensive = temp_db.query(HealthValueRankingRow).filter_by(product_id=31).first()

        # Same health score, but cheap should have higher health value
        assert cheap.health_score == expensive.health_score
        assert cheap.health_value_score > expensive.health_value_score


class TestComputeAllIntelligence:
    @pytest.fixture(autouse=True)
    def setup(self, temp_db):
        init_db()
        _seed_scrape_run(temp_db)
        _seed_products(temp_db, [
            {"webshop_id": 40, "title": "Test Product", "brand": "Brand A",
             "main_category": "Test", "current_price": 1.50, "nutriscore": "A"},
        ])
        _seed_price_metrics(temp_db, 40, {
            "avg_price": 2.00, "cheapest_price": 1.50, "price_volatility": 0.1,
        })
        _seed_nutrition(temp_db, 40, [
            ("eiwitten", 10, "per 100g", "g"),
            ("vezels", 3, "per 100g", "g"),
        ])
        temp_db.commit()

    def test_compute_all_returns_counts(self, temp_db):
        result = compute_all_intelligence(temp_db)
        temp_db.commit()

        assert "dealQualityScores" in result
        assert "categoryPriceRankings" in result
        assert "nutritionScores" in result
        assert "healthValueRankings" in result
        assert result["dealQualityScores"] >= 1
        assert result["nutritionScores"] >= 1
