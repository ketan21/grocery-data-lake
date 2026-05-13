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
    CategoryPriceRankingRow,
    DealQualityScoreRow,
    HealthValueRankingRow,
    NutritionScoreRow,
    ProductRow,
    get_session,
)
from ..intelligence import compute_all_intelligence

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


@router.get("/cheapest-by-category")
def cheapest_by_category(
    ranking_type: str = Query(
        "cheapest_price",
        pattern="^(cheapest_price|most_expensive_price|cheapest_unit_price|cheapest_healthy|best_deal)$",
        description="Ranking type",
    ),
    category: str | None = Query(None, description="Filter by main category"),
    rank_limit: int = Query(5, ge=1, le=50, description="Max rank to return per group"),
):
    """Return product rankings within categories.

    Ranking types:
    - cheapest_price: Lowest current price
    - most_expensive_price: Highest current price
    - cheapest_unit_price: Lowest price per unit
    - cheapest_healthy: Cheapest with Nutri-Score A/B
    - best_deal: Biggest discount percentage
    """
    session = get_session()
    query = (
        session.query(CategoryPriceRankingRow)
        .filter(CategoryPriceRankingRow.ranking_type == ranking_type)
        .filter(CategoryPriceRankingRow.rank <= rank_limit)
    )
    if category:
        query = query.filter(CategoryPriceRankingRow.main_category == category)

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
            }
            for score, product in rows
        ],
    }


@router.get("/nutrition-scores")
def nutrition_scores(
    min_health_score: float | None = Query(None, ge=0, le=100, description="Minimum health score"),
    nutriscore: str | None = Query(None, description="Filter by Nutri-Score (A/B/C/D/E)"),
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
        query = query.filter(
            NutritionScoreRow.nutriscore == nutriscore.upper()
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
            }
            for hv, product in rows
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
    """
    session = get_session()
    result = compute_all_intelligence(session)
    session.commit()
    return {
        "status": "completed",
        **result,
    }
