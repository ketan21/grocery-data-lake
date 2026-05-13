"""D3 visualization API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from grocery.database import get_db

router = APIRouter(prefix="/viz", tags=["visualization"])


def _round(value: float | int | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    """Return category breakdown with product count, price, bonus, and volatility."""
    rows = db.execute(
        text(
            """
            SELECT
                COALESCE(p.main_category, 'Uncategorized') AS category,
                COUNT(*) AS product_count,
                AVG(COALESCE(p.current_price, p.price_before_bonus)) AS avg_price,
                MIN(COALESCE(p.current_price, p.price_before_bonus)) AS min_price,
                MAX(COALESCE(p.current_price, p.price_before_bonus)) AS max_price,
                SUM(CASE WHEN p.is_bonus = 1 THEN 1 ELSE 0 END) AS bonus_count,
                AVG(
                    CASE
                        WHEN p.price_before_bonus IS NOT NULL
                            AND p.price_before_bonus > 0
                            AND p.current_price IS NOT NULL
                            AND p.current_price < p.price_before_bonus
                        THEN (p.price_before_bonus - p.current_price) * 100.0 / p.price_before_bonus
                    END
                ) AS avg_discount_pct,
                AVG(pm.price_volatility) AS volatility,
                AVG(pm.total_changes) AS avg_changes,
                AVG(dcm.avg_price_change_pct) AS avg_price_change_pct
            FROM products p
            LEFT JOIN price_metrics pm ON pm.product_id = p.webshop_id
            LEFT JOIN dashboard_category_metrics dcm
                ON dcm.category = COALESCE(p.main_category, 'Uncategorized')
            GROUP BY COALESCE(p.main_category, 'Uncategorized')
            ORDER BY product_count DESC, category ASC
            """
        )
    ).mappings()

    items = []
    for row in rows:
        product_count = int(row["product_count"] or 0)
        bonus_count = int(row["bonus_count"] or 0)
        items.append(
            {
                "category": row["category"],
                "productCount": product_count,
                "avgPrice": _round(row["avg_price"]),
                "minPrice": _round(row["min_price"]),
                "maxPrice": _round(row["max_price"]),
                "bonusCount": bonus_count,
                "bonusSharePct": _round(bonus_count * 100 / product_count if product_count else 0),
                "avgDiscountPct": _round(row["avg_discount_pct"]),
                "volatility": _round(row["volatility"], 4),
                "avgChanges": _round(row["avg_changes"]),
                "avgPriceChangePct": _round(row["avg_price_change_pct"]),
            }
        )

    return {"categories": items}


@router.get("/brands")
def brands(
    limit: int = Query(50, ge=1, le=250),
    db: Session = Depends(get_db),
):
    """Return top brands by product count."""
    rows = db.execute(
        text(
            """
            SELECT
                COALESCE(NULLIF(TRIM(brand), ''), 'Unknown') AS brand,
                COUNT(*) AS product_count,
                COUNT(DISTINCT COALESCE(main_category, 'Uncategorized')) AS category_count,
                AVG(COALESCE(current_price, price_before_bonus)) AS avg_price,
                SUM(CASE WHEN is_bonus = 1 THEN 1 ELSE 0 END) AS bonus_count
            FROM products
            GROUP BY COALESCE(NULLIF(TRIM(brand), ''), 'Unknown')
            ORDER BY product_count DESC, brand ASC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings()

    return {
        "brands": [
            {
                "brand": row["brand"],
                "productCount": int(row["product_count"] or 0),
                "categoryCount": int(row["category_count"] or 0),
                "avgPrice": _round(row["avg_price"]),
                "bonusCount": int(row["bonus_count"] or 0),
            }
            for row in rows
        ]
    }


