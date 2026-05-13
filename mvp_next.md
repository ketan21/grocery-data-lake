# MVP Next: Grocery Intelligence Features

## Objective

Turn the current grocery data lake into a higher-value Dutch grocery intelligence platform by adding price, promotion, nutrition, ingredient, allergen, basket, and product-substitution intelligence.

The core principle for this phase is:

> Keep original scrape tables immutable during analytics work. Build additive derived tables and dashboard serving tables that can be safely deleted and rebuilt.

## Existing Source Tables

Treat these as source/normalized data:

- `products`
- `price_history`
- `nutrition`
- `ingredients`
- `allergens`
- `images`
- `categories`
- `raw_json`
- `scrape_runs`

Do not overwrite these tables from analytics jobs except through the existing scrape/enrichment pipeline.

## Safe Post-Processing Strategy

All intelligence features should be implemented as deterministic post-processing:

```bash
grocery jobs rebuild-derived
```

The rebuild job should be extended to run:

1. Unit price normalization
2. Price metric computation
3. Category and subcategory rankings
4. Deal quality scoring
5. Nutrition scoring
6. Ingredient flagging
7. Allergen summary generation
8. Health value ranking
9. Brand intelligence
10. Product alternatives
11. Basket snapshots
12. Dashboard serving-table refresh

Derived tables should follow this convention:

```text
analytics_*      reusable derived data
dashboard_*      materialized API/dashboard serving data
```

Every derived row should include:

```text
computed_at
source_run_id or latest_scrape_run_id when applicable
```

## Feature Backlog

### 1. Cheapest By Category

Useful questions:

- What is the cheapest product in each category?
- What is the cheapest product in each subcategory?
- What is the cheapest product per unit in each category?
- Which category has the biggest price spread?
- Which category has the cheapest healthy option?

Suggested table:

```text
analytics_category_price_rankings
- id
- main_category
- sub_category
- ranking_type
- product_id
- product_title
- brand
- current_price
- unit_price
- base_unit
- rank
- product_count
- computed_at
```

Ranking types:

```text
cheapest_price
most_expensive_price
cheapest_unit_price
cheapest_healthy
best_deal
```

Implementation guidance:

- Use `COALESCE(current_price, price_before_bonus)` as effective price.
- Exclude products with null or non-positive prices.
- Use `unit_prices` for unit rankings.
- Compute rank per `main_category` and per `(main_category, sub_category)`.
- Store top N per group, not only rank 1, so the dashboard can show alternatives.

### 2. Deal Quality Score

Useful questions:

- Which current promotions are actually good deals?
- Which products are at a historical low?
- Which promotions are weak?
- Which products are cheaper than their average price?
- Which bonus products are not actually cheap compared with history?

Suggested table:

```text
analytics_deal_quality_scores
- product_id
- current_price
- price_before_bonus
- discount_pct
- avg_price
- historical_low_price
- current_vs_avg_pct
- current_vs_low_pct
- price_volatility
- deal_score
- deal_label
- computed_at
```

Labels:

```text
historical_low
excellent_deal
good_deal
normal_promotion
weak_promotion
not_a_deal
```

Implementation guidance:

- Join `products` to `price_metrics`.
- Calculate discount only where `is_bonus = true`, `price_before_bonus > 0`, and `current_price < price_before_bonus`.
- Score current price against average and historical low.
- Penalize high volatility so unstable products do not dominate.
- Keep scoring deterministic and documented in code.

### 3. Promotion Intelligence

Useful questions:

- Which categories have the highest bonus share?
- Which brands are most promotion-heavy?
- Which categories have the deepest discounts?
- Which products are frequently promoted?
- Which promotions are ending soon?

Existing useful table:

```text
dashboard_bonus_metrics
```

Suggested additional table:

```text
analytics_product_promotion_frequency
- product_id
- total_observations
- bonus_observations
- bonus_frequency_pct
- avg_discount_pct
- max_discount_pct
- latest_bonus_start_date
- latest_bonus_end_date
- computed_at
```

Implementation guidance:

- Use `price_history` for historical frequency.
- Use `products` for currently active promotions.
- Track promotion mechanism distribution separately if needed.
- Do not calculate discount depth from non-bonus rows.

### 4. Nutrition Intelligence

Useful questions:

- What are the healthiest products in each category?
- What are the cheapest healthy products?
- Which products are high protein per euro?
- Which products are lowest sugar per category?
- Which products are lowest salt per category?
- Which brands have the healthiest portfolio?

Suggested table:

