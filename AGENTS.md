# Grocery Data Lake — Agent Reference Guide

> **For AI agents working on this codebase.**  
> Last updated: 2026-05-14

---

## 1. Project Overview

A data lake that scrapes Albert Heijn (AH) grocery products, stores them in SQLite, and exposes analytics via a FastAPI + Cloudflare tunnel stack. Two dashboards:
1. `dashboard/index.html` — Main dashboard (Bonus Radar, Price changes, etc.)
2. `dashboard/intelligence.html` — Advanced analytics (Deals, Health, Ingredients, Brands)

---

## 2. Architecture

```
grocery/
├── api/                    # FastAPI routers
│   ├── app.py              # create_app() — main app factory
│   ├── products.py         # /api/products — list + detail
│   ├── intelligence.py     # /api/intelligence/* — deals, health, ingredients, alternatives, baskets
│   ├── viz.py              # /api/viz/* — categories, brands, bonus overview
│   ├── stats.py            # /api/stats — total products, bonus count, etc.
│   ├── analytics.py        # /api/analytics/* — price history, trends
│   ├── raw_json.py         # /api/raw/* — raw JSON endpoints
│   └── bonus.py            # /api/bonus/* — bonus-focused endpoints
├── client.py               # AHClient — fetches from AH API (v2)
├── db.py                   # SQLAlchemy models + DB init
├── enrich.py               # Product detail enrichment (allergens, ingredients, nutrition)
└── intelligence.py         # Core analytics engine + allergen summary computation

CLI entry: python -m grocery.cli (enrich, init-db, etc.)
```

---

## 3. Database Schema (SQLite)

File: `data/grocery.db` (~1.5GB)

Key tables:

| Table | Purpose |
|---|---|
| `products` | Main catalog (28,270 rows). Key cols: `webshop_id`, `title`, `brand`, `main_category`, `current_price`, `price_before_bonus`, `is_bonus`, `bonus_mechanism`, `bonus_start_date`, `bonus_end_date`, `nutriscore`, `ingredient_count`, `added_sugar`, `palm_oil`, `preservatives` |
| `price_history` | Price snapshots over time |
| `raw_json` | Raw API responses from AH |
| `allergens` | 20,000+ rows. `product_id` → `allergen_name` + `level` (`CONTAINS`, `FREE_FROM`, `MAY_CONTAIN`) |
| `ingredients` | Parsed ingredients per product |
| `nutrition_facts` | Per-100g nutrition data |
| `analytics_allergen_summary` | Pre-computed cache: risk scores per product |
| `analytics_brand_summary` | Brand-level aggregations |
| `analytics_category_summary` | Category-level price metrics |

SQLite specifics:
- `sqlite3` CLI not installed on this server — use Python `sqlite3` module instead.
- Concurrent write: SQLite supports one writer at a time. Long-running enrich jobs can block ad-hoc queries.

---

## 4. Running the Project

```bash
# Start API server
cd /home/ubuntu/grocery-data-lake
uvicorn grocery.api.app:create_app --host 0.0.0.0 --port 8000

# Background run
nohup uvicorn grocery.api.app:create_app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

# Cloudflare tunnel (auto-reconnects, but duplicates can accumulate — clean old ones)
nohup cloudflared tunnel --url http://localhost:8000 > /tmp/cloudflared.log 2>&1 &

# Full product enrichment (takes ~3.5 hours for 28k products)
python -m grocery.cli enrich all
```

---

## 5. Known Issues & Workarounds

### 5.1 Dashboard fields mismatched with API

**Issue**: Dashboard JS accesses field names that may differ from API responses.

**Already fixed**:
- `dashboard/intelligence.html:347` — `stats.productsOnBonus` → `stats.bonusProducts`

**Verify first** if dashboard shows zeros: check `updateExecStats()` and confirm field names match `/api/stats` response keys.

### 5.2 Allergen data bug (FIXED 2026-05-14)

**Bug**: `compute_allergen_summary()` in `grocery/intelligence.py` flagged `FREE_FROM` allergens as "contains", causing vegetables to show 100% allergen risk.

**Fix**: Added `level != 'FREE_FROM'` check at line 1091.

### 5.3 Bonus fields missing from list endpoint

**Fix**: Added `bonusMechanism`, `bonusStartDate`, `bonusEndDate` to `/api/products` list response in `grocery/api/products.py`.

---

## 6. API Endpoint Quick Reference