@router.get("/price-distribution")
def price_distribution(db: Session = Depends(get_db)):
    """Return fixed price histogram buckets."""
    rows = db.execute(
        text(
            """
            SELECT
                CASE
                    WHEN COALESCE(current_price, price_before_bonus) < 5 THEN '0-5'
                    WHEN COALESCE(current_price, price_before_bonus) < 10 THEN '5-10'
                    WHEN COALESCE(current_price, price_before_bonus) < 20 THEN '10-20'
                    WHEN COALESCE(current_price, price_before_bonus) < 50 THEN '20-50'
                    WHEN COALESCE(current_price, price_before_bonus) < 100 THEN '50-100'
                    ELSE '100+'
                END AS bucket,
                CASE
                    WHEN COALESCE(current_price, price_before_bonus) < 5 THEN 1
                    WHEN COALESCE(current_price, price_before_bonus) < 10 THEN 2
                    WHEN COALESCE(current_price, price_before_bonus) < 20 THEN 3
                    WHEN COALESCE(current_price, price_before_bonus) < 50 THEN 4
                    WHEN COALESCE(current_price, price_before_bonus) < 100 THEN 5
                    ELSE 6
                END AS bucket_order,
                COUNT(*) AS product_count,
                AVG(COALESCE(current_price, price_before_bonus)) AS avg_price,
                SUM(CASE WHEN is_bonus = 1 THEN 1 ELSE 0 END) AS bonus_count
            FROM products
            WHERE COALESCE(current_price, price_before_bonus) IS NOT NULL
            GROUP BY bucket, bucket_order
            ORDER BY bucket_order
            """
        )
    ).mappings()

    return {
        "buckets": [
            {
                "bucket": row["bucket"],
                "productCount": int(row["product_count"] or 0),
                "avgPrice": _round(row["avg_price"]),
                "bonusCount": int(row["bonus_count"] or 0),
            }
            for row in rows
        ]
    }


@router.get("/price-timeline")
def price_timeline(db: Session = Depends(get_db)):
    """Return average price per category per scrape run."""
    rows = db.execute(
        text(
            """
            SELECT
                COALESCE(p.main_category, 'Uncategorized') AS category,
                ph.scrape_run_id AS run_id,
                sr.started_at AS scraped_at,
                AVG(COALESCE(ph.current_price, ph.price_before_bonus)) AS avg_price,
                COUNT(*) AS snapshot_count,
                AVG(CASE WHEN ph.is_bonus = 1 THEN COALESCE(ph.current_price, ph.price_before_bonus) END) AS avg_bonus_price
            FROM price_history ph
            JOIN products p ON p.webshop_id = ph.product_id
            LEFT JOIN scrape_runs sr ON sr.id = ph.scrape_run_id
            WHERE COALESCE(ph.current_price, ph.price_before_bonus) IS NOT NULL
            GROUP BY COALESCE(p.main_category, 'Uncategorized'), ph.scrape_run_id, sr.started_at
            ORDER BY sr.started_at ASC, ph.scrape_run_id ASC, category ASC
            """
        )
    ).mappings()

    points = [
        {
            "category": row["category"],
            "runId": row["run_id"],
            "scrapedAt": row["scraped_at"],
            "avgPrice": _round(row["avg_price"]),
            "avgBonusPrice": _round(row["avg_bonus_price"]),
            "snapshotCount": int(row["snapshot_count"] or 0),
        }
        for row in rows
    ]

    runs = sorted(
        {
            (point["runId"], point["scrapedAt"])
            for point in points
            if point["runId"] is not None
        },
        key=lambda item: (item[1] or "", item[0]),
    )

    return {
        "points": points,
        "categories": sorted({point["category"] for point in points}),
        "runs": [{"runId": run_id, "scrapedAt": scraped_at} for run_id, scraped_at in runs],
    }