```text
analytics_nutrition_scores
- product_id
- calories_per_100g
- sugar_per_100g
- salt_per_100g
- saturated_fat_per_100g
- protein_per_100g
- fiber_per_100g
- nutriscore
- health_score
- protein_per_euro
- fiber_per_euro
- sugar_risk_level
- salt_risk_level
- saturated_fat_risk_level
- computed_at
```

Implementation guidance:

- Normalize nutrition names from `nutrition.nutrient_name`.
- Prefer values with basis like `per 100g` or `per 100ml`.
- Start with a transparent rule-based score:
  - reward protein, fiber, Nutri-Score A/B
  - penalize sugar, salt, saturated fat, high calories
- Store intermediate nutrient values so the score is explainable.
- Add tests with a small temp DB containing known nutrient rows.

### 5. Smart Ingredient Flags

Useful questions:

- Which products contain palm oil?
- Which products contain added sugars?
- Which products contain sweeteners?
- Which products contain preservatives, emulsifiers, colourants, or seed oils?
- Which products have short ingredient lists?
- Which products are clean-label candidates?
- Which products are possible vegan or vegetarian candidates?

Suggested table:

```text
analytics_ingredient_flags
- product_id
- ingredient_count
- contains_added_sugar
- contains_palm_oil
- contains_sweeteners
- contains_preservatives
- contains_emulsifiers
- contains_colourants
- contains_seed_oils
- contains_caffeine
- possible_vegan
- possible_vegetarian
- clean_label_score
- ultra_processed_score
- matched_terms_json
- computed_at
```

Implementation guidance:

- Use a curated dictionary of Dutch and English ingredient terms.
- Start rule-based, not ML.
- Keep `matched_terms_json` for explainability.
- Do not claim certified vegan/vegetarian; use `possible_*` labels.
- Add filters to the dashboard for:
  - no added sugar
  - no palm oil
  - no sweeteners
  - clean label
  - ultra-processed candidate

### 6. Allergen Intelligence

Useful questions:

- Which products contain gluten, milk, nuts, peanuts, soy, egg, fish, or shellfish?
- Which products are only `MAY_CONTAIN` versus confirmed `CONTAINS`?
- What are the cheapest allergen-safe alternatives?
- Which categories are most allergen-heavy?

Suggested table:

```text
analytics_allergen_summary
- product_id
- contains_gluten
- contains_milk
- contains_nuts
- contains_peanuts
- contains_soy
- contains_egg
- contains_fish
- contains_shellfish
- may_contain_count
- contains_count
- allergen_risk_score
- computed_at
```

Implementation guidance:

- Normalize allergen names from the `allergens` table.
- Respect containment level.
- Keep separate boolean fields for `contains_*` and counts for `MAY_CONTAIN`.
- Dashboard should allow allergen-safe filtering inside categories.

### 7. Health Value Index

Useful questions:

- Which products are healthy and cheap?
- Which products offer the most protein per euro?
- Which categories have affordable healthy options?
- Which brands provide the best health value?

Suggested table:

```text
analytics_health_value_rankings
- product_id
- main_category
- sub_category
- current_price
- unit_price
- health_score
- health_value_score
- protein_per_euro
- fiber_per_euro
- rank_in_category
- rank_in_subcategory
- computed_at
```

Implementation guidance:

- Depends on `analytics_nutrition_scores` and `unit_prices`.
- Avoid ranking products with missing price or missing nutrition data.
- For dashboard UX, show the reason for ranking:
  - high protein
  - low sugar
  - low salt
  - good Nutri-Score
  - low price

### 8. Product Alternatives

Useful questions:

- What is a cheaper alternative to this product?
- What is a healthier alternative?
- What is a better unit-price alternative?
- Is there a private-label alternative?
- Is there a similar product with fewer risky ingredients?

Suggested table:

```text
analytics_product_alternatives
- product_id
- alternative_product_id
- alternative_type
- price_saving_pct
- unit_price_saving_pct
- health_score_delta
- confidence
- explanation
- computed_at
```

Alternative types:

```text
cheaper
healthier
better_unit_price
private_label
cleaner_ingredients
same_brand
same_category
```

Implementation guidance:

- Match within the same subcategory first.
- Use normalized title tokens, brand, package size, and unit type.
- Prefer same base unit for unit-price alternatives.
- Keep confidence scores conservative.
- Store explanation text for dashboard display.

### 9. Basket Intelligence

Useful questions:

- What does a standard Dutch weekly basket cost?
- How much did a basket change over time?
- How much do current promotions save?
- What is the cheapest healthy basket?
- Which substitutions reduce basket cost?

Suggested tables:

