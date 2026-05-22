# Grocery Data Lake — Change Log

> Documenting all full-stack modifications made during the dashboard hardening session (May 22, 2026).

---

## 1. Background & Problem Statement

The React dashboard (`dashboard-v2/`) and FastAPI backend (`grocery/`) had several runtime bugs causing incorrect or missing data in the UI. This session addressed every layer: database query logic, API response shape, frontend hook wiring, and UI components.

**Before**: Blank dashboard pages, 422 Unprocessable Entity errors on `/cheapest`, Nutri-Score pills that didn't filter, ingredient results showing shower gel and baby wipes, broken Cloudflare tunnel.

**After**: All 7 dashboard tabs functional with correct data, filters wired end-to-end, non-food items excluded by default, fresh tunnel active.

---

## 2. Backend Changes (`grocery/`)

### 2.1 `grocery/api/intelligence.py`

#### Nutri-Score filter — `/api/intelligence/nutrition-scores`
**Lines**: ~214-258

- **Added**: `nutriscore` query param now accepts **comma-separated values** (e.g., `?nutriscore=A,B`).
- **Replaced**: Single `== nutriscore` equality check with `.in_([s.strip().upper() ...])` SQL `IN` filter.
- **Why**: The Health page has toggle pills for A/B/C/D/E. Previously these only filtered client-side among the first 50 pre-fetched rows, giving wrong counts and missing products. Now the backend filters at the database level.

#### Food-only filter — `/api/intelligence/ingredient-flags`
**Lines**: ~437-461

- **Added**: `food_only: bool = Query(False)` parameter.
- **Added**: Hardcoded `FOOD_CATEGORIES` whitelist (21 AH edible categories):
  ```
  Bier, wijn, aperitieven
  Soepen, sauzen, kruiden, olie
  Frisdrank, sappen, water
  Koek, snoep, chocolade
  Zuivel, eieren
  Borrel, chips, snacks
  Pasta, rijst, wereldkeuken
  Diepvries
  Koffie, thee
  Bakkerij
  Ontbijtgranen, beleg
  Kaas
  Groente, aardappelen
  Vleeswaren
  Vlees
  Vegetarisch, vegan en plantaardig
  Maaltijden, salades
  Vis
  Fruit, verse sappen
  Tussendoortjes
  Glutenvrij
  ```
- **Excluded non-food**: Drogisterij, Huishouden, Gezondheid en sport, Koken/tafelen, Huisdier, Baby en kind, AH Voordeelshop.
- **Why**: The ingredient flags endpoint returned all 26,825 products including personal care (2,928), household (1,291), pet food (800). Filtering "No Palm Oil" returned shower gel — correct but useless.

#### Response enrichment — `/api/intelligence/ingredient-flags`
**Lines**: ~478

- **Added**: `"mainCategory": product.main_category` to each product object in the response.
- **Why**: The UI needed to show category in the table so users can verify food-only is working.

#### Category filter — `/api/intelligence/ingredient-flags`
**Lines**: ~463-464

- **Added**: `category: str | None = Query(None)` — exact match on `ProductRow.main_category`.

#### Brand filter — `/api/intelligence/ingredient-flags`
**Lines**: ~465-466

- **Added**: `brand: str | None = Query(None)` — case-insensitive partial match via `ProductRow.brand.ilike(f'%{brand}%')`.
- **Why**: Users want to drill down by brand (e.g., "show me only AH cheese products").

### 2.2 `grocery/api/products.py` (pre-existing fix, verified)

- **Already present**: `bonusMechanism`, `bonusStartDate`, `bonusEndDate` in `/api/products` list response.
- **Why**: Bonus Radar on index.html was reading these fields; they were missing from the list endpoint.

### 2.3 `grocery/intelligence.py` (pre-existing fix, verified)

- **Already present**: `compute_allergen_summary()` skips `level == 'FREE_FROM'` at line ~1091.
- **Why**: Was flagging `FREE_FROM` allergens as "contains", causing vegetables to show 100% allergen risk.

---

## 3. Frontend Changes (`dashboard-v2/src/`)

### 3.1 `dashboard-v2/src/main.tsx`

- **Restored** full React entrypoint:
  ```tsx
  import { StrictMode } from 'react';
  import { createRoot } from 'react-dom/client';
  import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
  import { BrowserRouter } from 'react-router-dom';
  import App from './App';
  // ...
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>
  );
  ```
- **Before**: The deployed `dashboard/` bundle had a hacked `main.tsx` that rendered `LayoutNoIcons` directly without `<QueryClientProvider>`, `<BrowserRouter>`, or `<Routes>`, causing "FALLBACK: No render in 2s".

