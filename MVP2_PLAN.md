# MVP 2: Multi-Retailer Expansion (Jumbo + Dirk)

## Overview

Expand the Grocery Data Lake from Albert Heijn-only to a multi-retailer platform supporting Jumbo and Dirk van den Broek. This enables cross-retailer price comparison, deal aggregation, and unified grocery intelligence.

## Current State (MVP 1 — Complete)

- **27,718 AH products** across 28 categories
- Full scrape/enrich pipeline with retry/backoff
- Price history tracking across 11 scrape runs (51,338 snapshots)
- Unit price normalization, price metrics, category/brand inflation
- Bonus/promotion analytics
- FastAPI serving layer with analytics endpoints
- Daily orchestration job with backup/restore
- 15 passing tests

## Target State (MVP 2)

| Retailer | API Type | Auth | Status |
|----------|----------|------|--------|
| Albert Heijn | REST | OAuth2 token | ✅ Done (MVP 1) |
| Jumbo | GraphQL | Browser cookies | 🚧 MVP 2 |
| Dirk van den Broek | REST | API key headers | 🚧 MVP 2 |

## Phase 1: Schema Migration — Retailer-Aware Tables

**Goal:** Introduce retailer-aware tables additively without breaking existing AH tables.

### New Tables

- **`retailers`** — Stable retailer metadata
  - `id` (TEXT PK) — e.g. 'ah', 'jumbo', 'dirk'
  - `name` (TEXT) — Display name
  - `country` (TEXT) — 'NL'
  - `currency` (TEXT) — 'EUR'
  - `base_url` (TEXT) — API base URL
  - `api_type` (TEXT) — 'rest' | 'graphql'
  - `active` (BOOLEAN) — Is this retailer being scraped?

- **`retailer_products`** — Retailer-scoped product catalog
  - `id` (INTEGER PK)
  - `retailer_id` (TEXT FK → retailers.id)
  - `retailer_product_id` (TEXT) — e.g. webshop_id, SKU, productId
  - `title` (TEXT) — Product name
  - `brand` (TEXT)
  - `package_size` (TEXT)
  - `main_category` (TEXT) — Retailer's top-level category
  - `sub_category` (TEXT)
  - `gtin` (TEXT) — Barcode (if available)
  - `image_url` (TEXT)
  - `available` (BOOLEAN)
  - UNIQUE (retailer_id, retailer_product_id)

- **`retailer_categories`** — Raw retailer category taxonomies
  - `id` (INTEGER PK)
  - `retailer_id` (TEXT FK → retailers.id)
  - `category_id` (TEXT) — Retailer's category ID
  - `name` (TEXT)
  - `parent_category_id` (TEXT) — For hierarchy
  - `level` (INTEGER) — 1=top, 2=sub, 3=leaf

- **`canonical_products`** — Cross-retailer product identity
  - `id` (INTEGER PK)
  - `gtin` (TEXT UNIQUE) — Primary key for matching
  - `normalized_title` (TEXT) — Lowercased, stripped
  - `normalized_brand` (TEXT)
  - `package_size` (TEXT)

- **`product_matches`** — Mapping retailer → canonical
  - `id` (INTEGER PK)
  - `retailer_product_id` (INTEGER FK → retailer_products.id)
  - `canonical_product_id` (INTEGER FK → canonical_products.id)
  - `match_method` (TEXT) — 'gtin' | 'fuzzy' | 'manual'
  - `confidence` (REAL) — 0.0–1.0
  - `reviewed` (BOOLEAN)

- **`price_observations`** — Unified price time series
  - `id` (INTEGER PK)
  - `retailer_product_id` (INTEGER FK → retailer_products.id)
  - `retailer_id` (TEXT)
  - `price` (REAL)
  - `promotion_price` (REAL) — NULL if no promotion
  - `promotion_type` (TEXT) — e.g. 'bonus', 'aanbieding', NULL
  - `scrape_run_id` (INTEGER FK → scrape_runs.id)
  - `observed_at` (TIMESTAMP)
  - UNIQUE (retailer_product_id, scrape_run_id)

- **`retailer_raw_json`** — Source payload storage per retailer
  - `id` (INTEGER PK)
  - `retailer_id` (TEXT)
  - `source` (TEXT) — 'catalog', 'search', 'offers', 'bonus'
  - `sub_source` (TEXT)
  - `scrape_run_id` (INTEGER FK → scrape_runs.id)
  - `payload` (TEXT) — JSON blob
  - `created_at` (TIMESTAMP)

### Migration Plan

1. Create all new tables as additive migration (v7)
2. Backfill AH data:
   - Insert `retailers` row: id='ah', name='Albert Heijn'
   - Copy existing `products` → `retailer_products` with retailer_id='ah'
   - Copy existing AH categories → `retailer_categories`
   - Build `canonical_products` from GTINs in AH products
   - Create `product_matches` linking AH retailer_products → canonical
   - Copy `price_history` → `price_observations`
3. Keep existing AH tables untouched — they remain the fast path for AH-only queries
4. Update `scrape_runs` to include `retailer_id` column

