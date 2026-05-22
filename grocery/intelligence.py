"""Grocery intelligence analytics — price rankings, deal quality, nutrition scoring, health value.

All functions are deterministic post-processing: they read from source/normalized tables
and write to analytics_* derived tables. Every row includes computed_at and source_run_id.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from math import sqrt
from typing import Any

from sqlalchemy.orm import Session

from .db import (
    AllergenRow,
    AllergenSummaryRow,
    BasketDefinitionRow,
    BasketItemRow,
    BasketSnapshotRow,
    BrandIntelligenceRow,
    CategoryPriceRankingRow,
    DealQualityScoreRow,
    HealthValueRankingRow,
    IngredientFlagRow,
    IngredientRow,
    NutritionRow,
    NutritionScoreRow,
    PriceHistoryRow,
    PriceMetricsRow,
    ProductAlternativeRow,
    ProductPromotionFrequencyRow,
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
                current_price=_effective_price(product),
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
# Step 3: Promotion Frequency Intelligence
# ---------------------------------------------------------------------------

# Dutch/English terms for added sugars
_ADDED_SUGAR_TERMS = {
    "suiker", "suikers", "sugar", "sugars", "added sugar", "added sugars",
    "rietsuiker", "rietssuiker", "cane sugar", "beet sugar",
    "glucosesiroop", "glucose syrup", "high fructose corn syrup", "hfcs",
    "fructosesiroop", "fructose syrup", "high-fructose corn syrup",
    "maïssiroop", "maissirup", "corn syrup",
    "stroop", "syrup", "honey", "honing",
    "maltose", "maltodextrine", "maltodextrin",
    "dextrose", "dextrine",
    "invertsuiker", "invert sugar",
    "concentrated grape juice", "geconcentreerde druivensap",
    "concentrated apple juice", "geconcentreerde appelsap",
    "evap", "evapo", "evaporated cane juice",
    "honingsirup", "honey syrup",
}

# Palm oil terms
_PALM_OIL_TERMS = {
    "palmolie", "palm oil", "palmkernolie", "palm kernel oil",
    "palm fat", "palmvet", "palm kernel fat", "palmkernvet",
    "palmitate", "palmitic acid", "elaeis guineensis",
    "vegetable oil", " plantaardige olie",  # ambiguous but common proxy
}

# Sweetener terms
_SWEETENER_TERMS = {
    "aspartaam", "aspartame", "acesulfam", "acesulfame",
    "sucralose", "sucraloos", "saccharine", "saccharin",
    "sucraloos", "sorbitol", "xylitol", "maltitol",
    "isomalt", "erythritol", "mannitol",
    "styrax", "stevia", "steviolglycosiden", "steviol glycosides",
    "neotame", "adapaam", "advantam", "neohesperidine dihydrochalcone",
    "aloheseridine", "neohesperidine",
}

# Preservative terms
_PRESERVATIVE_TERMS = {
    "sorbinezuur", "sorbic acid", "sorbates", "sorraat",
    "benzoinezuur", "benzoic acid", "benzoates", "benzoaat",
    "propionaat", "propionates", "propionic acid",
    "natriumethylmaltol", "sodium ethyl maltolate",
    "sulfi", "sulfite", "sulphite", "zwaveldioxide", "sulfur dioxide",
    "natriumnitriet", "sodium nitrite", "kaliumnitriet", "potassium nitrite",
    "natriumnitraat", "sodium nitrate", "kaliumnitraat", "potassium nitrate",
    "e200", "e201", "e202", "e203", "e210", "e211", "e212", "e213",
    "e214", "e215", "e216", "e217", "e249", "e250", "e251", "e252",
}

# Emulsifier terms
_EMULSIFIER_TERMS = {
    "mono- en diglyceriden", "mono- and diglycerides",
    "lecithine", "lecithin", "sojalecithine", "soya lecithin",
    "zonnebloemlecithine", "sunflower lecithin",
    "polysorbaat", "polysorbate", "polysorbates",
    "carnaubawas", "carnauba wax", "was",
    "e471", "e322", "e432", "e433", "e434", "e435", "e436",
}

# Colourant terms
_COLOURANT_TERMS = {
    "tartrazine", "titan dioxide", "titanium dioxide",
    "caramel", "caramellering", "caramel color",
    "betanine", "betanin", "cursmine", "curcumin",
    "anthocyanine", "anthocyanins", "chlorofyl", "chlorophyll",
    "e100", "e101", "e102", "e104", "e110", "e120", "e122", "e123",
    "e124", "e127", "e129", "e133", "e140", "e141", "e150",
    "e150a", "e150b", "e150c", "e150d", "e160", "e161", "e162",
    "e170", "e171",
}

# Seed oil terms
_SEED_OIL_TERMS = {
    "zonnebloemolie", "sunflower oil", "raapzaadolie", "rapeseed oil",
    "canola oil", "maïsolie", "corn oil", "sojaolie", "soya oil",
    "zadenolie", "seed oil", "plantaardige olie", "vegetable oil",
    "lijnzaadolie", "linseed oil", "saflorolie", "safflower oil",
}

# Caffeine terms
_CAFFEINE_TERMS = {
    "caffeïne", "caffeine", "guarana", "mate", "taurine",
    "taurien", "guarana extract", "koffie", "coffee extract",
}

# Animal-derived terms (for vegan detection)
_ANIMAL_TERMS = {
    "melk", "milk", "boter", "butter", "kaas", "cheese",
    "room", "cream", "yoghurt", "yogurt", "whey", "wei",
    "caseïne", "casein", "lactose", "melkpoeder", "milk powder",
    "ei", "egg", "eieren", "eiwit", "egg white",
    "eiwitten", "eggs", "egg yolk", "eidooier",
    "vis", "fish", "vlees", "meat", "kip", "chicken",
    "varken", "pork", "rund", "beef", "lam", "lamb",
    "gelatine", "gelatin", "dierlijk", "animal",
    "honing", "honey", "bijenwas", "beeswax",
    "schelpdier", "shellfish", "garnalen", "shrimp",
    "inktvis", "squid", "zeewier", "seaweed",  # seaweed is plant-based but often grouped
}

# Vegan-friendly terms (plant-based indicators)
_VEGAN_INDICATORS = {
    "plantaardig", "plant-based", "vegetisch", "vegetable",
    "vegetarisch", "vegetarian", "vegan", "vega",
}


def compute_promotion_frequency(session: Session) -> int:
    """Compute promotion frequency from price_history.

    For each product with price history:
    - Count total observations (scrape runs)
    - Count bonus observations
    - Calculate bonus_frequency_pct = bonus_observations / total_observations * 100
    - Calculate avg/max discount from bonus periods
    - Track latest bonus start/end dates

    Returns:
        Number of rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)

    session.query(ProductPromotionFrequencyRow).delete()

    # Group price history by product
    histories = session.query(PriceHistoryRow).all()
    product_histories: dict[int, list[PriceHistoryRow]] = defaultdict(list)
    for h in histories:
        product_histories[h.product_id].append(h)

    rows_added = 0
    for product_id, history_list in product_histories.items():
        total = len(history_list)
        bonus_obs = [h for h in history_list if h.is_bonus]
        bonus_count = len(bonus_obs)

        bonus_freq = round(bonus_count / total * 100, 2) if total > 0 else 0

        # Calculate discounts for bonus observations
        discounts = []
        for h in bonus_obs:
            if (h.price_before_bonus and h.price_before_bonus > 0
                    and h.current_price and h.current_price < h.price_before_bonus):
                disc = round((h.price_before_bonus - h.current_price) / h.price_before_bonus * 100, 2)
                discounts.append(disc)

        avg_discount = round(sum(discounts) / len(discounts), 2) if discounts else None
        max_discount = max(discounts) if discounts else None

        # Latest bonus dates
        latest_start = None
        latest_end = None
        for h in bonus_obs:
            if h.bonus_start_date:
                if latest_start is None or h.bonus_start_date > latest_start:
                    latest_start = h.bonus_start_date
            if h.bonus_end_date:
                if latest_end is None or h.bonus_end_date > latest_end:
                    latest_end = h.bonus_end_date

        row = ProductPromotionFrequencyRow(
            product_id=product_id,
            total_observations=total,
            bonus_observations=bonus_count,
            bonus_frequency_pct=bonus_freq,
            avg_discount_pct=avg_discount,
            max_discount_pct=max_discount,
            latest_bonus_start_date=latest_start,
            latest_bonus_end_date=latest_end,
            computed_at=computed_at,
            source_run_id=source_run_id,
        )
        session.add(row)
        rows_added += 1

    return rows_added