### 3.2 `dashboard-v2/src/App.tsx`

- **Added**: `basename="/dashboard"` to `<BrowserRouter>`.
- **Why**: FastAPI mounts the static build at `/dashboard/`. Without basename, React Router looks for routes at `/` and every route returns "No routes matched location /dashboard/...".

### 3.3 `dashboard-v2/src/pages/CheapestPage.tsx`

- **Changed default**: `useState('cheapest_overall')` → `useState('cheapest_price')`.
- **Updated `<option>` values** in dropdown:
  - `cheapest_price` ✓
  - `most_expensive_price` ✓
  - `cheapest_unit_price` ✓
  - `cheapest_healthy` ✓
  - `best_deal` ✓
- **Removed**: `cheapest_overall` (invalid — backend regex rejects it).
- **Why**: Backend validates `ranking_type` with `^(cheapest_price|most_expensive_price|cheapest_unit_price|cheapest_healthy|best_deal)$`. Sending `cheapest_overall` caused 422.

### 3.4 `dashboard-v2/src/pages/HealthPage.tsx`

- **Added**: Passed `nutriFilters` state into `useNutritionScores(minScore, 50, nutriFilters)`.
- **Before**: Nutri-Score A/B/C/D/E pills only filtered among the pre-fetched 50 rows client-side.
- **After**: Active pills are forwarded to the backend so the database returns only matching products.

### 3.5 `dashboard-v2/src/pages/IngredientsPage.tsx`

**Complete rewrite** with new filter controls:

- **🍽 Food Only toggle** (default: ON) — passes `foodOnly: true` to API.
- **Category dropdown** — populated from `useCategories()` (all 28 AH categories with counts).
- **Brand text input** — debounced at 400ms, placeholder "e.g. AH, Unox, Verstegen...".
- **Active filter pills** — 📁 Category badge and 🏷 Brand badge appear below filters with matching count.
- **× clear button** on brand input.
- **Clear all filters** button when any filter is active.
- **Category column** added to product table.

### 3.6 `dashboard-v2/src/lib/api.ts`

#### `useNutritionScores`
**Lines**: ~51-59

- **Expanded signature**: `useNutritionScores(minHealthScore, limit, nutriscores?: string[])`
- **Added**: `if (nutriscores && nutriscores.length > 0) params.set('nutriscore', nutriscores.join(','));`

#### `useIngredientFlags`
**Lines**: ~81-99

- **Expanded filters type**: added `category?: string` and `brand?: string`
- **Added**: `if (filters.category) params.set('category', filters.category);`
- **Added**: `if (filters.brand) params.set('brand', filters.brand);`
- **Already present**: `foodOnly?: boolean` forwarding to `food_only=true`.

### 3.7 `dashboard-v2/src/lib/types.ts`

- **Added**: `mainCategory?: string` to `IngredientFlags` interface.
- **Why**: Required for TypeScript build after adding category column to ingredient table.

---

## 4. Build & Deployment

### Build pipeline

```bash
cd /home/ubuntu/grocery-data-lake/dashboard-v2
npm run build   # tsc -b && vite build && node strip-cors.js
```

- **Output**: `../dashboard/` (Vite `outDir: '../dashboard'`)
- **Warning**: Chunk size ~728 KB (informational, not an error)
- **strip-cors.js**: Removes `crossorigin` attributes from the generated `index.html` to avoid CORS issues when served by FastAPI

### Uvicorn restart procedure

After every backend edit, **clear `__pycache__` and restart**:

```bash
pkill -f "uvicorn grocery.api.app:create_app"
find /home/ubuntu/grocery-data-lake -path './venv' -prune -o -name '__pycache__' -type d -exec rm -rf {} +
cd /home/ubuntu/grocery-data-lake && uvicorn grocery.api.app:create_app --host 0.0.0.0 --port 8000
```

**Why**: FastAPI/uvicorn caches compiled bytecode. Edits to `intelligence.py` are invisible until `__pycache__` is wiped and the process restarted.

### Cloudflare tunnel

```bash
cloudflared tunnel --url http://localhost:8000
```

- **Current URL**: `https://transportation-consciousness-critics-platform.trycloudflare.com`
- **Caveat**: URL changes on every restart. Tunnel process accumulates duplicates — clean old ones with `pkill -f cloudflared` before starting fresh.

---

## 5. Verification Matrix

