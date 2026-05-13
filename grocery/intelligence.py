"""Grocery intelligence analytics — price rankings, deal quality, nutrition scoring, health value.

All functions are deterministic post-processing: they read from source/normalized tables
and write to analytics_* derived tables. Every row includes computed_at and source_run_id.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import sqrt
from typing import Any

from sqlalchemy.orm import Session

from .db import (
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
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RANKING_TOP_N = 10  # Store top N per group for dashboard flexibility

RANKING_TYPES = [
    "cheapest_price",
    "most_expensive_price",
    "cheapest_unit_price",
    "cheapest_healthy",
    "best_deal",
]

# Nutrient name normalization (Dutch/English → canonical)
_NUTRIENT_MAP: dict[str, str] = {
    # Calories
    "energie (kj)": "calories",
    "energie (kcal)": "calories",
    "energy (kj)": "calories",
    "energy (kcal)": "calories",
    "calories": "calories",
    "kcal": "calories",
    "kj": "calories",
    "energy": "calories",
    "energie": "calories",
    # Sugar
    "suikers": "sugar",
    "sugars": "sugar",
    "sugar": "sugar",
    "suiker": "sugar",
    "waarvan suikers": "sugar",
    "waarvan: suikers": "sugar",
    "which of which sugars": "sugar",
    # Salt
    "zout": "salt",
    "salt": "salt",
    # Saturated fat
    "verzadigde vetten": "saturated_fat",
    "saturated fat": "saturated_fat",
    "saturated fats": "saturated_fat",
    "verzadigd vet": "saturated_fat",
    "waarvan verzadigde vetten": "saturated_fat",
    "waarvan: verzadigde vetten": "saturated_fat",
    "of which saturates": "saturated_fat",
    # Protein
    "eiwitten": "protein",
    "protein": "protein",
    "proteins": "protein",
    "eiwit": "protein",
    # Fiber
    "vezels": "fiber",
    "fibre": "fiber",
    "fiber": "fiber",
    "dietary fibre": "fiber",
    "dietary fiber": "fiber",
    # Fat (general)
    "vetten": "fat",
    "fat": "fat",
    "fats": "fat",
    "vet": "fat",
    # Carbohydrates
    "koolhydraten": "carbohydrates",
    "carbohydrates": "carbohydrates",
    "carbs": "carbohydrates",
}

# Risk thresholds (per 100g) — based on Dutch/EU nutrition guidelines
_SUGAR_RISK = {"low": 5.0, "medium": 15.0}  # g per 100g
_SALT_RISK = {"low": 0.3, "medium": 1.2}  # g per 100g
_SAT_FAT_RISK = {"low": 3.0, "medium": 10.0}  # g per 100g

# Nutri-Score mapping to numeric value (A=5 best, E=1 worst)
_NUTRISCORE_VALUES = {"a": 5, "b": 4, "c": 3, "d": 2, "e": 1}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _latest_scrape_run_id(session: Session) -> int | None:
    """Return the ID of the most recent completed scrape run."""
    run = (
        session.query(ScrapeRun)
        .filter(ScrapeRun.status == "completed")
        .order_by(ScrapeRun.id.desc())
        .first()
    )
    return run.id if run else None


def _effective_price(product: ProductRow) -> float | None:
    """COALESCE(current_price, price_before_bonus) as effective price."""
    if product.current_price is not None and product.current_price > 0:
        return product.current_price
    if product.price_before_bonus is not None and product.price_before_bonus > 0:
        return product.price_before_bonus
    return None


def _normalize_nutrient_name(name: str) -> str:
    """Normalize a nutrient name to a canonical key."""
    return _NUTRIENT_MAP.get(name.lower().strip(), name.lower().strip())


def _risk_level(value: float | None, thresholds: dict[str, float]) -> str:
    """Return 'low', 'medium', or 'high' risk level for a nutrient value."""
    if value is None:
        return "unknown"
    if value <= thresholds["low"]:
        return "low"
    if value <= thresholds["medium"]:
        return "medium"
    return "high"


def _compute_health_score(
    calories: float | None,
    sugar: float | None,
    salt: float | None,
    sat_fat: float | None,
    protein: float | None,
    fiber: float | None,
    nutriscore: str | None,
) -> float:
    """Compute a health score (0-100) based on nutrient values and Nutri-Score.

    Scoring rules:
    - Start at 50 (neutral)
    - Nutri-Score: A=+20, B=+10, C=0, D=-10, E=-20
    - Protein (per 100g): +1 per g, max +15
    - Fiber (per 100g): +1 per g, max +10
    - Sugar (per 100g): -1 per g above 5g, min -20
    - Salt (per 100g): -2 per g above 0.3g, min -15
    - Saturated fat (per 100g): -1 per g above 3g, min -15
    - Calories (per 100g): -0.02 per kcal above 200, min -10
    """
    score = 50.0

    # Nutri-Score bonus/penalty
    if nutriscore:
        ns_val = _NUTRISCORE_VALUES.get(nutriscore.lower())
        if ns_val is not None:
            score += (ns_val - 3) * 10  # A=+20, B=+10, C=0, D=-10, E=-20

    # Protein reward (up to +15)
    if protein is not None and protein > 0:
        score += min(protein * 1.0, 15)

    # Fiber reward (up to +10)
    if fiber is not None and fiber > 0:
        score += min(fiber * 1.0, 10)

    # Sugar penalty (above 5g/100g)
    if sugar is not None and sugar > 5:
        score -= min((sugar - 5) * 1.0, 20)

    # Salt penalty (above 0.3g/100g)
    if salt is not None and salt > 0.3:
        score -= min((salt - 0.3) * 2.0, 15)

    # Saturated fat penalty (above 3g/100g)
    if sat_fat is not None and sat_fat > 3:
        score -= min((sat_fat - 3) * 1.0, 15)

    # Calories penalty (above 200kcal/100g)
    if calories is not None and calories > 200:
        score -= min((calories - 200) * 0.02, 10)

    return max(0.0, min(100.0, round(score, 1)))


# ---------------------------------------------------------------------------
# Step 1: Category Price Rankings
# ---------------------------------------------------------------------------

def compute_category_price_rankings(session: Session) -> int:
    """Compute product rankings within categories.

    Ranking types:
    - cheapest_price: lowest current price per category/subcategory
    - most_expensive_price: highest current price
    - cheapest_unit_price: lowest unit price (requires unit_prices table)
    - cheapest_healthy: cheapest product with Nutri-Score A/B
    - best_deal: biggest discount percentage (bonus products only)

    Returns:
        Number of ranking rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)

    # Clear existing rankings
    session.query(CategoryPriceRankingRow).delete()

    # Get all products with valid prices
    products = session.query(ProductRow).filter(
        ProductRow.main_category.isnot(None),
    ).all()

    # Build category/subcategory groupings
    cat_products: dict[str, list[ProductRow]] = defaultdict(list)
    subcat_products: dict[tuple[str, str], list[ProductRow]] = defaultdict(list)

    for p in products:
        eff = _effective_price(p)
        if eff is not None:
            cat_products[p.main_category].append(p)
            if p.sub_category:
                subcat_products[(p.main_category, p.sub_category)].append(p)

    # Build unit price lookup
    unit_prices = {
        up.product_id: up
        for up in session.query(UnitPriceRow).all()
    }

    # Build deal score lookup (for best_deal ranking)
    deal_scores = {
        d.product_id: d.deal_score
        for d in session.query(DealQualityScoreRow).all()
    }

    rows_added = 0

    def _rank_group(
        ranking_type: str,
        group_key: str,
        group_label: str | None,
        product_list: list[ProductRow],
        reverse: bool = False,
        key_fn=None,
    ) -> None:
        nonlocal rows_added

        if key_fn is None:
            key_fn = lambda p: _effective_price(p) or 0

        scored = []
        for p in product_list:
            val = key_fn(p)
            if val is not None:
                scored.append((p, val))

        scored.sort(key=lambda x: x[1], reverse=reverse)

        for rank, (product, _) in enumerate(scored[:RANKING_TOP_N], 1):
            up = unit_prices.get(product.webshop_id)
            row = CategoryPriceRankingRow(
                main_category=group_key,
                sub_category=group_label,
                ranking_type=ranking_type,
                product_id=product.webshop_id,
                product_title=product.title,
                brand=product.brand,
                current_price=product.current_price,
                unit_price=up.normalized_price_eur_per_unit if up else None,
                base_unit=up.base_unit if up else None,
                rank=rank,
                product_count=len(scored),
                computed_at=computed_at,
                source_run_id=source_run_id,
            )
            session.add(row)
            rows_added += 1

    # cheapest_price (ascending)
    for cat, plist in cat_products.items():
        _rank_group("cheapest_price", cat, None, plist, reverse=False)
    for (cat, sub), plist in subcat_products.items():
        _rank_group("cheapest_price", cat, sub, plist, reverse=False)

    # most_expensive_price (descending)
    for cat, plist in cat_products.items():
        _rank_group("most_expensive_price", cat, None, plist, reverse=True)
    for (cat, sub), plist in subcat_products.items():
        _rank_group("most_expensive_price", cat, sub, plist, reverse=True)

    # cheapest_unit_price (ascending, requires unit_prices)
    for cat, plist in cat_products.items():
        _rank_group(
            "cheapest_unit_price", cat, None, plist, reverse=False,
            key_fn=lambda p: unit_prices.get(p.webshop_id).normalized_price_eur_per_unit
            if unit_prices.get(p.webshop_id) else None,
        )
    for (cat, sub), plist in subcat_products.items():
        _rank_group(
            "cheapest_unit_price", cat, sub, plist, reverse=False,
            key_fn=lambda p: unit_prices.get(p.webshop_id).normalized_price_eur_per_unit
            if unit_prices.get(p.webshop_id) else None,
        )

    # cheapest_healthy (cheapest with Nutri-Score A/B)
    for cat, plist in cat_products.items():
        healthy = [p for p in plist if p.nutriscore and p.nutriscore.lower() in ("a", "b")]
        if healthy:
            _rank_group("cheapest_healthy", cat, None, healthy, reverse=False)
    for (cat, sub), plist in subcat_products.items():
        healthy = [p for p in plist if p.nutriscore and p.nutriscore.lower() in ("a", "b")]
        if healthy:
            _rank_group("cheapest_healthy", cat, sub, healthy, reverse=False)

    # best_deal (highest deal_score)
    for cat, plist in cat_products.items():
        with_deals = [p for p in plist if deal_scores.get(p.webshop_id) is not None]
        if with_deals:
            _rank_group(
                "best_deal", cat, None, with_deals, reverse=True,
                key_fn=lambda p: deal_scores.get(p.webshop_id),
            )
    for (cat, sub), plist in subcat_products.items():
        with_deals = [p for p in plist if deal_scores.get(p.webshop_id) is not None]
        if with_deals:
            _rank_group(
                "best_deal", cat, sub, with_deals, reverse=True,
                key_fn=lambda p: deal_scores.get(p.webshop_id),
            )

    return rows_added