@router.get("/price-changes")
def price_changes(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Return latest product price movements with shelf and bonus context."""
    rows = db.execute(
        text(
            """
            WITH ranked AS (
                SELECT
                    ph.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY ph.product_id
                        ORDER BY COALESCE(ph.scrape_run_id, 0) DESC, ph.recorded_at DESC, ph.id DESC
                    ) AS rn,
                    LEAD(COALESCE(ph.current_price, ph.price_before_bonus)) OVER (
                        PARTITION BY ph.product_id
                        ORDER BY COALESCE(ph.scrape_run_id, 0) DESC, ph.recorded_at DESC, ph.id DESC
                    ) AS previous_effective_price,
                    LEAD(ph.price_before_bonus) OVER (
                        PARTITION BY ph.product_id
                        ORDER BY COALESCE(ph.scrape_run_id, 0) DESC, ph.recorded_at DESC, ph.id DESC
                    ) AS previous_shelf_price,
                    LEAD(ph.is_bonus) OVER (
                        PARTITION BY ph.product_id
                        ORDER BY COALESCE(ph.scrape_run_id, 0) DESC, ph.recorded_at DESC, ph.id DESC
                    ) AS previous_is_bonus
                FROM price_history ph
                WHERE COALESCE(ph.current_price, ph.price_before_bonus) IS NOT NULL
            )
            SELECT
                r.product_id,
                p.title,
                p.brand,
                COALESCE(p.main_category, 'Uncategorized') AS category,
                COALESCE(r.current_price, r.price_before_bonus) AS effective_price,
                r.previous_effective_price,
                r.price_before_bonus AS shelf_price,
                r.previous_shelf_price,
                r.is_bonus,
                r.previous_is_bonus,
                r.bonus_mechanism,
                r.recorded_at,
                r.scrape_run_id,
                (COALESCE(r.current_price, r.price_before_bonus) - r.previous_effective_price) AS price_change,
                CASE
                    WHEN r.previous_effective_price > 0
                    THEN (COALESCE(r.current_price, r.price_before_bonus) - r.previous_effective_price) * 100.0 / r.previous_effective_price
                END AS price_change_pct,
                CASE
                    WHEN r.previous_shelf_price > 0
                        AND r.price_before_bonus IS NOT NULL
                    THEN (r.price_before_bonus - r.previous_shelf_price) * 100.0 / r.previous_shelf_price
                END AS shelf_change_pct
            FROM ranked r
            JOIN products p ON p.webshop_id = r.product_id
            WHERE r.rn = 1
                AND r.previous_effective_price IS NOT NULL
                AND ABS(COALESCE(r.current_price, r.price_before_bonus) - r.previous_effective_price) > 0.0001
            ORDER BY ABS(price_change_pct) DESC, r.recorded_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings()

    return {
        "changes": [
            {
                "productId": row["product_id"],
                "name": row["title"],
                "brand": row["brand"],
                "category": row["category"],
                "effectivePrice": _round(row["effective_price"]),
                "previousPrice": _round(row["previous_effective_price"]),
                "shelfPrice": _round(row["shelf_price"]),
                "previousShelfPrice": _round(row["previous_shelf_price"]),
                "priceChange": _round(row["price_change"]),
                "priceChangePct": _round(row["price_change_pct"]),
                "shelfChangePct": _round(row["shelf_change_pct"]),
                "isBonus": bool(row["is_bonus"]),
                "previousIsBonus": bool(row["previous_is_bonus"]),
                "bonusMechanism": row["bonus_mechanism"],
                "recordedAt": row["recorded_at"],
                "runId": row["scrape_run_id"],
            }
            for row in rows
        ]
    }