def compute_ingredient_flags(session: Session) -> int:
    """Compute smart ingredient flags from ingredient text.

    For each product with ingredients:
    - Scan ingredient text for known terms
    - Set boolean flags for each category
    - Compute clean_label_score (0-100, higher = cleaner)
    - Compute ultra_processed_score (0-100, higher = more processed)
    - Store matched terms as JSON

    Returns:
        Number of rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)

    session.query(IngredientFlagRow).delete()

    products = session.query(ProductRow).all()
    rows_added = 0

    for product in products:
        # Get ingredients text
        ingredients_text = ""
        if product.ingredients:
            try:
                ing_list = json.loads(product.ingredients)
                if isinstance(ing_list, list):
                    ingredients_text = " ".join(str(i) for i in ing_list).lower()
                else:
                    ingredients_text = str(ing_list).lower()
            except (json.JSONDecodeError, TypeError):
                ingredients_text = str(product.ingredients).lower()
        elif product.description_highlights:
            ingredients_text = product.description_highlights.lower()

        if not ingredients_text:
            continue

        matched_terms: dict[str, list[str]] = {}

        def _scan(terms: set, key: str) -> bool:
            matches = []
            for term in terms:
                if term.lower() in ingredients_text:
                    matches.append(term)
            if matches:
                matched_terms[key] = matches
            return len(matches) > 0

        has_added_sugar = _scan(_ADDED_SUGAR_TERMS, "added_sugar")
        has_palm_oil = _scan(_PALM_OIL_TERMS, "palm_oil")
        has_sweeteners = _scan(_SWEETENER_TERMS, "sweeteners")
        has_preservatives = _scan(_PRESERVATIVE_TERMS, "preservatives")
        has_emulsifiers = _scan(_EMULSIFIER_TERMS, "emulsifiers")
        has_colourants = _scan(_COLOURANT_TERMS, "colourants")
        has_seed_oils = _scan(_SEED_OIL_TERMS, "seed_oils")
        has_caffeine = _scan(_CAFFEINE_TERMS, "caffeine")

        # Vegan/vegetarian detection
        has_animal = _scan(_ANIMAL_TERMS, "animal_derived")
        has_vegan_indicator = _scan(_VEGAN_INDICATORS, "vegan_indicators")

        possible_vegetarian = not has_animal or has_vegan_indicator
        possible_vegan = not has_animal and has_vegan_indicator

        # Clean label score (100 = perfectly clean)
        clean_score = 100.0
        if has_added_sugar:
            clean_score -= 15
        if has_palm_oil:
            clean_score -= 10
        if has_sweeteners:
            clean_score -= 15
        if has_preservatives:
            clean_score -= 15
        if has_emulsifiers:
            clean_score -= 10
        if has_colourants:
            clean_score -= 15
        if has_seed_oils:
            clean_score -= 5
        clean_score = max(0, min(100, round(clean_score, 1)))

        # Ultra-processed score (0 = whole food, 100 = ultra-processed)
        ultra_score = 0.0
        if has_added_sugar:
            ultra_score += 15
        if has_sweeteners:
            ultra_score += 15
        if has_preservatives:
            ultra_score += 20
        if has_emulsifiers:
            ultra_score += 20
        if has_colourants:
            ultra_score += 15
        if has_seed_oils:
            ultra_score += 10
        if has_palm_oil:
            ultra_score += 5
        ultra_score = max(0, min(100, round(ultra_score, 1)))

        # Count ingredients (rough estimate from text)
        ingredient_count = len([i for i in ingredients_text.split(",") if i.strip()])

        row = IngredientFlagRow(
            product_id=product.webshop_id,
            ingredient_count=ingredient_count,
            contains_added_sugar=has_added_sugar,
            contains_palm_oil=has_palm_oil,
            contains_sweeteners=has_sweeteners,
            contains_preservatives=has_preservatives,
            contains_emulsifiers=has_emulsifiers,
            contains_colourants=has_colourants,
            contains_seed_oils=has_seed_oils,
            contains_caffeine=has_caffeine,
            possible_vegan=possible_vegan,
            possible_vegetarian=possible_vegetarian,
            clean_label_score=clean_score,
            ultra_processed_score=ultra_score,
            matched_terms_json=json.dumps(matched_terms, ensure_ascii=False),
            computed_at=computed_at,
            source_run_id=source_run_id,
        )
        session.add(row)
        rows_added += 1

    return rows_added


def compute_allergen_summary(session: Session) -> int:
    """Compute allergen summary from allergen rows.

    For each product with allergen data:
    - Normalize allergen names to categories
    - Set boolean flags for each major allergen
    - Count CONTAINS vs MAY_CONTAIN
    - Compute allergen_risk_score (0-100, higher = more allergens)

    Returns:
        Number of rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)

    session.query(AllergenSummaryRow).delete()

    # Allergen name normalization
    ALLERGEN_MAP: dict[str, set[str]] = {
        "gluten": {"gluten", "tarwe", "wheat", "weizen", "rogge", "rye", "gerst", "barley", "haver", "oats", "spelt", "kamut", "secale cereale", "triticum"},
        "milk": {"melk", "milk", "lactose", "caseïne", "caseine", "casein", "wei", "whey", "boter", "butter", "kaas", "cheese", "room", "cream"},
        "nuts": {"noten", "nuts", "amandel", "almond", "hazelnoot", "hazelnut", "cashew", "pinda", "walnoot", "walnut", "pecan", "macadamia", "pistache", "pistachio"},
        "peanuts": {"pinda", "peanut", "pinda's", "peanuts", "arachis"},
        "soy": {"soja", "soy", "sojaboon", "soybean", "sojameel", "soya flour"},
        "egg": {"ei", "egg", "eieren", "eggs", "eidooier", "egg yolk", "eiwit", "egg white", "albumine", "albumin"},
        "fish": {"vis", "fish", "zalm", "salmon", "tonijn", "tuna", "cabillaud", "cod", "heek", "haddock"},
        "shellfish": {"schelpdier", "shellfish", "garnalen", "shrimp", "kreeft", "crab", "inktvis", "squid", "mosselen", "mussels", "oesters", "oysters", "garnalen", "prawns"},
    }

    allergen_rows = session.query(AllergenRow).all()
    product_allergens: dict[int, list[AllergenRow]] = defaultdict(list)
    for a in allergen_rows:
        product_allergens[a.product_id].append(a)

    rows_added = 0
    for product_id, allergen_list in product_allergens.items():
        contains_gluten = False
        contains_milk = False
        contains_nuts = False
        contains_peanuts = False
        contains_soy = False
        contains_egg = False
        contains_fish = False
        contains_shellfish = False

        may_contain_count = 0
        contains_count = 0

        for a in allergen_list:
            name_lower = (a.allergen_name or "").lower()
            level = (a.level or "CONTAINS").upper()

            # Skip FREE_FROM — product doesn't actually contain this allergen
            if level == "FREE_FROM":
                continue

            if "MAY" in level:
                may_contain_count += 1
            else:
                contains_count += 1

            for category, terms in ALLERGEN_MAP.items():
                if name_lower in terms:
                    if category == "gluten":
                        contains_gluten = True
                    elif category == "milk":
                        contains_milk = True
                    elif category == "nuts":
                        contains_nuts = True
                    elif category == "peanuts":
                        contains_peanuts = True
                    elif category == "soy":
                        contains_soy = True
                    elif category == "egg":
                        contains_egg = True
                    elif category == "fish":
                        contains_fish = True
                    elif category == "shellfish":
                        contains_shellfish = True

        # Risk score: weighted by severity
        risk = 0.0
        if contains_gluten:
            risk += 20
        if contains_milk:
            risk += 15
        if contains_nuts:
            risk += 20
        if contains_peanuts:
            risk += 20
        if contains_soy:
            risk += 10
        if contains_egg:
            risk += 10
        if contains_fish:
            risk += 10
        if contains_shellfish:
            risk += 15
        risk += min(may_contain_count * 5, 15)
        risk = min(100, round(risk, 1))

        row = AllergenSummaryRow(
            product_id=product_id,
            contains_gluten=contains_gluten,
            contains_milk=contains_milk,
            contains_nuts=contains_nuts,
            contains_peanuts=contains_peanuts,
            contains_soy=contains_soy,
            contains_egg=contains_egg,
            contains_fish=contains_fish,
            contains_shellfish=contains_shellfish,
            may_contain_count=may_contain_count,
            contains_count=contains_count,
            allergen_risk_score=risk,
            computed_at=computed_at,
            source_run_id=source_run_id,
        )
        session.add(row)
        rows_added += 1

    return rows_added