| Endpoint | Returns | Dashboard Tab |
|---|---|---|
| `GET /api/stats` | `totalProducts`, `bonusProducts`, `totalCategories`, `uniqueBrands`, `priceRange`, `lastScrapeRun` | Executive |
| `GET /api/viz/categories` | `categories[]` with `productCount`, `bonusCount`, `bonusSharePct`, `avgDiscountPct` | — |
| `GET /api/viz/brands?limit=100` | `brands[]` with `productCount`, `categoryCount`, `avgPrice`, `avgHealthScore`, `bonusSharePct` | — |
| `GET /api/viz/bonus-overview` | `categories[]`, `topDeals[]` | Bonus Radar (index.html) |
| `GET /api/intelligence/deals?label=excellent_deal&limit=10` | `total`, `deals[]` with `productId`, `productTitle`, `brand`, `currentPrice`, `priceBeforeBonus`, `discountPct`, `dealScore`, `dealLabel` | Executive, Deals |
| `GET /api/intelligence/nutrition-scores?min_health_score=80&limit=10` | `total`, `products[]` with `nutriscore`, `healthScore`, `caloriesPer100g`, etc. | Executive, Health |
| `GET /api/intelligence/brand-intelligence?limit=10` | `total`, `brands[]` with `productCount`, `avgPrice`, `avgHealthScore`, `bonusSharePct`, `privateLabelCandidate` | Executive, Brands |
| `GET /api/intelligence/cheapest-by-category?ranking_type=cheapest_price&rank_limit=5` | `rankingType`, `total`, `rankings[]` with `rank`, `productTitle`, `brand`, `currentPrice`, `unitPrice`, `baseUnit`, `mainCategory`, `subCategory` | Cheapest |
| `GET /api/intelligence/health-value?limit=30&rank_limit=5` | `total`, `rankings[]` with `rankInCategory`, `healthScore`, `mainCategory` | Health |
| `GET /api/intelligence/ingredient-flags?limit=50` | `total`, `products[]` with `cleanLabelScore`, `ultraProcessedScore`, `containsAddedSugar`, `containsPalmOil`, `containsPreservatives`, `allergenRiskScore` | Ingredients |
| `GET /api/intelligence/allergen-summary?limit=50` | `total`, `products[]` with `containsGluten`, `containsMilk`, `containsNuts`, `containsPeanuts`, `containsSoy`, `containsEgg`, `containsFish`, `containsShellfish`, `containsCount`, `allergenRiskScore` | Ingredients |
| `GET /api/intelligence/baskets` | `baskets[]` (empty if none created) | Baskets |
| `GET /api/intelligence/product-alternatives/{product_id}` | `productId`, `total`, `alternatives[]` with `alternativeTitle`, `alternativeBrand`, `alternativeType`, `priceSavingPct`, `healthScoreDelta`, `confidence`, `explanation` | Alternatives |

---

## 7. Common Tasks

### Recompute allergen analytics
```python
from grocery.db import get_session
from grocery.intelligence import compute_allergen_summary
session = get_session()
count = compute_allergen_summary(session)
```

### Query database (no sqlite3 CLI)
```python
import sqlite3
conn = sqlite3.connect('/home/ubuntu/grocery-data-lake/data/grocery.db')
c = conn.cursor()
```

### Kill stale Cloudflare tunnel processes
```bash
# Find duplicates
ps aux | grep cloudflared | grep -v grep
# Kill old ones, keep newest
```

### Enrich a single product
```python
from grocery.db import get_session, init_db, _store_allergens
from grocery.client import AHClient
init_db()
session = get_session()
client = AHClient()
detail = client.get_product_detail(769)  # product webshop_id
if detail:
    _store_allergens(session, 769, detail.get('allergenInfo', []))
    session.commit()
```

---

## 8. Environment

- **Server**: Ubuntu 24.04, ARM64, CPU-only (no GPU)
- **Python**: 3.12 (venv active)
- **Key deps**: `fastapi`, `uvicorn`, `sqlalchemy`, `httpx`, `beautifulsoup4`, `python-dotenv`
- **Cloudflare tunnel**: Auto-generated URL, changes on restart
- **Current tunnel** (as of 2026-05-14): `https://trim-priced-tables-amber.trycloudflare.com`

---

## 9. Data Quality Notes

| Metric | Value (2026-05-14) |
|---|---|
| Total products | 28,270 |
| Bonus products | 9,911 |
| Categories | 28 |
| Unique brands | 1,941 |
| Products with allergen data | 13,153 |
| Products with nutrition data | ~5,000+ |
| Products with ingredients | 27,416 |

---

## 10. File Checklist for Future Agents

Before making changes, confirm these files are consistent:
- [ ] `grocery/api/products.py` — bonus fields in list response
- [ ] `grocery/api/intelligence.py` — deal/nutrition/ingredient/allergen endpoints
- [ ] `grocery/api/viz.py` — bonus-overview, categories, brands
- [ ] `grocery/api/stats.py` — field names match dashboard expectations
- [ ] `grocery/intelligence.py` — `compute_allergen_summary()` skips `FREE_FROM`
- [ ] `dashboard/index.html` — main dashboard
- [ ] `dashboard/intelligence.html` — advanced analytics dashboard
- [ ] `grocery/db.py` — models match schema

---

## 11. AH.nl Product URLs

- **URL Pattern**: `https://www.ah.nl/producten/product/{webshopId}`
- **API Field**: `ahUrl` (added to all endpoints)
- **Not captured during scraping** — `externalWebshopUrl` is null for 99.9% of products
- **Constructed dynamically** from `webshop_id` in API responses

### Endpoints with `ahUrl`:
- `/api/products/*` — list, detail, search
- `/api/intelligence/*` — deals, nutrition, health, ingredients, allergens, brands, promotion-frequency
- `/api/viz/*` — price-changes, bonus-overview

### Dashboard links:
- **index.html**: Price changes feed titles are clickable
- **intelligence.html**: All product tables have clickable titles linking to AH.nl