| Endpoint | Test | Expected | Status |
|---|---|---|---|
| `GET /api/stats` | `curl localhost:8000/api/stats` | 29,622 total, 13,205 bonus, 28 categories | ✓ |
| `GET /api/intelligence/nutrition-scores?nutriscore=A&limit=50` | `curl` then inspect JSON | Returns 2,378 A-grade products | ✓ |
| `GET /api/intelligence/ingredient-flags?food_only=true&limit=5` | `curl` then inspect categories | All categories edible (fruit, beer, coffee) | ✓ |
| `GET /api/intelligence/ingredient-flags?category=Kaas&brand=AH&limit=3` | `curl` then inspect JSON | 405 matching products, all cheese, brand contains "AH" | ✓ |
| `/dashboard/` (browser) | Navigate, check for "FALLBACK" | No fallback message, full React app loads | ✓ |
| `/dashboard/cheapest` | Select ranking type | No 422, data loads | ✓ |
| `/dashboard/health` | Click Nutri-Score pills | API requests fire, table updates with filtered results | ✓ |
| `/dashboard/ingredients` | Toggle Food Only OFF | Non-food items (Drogisterij, Huishouden) appear | ✓ |
| `/dashboard/ingredients` | Select Category=Kaas, Brand=AH | Only cheese products, AH brands, 405 count badge | ✓ |

---

## 6. File Inventory

### Modified files

| File | What changed |
|---|---|
| `grocery/api/intelligence.py` | Nutri-Score `.in_()` filter; `food_only` param + `FOOD_CATEGORIES`; `mainCategory` in response; `category` exact match; `brand` `.ilike()` match |
| `dashboard-v2/src/main.tsx` | Restored full React entrypoint with providers |
| `dashboard-v2/src/App.tsx` | Added `basename="/dashboard"` to BrowserRouter |
| `dashboard-v2/src/pages/CheapestPage.tsx` | Fixed `ranking_type` default and option values |
| `dashboard-v2/src/pages/HealthPage.tsx` | Passed `nutriFilters` to `useNutritionScores` |
| `dashboard-v2/src/pages/IngredientsPage.tsx` | Complete rewrite: Food Only toggle, Category dropdown, Brand input, filter pills, Category column |
| `dashboard-v2/src/lib/api.ts` | Expanded `useNutritionScores` and `useIngredientFlags` signatures |
| `dashboard-v2/src/lib/types.ts` | Added `mainCategory?: string` to `IngredientFlags` |

### Generated files (do not edit directly)

| File | Source |
|---|---|
| `dashboard/index.html` | Vite build output |
| `dashboard/assets/index-*.js` | Vite build output |
| `dashboard/assets/index-*.css` | Vite build output |

---

## 7. Known Remaining Items

1. **Vite chunk size warning** — Bundle is 728 KB. Consider dynamic `import()` code splitting if load time becomes an issue.
2. **Cloudflare tunnel URL rotation** — Each restart generates a new URL. For a persistent URL, configure a named Cloudflare tunnel with a fixed domain.
3. **Other pages** — Spot-check `/deals`, `/brands`, `/alternatives` for similar frontend/backend enum mismatches or non-food leakage.
4. **Ingredient flags `possible_vegetarian` param** — Added to backend query function but not exposed in UI toggle yet.

---

## 8. Architecture Reminder

```
grocery/
├── api/
│   ├── app.py              # FastAPI factory, static mount at /dashboard
│   ├── products.py         # /api/products
│   ├── intelligence.py     # /api/intelligence/* ← MODIFIED
│   ├── viz.py              # /api/viz/* (categories, brands, bonus)
│   ├── stats.py            # /api/stats
│   ├── analytics.py        # /api/analytics/*
│   ├── raw_json.py         # /api/raw/*
│   └── bonus.py            # /api/bonus/*
├── client.py               # AHClient
├── db.py                   # SQLAlchemy models
├── enrich.py               # Product enrichment
└── intelligence.py         # Core analytics engine

dashboard-v2/               # Source of truth (React + Vite)
├── src/
│   ├── main.tsx            # ← MODIFIED
│   ├── App.tsx             # ← MODIFIED
│   ├── pages/
│   │   ├── CheapestPage.tsx    # ← MODIFIED
│   │   ├── HealthPage.tsx      # ← MODIFIED
│   │   ├── IngredientsPage.tsx # ← MODIFIED
│   │   └── ...
│   ├── lib/
│   │   ├── api.ts          # ← MODIFIED
│   │   └── types.ts        # ← MODIFIED
│   └── ...
└── vite.config.ts          # base: '/dashboard/', outDir: '../dashboard'

dashboard/                  # DEPLOYED BUNDLE (DO NOT EDIT)
├── index.html              # Generated by Vite build
└── assets/
    ├── index-*.js          # Generated by Vite build
    └── index-*.css         # Generated by Vite build
```

---

*Last updated: May 22, 2026*
