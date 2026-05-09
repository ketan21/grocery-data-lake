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
- `scrape_runs`: 11 rows
- `raw_json`: 65,089 rows
- Migrations: 5/5 applied

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
- [x] Unit price normalization run against existing products
- [x] Price metrics computation run against existing price history

## Phase 5: Operations - DONE

- [x] Auto-run migrations on CLI/API startup through `init_db()`
- [x] Daily scheduling example documented
- [x] Backup guidance before scrape and enrichment runs documented
- [x] Health check CLI command: `grocery query health`
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

- `pytest -q` -> 9 passed
- `grocery query stats` -> works
- `grocery query price-history` -> works
- `grocery query cheapest-unit g --limit 3` -> works
- `grocery query bonus-analytics --limit 3` -> works
- `grocery query health` -> works
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
- [ ] Add persistent serving tables for dashboard-ready bonus/category/brand metrics.
- [ ] Add a full daily job command that runs scrape, rebuild-derived, health checks, and emits a single summary.
- [ ] Add multi-retailer schema design notes before expanding beyond Albert Heijn.
