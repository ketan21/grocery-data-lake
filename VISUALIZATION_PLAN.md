# Grocery Data Lake — D3.js Visualization Dashboard

## Data Inventory

| Table | Records | Description |
|---|---|---|
| products | 28,208 | Product catalog (28 categories, 668 brands) |
| price_history | 162,831 | Price snapshots per scrape run |
| scrape_runs | 15 | Daily snapshots (May 9-11, 2026) |
| price_metrics | 8,287 | Computed: avg price, volatility, cheapest/most expensive |
| unit_prices | 17,061 | Normalized: g (10,897), ml (6,153), m (11) |
| bonus | 9,848 products | Currently promotional (avg 81% of regular price) |

## Dashboard Architecture

**Single-page app** served by the existing FastAPI (`grocery/api/`).
Tech stack: D3.js v7, vanilla HTML/CSS/JS, no frameworks.

### API Endpoints (to be added to `grocery/api/`)

```
GET /api/viz/categories          # Category breakdown with product counts, avg prices, volatility
GET /api/viz/brands?limit=50     # Top brands with product counts
GET /api/viz/price-distribution  # Price histogram buckets
GET /api/viz/price-timeline      # Price history time series (per category or brand)
GET /api/viz/price-changes       # Latest price changes (up/down, with/without bonus)
GET /api/viz/unit-prices?unit=g  # Cheapest per unit (g/ml/m)
GET /api/viz/bonus-overview      # Bonus stats: count, avg discount, top deals
GET /api/viz/volatility          # Price volatility by category/brand
GET /api/viz/search?q=           # Full-text product search with price history
```

## Visualizations

### 1. Hero: Price Distribution Sunburst
- **Type:** D3 sunburst chart
- **Data:** Categories → Sub-categories → Price ranges
- **Insight:** At-a-glance view of the entire catalog structure with price density
- **Interaction:** Click to filter all other charts

### 2. Price Timeline (Sparkline Grid)
- **Type:** D3 line chart grid (one per category)
- **Data:** price_history grouped by category over scrape_runs
- **Insight:** Which categories are inflating/deflating over time
- **Interaction:** Hover for exact values, click to drill into brand-level

### 3. Price Change Heatmap
- **Type:** D3 heatmap (categories × time)
- **Data:** % price change between consecutive runs
- **Insight:** Instantly spot which categories had price movements
- **Interaction:** Click cell to see product-level changes

### 4. Unit Price Comparison (Bar Chart)
- **Type:** Horizontal bar chart, grouped by unit (g/ml)
- **Data:** Cheapest products per unit, grouped by category
- **Insight:** "Where do I get the most bang for my buck?"
- **Interaction:** Sort by unit price, filter by category

### 5. Bonus Deals Radar
- **Type:** D3 radar/spider chart
- **Data:** Bonus coverage by category, avg discount depth, product count
- **Insight:** Which categories have the deepest/broadest promotions
- **Interaction:** Click category to list specific deals

### 6. Brand Dominance Pack
- **Type:** D3 treemap
- **Data:** Brands nested under categories, sized by product count
- **Insight:** Market share visualization — AH dominates with 6093 products
- **Interaction:** Click brand to filter, see avg price vs category avg

### 7. Volatility Scatter Plot
- **Type:** D3 scatter plot (bubble chart)
- **Data:** x=avg_price, y=volatility, size=total_changes, color=category
- **Insight:** Which products/categories have unstable pricing
- **Interaction:** Brush to filter, hover for product details

### 8. Price Change Feed (Live List)
- **Type:** Animated list with D3 transitions
- **Data:** Latest price changes (separate tabs: all / shelf-only / bonus-on / bonus-off)
- **Insight:** Real-time price intelligence
- **Interaction:** Filter by min % change, search by product name

## Design System

- **Theme:** Dark mode (dark bg #0f1117, cards #1a1d27, text #e4e4e7)
- **Colors:** D3 category palette (28 distinct colors), green for ↓ prices, red for ↑ prices
- **Typography:** System fonts (Inter/SF Pro), monospace for prices
- **Layout:** CSS Grid, responsive (mobile: stacked, desktop: 2-3 columns)
- **Animations:** D3 transitions on data updates, smooth enter/exit

## File Structure

```
grocery-data-lake/
├── grocery/
│   ├── api/
│   │   ├── viz_routes.py      # New: /api/viz/* endpoints
│   │   └── viz_queries.py     # SQL queries for viz data
│   └── static/
│       ├── dashboard.html     # Single-page dashboard
│       ├── css/
│       │   └── dashboard.css  # Dark theme, grid layout
│       └── js/
│           ├── dashboard.js   # Main app: fetch data, render charts
│           ├── charts/
│           │   ├── sunburst.js
│           │   ├── timeline.js
│           │   ├── heatmap.js
│           │   ├── barchart.js
│           │   ├── radar.js
│           │   ├── treemap.js
│           │   ├── scatter.js
│           │   └── changefeed.js
│           └── utils.js       # Shared: color scale, formatters, fetch helpers
```

## Implementation Order

1. **API layer** — viz_routes.py + viz_queries.py (data endpoints)
2. **Shell** — dashboard.html + CSS grid layout + dark theme
3. **Charts** (in order of impact):
   - Price change heatmap (immediate value)
   - Price timeline (inflation tracking)
   - Brand treemap (catalog overview)
   - Volatility scatter (price intelligence)
   - Unit price bars (shopping optimization)
   - Sunburst (hero visual)
   - Bonus radar (promo tracking)
   - Change feed (live monitoring)
4. **Interactivity** — cross-filtering, search, drill-down
5. **Polish** — animations, responsive, loading states
