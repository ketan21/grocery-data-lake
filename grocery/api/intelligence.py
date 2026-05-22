"""Grocery intelligence API endpoints.

Exposes derived analytics tables:
- Cheapest by category
- Deal quality scores
- Nutrition scores
- Health value rankings
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..db import (
    AllergenSummaryRow,
    BasketDefinitionRow,
    BasketSnapshotRow,
    BrandIntelligenceRow,
    CategoryPriceRankingRow,
    DealQualityScoreRow,
    HealthValueRankingRow,
    IngredientFlagRow,
    NutritionScoreRow,
    ProductAlternativeRow,
    ProductPromotionFrequencyRow,
    ProductRow,
    get_session,
)
from ..intelligence import (
    compute_all_intelligence,
    compute_allergen_summary,
    compute_basket_snapshots,
    compute_brand_intelligence,
    compute_ingredient_flags,
    compute_product_alternatives,
    compute_promotion_frequency,
)

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


@router.get("/cheapest-by-category")
def cheapest_by_category(
    ranking_type: str = Query(
        "cheapest_price",
        pattern="^(cheapest_price|most_expensive_price|cheapest_unit_price|cheapest_healthy|best_deal)$",
        description="Ranking type",
    ),
    category: str | None = Query(None, description="Filter by main category"),
    sub_category: str | None = Query(None, description="Filter by sub-category"),
    rank_limit: int = Query(5, ge=1, le=50, description="Max rank to return per group"),
):
    """Return product rankings within categories.

    Ranking types:
    - cheapest_price: Lowest current price per category/subcategory
    - most_expensive_price: Highest current price
    - cheapest_unit_price: Lowest price per unit
    - cheapest_healthy: Cheapest product with Nutri-Score A/B
    - best_deal: Biggest discount percentage (bonus products only)

    Filters:
    - category: filter by main category name
    - sub_category: filter by sub-category name
    """
    session = get_session()
    query = (
        session.query(CategoryPriceRankingRow)
        .filter(CategoryPriceRankingRow.ranking_type == ranking_type)
        .filter(CategoryPriceRankingRow.rank <= rank_limit)
    )
    if category:
        query = query.filter(CategoryPriceRankingRow.main_category == category)
    if sub_category:
        query = query.filter(CategoryPriceRankingRow.sub_category == sub_category)

    rows = query.order_by(
        CategoryPriceRankingRow.main_category.asc(),
        CategoryPriceRankingRow.sub_category.asc(),
        CategoryPriceRankingRow.rank.asc(),
    ).all()

    return {
        "rankingType": ranking_type,
        "category": category,
        "rankLimit": rank_limit,
        "total": len(rows),
        "rankings": [
            {
                "mainCategory": row.main_category,
                "subCategory": row.sub_category,
                "rank": row.rank,
                "productId": row.product_id,
                "productTitle": row.product_title,
                "brand": row.brand,
                "currentPrice": row.current_price,
                "unitPrice": row.unit_price,
                "baseUnit": row.base_unit,
                "productCount": row.product_count,
                    "ahUrl": f"https://www.ah.nl/producten/product/wi{row.product_id}",
            }
            for row in rows
        ],
    }


@router.get("/deals")
def deal_quality(
    label: str | None = Query(
        None,
        pattern="^(historical_low|excellent_deal|good_deal|normal_promotion|weak_promotion|not_a_deal)$",
        description="Filter by deal label",
    ),
    min_score: float | None = Query(None, ge=0, le=100, description="Minimum deal score"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    recompute: bool = Query(False, description="Recompute deal scores before returning"),
):
    """Return deal quality scores for products.

    Scores range from 0-100. Labels:
    - historical_low (>= 85): At or near all-time low price
    - excellent_deal (>= 70): Significantly below average
    - good_deal (>= 55): Below average with good discount
    - normal_promotion (>= 45): Standard promotion
    - weak_promotion (>= 30): Minimal savings
    - not_a_deal (< 30): Not actually cheaper than usual
    """
    session = get_session()
    if recompute:
        from ..intelligence import compute_deal_quality_scores
        compute_deal_quality_scores(session)
        session.commit()

    query = session.query(DealQualityScoreRow, ProductRow).join(
        ProductRow, ProductRow.webshop_id == DealQualityScoreRow.product_id
    )

    if label:
        query = query.filter(DealQualityScoreRow.deal_label == label)
    if min_score is not None:
        query = query.filter(DealQualityScoreRow.deal_score >= min_score)

    total = query.count()
    rows = (
        query.order_by(DealQualityScoreRow.deal_score.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "deals": [
            {
                "productId": score.product_id,
                "productTitle": product.title,
                "brand": product.brand,
                "mainCategory": product.main_category,
                "currentPrice": score.current_price,
                "priceBeforeBonus": score.price_before_bonus,
                "discountPct": score.discount_pct,
                "avgPrice": round(score.avg_price, 4) if score.avg_price else None,
                "historicalLowPrice": score.historical_low_price,
                "currentVsAvgPct": score.current_vs_avg_pct,
                "currentVsLowPct": score.current_vs_low_pct,
                "priceVolatility": round(score.price_volatility, 6) if score.price_volatility else None,
                "dealScore": score.deal_score,
                "dealLabel": score.deal_label,
                "ahUrl": f"https://www.ah.nl/producten/product/wi{score.product_id}",
            }
            for score, product in rows
        ],
    }


@router.get("/nutrition-scores")
def nutrition_scores(
    min_health_score: float | None = Query(None, ge=0, le=100, description="Minimum health score"),
    nutriscore: str | None = Query(None, description="Filter by Nutri-Score (A/B/C/D/E). Comma-separated for multiple"),
    sugar_risk: str | None = Query(None, pattern="^(low|medium|high|unknown)$", description="Sugar risk level"),
    salt_risk: str | None = Query(None, pattern="^(low|medium|high|unknown)$", description="Salt risk level"),
    min_protein_per_euro: float | None = Query(None, ge=0, description="Minimum protein per euro"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    recompute: bool = Query(False, description="Recompute nutrition scores before returning"),
):
    """Return nutrition scores for products.

    Health score ranges from 0-100. Higher is healthier.
    Includes risk levels for sugar, salt, and saturated fat.
    """
    session = get_session()
    if recompute:
        from ..intelligence import compute_nutrition_scores
        compute_nutrition_scores(session)
        session.commit()

    query = session.query(NutritionScoreRow, ProductRow).join(
        ProductRow, ProductRow.webshop_id == NutritionScoreRow.product_id
    )

    if min_health_score is not None:
        query = query.filter(NutritionScoreRow.health_score >= min_health_score)
    if nutriscore:
        scores = [s.strip().upper() for s in nutriscore.split(',') if s.strip()]
        if scores:
            query = query.filter(
                NutritionScoreRow.nutriscore.in_(scores)
            )
    if sugar_risk:
        query = query.filter(NutritionScoreRow.sugar_risk_level == sugar_risk)
    if salt_risk:
        query = query.filter(NutritionScoreRow.salt_risk_level == salt_risk)
    if min_protein_per_euro is not None:
        query = query.filter(
            NutritionScoreRow.protein_per_euro.isnot(None),
            NutritionScoreRow.protein_per_euro >= min_protein_per_euro,
        )

    total = query.count()
    rows = (
        query.order_by(NutritionScoreRow.health_score.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "products": [
            {
                "productId": score.product_id,
                "productTitle": product.title,
                "brand": product.brand,
                "mainCategory": product.main_category,
                "currentPrice": product.current_price,
                "caloriesPer100g": score.calories_per_100g,
                "sugarPer100g": score.sugar_per_100g,
                "saltPer100g": score.salt_per_100g,
                "saturatedFatPer100g": score.saturated_fat_per_100g,
                "proteinPer100g": score.protein_per_100g,
                "fiberPer100g": score.fiber_per_100g,
                "nutriscore": score.nutriscore,
                "healthScore": score.health_score,
                "proteinPerEuro": score.protein_per_euro,
                "fiberPerEuro": score.fiber_per_euro,
                "sugarRiskLevel": score.sugar_risk_level,
                "saltRiskLevel": score.salt_risk_level,
                "saturatedFatRiskLevel": score.saturated_fat_risk_level,
                    "ahUrl": f"https://www.ah.nl/producten/product/wi{score.product_id}",
            }
            for score, product in rows
        ],
    }


@router.get("/health-value")
def health_value_rankings(
    category: str | None = Query(None, description="Filter by main category"),
    min_health_score: float | None = Query(None, ge=0, le=100, description="Minimum health score"),
    rank_limit: int = Query(10, ge=1, le=100, description="Max rank to return per category"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    recompute: bool = Query(False, description="Recompute rankings before returning"),
):
    """Return health value rankings — healthy products ranked by affordability.

    Health value score combines health_score with price to find the best
    health-value products. Higher score = healthier AND cheaper.
    """
    session = get_session()
    if recompute:
        from ..intelligence import compute_health_value_rankings
        compute_health_value_rankings(session)
        session.commit()

    query = session.query(HealthValueRankingRow, ProductRow).join(
        ProductRow, ProductRow.webshop_id == HealthValueRankingRow.product_id
    )

    if category:
        query = query.filter(HealthValueRankingRow.main_category == category)
    if min_health_score is not None:
        query = query.filter(HealthValueRankingRow.health_score >= min_health_score)
    query = query.filter(HealthValueRankingRow.rank_in_category <= rank_limit)

    total = query.count()
    rows = (
        query.order_by(
            HealthValueRankingRow.main_category.asc(),
            HealthValueRankingRow.rank_in_category.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "rankings": [
            {
                "productId": hv.product_id,
                "productTitle": product.title,
                "brand": product.brand,
                "mainCategory": hv.main_category,
                "subCategory": hv.sub_category,
                "currentPrice": hv.current_price,
                "unitPrice": hv.unit_price,
                "healthScore": hv.health_score,
                "healthValueScore": hv.health_value_score,
                "proteinPerEuro": hv.protein_per_euro,
                "fiberPerEuro": hv.fiber_per_euro,
                "rankInCategory": hv.rank_in_category,
                "rankInSubcategory": hv.rank_in_subcategory,
                    "ahUrl": f"https://www.ah.nl/producten/product/wi{hv.product_id}",
            }
            for hv, product in rows
        ],
    }


@router.get("/promotion-frequency")
def promotion_frequency(
    min_bonus_freq: float | None = Query(None, ge=0, le=100, description="Minimum bonus frequency %"),
    min_avg_discount: float | None = Query(None, ge=0, le=100, description="Minimum avg discount %"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    recompute: bool = Query(False, description="Recompute before returning"),
):
    """Return promotion frequency analysis per product.

    Shows how often products go on bonus, average/max discounts,
    and latest bonus period dates.
    """
    session = get_session()
    if recompute:
        compute_promotion_frequency(session)
        session.commit()

    query = session.query(ProductPromotionFrequencyRow, ProductRow).outerjoin(
        ProductRow, ProductRow.webshop_id == ProductPromotionFrequencyRow.product_id
    )

    if min_bonus_freq is not None:
        query = query.filter(ProductPromotionFrequencyRow.bonus_frequency_pct >= min_bonus_freq)
    if min_avg_discount is not None:
        query = query.filter(
            ProductPromotionFrequencyRow.avg_discount_pct.isnot(None),
            ProductPromotionFrequencyRow.avg_discount_pct >= min_avg_discount,
        )

    total = query.count()
    rows = (
        query.order_by(ProductPromotionFrequencyRow.bonus_frequency_pct.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "products": [
            {
                "productId": freq.product_id,
                "productTitle": product.title if product else None,
                "brand": product.brand if product else None,
                "totalObservations": freq.total_observations,
                "bonusObservations": freq.bonus_observations,
                "bonusFrequencyPct": freq.bonus_frequency_pct,
                "avgDiscountPct": freq.avg_discount_pct,
                "maxDiscountPct": freq.max_discount_pct,
                "latestBonusStartDate": freq.latest_bonus_start_date,
                "latestBonusEndDate": freq.latest_bonus_end_date,
                    "ahUrl": f"https://www.ah.nl/producten/product/wi{freq.product_id}",
            }
            for freq, product in rows
        ],
    }


@router.get("/ingredient-flags")
def ingredient_flags(
    contains_added_sugar: bool | None = Query(None, description="Filter by added sugar"),
    contains_palm_oil: bool | None = Query(None, description="Filter by palm oil"),
    contains_sweeteners: bool | None = Query(None, description="Filter by sweeteners"),
    contains_preservatives: bool | None = Query(None, description="Filter by preservatives"),
    possible_vegan: bool | None = Query(None, description="Filter by possible vegan"),
    possible_vegetarian: bool | None = Query(None, description="Filter by possible vegetarian"),
    min_clean_label: float | None = Query(None, ge=0, le=100, description="Minimum clean label score"),
    max_ultra_processed: float | None = Query(None, ge=0, le=100, description="Maximum ultra-processed score"),
    food_only: bool = Query(False, description="Exclude non-food categories (cleaning, personal care, pet, household)"),
    category: str | None = Query(None, description="Filter by exact product category"),
    brand: str | None = Query(None, description="Filter by brand (case-insensitive partial match)"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    recompute: bool = Query(False, description="Recompute before returning"),
):
    """Return smart ingredient flags per product.

    Shows detected ingredients categories, clean label score,
    ultra-processed score, and vegan/vegetarian indicators.
    """
    session = get_session()
    if recompute:
        compute_ingredient_flags(session)
        session.commit()

    query = session.query(IngredientFlagRow, ProductRow).outerjoin(
        ProductRow, ProductRow.webshop_id == IngredientFlagRow.product_id
    )

    if contains_added_sugar is not None:
        query = query.filter(IngredientFlagRow.contains_added_sugar == contains_added_sugar)
    if contains_palm_oil is not None:
        query = query.filter(IngredientFlagRow.contains_palm_oil == contains_palm_oil)
    if contains_sweeteners is not None:
        query = query.filter(IngredientFlagRow.contains_sweeteners == contains_sweeteners)
    if contains_preservatives is not None:
        query = query.filter(IngredientFlagRow.contains_preservatives == contains_preservatives)
    if possible_vegan is not None:
        query = query.filter(IngredientFlagRow.possible_vegan == possible_vegan)
    if possible_vegetarian is not None:
        query = query.filter(IngredientFlagRow.possible_vegetarian == possible_vegetarian)
    if min_clean_label is not None:
        query = query.filter(IngredientFlagRow.clean_label_score >= min_clean_label)
    if max_ultra_processed is not None:
        query = query.filter(IngredientFlagRow.ultra_processed_score <= max_ultra_processed)
    if food_only:
        food_cats = [
            'Bier, wijn, aperitieven',
            'Soepen, sauzen, kruiden, olie',
            'Frisdrank, sappen, water',
            'Koek, snoep, chocolade',
            'Zuivel, eieren',
            'Borrel, chips, snacks',
            'Pasta, rijst, wereldkeuken',
            'Diepvries',
            'Koffie, thee',
            'Bakkerij',
            'Ontbijtgranen, beleg',
            'Kaas',
            'Groente, aardappelen',
            'Vleeswaren',
            'Vlees',
            'Vegetarisch, vegan en plantaardig',
            'Maaltijden, salades',
            'Vis',
            'Fruit, verse sappen',
            'Tussendoortjes',
            'Glutenvrij',
        ]
        query = query.filter(ProductRow.main_category.in_(food_cats))

    if category:
        query = query.filter(ProductRow.main_category == category)
    if brand:
        query = query.filter(ProductRow.brand.ilike(f'%{brand}%'))

    total = query.count()
    rows = (
        query.order_by(IngredientFlagRow.clean_label_score.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "products": [
            {
                "productId": flag.product_id,
                "productTitle": product.title if product else None,
                "brand": product.brand if product else None,
                "mainCategory": product.main_category if product else None,
                "ingredientCount": flag.ingredient_count,
                "containsAddedSugar": flag.contains_added_sugar,
                "containsPalmOil": flag.contains_palm_oil,
                "containsSweeteners": flag.contains_sweeteners,
                "containsPreservatives": flag.contains_preservatives,
                "containsEmulsifiers": flag.contains_emulsifiers,
                "containsColourants": flag.contains_colourants,
                "containsSeedOils": flag.contains_seed_oils,
                "containsCaffeine": flag.contains_caffeine,
                "possibleVegan": flag.possible_vegan,
                "possibleVegetarian": flag.possible_vegetarian,
                "cleanLabelScore": flag.clean_label_score,
                "ultraProcessedScore": flag.ultra_processed_score,
                    "ahUrl": f"https://www.ah.nl/producten/product/wi{flag.product_id}",
            }
            for flag, product in rows
        ],
    }


@router.get("/allergen-summary")
def allergen_summary(
    contains_gluten: bool | None = Query(None, description="Filter by gluten"),
    contains_milk: bool | None = Query(None, description="Filter by milk"),
    contains_nuts: bool | None = Query(None, description="Filter by nuts"),
    max_risk_score: float | None = Query(None, ge=0, le=100, description="Maximum allergen risk score"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    recompute: bool = Query(False, description="Recompute before returning"),
):
    """Return allergen summary per product.

    Shows detected allergens, CONTAINS vs MAY_CONTAIN counts,
    and allergen risk score.
    """
    session = get_session()
    if recompute:
        compute_allergen_summary(session)
        session.commit()

    query = session.query(AllergenSummaryRow, ProductRow).outerjoin(
        ProductRow, ProductRow.webshop_id == AllergenSummaryRow.product_id
    )

    if contains_gluten is not None:
        query = query.filter(AllergenSummaryRow.contains_gluten == contains_gluten)
    if contains_milk is not None:
        query = query.filter(AllergenSummaryRow.contains_milk == contains_milk)
    if contains_nuts is not None:
        query = query.filter(AllergenSummaryRow.contains_nuts == contains_nuts)
    if max_risk_score is not None:
        query = query.filter(AllergenSummaryRow.allergen_risk_score <= max_risk_score)

    total = query.count()
    rows = (
        query.order_by(AllergenSummaryRow.allergen_risk_score.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "products": [
            {
                "productId": allergen.product_id,
                "productTitle": product.title if product else None,
                "brand": product.brand if product else None,
                "containsGluten": allergen.contains_gluten,
                "containsMilk": allergen.contains_milk,
                "containsNuts": allergen.contains_nuts,
                "containsPeanuts": allergen.contains_peanuts,
                "containsSoy": allergen.contains_soy,
                "containsEgg": allergen.contains_egg,
                "containsFish": allergen.contains_fish,
                "containsShellfish": allergen.contains_shellfish,
                "mayContainCount": allergen.may_contain_count,
                "containsCount": allergen.contains_count,
                "allergenRiskScore": allergen.allergen_risk_score,
                    "ahUrl": f"https://www.ah.nl/producten/product/wi{allergen.product_id}",
            }
            for allergen, product in rows
        ],
    }


@router.get("/product-alternatives/{product_id}")
def product_alternatives(
    product_id: int,
    alternative_type: str | None = Query(
        None,
        pattern="^(cheaper_alternative|healthier_alternative|same_brand)$",
        description="Filter by alternative type",
    ),
    recompute: bool = Query(False, description="Recompute before returning"),
):
    """Return product alternatives for a specific product.

    Alternative types:
    - cheaper_alternative: Same category, lower price
    - healthier_alternative: Same category, higher health score
    - same_brand: Same brand, different product
    """
    session = get_session()
    if recompute:
        compute_product_alternatives(session)
        session.commit()

    query = session.query(ProductAlternativeRow).filter(
        ProductAlternativeRow.product_id == product_id
    )

    if alternative_type:
        query = query.filter(ProductAlternativeRow.alternative_type == alternative_type)

    rows = query.order_by(ProductAlternativeRow.confidence.desc()).all()

    # Get product details for each alternative
    alt_ids = [r.alternative_product_id for r in rows]
    alt_products = {p.webshop_id: p for p in session.query(ProductRow).filter(ProductRow.webshop_id.in_(alt_ids)).all()} if alt_ids else {}

    return {
        "productId": product_id,
        "total": len(rows),
        "alternatives": [
            {
                "alternativeProductId": alt.alternative_product_id,
                "alternativeTitle": alt_products.get(alt.alternative_product_id, {}).title if alt_products.get(alt.alternative_product_id) else None,
                "alternativeBrand": alt_products.get(alt.alternative_product_id, {}).brand if alt_products.get(alt.alternative_product_id) else None,
                "alternativeType": alt.alternative_type,
                "priceSavingPct": alt.price_saving_pct,
                "unitPriceSavingPct": alt.unit_price_saving_pct,
                "healthScoreDelta": alt.health_score_delta,
                "confidence": alt.confidence,
                "explanation": alt.explanation,
            }
            for alt in rows
        ],
    }


@router.get("/baskets")
def list_baskets():
    """List all basket definitions."""
    session = get_session()
    baskets = session.query(BasketDefinitionRow).all()

    return {
        "baskets": [
            {
                "basketId": b.basket_id,
                "basketName": b.basket_name,
                "description": b.description,
                "active": b.active,
                "createdAt": b.created_at.isoformat() if b.created_at else None,
            }
            for b in baskets
        ],
    }


@router.get("/basket-snapshots")
def basket_snapshots(
    basket_id: int | None = Query(None, description="Filter by basket ID"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    recompute: bool = Query(False, description="Recompute before returning"),
):
    """Return basket cost snapshots over time.

    Shows total current price, regular price, bonus savings,
    and item count for each basket snapshot.
    """
    session = get_session()
    if recompute:
        compute_basket_snapshots(session)
        session.commit()

    query = session.query(BasketSnapshotRow, BasketDefinitionRow).join(
        BasketDefinitionRow, BasketDefinitionRow.basket_id == BasketSnapshotRow.basket_id
    )

    if basket_id is not None:
        query = query.filter(BasketSnapshotRow.basket_id == basket_id)

    total = query.count()
    rows = (
        query.order_by(BasketSnapshotRow.snapshot_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "snapshots": [
            {
                "basketSnapshotId": snap.basket_snapshot_id,
                "basketId": snap.basket_id,
                "basketName": basket.basket_name,
                "snapshotDate": snap.snapshot_date,
                "totalCurrentPrice": snap.total_current_price,
                "totalRegularPrice": snap.total_regular_price,
                "bonusSavings": snap.bonus_savings,
                "itemCount": snap.item_count,
            }
            for snap, basket in rows
        ],
    }


@router.get("/brand-intelligence")
def brand_intelligence(
    min_avg_price: float | None = Query(None, ge=0, description="Minimum average price"),
    min_avg_health: float | None = Query(None, ge=0, le=100, description="Minimum avg health score"),
    private_label_only: bool | None = Query(None, description="Only private label candidates"),
    min_bonus_share: float | None = Query(None, ge=0, le=100, description="Minimum bonus share %"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    recompute: bool = Query(False, description="Recompute before returning"),
):
    """Return brand-level intelligence metrics.

    Shows product count, category count, average price/health,
    bonus share, avg discount, price volatility,
    and private label candidate flag.
    """
    session = get_session()
    if recompute:
        compute_brand_intelligence(session)
        session.commit()

    query = session.query(BrandIntelligenceRow)

    if min_avg_price is not None:
        query = query.filter(BrandIntelligenceRow.avg_price >= min_avg_price)
    if min_avg_health is not None:
        query = query.filter(BrandIntelligenceRow.avg_health_score >= min_avg_health)
    if private_label_only is not None:
        query = query.filter(BrandIntelligenceRow.private_label_candidate == private_label_only)
    if min_bonus_share is not None:
        query = query.filter(BrandIntelligenceRow.bonus_share_pct >= min_bonus_share)

    total = query.count()
    rows = (
        query.order_by(BrandIntelligenceRow.product_count.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "brands": [
            {
                "brand": b.brand,
                "productCount": b.product_count,
                "categoryCount": b.category_count,
                "avgPrice": b.avg_price,
                "avgUnitPrice": b.avg_unit_price,
                "avgHealthScore": b.avg_health_score,
                "bonusSharePct": b.bonus_share_pct,
                "avgDiscountPct": b.avg_discount_pct,
                "priceVolatility": b.price_volatility,
                "privateLabelCandidate": b.private_label_candidate,
            }
            for b in rows
        ],
    }


@router.get("/recompute")
def recompute_all():
    """Trigger a full recompute of all intelligence tables.

    Runs in dependency order:
    1. Deal quality scores
    2. Category price rankings
    3. Nutrition scores
    4. Health value rankings
    5. Promotion frequency
    6. Ingredient flags
    7. Allergen summary
    8. Product alternatives
    9. Basket snapshots
    10. Brand intelligence
    """
    session = get_session()
    result = compute_all_intelligence(session)
    session.commit()
    return {
        "status": "completed",
        **result,
    }