```text
basket_definitions
- basket_id
- basket_name
- description
- active
- created_at

basket_items
- basket_item_id
- basket_id
- main_category
- sub_category
- product_rule
- quantity
- preferred_product_id

basket_snapshots
- basket_snapshot_id
- basket_id
- snapshot_date
- total_current_price
- total_regular_price
- bonus_savings
- item_count
- computed_at
```

Implementation guidance:

- Start with curated basket definitions:
  - basic weekly basket
  - student basket
  - family basket
  - healthy basket
  - vegetarian basket
  - cleaning basket
- Resolve basket items deterministically using category rules and ranking tables.
- Store snapshots so basket cost trends can be charted.

### 10. Brand Intelligence

Useful questions:

- Which brands are cheapest?
- Which brands are healthiest?
- Which brands rely most on promotions?
- Which brands are most volatile?
- How does AH private label compare to A-brands?

Suggested table:

```text
analytics_brand_intelligence
- brand
- product_count
- category_count
- avg_price
- avg_unit_price
- avg_health_score
- bonus_share_pct
- avg_discount_pct
- price_volatility
- private_label_candidate
- computed_at
```

Implementation guidance:

- Build from `products`, `unit_prices`, `price_metrics`, `analytics_nutrition_scores`, and promotion metrics.
- Mark likely private label brands using a configurable list:
  - AH
  - AH Excellent
  - AH Biologisch
  - AH Terra
  - AH Basic if present

## Dashboard Enhancements

### Executive Overview

Cards:

- total products
- active bonus products
- average discount
- cheapest category
- healthiest value category
- most volatile category
- latest scrape status

### Cheapest By Category

Views:

- cheapest product
- cheapest per unit
- cheapest healthy product
- top 10 alternatives

### Best Deals

Views:

- best current deals
- historical lows
- weak deals to avoid
- ending soon promotions

### Health Explorer

Filters:

- Nutri-Score A/B
- low sugar
- low salt
- high protein
- high fiber
- clean label

### Ingredient And Allergen Explorer

Filters:

- no palm oil
- no added sugar
- no sweeteners
- no gluten
- no milk
- no nuts
- possible vegan
- possible vegetarian

### Basket Tracker

Views:

- basket cost trend
- bonus savings
- cheapest substitutions
- healthy basket cost

### Product Alternatives

For each product:

- cheaper alternative
- healthier alternative
- better unit price alternative
- cleaner ingredient alternative

## API Additions

Suggested endpoints:

```text
GET /api/intelligence/cheapest-by-category
GET /api/intelligence/deals
GET /api/intelligence/nutrition-scores
GET /api/intelligence/ingredient-flags
GET /api/intelligence/allergen-summary
GET /api/intelligence/health-value
GET /api/intelligence/product-alternatives/{product_id}
GET /api/intelligence/baskets
GET /api/intelligence/baskets/{basket_id}/snapshots
GET /api/intelligence/brands
```

Dashboard-serving versions can be materialized under:

```text
GET /api/analytics/serving/*
```

## Implementation Order

### Step 1: Category And Deal Intelligence

- Add `analytics_category_price_rankings`.
- Add `analytics_deal_quality_scores`.
- Add API endpoints for cheapest-by-category and deals.
- Add dashboard sections for Cheapest By Category and Best Deals.

### Step 2: Nutrition And Health Value

- Add nutrition normalization helper.
- Add `analytics_nutrition_scores`.
- Add `analytics_health_value_rankings`.
- Add Health Explorer dashboard filters.

### Step 3: Ingredients And Allergens

- Add ingredient term dictionaries.
- Add `analytics_ingredient_flags`.
- Add `analytics_allergen_summary`.
- Add Ingredient and Allergen Explorer dashboard sections.

### Step 4: Product Alternatives

- Add product similarity helpers.
- Add `analytics_product_alternatives`.
- Add product-detail alternative recommendations.

### Step 5: Basket Tracker

- Add basket definition tables.
- Add basket snapshot computation.
- Add basket dashboard views.

### Step 6: Brand Intelligence

- Add `analytics_brand_intelligence`.
- Add brand dashboard views and comparison tables.

## Safety Requirements

- All migrations must be additive.
- Original scrape tables must not be overwritten by analytics jobs.
- Every analytics table must be rebuildable.
- `grocery jobs daily-snapshot` must continue to create and restore backups on failure.
- New analytics jobs must be covered by temp-DB tests.
- Dashboard endpoints should read from serving tables when possible.

## Acceptance Criteria

- `pytest -q` passes.
- `grocery jobs rebuild-derived` rebuilds all derived tables.
- `grocery jobs daily-snapshot --skip-scrape` runs safely.
- Existing API endpoints continue to work.
- New intelligence endpoints return deterministic results from a temp DB.
- Dashboard renders enriched sections without requiring external data files.