# ---------------------------------------------------------------------------
# Step 1: Deal Quality Scores
# ---------------------------------------------------------------------------

def compute_deal_quality_scores(session: Session) -> int:
    """Compute deal quality scores for all products with price history.

    Scoring algorithm (0-100):
    - Start at 50
    - If current price == historical low: +30 (historical_low)
    - If current price < avg price: +15 (scaled by how much below avg)
    - If current price < historical low * 1.1: +10
    - If is_bonus with valid discount: +discount_pct * 0.3 (max +15)
    - Penalty for high volatility: -volatility * 5 (max -15)
    - Clamp to 0-100

    Labels based on final score:
    - >= 85: historical_low
    - >= 70: excellent_deal
    - >= 55: good_deal
    - >= 45: normal_promotion
    - >= 30: weak_promotion
    - < 30: not_a_deal

    Returns:
        Number of deal score rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)

    session.query(DealQualityScoreRow).delete()

    # Get products with price metrics
    products_with_metrics = (
        session.query(ProductRow, PriceMetricsRow)
        .join(PriceMetricsRow, PriceMetricsRow.product_id == ProductRow.webshop_id)
        .filter(PriceMetricsRow.avg_price.isnot(None))
        .all()
    )

    rows_added = 0
    for product, metrics in products_with_metrics:
        eff_price = _effective_price(product)
        if eff_price is None:
            continue

        avg_price = metrics.avg_price
        hist_low = metrics.cheapest_price
        volatility = metrics.price_volatility or 0

        # Discount calculation (only for valid bonus products)
        discount_pct = None
        if (
            product.is_bonus
            and product.price_before_bonus and product.price_before_bonus > 0
            and product.current_price is not None
            and product.current_price < product.price_before_bonus
        ):
            discount_pct = round(
                (product.price_before_bonus - product.current_price)
                / product.price_before_bonus * 100,
                2,
            )

        # vs avg price
        current_vs_avg_pct = None
        if avg_price and avg_price > 0:
            current_vs_avg_pct = round((eff_price - avg_price) / avg_price * 100, 2)

        # vs historical low
        current_vs_low_pct = None
        if hist_low and hist_low > 0:
            current_vs_low_pct = round((eff_price - hist_low) / hist_low * 100, 2)

        # --- Score computation ---
        score = 50.0

        # Historical low bonus
        if hist_low and abs(eff_price - hist_low) < 0.001:
            score += 30

        # Below average price bonus
        if avg_price and eff_price < avg_price:
            below_pct = (avg_price - eff_price) / avg_price
            score += min(below_pct * 100, 15)

        # Near historical low bonus
        if hist_low and eff_price <= hist_low * 1.1:
            score += 10

        # Discount bonus
        if discount_pct is not None:
            score += min(discount_pct * 0.3, 15)

        # Volatility penalty
        score -= min(volatility * 5, 15)

        score = max(0.0, min(100.0, round(score, 1)))

        # Label assignment
        if score >= 85:
            label = "historical_low"
        elif score >= 70:
            label = "excellent_deal"
        elif score >= 55:
            label = "good_deal"
        elif score >= 45:
            label = "normal_promotion"
        elif score >= 30:
            label = "weak_promotion"
        else:
            label = "not_a_deal"

        row = DealQualityScoreRow(
            product_id=product.webshop_id,
            current_price=product.current_price,
            price_before_bonus=product.price_before_bonus,
            discount_pct=discount_pct,
            avg_price=avg_price,
            historical_low_price=hist_low,
            current_vs_avg_pct=current_vs_avg_pct,
            current_vs_low_pct=current_vs_low_pct,
            price_volatility=volatility,
            deal_score=score,
            deal_label=label,
            computed_at=computed_at,
            source_run_id=source_run_id,
        )
        session.add(row)
        rows_added += 1

    return rows_added


# ---------------------------------------------------------------------------
# Step 2: Nutrition Scores
# ---------------------------------------------------------------------------

def compute_nutrition_scores(session: Session) -> int:
    """Compute nutrition scores for all products with nutrition data.

    For each product:
    1. Normalize nutrient names from the nutrition table
    2. Extract per-100g values for key nutrients
    3. Compute health_score (0-100) using rule-based algorithm
    4. Compute protein_per_euro and fiber_per_euro
    5. Assign risk levels for sugar, salt, saturated fat

    Returns:
        Number of nutrition score rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)

    session.query(NutritionScoreRow).delete()

    # Get all products with nutrition data
    products = session.query(ProductRow).all()

    # Build nutrition lookup: product_id -> {nutrient_name: value}
    nutrition_lookup: dict[int, dict[str, list[tuple[float | None, str | None]]]] = defaultdict(dict)
    for nutr in session.query(NutritionRow).all():
        canonical = _normalize_nutrient_name(nutr.nutrient_name or "")
        # Prefer per-100g values
        basis = (nutr.basis or "").lower()
        key = f"{canonical}_{basis}"
        nutrition_lookup[nutr.product_id][key] = (nutr.value, nutr.unit)

    rows_added = 0
    for product in products:
        pid = product.webshop_id
        nutr_data = nutrition_lookup.get(pid, {})

        # Extract key nutrients (prefer per 100g/ml values)
        def _get_nutrient(canonical: str) -> float | None:
            """Get nutrient value, preferring per-100g basis."""
            # Try per 100g first
            for key, (val, unit) in nutr_data.items():
                if key.startswith(canonical) and "100" in key and val is not None:
                    return val
            # Fall back to any value
            for key, (val, unit) in nutr_data.items():
                if key.startswith(canonical) and val is not None:
                    return val
            return None

        calories = _get_nutrient("calories")
        sugar = _get_nutrient("sugar")
        salt = _get_nutrient("salt")
        sat_fat = _get_nutrient("saturated_fat")
        protein = _get_nutrient("protein")
        fiber = _get_nutrient("fiber")

        # Skip if no meaningful nutrition data at all
        if all(v is None for v in [calories, sugar, salt, sat_fat, protein, fiber]):
            continue

        # Compute health score
        health_score = _compute_health_score(
            calories, sugar, salt, sat_fat, protein, fiber, product.nutriscore
        )

        # Protein/fiber per euro
        eff_price = _effective_price(product)
        protein_per_euro = None
        fiber_per_euro = None
        if eff_price and eff_price > 0:
            if protein is not None:
                protein_per_euro = round(protein / eff_price, 2)
            if fiber is not None:
                fiber_per_euro = round(fiber / eff_price, 2)

        # Risk levels
        sugar_risk = _risk_level(sugar, _SUGAR_RISK)
        salt_risk = _risk_level(salt, _SALT_RISK)
        sat_fat_risk = _risk_level(sat_fat, _SAT_FAT_RISK)

        row = NutritionScoreRow(
            product_id=pid,
            calories_per_100g=calories,
            sugar_per_100g=sugar,
            salt_per_100g=salt,
            saturated_fat_per_100g=sat_fat,
            protein_per_100g=protein,
            fiber_per_100g=fiber,
            nutriscore=product.nutriscore,
            health_score=health_score,
            protein_per_euro=protein_per_euro,
            fiber_per_euro=fiber_per_euro,
            sugar_risk_level=sugar_risk,
            salt_risk_level=salt_risk,
            saturated_fat_risk_level=sat_fat_risk,
            computed_at=computed_at,
            source_run_id=source_run_id,
        )
        session.add(row)
        rows_added += 1

    return rows_added