### Acceptance Criteria

- [ ] Migration v7 creates all new tables without errors
- [ ] AH backfill populates retailer-aware tables with existing data
- [ ] Existing AH queries (`grocery query stats`, etc.) still work
- [ ] New query: `grocery query multi-stats` shows per-retailer counts
- [ ] Tests pass (temp DB with migration)

---

## Phase 2: Jumbo GraphQL Scraper

**Goal:** Scrape Jumbo product catalog via their GraphQL API.

### API Details

- **Endpoint:** `https://www.jumbo.com/api/graphql`
- **Auth:** Browser cookies (extracted from `document.cookie` after login)
- **Headers:**
  ```
  apollographql-client-name: JUMBO_MOBILE-orders
  apollographql-client-version: 30.14.0
  x-source: JUMBO_MOBILE-orders
  jmb-device-id: <random-device-id>
  ```

### Implementation

- **`grocery/jumbo_client.py`** — GraphQL client for Jumbo
  - Cookie-based auth with file-based cookie storage
  - GraphQL query builder
  - Rate limiting (TBD — start with 1.5s like AH, adjust based on errors)
  - Retry/backoff with exponential delays

- **`grocery/jumbo_scraper.py`** — Jumbo catalog scraper
  - `scrape_jumbo_categories()` — Discover categories via SearchSuggestions
  - `scrape_jumbo_products()` — SearchProducts per category
  - Upsert into `retailer_products` (retailer_id='jumbo')
  - Record prices in `price_observations`
  - Store raw JSON in `retailer_raw_json`

- **CLI commands:**
  - `grocery scrape jumbo categories` — Scrape Jumbo categories
  - `grocery scrape jumbo full` — Full Jumbo catalog scrape
  - `grocery scrape jumbo products <category>` — Single category

### Authentication Strategy

1. **Manual cookie extraction** (MVP): User pastes cookies from browser
2. **Headless browser** (future): Use Obscura or Playwright to auto-extract cookies

Cookie file format (`data/jumbo_cookies.txt`):
```
cookie1=value1; cookie2=value2; ...
```

### Key GraphQL Operations

```graphql
# Product search
query SearchProducts($input: ProductSearchInput!) {
  searchProducts(input: $input) {
    products {
      sku
      name
      brandName
      price
      promotionPrice
      categories
      imageUrl
      gtin
    }
    totalCount
  }
}

# Category suggestions
query SearchSuggestions($input: SearchSuggestionsInput!) {
  searchSuggestions(input: $input) {
    suggestions {
      type
      text
    }
  }
}
```

### Acceptance Criteria

- [ ] Jumbo client authenticates with cookies
- [ ] Category discovery returns Jumbo taxonomy
- [ ] Full scrape populates `retailer_products` with retailer_id='jumbo'
- [ ] Price observations recorded for Jumbo products
- [ ] Raw JSON stored for audit trail
- [ ] Rate limiting handles Jumbo's limits gracefully
- [ ] CLI commands work end-to-end
- [ ] Error handling for expired cookies (clear error message)

---

## Phase 3: Dirk REST Scraper

**Goal:** Scrape Dirk product catalog via their REST API.

### API Details

- **Endpoint:** `https://app-api.dirk.nl/v2/`
- **Auth:** Custom headers (`x-api-id`, `x-api-key`)
- **User-Agent:** `okhttp/4.9.1`
- **Required param:** `storeId` (mandatory for all catalog endpoints)

### Implementation

- **`grocery/dirk_client.py`** — REST client for Dirk
  - API key auth via config/env vars
  - Store selection (default store or configurable)
  - Rate limiting (TBD — start with 1.5s)
  - Retry/backoff

- **`grocery/dirk_scraper.py`** — Dirk catalog scraper
  - `scrape_dirk_stores()` — List stores, select default
  - `scrape_dirk_categories()` — Product categories
  - `scrape_dirk_products()` — Full catalog with prices
  - `scrape_dirk_offers()` — Temporary promotions
  - Upsert into `retailer_products` (retailer_id='dirk')
  - Record prices in `price_observations`

- **CLI commands:**
  - `grocery scrape dirk stores` — List available stores
  - `grocery scrape dirk categories` — Scrape categories
  - `grocery scrape dirk full` — Full Dirk catalog scrape
  - `grocery scrape dirk offers` — Scrape current promotions

### Key Endpoints

```
GET /stores?formulaId=2                    # Dirk stores only
GET /stores/{storeId}                      # Store details
GET /catalog/products/categories?storeId=X&priceDate=Y  # Categories
GET /catalog/products?storeId=X&priceDate=Y             # Products
GET /catalog/offers?storeId=X&startDate=Y&endDate=Z     # Promotions
```

### Authentication Strategy

1. **Env vars or config file** (MVP):
   ```bash
   export DIRK_API_ID="..."
   export DIRK_API_KEY="..."
   export DIRK_STORE_ID="12345"
   ```
2. Store credentials in `data/dirk_config.json` (encrypted or plaintext with warning)

### Acceptance Criteria

