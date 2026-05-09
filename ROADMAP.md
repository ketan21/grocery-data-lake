# Grocery Intelligence Data Lake Improvement Plan

## Current State

This project is a grocery intelligence data lake for Albert Heijn product data.

Current local database baseline:

- `products`: 1,043 rows
- `categories`: 28 rows
- `nutrition`: 8,650 rows
- `allergens`: 15,535 rows
- `ingredients`: 850 rows
- `images`: 5,190 rows
- `price_history`: 1 row (only 1 product tracked — scraping not recording prices properly)
- `scrape_runs`: 8 rows
- `raw_json`: 23+ rows
- Migrations: 4/5 applied (v5 pending — unit_prices + price_metrics tables)

## Phase 1: Stabilize Runtime — ✅ DONE

- [x] Install and verify project dependencies from `pyproject.toml`
- [x] Fix the missing SQLAlchemy `Index` import (was already fixed)
- [x] Quarantine stale async database/repository modules → moved to `stale/` with README
- [x] Remove obsolete CDP probe tests → moved to `stale/`
- [x] Replace stale tests with current smoke tests → 6 tests passing (`pytest -q`)
- [x] Verify CLI import works: `from grocery.cli import main` ✓
- [x] Verify API import works: `from grocery.api.app import create_app` ✓

## Phase 2: Fix Schema and Data Correctness — ✅ DONE

- [x] Additive SQLite migration path → `grocery/migrations.py` with 5 migrations, version tracker
- [x] `raw_json.sub_source` column added (migration v1, applied)
- [x] Extra product columns added (migration v2, applied)
- [x] Parse allergen containment level from `levelOfContainmentCode` → implemented in `db.py:386-394`
- [x] Prioritize `tradeItem.gtin` for barcode extraction → implemented in `db.py:448-451`
- [x] Fix bonus scrape run accounting → `bonus_scraper.py:127` uses `products_scraped` correctly
- [x] Raw bonus storage validated against `source`, `sub_source`, `scrape_run_id`, nullable `product_id`

## Phase 3: Make Scraping Repeatable — ✅ DONE

- [x] Retry/backoff handling around AH API calls → `client.py` with exponential backoff (1s, 2s, 4s...), max 3 retries, token refresh on 401
- [x] Retry stats tracked and reported in scrape run notes
- [x] Scrape-run failure notes with counts → `scraper.py:219-252` builds detailed notes with products/categories/retries
- [x] Price history dedupe policy → `record_price_snapshot` checks for existing product+run combo; migration v4 adds unique index
- [ ] Document safe scrape/enrichment commands in README (partially done — needs update)

## Phase 4: Add Grocery Intelligence Features — ⚠️ PARTIAL

Code exists but not fully wired up or populated:

- [x] Unit price normalization → `grocery/unit_price.py` with regex parser + unit aliases
- [x] Price metrics table schema → `price_metrics` table in migration v5 (cheapest, most expensive, avg, volatility)
- [x] Price metrics computation → `grocery/analytics.py` with `compute_price_metrics()`
- [x] Category-level inflation summaries → `grocery/category_analytics.py` with `compute_category_inflation()`
- [ ] Unit price enrichment CLI command (needs wiring)
- [ ] Price metrics computation CLI command (needs wiring)
- [ ] Category inflation CLI command (needs wiring)
- [ ] Bonus frequency and promotion-depth analytics per product/brand
- [ ] Query/API endpoints for derived metrics (unit prices, price metrics, category inflation)
- [ ] Run unit price normalization against existing products
- [ ] Run price metrics computation (blocked on price_history data — only 1 record)

## Phase 5: Operations — ❌ NOT STARTED

- [ ] Auto-run migrations on startup (migrations.py exists but not called automatically)
- [ ] Documented daily scheduling setup for full scrape or price-only scrape
- [ ] Backup guidance before scrape and enrichment runs
- [ ] Run health checks CLI command:
  - Last scrape status
  - Product count delta
  - Failed detail count
  - Raw JSON count
  - Latest price snapshot date
- [ ] Simple recovery workflow for interrupted scrapes

## Remaining Work (Priority Order)

### Immediate (unblocks everything else)
1. **Run migration v5** — create `unit_prices` and `price_metrics` tables
2. **Auto-run migrations** on CLI/API startup
3. **Fix price scraping** — scrape runs show 0 products scraped; price_history has only 1 record
4. **Wire up analytics CLI commands** — unit price, price metrics, category inflation

### Short-term
5. **Run a full scrape + enrich cycle** to build real price history data
6. **Add bonus analytics** — promotion frequency, depth per product/brand
7. **Add API endpoints** for derived metrics
8. **Health check CLI command**
9. **Cron job** for daily price snapshots

### Long-term
10. Multi-store comparison (Jumbo, etc.)
11. Receipt data (requires authenticated user tokens)

## Acceptance Criteria

- CLI and API imports succeed in a fresh environment after installing dependencies. ✅
- `pytest -q` collects and runs tests without stale import errors. ✅ (6 passed)
- Existing `data/grocery.db` remains readable and receives only additive migrations. ✅
- `grocery query stats` works against the existing database.
- FastAPI product, category, stats, price-history, and raw JSON endpoints work.
- Enrichment stores GTIN barcodes and correct allergen containment levels. ✅
- Bonus scraping records raw bonus JSON and updates scrape-run counts. ✅
- Price history has meaningful data from multiple scrape runs. ❌
- Analytics endpoints return computed metrics. ❌

## Assumptions

- The active implementation path is SQLAlchemy in `grocery/db.py`; the async `aiosqlite` path is stale (quarantined in `stale/`).
- `SKILL.md` and `references/data-lake-implementation.md` are the intended source of truth.
- Initial work prioritizes reliability and data correctness before adding new intelligence features.