# ---------------------------------------------------------------------------
# Step 2: Health Value Rankings
# ---------------------------------------------------------------------------

def compute_health_value_rankings(session: Session) -> int:
    """Compute health value rankings.

    Combines health_score with price data to find the best health-value products.

    Health value score = health_score * (1 + 10 / (price + 1))
    This rewards healthy products that are also affordable.

    Products are ranked within their main_category and sub_category.

    Returns:
        Number of health value ranking rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)

    session.query(HealthValueRankingRow).delete()

    # Get products with nutrition scores
    nutrition_scores = session.query(NutritionScoreRow).all()
    if not nutrition_scores:
        return 0

    # Build product lookup
    product_ids = {ns.product_id for ns in nutrition_scores}
    products = {
        p.webshop_id: p
        for p in session.query(ProductRow).filter(
            ProductRow.webshop_id.in_(product_ids)
        ).all()
    }

    # Build unit price lookup
    unit_prices = {
        up.product_id: up
        for up in session.query(UnitPriceRow).all()
    }

    # Compute health value for each product
    scored_products: list[tuple[int, dict[str, Any]]] = []

    for ns in nutrition_scores:
        product = products.get(ns.product_id)
        if not product:
            continue

        eff_price = _effective_price(product)
        if eff_price is None or eff_price <= 0:
            continue

        # Health value score: rewards health + affordability
        # Formula: health_score * (1 + 10 / (price + 1))
        # This gives more weight to cheap healthy products
        hv_score = round(ns.health_score * (1 + 10 / (eff_price + 1)), 2)

        up = unit_prices.get(ns.product_id)

        scored_products.append((ns.product_id, {
            "product": product,
            "nutrition": ns,
            "eff_price": eff_price,
            "hv_score": hv_score,
            "unit_price": up.normalized_price_eur_per_unit if up else None,
            "base_unit": up.base_unit if up else None,
        }))

    # Group by category and subcategory
    cat_groups: dict[str, list] = defaultdict(list)
    subcat_groups: dict[tuple[str, str], list] = defaultdict(list)

    for pid, data in scored_products:
        cat = data["product"].main_category or "Unknown"
        sub = data["product"].sub_category
        cat_groups[cat].append((pid, data))
        if sub:
            subcat_groups[(cat, sub)].append((pid, data))

    # Rank within categories
    cat_ranks: dict[int, int] = {}
    for cat, items in cat_groups.items():
        items.sort(key=lambda x: x[1]["hv_score"], reverse=True)
        for rank, (pid, _) in enumerate(items, 1):
            cat_ranks[pid] = rank

    # Rank within subcategories
    subcat_ranks: dict[int, int] = {}
    for (cat, sub), items in subcat_groups.items():
        items.sort(key=lambda x: x[1]["hv_score"], reverse=True)
        for rank, (pid, _) in enumerate(items, 1):
            subcat_ranks[pid] = rank

    # Insert rows
    rows_added = 0
    for pid, data in scored_products:
        product = data["product"]
        ns = data["nutrition"]

        row = HealthValueRankingRow(
            product_id=pid,
            main_category=product.main_category,
            sub_category=product.sub_category,
            current_price=product.current_price,
            unit_price=data["unit_price"],
            health_score=ns.health_score,
            health_value_score=data["hv_score"],
            protein_per_euro=ns.protein_per_euro,
            fiber_per_euro=ns.fiber_per_euro,
            rank_in_category=cat_ranks.get(pid),
            rank_in_subcategory=subcat_ranks.get(pid),
            computed_at=computed_at,
            source_run_id=source_run_id,
        )
        session.add(row)
        rows_added += 1

    return rows_added


# ---------------------------------------------------------------------------
# Public convenience: run all intelligence computations
# ---------------------------------------------------------------------------

def compute_all_intelligence(session: Session) -> dict[str, int]:
    """Run all intelligence computations in the correct dependency order.

    Order:
    1. deal_quality_scores (needed by category_price_rankings for best_deal)
    2. category_price_rankings
    3. nutrition_scores
    4. health_value_rankings (depends on nutrition_scores)

    Returns:
        Dict of {table_name: rows_inserted}.
    """
    deal_scores = compute_deal_quality_scores(session)
    session.flush()  # Make deal scores available for category rankings

    cat_rankings = compute_category_price_rankings(session)
    session.flush()

    nutr_scores = compute_nutrition_scores(session)
    session.flush()

    hv_rankings = compute_health_value_rankings(session)

    return {
        "dealQualityScores": deal_scores,
        "categoryPriceRankings": cat_rankings,
        "nutritionScores": nutr_scores,
        "healthValueRankings": hv_rankings,
    }
