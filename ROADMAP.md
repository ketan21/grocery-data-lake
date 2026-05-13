# Grocery Intelligence Data Lake Roadmap

## Current State

This project is a grocery intelligence data lake for Albert Heijn product data.

Current local database baseline:

- `products`: 27,718 rows
- `categories`: 28 rows
- `nutrition`: 8,650 rows
- `allergens`: 15,535 rows
- `ingredients`: 850 rows
- `images`: 138,030 rows
- `price_history`: 51,338 rows across 4 scrape runs
- `price_metrics`: 7,824 rows
- `unit_prices`: 16,988 rows
- `dashboard_category_metrics`: 23 rows
- `dashboard_brand_metrics`: 512 rows
- `dashboard_bonus_metrics`: 29,651 rows
- `scrape_runs`: 11 rows
- `raw_json`: 65,089 rows
- Migrations: 6/6 applied

## Phase 1: Stabilize Runtime - DONE

- [x] Install and verify project dependencies from `pyproject.toml`
- [x] Fix SQLAlchemy runtime imports
- [x] Quarantine stale async database/repository modules in `stale/`
- [x] Remove obsolete CDP probe tests
- [x] Replace stale tests with current smoke tests
- [x] Verify CLI import works: `from grocery.cli import main`
- [x] Verify API import works: `from grocery.api.app import create_app`

## Phase 2: Fix Schema and Data Correctness - DONE

- [x] Additive SQLite migration path in `grocery/migrations.py`
- [x] `raw_json.sub_source` column added
- [x] Extra product detail columns added
- [x] Allergen containment level parsing implemented
- [x] Barcode extraction prioritizes `tradeItem.gtin`
- [x] Bonus scrape run accounting fixed
- [x] Raw bonus storage includes `source`, `sub_source`, `scrape_run_id`, nullable `product_id`
- [x] Unit price and price metrics schema applied

## Phase 3: Make Scraping Repeatable - DONE

- [x] Retry/backoff handling around AH API calls
- [x] Retry stats tracked and reported in scrape run notes
- [x] Scrape-run failure notes include product/category/retry counts
- [x] Price history dedupe policy via product/run unique index
- [x] Safe scrape and enrichment commands documented in README
- [x] Price history contains meaningful data from multiple scrape runs

## Phase 4: Grocery Intelligence Features - DONE

- [x] Unit price normalization parser supports AH formats such as `EUR2,50/100g` and `prijs per kg EUR1.16`
- [x] Unit price enrichment CLI command: `grocery query normalize-unit-prices`
- [x] Cheapest unit price CLI query: `grocery query cheapest-unit`
- [x] Price metrics computation CLI command: `grocery query compute-price-metrics`
- [x] Cheapest observed prices CLI query: `grocery query cheapest-prices`
- [x] Category inflation CLI command: `grocery query category-inflation`
- [x] Brand inflation CLI command: `grocery query brand-inflation`
- [x] Bonus frequency and promotion-depth analytics CLI command: `grocery query bonus-analytics`
- [x] API endpoints for derived metrics:
  - `/api/analytics/price-metrics`
  - `/api/analytics/unit-prices`
  - `/api/analytics/category-inflation`
- `/api/analytics/brand-inflation`
- `/api/analytics/bonus`
- `/api/analytics/serving/category-metrics`
- `/api/analytics/serving/brand-metrics`
- `/api/analytics/serving/bonus-metrics`
- [x] Unit price normalization run against existing products
- [x] Price metrics computation run against existing price history
- [x] Materialized dashboard serving tables defined for category, brand, and bonus metrics

## Phase 5: Operations - DONE

- [x] Auto-run migrations on CLI/API startup through `init_db()`
- [x] Daily scheduling example documented
- [x] Backup guidance before scrape and enrichment runs documented
- [x] Health check CLI command: `grocery query health`
- [x] Derived rebuild job: `grocery jobs rebuild-derived`
- [x] Safe daily orchestration job: `grocery jobs daily-snapshot`
- [x] Daily job creates a pre-run database backup and restores it automatically on scrape/quality-check failure
- [x] Recovery workflow for interrupted scrapes documented

## Acceptance Criteria

- [x] CLI and API imports succeed in a fresh environment after installing dependencies
- [x] `pytest -q` collects and runs tests without stale import errors
- [x] Existing `data/grocery.db` remains readable and receives only additive migrations
- [x] `grocery query stats` works against the existing database
- [x] FastAPI product, category, stats, price-history, raw JSON, bonus, and analytics endpoints work
- [x] Enrichment stores GTIN barcodes and correct allergen containment levels
- [x] Bonus scraping records raw bonus JSON and updates scrape-run counts
- [x] Price history has meaningful data from multiple scrape runs
- [x] Analytics endpoints return computed metrics
- [x] Unit price normalization is populated from existing product data
- [x] Health check command reports last scrape status, product-count delta, raw JSON counts, and latest price snapshot date