@router.get("/unit-prices")
def unit_prices(
    unit: str = Query("g", pattern="^(g|ml)$"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Return cheapest products per normalized unit."""
    rows = db.execute(
        text(
            """
            SELECT
                p.webshop_id,
                p.title,
                p.brand,
                COALESCE(p.main_category, 'Uncategorized') AS category,
                COALESCE(p.current_price, p.price_before_bonus) AS effective_price,
                up.normalized_price_eur_per_unit,
                up.base_unit,
                up.original_description,
                p.image_url
            FROM unit_prices up
            JOIN products p ON p.webshop_id = up.product_id
            WHERE up.base_unit = :unit
                AND up.normalized_price_eur_per_unit IS NOT NULL
            ORDER BY up.normalized_price_eur_per_unit ASC, p.title ASC
            LIMIT :limit
            """
        ),
        {"unit": unit, "limit": limit},
    ).mappings()

    return {
        "unit": unit,
        "products": [
            {
                "productId": row["webshop_id"],
                "name": row["title"],
                "brand": row["brand"],
                "category": row["category"],
                "effectivePrice": _round(row["effective_price"]),
                "unitPrice": _round(row["normalized_price_eur_per_unit"], 4),
                "baseUnit": row["base_unit"],
                "description": row["original_description"],
                "imageUrl": row["image_url"],
            }
            for row in rows
        ],
    }


@router.get("/bonus-overview")
def bonus_overview(db: Session = Depends(get_db)):
    """Return promotion stats by category and the deepest current deals."""
    category_rows = db.execute(
        text(
            """
            SELECT
                COALESCE(main_category, 'Uncategorized') AS category,
                COUNT(*) AS product_count,
                SUM(CASE WHEN is_bonus = 1 THEN 1 ELSE 0 END) AS bonus_count,
                AVG(
                    CASE
                        WHEN is_bonus = 1
                            AND price_before_bonus IS NOT NULL
                            AND price_before_bonus > 0
                            AND current_price IS NOT NULL
                        THEN (price_before_bonus - current_price) * 100.0 / price_before_bonus
                    END
                ) AS avg_discount_pct,
                MAX(
                    CASE
                        WHEN is_bonus = 1
                            AND price_before_bonus IS NOT NULL
                            AND price_before_bonus > 0
                            AND current_price IS NOT NULL
                        THEN (price_before_bonus - current_price) * 100.0 / price_before_bonus
                    END
                ) AS max_discount_pct
            FROM products
            GROUP BY COALESCE(main_category, 'Uncategorized')
            ORDER BY bonus_count DESC, product_count DESC
            """
        )
    ).mappings()

    deal_rows = db.execute(
        text(
            """
            SELECT
                webshop_id,
                title,
                brand,
                COALESCE(main_category, 'Uncategorized') AS category,
                current_price,
                price_before_bonus,
                bonus_mechanism,
                (price_before_bonus - current_price) * 100.0 / price_before_bonus AS discount_pct
            FROM products
            WHERE is_bonus = 1
                AND price_before_bonus IS NOT NULL
                AND price_before_bonus > 0
                AND current_price IS NOT NULL
                AND current_price < price_before_bonus
            ORDER BY discount_pct DESC, title ASC
            LIMIT 50
            """
        )
    ).mappings()

    categories = []
    for row in category_rows:
        product_count = int(row["product_count"] or 0)
        bonus_count = int(row["bonus_count"] or 0)
        categories.append(
            {
                "category": row["category"],
                "productCount": product_count,
                "bonusCount": bonus_count,
                "bonusSharePct": _round(bonus_count * 100 / product_count if product_count else 0),
                "avgDiscountPct": _round(row["avg_discount_pct"]),
                "maxDiscountPct": _round(row["max_discount_pct"]),
            }
        )

    return {
        "categories": categories,
        "topDeals": [
            {
                "productId": row["webshop_id"],
                "name": row["title"],
                "brand": row["brand"],
                "category": row["category"],
                "currentPrice": _round(row["current_price"]),
                "shelfPrice": _round(row["price_before_bonus"]),
                "discountPct": _round(row["discount_pct"]),
                "bonusMechanism": row["bonus_mechanism"],
            }
            for row in deal_rows
        ],
    }


@router.get("/volatility")
def volatility(db: Session = Depends(get_db)):
    """Return price instability by category plus volatile product examples."""
    category_rows = db.execute(
        text(
            """
            SELECT
                COALESCE(p.main_category, 'Uncategorized') AS category,
                COUNT(pm.product_id) AS tracked_products,
                AVG(pm.avg_price) AS avg_price,
                AVG(pm.price_volatility) AS avg_volatility,
                MAX(pm.price_volatility) AS max_volatility,
                AVG(pm.total_changes) AS avg_changes,
                SUM(pm.total_changes) AS total_changes
            FROM products p
            JOIN price_metrics pm ON pm.product_id = p.webshop_id
            GROUP BY COALESCE(p.main_category, 'Uncategorized')
            ORDER BY avg_volatility DESC, tracked_products DESC
            """
        )
    ).mappings()

    product_rows = db.execute(
        text(
            """
            SELECT
                p.webshop_id,
                p.title,
                p.brand,
                COALESCE(p.main_category, 'Uncategorized') AS category,
                p.current_price,
                pm.avg_price,
                pm.price_volatility,
                pm.total_changes,
                pm.cheapest_price,
                pm.most_expensive_price
            FROM price_metrics pm
            JOIN products p ON p.webshop_id = pm.product_id
            WHERE pm.price_volatility IS NOT NULL
            ORDER BY pm.price_volatility DESC, pm.total_changes DESC
            LIMIT 250
            """
        )
    ).mappings()

    return {
        "categories": [
            {
                "category": row["category"],
                "trackedProducts": int(row["tracked_products"] or 0),
                "avgPrice": _round(row["avg_price"]),
                "avgVolatility": _round(row["avg_volatility"], 4),
                "maxVolatility": _round(row["max_volatility"], 4),
                "avgChanges": _round(row["avg_changes"]),
                "totalChanges": int(row["total_changes"] or 0),
            }
            for row in category_rows
        ],
        "products": [
            {
                "productId": row["webshop_id"],
                "name": row["title"],
                "brand": row["brand"],
                "category": row["category"],
                "currentPrice": _round(row["current_price"]),
                "avgPrice": _round(row["avg_price"]),
                "volatility": _round(row["price_volatility"], 4),
                "totalChanges": int(row["total_changes"] or 0),
                "cheapestPrice": _round(row["cheapest_price"]),
                "mostExpensivePrice": _round(row["most_expensive_price"]),
            }
            for row in product_rows
        ],
    }


@router.get("/search")
def search(
    q: str = Query("", max_length=120),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return product search results with compact price-history metadata."""
    like = f"%{q.strip()}%"
    rows = db.execute(
        text(
            """
            SELECT
                p.webshop_id,
                p.title,
                p.brand,
                COALESCE(p.main_category, 'Uncategorized') AS category,
                p.sub_category,
                p.current_price,
                p.price_before_bonus,
                p.is_bonus,
                p.bonus_mechanism,
                p.unit_price_description,
                p.image_url,
                COUNT(ph.id) AS snapshot_count,
                MIN(ph.current_price) AS min_price,
                MAX(ph.current_price) AS max_price,
                AVG(ph.current_price) AS avg_price
            FROM products p
            LEFT JOIN price_history ph ON ph.product_id = p.webshop_id
            WHERE :q = ''
                OR p.title LIKE :like
                OR p.brand LIKE :like
                OR p.main_category LIKE :like
                OR p.sub_category LIKE :like
            GROUP BY p.webshop_id
            ORDER BY
                CASE WHEN p.title LIKE :like THEN 0 ELSE 1 END,
                p.title ASC
            LIMIT :limit
            """
        ),
        {"q": q.strip(), "like": like, "limit": limit},
    ).mappings()

    return {
        "query": q,
        "products": [
            {
                "productId": row["webshop_id"],
                "name": row["title"],
                "brand": row["brand"],
                "category": row["category"],
                "subCategory": row["sub_category"],
                "currentPrice": _round(row["current_price"]),
                "shelfPrice": _round(row["price_before_bonus"]),
                "isBonus": bool(row["is_bonus"]),
                "bonusMechanism": row["bonus_mechanism"],
                "unitPriceDescription": row["unit_price_description"],
                "imageUrl": row["image_url"],
                "snapshotCount": int(row["snapshot_count"] or 0),
                "minPrice": _round(row["min_price"]),
                "maxPrice": _round(row["max_price"]),
                "avgPrice": _round(row["avg_price"]),
            }
            for row in rows
        ],
    }