def compute_product_alternatives(session: Session) -> int:
    """Compute product alternatives based on category, brand, and price.

    For each product, find alternatives:
    - cheaper_alternative: same category/subcategory, lower price
    - healthier_alternative: same category, higher health score
    - same_brand_alternative: same brand, different product

    Returns:
        Number of alternative rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)

    session.query(ProductAlternativeRow).delete()

    products = session.query(ProductRow).all()
    nutrition_scores = {ns.product_id: ns for ns in session.query(NutritionScoreRow).all()}
    unit_prices = {up.product_id: up for up in session.query(UnitPriceRow).all()}

    # Group by category/subcategory
    cat_groups: dict[str, list[ProductRow]] = defaultdict(list)
    subcat_groups: dict[tuple[str, str], list[ProductRow]] = defaultdict(list)
    brand_groups: dict[str, list[ProductRow]] = defaultdict(list)

    for p in products:
        if p.main_category:
            cat_groups[p.main_category].append(p)
        if p.sub_category:
            subcat_groups[(p.main_category, p.sub_category)].append(p)
        if p.brand:
            brand_groups[p.brand].append(p)

    rows_added = 0

    for product in products:
        eff_price = _effective_price(product)
        if eff_price is None:
            continue

        my_health = nutrition_scores.get(product.webshop_id)
        my_up = unit_prices.get(product.webshop_id)

        # Cheaper alternative (same subcategory or category)
        candidates = []
        if product.sub_category:
            candidates = subcat_groups.get((product.main_category, product.sub_category), [])
        if not candidates and product.main_category:
            candidates = cat_groups.get(product.main_category, [])

        for alt in candidates:
            if alt.webshop_id == product.webshop_id:
                continue
            alt_price = _effective_price(alt)
            if alt_price is None or alt_price >= eff_price:
                continue

            saving_pct = round((eff_price - alt_price) / eff_price * 100, 2)
            alt_up = unit_prices.get(alt.webshop_id)
            unit_saving = None
            if my_up and alt_up:
                unit_saving = round((my_up.normalized_price_eur_per_unit - alt_up.normalized_price_eur_per_unit) / my_up.normalized_price_eur_per_unit * 100, 2)

            alt_health = nutrition_scores.get(alt.webshop_id)
            health_delta = None
            if my_health and alt_health:
                health_delta = round(alt_health.health_score - my_health.health_score, 1)

            confidence = min(0.9, 0.5 + (0.1 if product.sub_category == alt.sub_category else 0) + (0.1 if product.brand == alt.brand else 0) + (0.1 if saving_pct > 20 else 0))

            session.add(ProductAlternativeRow(
                product_id=product.webshop_id,
                alternative_product_id=alt.webshop_id,
                alternative_type="cheaper_alternative",
                price_saving_pct=saving_pct,
                unit_price_saving_pct=unit_saving,
                health_score_delta=health_delta,
                confidence=round(confidence, 2),
                explanation=f"{alt.brand or 'Unknown'} {alt.title[:50]}... is {saving_pct}% cheaper",
                computed_at=computed_at,
                source_run_id=source_run_id,
            ))
            rows_added += 1
            break  # Only top cheaper alternative

        # Healthier alternative (same category, higher health score)
        if my_health:
            cat_candidates = cat_groups.get(product.main_category, [])
            healthier = [
                c for c in cat_candidates
                if c.webshop_id != product.webshop_id
                and nutrition_scores.get(c.webshop_id)
                and nutrition_scores[c.webshop_id].health_score > my_health.health_score
            ]
            if healthier:
                healthier.sort(key=lambda c: nutrition_scores[c.webshop_id].health_score, reverse=True)
                best = healthier[0]
                alt_health = nutrition_scores[best.webshop_id]
                health_delta = round(alt_health.health_score - my_health.health_score, 1)
                alt_price = _effective_price(best)
                price_saving = None
                if alt_price:
                    price_saving = round((eff_price - alt_price) / eff_price * 100, 2)

                session.add(ProductAlternativeRow(
                    product_id=product.webshop_id,
                    alternative_product_id=best.webshop_id,
                    alternative_type="healthier_alternative",
                    price_saving_pct=price_saving,
                    unit_price_saving_pct=None,
                    health_score_delta=health_delta,
                    confidence=0.85,
                    explanation=f"{best.brand or 'Unknown'} {best.title[:50]}... has health score {alt_health.health_score} vs {my_health.health_score}",
                    computed_at=computed_at,
                    source_run_id=source_run_id,
                ))
                rows_added += 1

        # Same brand alternative
        if product.brand:
            brand_candidates = brand_groups.get(product.brand, [])
            for alt in brand_candidates:
                if alt.webshop_id == product.webshop_id:
                    continue
                alt_price = _effective_price(alt)
                if alt_price is None:
                    continue
                price_diff_pct = round((alt_price - eff_price) / eff_price * 100, 2)
                session.add(ProductAlternativeRow(
                    product_id=product.webshop_id,
                    alternative_product_id=alt.webshop_id,
                    alternative_type="same_brand",
                    price_saving_pct=-price_diff_pct if price_diff_pct < 0 else None,
                    unit_price_saving_pct=None,
                    health_score_delta=None,
                    confidence=0.7,
                    explanation=f"Same brand ({product.brand}): {alt.title[:50]}...",
                    computed_at=computed_at,
                    source_run_id=source_run_id,
                ))
                rows_added += 1
                break  # Only one same-brand alternative

    return rows_added


def compute_basket_snapshots(session: Session) -> int:
    """Compute basket cost snapshots for all active baskets.

    For each active basket:
    - Match basket items to current products
    - Calculate total current price (with bonuses)
    - Calculate total regular price (before bonuses)
    - Calculate bonus savings
    - Store snapshot

    Returns:
        Number of snapshot rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)
    today = datetime.utcnow().strftime("%Y-%m-%d")

    baskets = session.query(BasketDefinitionRow).filter(BasketDefinitionRow.active == True).all()
    rows_added = 0

    for basket in baskets:
        items = session.query(BasketItemRow).filter(BasketItemRow.basket_id == basket.basket_id).all()
        if not items:
            continue

        total_current = 0.0
        total_regular = 0.0
        item_count = 0

        for item in items:
            # Find matching product
            query = session.query(ProductRow).filter(
                ProductRow.main_category == item.main_category,
            )
            if item.sub_category:
                query = query.filter(ProductRow.sub_category == item.sub_category)

            # Prefer specific product if set
            if item.preferred_product_id:
                query = query.filter(ProductRow.webshop_id == item.preferred_product_id)
            elif item.product_rule == "cheapest":
                query = query.order_by(ProductRow.current_price.asc())
            elif item.product_rule == "healthiest":
                # Join with nutrition scores
                query = query.join(NutritionScoreRow, NutritionScoreRow.product_id == ProductRow.webshop_id).order_by(NutritionScoreRow.health_score.desc())

            product = query.first()
            if product:
                eff_price = _effective_price(product) or 0
                regular_price = product.price_before_bonus or product.current_price or 0
                total_current += eff_price * item.quantity
                total_regular += regular_price * item.quantity
                item_count += item.quantity

        bonus_savings = round(total_regular - total_current, 2)

        row = BasketSnapshotRow(
            basket_id=basket.basket_id,
            snapshot_date=today,
            total_current_price=round(total_current, 2),
            total_regular_price=round(total_regular, 2),
            bonus_savings=bonus_savings,
            item_count=item_count,
            computed_at=computed_at,
            source_run_id=source_run_id,
        )
        session.add(row)
        rows_added += 1

    return rows_added