## Verified Checks

- `pytest -q` -> 15 passed
- `grocery query stats` -> works
- `grocery query price-history` -> works
- `grocery query cheapest-unit g --limit 3` -> works
- `grocery query bonus-analytics --limit 3` -> works
- `grocery query health` -> works
- `grocery jobs rebuild-derived` -> rebuilds deterministic derived and serving tables
- `grocery jobs daily-snapshot --skip-scrape` -> rebuilds serving tables and runs health checks without network scrape
- FastAPI TestClient checks pass for analytics endpoints

## Long-Term Extensions

- Multi-store comparison with Jumbo, PLUS, Lidl, Dirk, Picnic, and Aldi
- Receipt/order ingestion for personalized basket intelligence
- Historical promotion calendar and campaign recurrence modeling
- Alerting for price drops, bonus starts/ends, and new historical lows
- Frontend intelligence dashboard for brands, categories, baskets, and inflation

## Senior Data Engineering Recommendations

These findings guide the next phase from prototype toward a reliable grocery intelligence platform.

- Treat `data/grocery.db` as local runtime state, not as product source of truth. Raw scrape payloads plus deterministic transformations should be enough to rebuild derived tables.
- Keep raw, normalized, derived, and serving layers conceptually separate:
  - Raw: `raw_json`, scrape metadata
  - Normalized: `products`, `categories`, `nutrition`, `allergens`, `images`
  - Derived: `price_history`, `unit_prices`, `price_metrics`
  - Serving: category/brand inflation, bonus analytics, basket indexes, deal scores
- Make all transformation jobs idempotent and safe to rerun.
- Keep analytics semantics precise. Promotion depth must be computed only from active bonus products with valid current and pre-bonus prices.
- Run data quality checks after scrape and enrichment jobs: product/category counts, negative prices, impossible discounts, raw JSON volume, latest completed scrape, and latest price snapshot.
- Keep API handlers thin. Shared service modules should power both CLI and API behavior.
- Add an explicit operational job layer for rebuilds and daily snapshots.
- Prepare the schema for multi-retailer support before adding Jumbo, Picnic, Lidl, Dirk, PLUS, or Aldi.

## Near-Term Engineering Priorities

- [x] Fix bonus analytics semantics so discount depth excludes non-bonus products.
- [x] Add shared `grocery.bonus_analytics` service used by CLI and API.
- [x] Add shared `grocery.health` service with reusable health and data quality checks.
- [x] Add temp-DB tests for unit price parsing, analytics endpoints, bonus semantics, health checks, and CLI registration.
- [x] Fix `init_db()` migration path so tests using monkeypatched `DB_PATH` stay isolated.
- [x] Add operational job command: `grocery jobs rebuild-derived`.
- [x] Add persistent serving tables for dashboard-ready bonus/category/brand metrics.
- [x] Add a full daily job command that runs scrape, rebuild-derived, health checks, and emits a single summary.
- [x] Add multi-retailer schema design notes before expanding beyond Albert Heijn.

## Multi-Retailer Schema Direction

Before adding another retailer, introduce retailer-aware identity and taxonomy concepts so AH-specific assumptions do not leak into the platform.

- `retailers`: stable retailer metadata such as `id`, `name`, `country`, `currency`, `base_url`, and active status.
- `retailer_products`: retailer-scoped product identifiers, including `retailer_id`, `retailer_product_id`, title, brand, package size, availability, and current retailer taxonomy references.
- `canonical_products`: cross-retailer product identity keyed by GTIN/barcode where possible, with fallback matching by normalized brand, title, and package size.
- `product_matches`: mapping between `retailer_products` and `canonical_products`, including match method, confidence, and reviewed status.
- `retailer_categories`: raw retailer category taxonomies, preserving source hierarchy.
- `canonical_categories`: normalized grocery taxonomy used for cross-retailer analytics.
- `price_observations`: retailer-scoped time-series prices with promotion state, scrape run, and observed timestamp.
- `promotion_observations`: retailer-scoped promotion windows, mechanism, discount depth, and source payload linkage.
- `retailer_raw_json`: source payload storage partitioned by retailer/source/run for replay and auditing.

Migration strategy:

- Keep the current AH tables as the local AH implementation path until multi-retailer ingestion exists.
- Add new retailer-aware tables additively rather than rewriting the current schema in place.
- Backfill AH data into retailer-aware tables with `retailer_id='ah'` once a second retailer is ready.
- Keep dashboard serving tables sourced from canonical retailer-aware tables after backfill.