- [ ] Dirk client authenticates with API keys
- [ ] Store selection works (default or configured)
- [ ] Category discovery returns Dirk taxonomy
- [ ] Full scrape populates `retailer_products` with retailer_id='dirk'
- [ ] Price observations recorded for Dirk products
- [ ] Offers/promotions scraped separately
- [ ] CLI commands work end-to-end
- [ ] Error handling for invalid API keys

---

## Phase 4: Cross-Retailer Intelligence

**Goal:** Enable price comparison and unified analytics across retailers.

### New Analytics

- **`grocery query compare-prices`** — Compare prices for matched products across retailers
  - Input: product search term or canonical_product_id
  - Output: Price table across AH, Jumbo, Dirk with cheapest highlighted

- **`grocery query cross-retailer-stats`** — Per-retailer product counts, match rates
  - Total products per retailer
  - GTIN match rate (% of products with canonical matches)
  - Category overlap analysis

- **`grocery query cheapest-retailer`** — Which retailer has the cheapest price for a product
  - Input: canonical_product_id or search term
  - Output: Ranked retailers by current price

### New API Endpoints

- `GET /api/multi-retailer/compare?query=...` — Cross-retailer price comparison
- `GET /api/multi-retailer/stats` — Per-retailer statistics
- `GET /api/multi-retailer/cheapest?query=...` — Cheapest retailer for a product
- `GET /api/multi-retailer/products/{canonical_id}` — Canonical product with all retailer prices

### Product Matching

- **GTIN-based matching** (primary): Exact barcode match across retailers
- **Fuzzy matching** (fallback): Normalized title + brand + package size similarity
- **Manual review queue**: Low-confidence matches flagged for user review

### Acceptance Criteria

- [ ] Cross-retailer price comparison works for GTIN-matched products
- [ ] Cheapest retailer query returns ranked results
- [ ] API endpoints return unified cross-retailer data
- [ ] Product matching achieves >80% match rate for common products
- [ ] Low-confidence matches flagged for review

---

## Phase 5: Unified Operations

**Goal:** Multi-retailer daily jobs and monitoring.

### New CLI Commands

- `grocery scrape all` — Scrape all active retailers in sequence
- `grocery jobs multi-daily-snapshot` — Full multi-retailer daily job with backup
- `grocery query multi-health` — Health check across all retailers

### Configuration

```yaml
# grocery/config.py additions
RETAILER_CONFIG = {
    'ah': {
        'active': True,
        'delay': 1.5,
        'auth_type': 'oauth2',
    },
    'jumbo': {
        'active': True,
        'delay': 1.5,  # TBD
        'auth_type': 'cookies',
        'cookie_file': 'data/jumbo_cookies.txt',
    },
    'dirk': {
        'active': True,
        'delay': 1.5,  # TBD
        'auth_type': 'api_key',
        'api_id_env': 'DIRK_API_ID',
        'api_key_env': 'DIRK_API_KEY',
        'store_id_env': 'DIRK_STORE_ID',
    },
}
```

### Acceptance Criteria

- [ ] `grocery scrape all` runs all active retailers sequentially
- [ ] Multi-daily job includes backup, scrape, rebuild, health checks
- [ ] Failed retailer scrape doesn't block others (graceful degradation)
- [ ] Health check shows per-retailer status
- [ ] Configurable which retailers are active/inactive

---

## Implementation Order

1. **Phase 1** — Schema migration + AH backfill (foundation)
2. **Phase 2** — Jumbo scraper (GraphQL, cookie auth)
3. **Phase 3** — Dirk scraper (REST, API key auth)
4. **Phase 4** — Cross-retailer intelligence (matching, comparison)
5. **Phase 5** — Unified operations (multi-retailer jobs)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Jumbo cookie auth expires | Scraper breaks | Clear error message, manual cookie refresh |
| Dirk API key revoked | Scraper breaks | Monitor for 401/403, alert user |
| Rate limiting unknown | Scrapes fail | Start conservative (1.5s), increase gradually |
| Product matching low accuracy | Bad comparisons | GTIN-first, fuzzy fallback, manual review |
| Schema changes by retailers | Breaking changes | Raw JSON storage for replay, versioned scrapers |

## Estimated Effort

| Phase | Complexity | Estimated Time |
|-------|------------|----------------|
| Phase 1: Schema | Medium | 2-3 hours |
| Phase 2: Jumbo | High (GraphQL + cookies) | 3-4 hours |
| Phase 3: Dirk | Medium (REST + API keys) | 2-3 hours |
| Phase 4: Intelligence | High (matching logic) | 3-4 hours |
| Phase 5: Operations | Low-Medium | 1-2 hours |
| **Total** | | **11-16 hours** |

## Dependencies

- **Community projects for reference:**
  - `bartmachielsen/SupermarktConnector` — Jumbo GraphQL queries
  - `DanielOostdam-Create/jumbo-cli` — Full Jumbo API examples
  - BillyNate GitHub Gist — Dirk API documentation
- **Authentication credentials needed:**
  - Jumbo: Browser cookies (manual extraction)
  - Dirk: `x-api-id`, `x-api-key`, `storeId` (from mobile app)
