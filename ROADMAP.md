# Grocery Intelligence Data Lake Improvement Plan

## Current State

This project is intended to be a grocery intelligence data lake for Albert Heijn product data. It already has the main pieces in place:

- AH anonymous auth and a rate-limited HTTP client.
- Category-based product scraping via `taxonomyId`.
- Product enrichment from the detail endpoint for nutrition, allergens, ingredients, barcodes, and raw JSON.
- SQLite storage through the SQLAlchemy implementation in `grocery/db.py`.
- CLI commands for scraping, enrichment, querying, serving the API, and bonus scraping.
- FastAPI routes for products, categories, stats, price history, and raw JSON.

Current local database baseline:

- `products`: 1,043 rows
- `categories`: 28 rows
- `nutrition`: 8,650 rows
- `allergens`: 15,535 rows
- `ingredients`: 850 rows
- `images`: 5,190 rows
- `price_history`: 1 row
- `scrape_runs`: 2 rows
- `raw_json`: 23 rows

The Hermes skill documentation at `/home/ubuntu/.hermes/skills/nl-grocery-api-integration` describes this project as the working data lake. The current repo mostly follows that intended design, but implementation, schema, tests, and operational notes have drifted.

## Top Risks

- Runtime imports fail in the current environment because `sqlalchemy` is not installed.
- `grocery/db.py` uses `Index(...)` but does not import `Index` from SQLAlchemy.
- The existing `raw_json` table does not include the ORM's `sub_source` column. `Base.metadata.create_all()` will not add this column to an existing SQLite table.
- `grocery/database.py` and `grocery/repository.py` are stale async/aiosqlite code paths that reference removed config and model APIs.
- The test suite targets an older async implementation and currently fails during collection.
- `grocery/bonus_scraper.py` sets `run.scraped_products`, but the SQLAlchemy model field is `products_scraped`.
- Allergen enrichment currently defaults every allergen to `CONTAINS` instead of parsing `levelOfContainmentCode`.
- Barcode extraction should prioritize `tradeItem.gtin`.
- The skill docs mention a daily scrape cron job, but no user crontab is currently installed.

## Improvement Backlog

### Phase 1: Stabilize Runtime

- Install and verify project dependencies from `pyproject.toml`, including dev dependencies.
- Fix the missing SQLAlchemy `Index` import.
- Remove, quarantine, or clearly mark the stale async database/repository modules as obsolete.
- Remove or isolate the obsolete CDP probe tests that require `websockets`.
- Replace stale tests with current SQLAlchemy, CLI, API, and data parsing smoke tests.
- Verify these commands work:
  - `python3 -m grocery.cli --help`
  - `python3 -c 'from grocery.api.app import create_app; print(create_app().title)'`
  - `pytest -q`

### Phase 2: Fix Schema and Data Correctness

- Add an explicit additive SQLite migration path instead of relying on `create_all()` for schema upgrades.
- Start migrations by adding `raw_json.sub_source` when missing.
- Parse allergen containment level from `tradeItem.allergenInformation[].items[].levelOfContainmentCode`.
- Prioritize `tradeItem.gtin` for barcode extraction.
- Fix bonus scrape run accounting by writing `products_scraped`.
- Validate raw bonus storage against `source`, `sub_source`, `scrape_run_id`, and nullable `product_id`.

### Phase 3: Make Scraping Repeatable

- Document safe scrape and enrichment commands in a project README or operations note.
- Decide and enforce a smaller commit cadence for long scrapes to reduce data-loss risk.
- Add retry/backoff handling around AH API calls for transient 401, 429, 503, timeout, and JSON parse failures.
- Add scrape-run failure notes that include counts of failed pages, failed details, and skipped records.
- Add a dedupe policy for price history if daily runs create duplicate unchanged snapshots.

### Phase 4: Add Grocery Intelligence Features

- Normalize unit prices from `unit_price_description` for cross-product comparison.
- Add cheapest observed price and price change metrics per product.
- Add category-level inflation summaries.
- Add bonus frequency and promotion-depth analytics per product and brand.
- Add query/API endpoints for these derived metrics.
- Keep raw JSON as the audit source so parsers can be corrected and replayed later.

### Phase 5: Operations

- Add documented daily scheduling setup for full scrape or price-only scrape.
- Add backup guidance before scrape and enrichment runs.
- Add run health checks:
  - last scrape status
  - product count delta
  - failed detail count
  - raw JSON count
  - latest price snapshot date
- Add a simple recovery workflow for interrupted scrapes.

## Acceptance Criteria

- CLI and API imports succeed in a fresh environment after installing dependencies.
- `pytest -q` collects and runs tests for the current implementation without stale import errors.
- Existing `data/grocery.db` remains readable and receives only additive migrations.
- `grocery query stats` works against the existing database.
- FastAPI product, category, stats, price-history, and raw JSON endpoints work against the existing database.
- Enrichment stores GTIN barcodes and correct allergen containment levels.
- Bonus scraping records raw bonus JSON and updates scrape-run counts without attribute drift.
- The roadmap clearly separates reliability work from later analytics features.

## Assumptions

- The active implementation path is SQLAlchemy in `grocery/db.py`; the async `aiosqlite` path is stale.
- `SKILL.md` and `references/data-lake-implementation.md` are the intended source of truth for this project.
- The skill reference that says all AH REST endpoints return 404 is treated as stale or as a failed probing trace.
- Initial work should prioritize reliability and data correctness before adding new intelligence features.