def compute_brand_intelligence(session: Session) -> int:
    """Compute brand-level intelligence metrics.

    For each brand:
    - Count products and categories
    - Average price, unit price, health score
    - Bonus share % and avg discount
    - Price volatility
    - Private label candidate flag

    Returns:
        Number of rows inserted.
    """
    computed_at = datetime.utcnow()
    source_run_id = _latest_scrape_run_id(session)

    session.query(BrandIntelligenceRow).delete()

    products = session.query(ProductRow).filter(ProductRow.brand.isnot(None)).all()
    nutrition_scores = {ns.product_id: ns for ns in session.query(NutritionScoreRow).all()}
    unit_prices = {up.product_id: up for up in session.query(UnitPriceRow).all()}
    price_metrics = {pm.product_id: pm for pm in session.query(PriceMetricsRow).all()}

    brand_groups: dict[str, list[ProductRow]] = defaultdict(list)
    for p in products:
        brand_groups[p.brand].append(p)

    rows_added = 0
    for brand, brand_products in brand_groups.items():
        prices = [_effective_price(p) for p in brand_products]
        prices = [p for p in prices if p is not None]

        unit_price_vals = [
            unit_prices[p.webshop_id].normalized_price_eur_per_unit
            for p in brand_products
            if unit_prices.get(p.webshop_id)
        ]

        health_vals = [
            nutrition_scores[p.webshop_id].health_score
            for p in brand_products
            if nutrition_scores.get(p.webshop_id)
        ]

        bonus_products = [p for p in brand_products if p.is_bonus]
        bonus_share = round(len(bonus_products) / len(brand_products) * 100, 2) if brand_products else 0

        # Avg discount for bonus products
        discounts = []
        for p in bonus_products:
            if (p.price_before_bonus and p.price_before_bonus > 0
                    and p.current_price and p.current_price < p.price_before_bonus):
                discounts.append((p.price_before_bonus - p.current_price) / p.price_before_bonus * 100)
        avg_discount = round(sum(discounts) / len(discounts), 2) if discounts else None

        # Avg volatility
        volatilities = [
            price_metrics[p.webshop_id].price_volatility
            for p in brand_products
            if price_metrics.get(p.webshop_id) and price_metrics[p.webshop_id].price_volatility is not None
        ]
        avg_volatility = round(sum(volatilities) / len(volatilities), 4) if volatilities else None

        # Category count
        categories = set()
        for p in brand_products:
            if p.main_category:
                categories.add(p.main_category)

        # Private label candidate: low product count, single category, low bonus share
        private_label = (
            len(brand_products) <= 20
            and len(categories) <= 2
            and bonus_share < 10
        )

        row = BrandIntelligenceRow(
            brand=brand,
            product_count=len(brand_products),
            category_count=len(categories),
            avg_price=round(sum(prices) / len(prices), 2) if prices else None,
            avg_unit_price=round(sum(unit_price_vals) / len(unit_price_vals), 2) if unit_price_vals else None,
            avg_health_score=round(sum(health_vals) / len(health_vals), 1) if health_vals else None,
            bonus_share_pct=bonus_share,
            avg_discount_pct=avg_discount,
            price_volatility=avg_volatility,
            private_label_candidate=private_label,
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
    5. promotion_frequency (depends on price_history)
    6. ingredient_flags (depends on product ingredients)
    7. allergen_summary (depends on allergen rows)
    8. product_alternatives (depends on nutrition_scores, unit_prices)
    9. basket_snapshots (depends on basket definitions)
    10. brand_intelligence (depends on all metrics)

    Returns:
        Dict of {table_name: rows_inserted}.
    """
    deal_scores = compute_deal_quality_scores(session)
    session.flush()

    cat_rankings = compute_category_price_rankings(session)
    session.flush()

    nutr_scores = compute_nutrition_scores(session)
    session.flush()

    hv_rankings = compute_health_value_rankings(session)
    session.flush()

    promo_freq = compute_promotion_frequency(session)
    session.flush()

    ingr_flags = compute_ingredient_flags(session)
    session.flush()

    allergen_sum = compute_allergen_summary(session)
    session.flush()

    alternatives = compute_product_alternatives(session)
    session.flush()

    basket_snaps = compute_basket_snapshots(session)
    session.flush()

    brand_intel = compute_brand_intelligence(session)

    return {
        "dealQualityScores": deal_scores,
        "categoryPriceRankings": cat_rankings,
        "nutritionScores": nutr_scores,
        "healthValueRankings": hv_rankings,
        "promotionFrequency": promo_freq,
        "ingredientFlags": ingr_flags,
        "allergenSummary": allergen_sum,
        "productAlternatives": alternatives,
        "basketSnapshots": basket_snaps,
        "brandIntelligence": brand_intel,
    }
