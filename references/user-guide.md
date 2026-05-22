# User Guide

## Getting Started

### Prerequisites

- Python 3.11+
- SQLite3
- Linux/macOS/WSL environment

### Installation

```bash
# Clone the repository
cd /home/ubuntu/grocery-data-lake

# Install dependencies
pip install -r requirements.txt

# Initialize the database
python3 -c "from grocery.db import init_db; init_db()"

# Verify installation
python3 -m grocery.cli query stats
```

### First-Time Setup

1. **Database Initialization**
   ```bash
   python3 -c "from grocery.db import init_db; init_db()"
   ```
   This creates the database with all tables and applies the latest migrations.

2. **Run Your First Scrape**
   ```bash
   python3 -m grocery.cli scrape full
   ```
   This will take approximately 8 minutes and scrape all 28 AH categories.

3. **Verify Data**
   ```bash
   python3 -m grocery.cli query stats
   ```
   Should show ~27,000 products and ~230,000 price snapshots.

## Daily Usage

### Running the Daily Pipeline

The complete daily pipeline is run via:
```bash
grocery jobs daily-snapshot
```

This performs:
1. **Database backup** - Creates timestamped backup in `data/backups/`
2. **Full scrape** - Scrapes all 28 AH categories
3. **Derived table rebuild** - Recomputes all analytics and intelligence tables
4. **Quality checks** - Validates data integrity

**Check the log:**
```bash
tail -f data/daily-snapshot.log
```

**Schedule via cron (already configured):**
```bash
crontab -l | grep grocery
# 0 3 * * * cd /home/ubuntu/grocery-data-lake && /home/ubuntu/.local/bin/grocery jobs daily-snapshot
```

Runs daily at 3:00 AM CET.

### Quick Queries

**Check latest scrape:**
```bash
python3 -c "from grocery.db import get_session; from grocery.models import ScrapeRun; s=get_session(); r=s.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).first(); print(f'Last run: {r.started_at}, Products: {r.products_scraped}, Status: {r.status}')"
```

**Get database stats:**
```bash
python3 -m grocery.cli query stats
```

**Find cheapest products per gram:**
```bash
python3 -m grocery.cli query cheapest-unit g
```

**Find cheapest products per milliliter:**
```bash
python3 -m grocery.cli query cheapest-unit ml
```

## Dashboard Usage

### Starting the Dashboard Server

```bash
# Method 1: Direct uvicorn (recommended)
python3 -c "from grocery.api.app import create_app; import uvicorn; uvicorn.run(create_app(), host='0.0.0.0', port=8000)"

# Method 2: Via CLI
grocery serve run-server
```

### Accessing the Dashboard

Open in browser:
```
http://localhost:8000/dashboard/
```

### Dashboard Features

**Interactive Charts:**
1. **Category Heatmap** - Click any category to filter all other charts
2. **Brand Treemap** - Visual hierarchy of brands by product count
3. **Price Histogram** - Distribution of prices across buckets
4. **Price Timeline** - Track average prices over time
5. **Price Changes** - Latest price changes with before/after
6. **Unit Prices** - Cheapest products per unit (g/ml)
7. **Bonus Overview** - Promotion statistics by category
8. **Volatility Chart** - Price instability by category

**Cross-Filtering:**
- Click any chart element to filter all other charts
- Click again to clear filters
- All filters are combinatorial

**Auto-Refresh:**
- Dashboard refreshes every 5 minutes automatically
- Manual refresh: Click the refresh button

### External Access

To expose the dashboard externally:

```bash
# Start cloudflared tunnel
/tmp/cloudflared tunnel --url http://localhost:8000

# The dashboard will be available at:
# https://<random-subdomain>.trycloudflare.com/dashboard/
```

**Note:** Quick tunnels get random URLs each time. No static subdomain without a Cloudflare account.

## Intelligence Features

### Using the Intelligence API

All intelligence endpoints are under `/api/intelligence/`.

#### 1. Category Price Rankings

```bash
# Cheapest products by category
curl "http://localhost:8000/api/intelligence/cheapest-by-category?ranking_type=cheapest_price&category=Dairy&rank_limit=10"

# Best deals by category
curl "http://localhost:8000/api/intelligence/cheapest-by-category?ranking_type=best_deal&category=Meat&rank_limit=5"

# Cheapest per unit
curl "http://localhost:8000/api/intelligence/cheapest-by-category?ranking_type=cheapest_unit_price&category=Soft+Drinks&rank_limit=10"
```

**Ranking Types:** `cheapest_price`, `most_expensive`, `cheapest_unit_price`, `cheapest_healthy`, `best_deal`

#### 2. Deal Quality Scores

```bash
# Find historical lows
curl "http://localhost:8000/api/intelligence/deals?label=historical_low&min_score=80&limit=20"

# Find excellent deals
curl "http://localhost:8000/api/intelligence/deals?label=excellent_deal&min_score=70&limit=20"

# All deals sorted by score
curl "http://localhost:8000/api/intelligence/deals?limit=50&sort_by=score"
```

**Deal Labels:** `historical_low`, `excellent_deal`, `good_deal`, `normal_promotion`, `weak_promotion`, `not_a_deal`

#### 3. Nutrition Scores

```bash
# Healthiest products
curl "http://localhost:8000/api/intelligence/nutrition-scores?min_health_score=70&sort_by=health_score&limit=20"

# Products with good Nutriscore
curl "http://localhost:8000/api/intelligence/nutrition-scores?nutriscore=A&limit=20"

# High protein per euro
curl "http://localhost:8000/api/intelligence/nutrition-scores?sort_by=protein_per_euro&limit=20"
```

#### 4. Health Value Rankings

```bash
# Best health+price value in category
curl "http://localhost:8000/api/intelligence/health-value?category=Dairy&rank_limit=10"

# Overall rankings
curl "http://localhost:8000/api/intelligence/health-value?rank_limit=20"
```

#### 5. Promotion Frequency

```bash
# Frequently promoted products
curl "http://localhost:8000/api/intelligence/promotion-frequency?min_bonus_freq=50&limit=20"

# High discount products
curl "http://localhost:8000/api/intelligence/promotion-frequency?min_avg_discount=30&limit=20"
```

#### 6. Ingredient Flags

```bash
# No added sugar
curl "http://localhost:8000/api/intelligence/ingredient-flags?contains_added_sugar=false&limit=20"

# Vegan products
curl "http://localhost:8000/api/intelligence/ingredient-flags?possible_vegan=true&limit=20"

# Clean label products
curl "http://localhost:8000/api/intelligence/ingredient-flags?min_clean_label=80&limit=20"

# No preservatives
curl "http://localhost:8000/api/intelligence/ingredient-flags?contains_preservatives=false&limit=20"
```

**Available Flags:**
- `contains_added_sugar` (true/false)
- `contains_palm_oil` (true/false)
- `contains_artificial_sweeteners` (true/false)
- `contains_preservatives` (true/false)
- `contains_emulsifiers` (true/false)
- `contains_colourants` (true/false)
- `contains_seed_oils` (true/false)
- `contains_caffeine` (true/false)
- `possible_vegan` (true/false)
- `possible_vegetarian` (true/false)
- `min_clean_label` (0-100 score)
- `max_ultra_processed` (0-100 score)

#### 7. Allergen Summary

```bash
# Gluten-free products
curl "http://localhost:8000/api/intelligence/allergen-summary?contains_gluten=false&limit=20"

# Low allergen risk
curl "http://localhost:8000/api/intelligence/allergen-summary?max_risk_score=30&limit=20"

# No nuts
curl "http://localhost:8000/api/intelligence/allergen-summary?contains_nuts=false&limit=20"
```

**Allergen Filters:** `contains_gluten`, `contains_milk`, `contains_nuts`, `contains_peanuts`, `contains_soy`, `contains_egg`, `contains_fish`, `contains_shellfish`

#### 8. Product Alternatives

```bash
# Find cheaper alternative
curl "http://localhost:8000/api/intelligence/product-alternatives/12345?alternative_type=cheaper_alternative"

# Find healthier alternative
curl "http://localhost:8000/api/intelligence/product-alternatives/12345?alternative_type=healthier_alternative"

# Same brand alternative
curl "http://localhost:8000/api/intelligence/product-alternatives/12345?alternative_type=same_brand_alternative"
```

**Alternative Types:** `cheaper_alternative`, `healthier_alternative`, `same_brand_alternative`

#### 9. Basket Intelligence

```bash
# List basket definitions
curl "http://localhost:8000/api/intelligence/baskets"

# Get basket snapshots
curl "http://localhost:8000/api/intelligence/basket-snapshots?basket_id=1&limit=20"
```

**Note:** Basket definitions must be seeded manually. No automatic seed data exists.

#### 10. Brand Intelligence

```bash
# High-quality brands
curl "http://localhost:8000/api/intelligence/brand-intelligence?min_avg_health=70&limit=20"

# Private label candidates
curl "http://localhost:8000/api/intelligence/brand-intelligence?private_label_only=true&limit=20"

# Brands with frequent promotions
curl "http://localhost:8000/api/intelligence/brand-intelligence?min_bonus_share=50&limit=20"
```

### Recomputing Intelligence

To force a full recompute of all intelligence tables:
```bash
curl "http://localhost:8000/api/intelligence/recompute"
```

Or via Python:
```bash
python3 -c "from grocery.db import get_session; from grocery.intelligence import compute_all_intelligence; r = compute_all_intelligence(get_session()); [print(f'{k}: {v}') for k,v in sorted(r.items())]"
```

**Expected baseline:**
- ~28K promotion frequency
- ~25K ingredient flags
- ~2K brand intelligence
- ~54K product alternatives
- ~856 nutrition/health value
- ~696 allergen summary
- ~44K category price rankings
- ~8K deal quality scores

## Advanced Queries

### Price Change Analysis

**Find products that changed price between runs:**
```sql
-- Get last 2 run IDs
SELECT id, started_at FROM scrape_runs ORDER BY started_at DESC LIMIT 2;

-- Compare prices between runs
SELECT p.brand, p.main_category, p.title,
       ph_prev.current_price AS prev_price,
       ph_curr.current_price AS curr_price,
       ROUND((ph_curr.current_price - ph_prev.current_price) * 100.0 / NULLIF(ph_prev.current_price, 0), 2) AS pct_change
FROM price_history ph_curr
JOIN price_history ph_prev ON ph_prev.product_id = ph_curr.product_id AND ph_prev.scrape_run_id = ?
JOIN products p ON p.webshop_id = ph_curr.product_id
WHERE ph_curr.scrape_run_id = ?
  AND ph_curr.current_price != ph_prev.current_price
ORDER BY ABS(pct_change) DESC;
```

**Find new bonus products:**
```sql
SELECT p.brand, p.main_category, p.title,
       p.current_price AS bonus_price,
       p.price_before_bonus AS reg_price,
       ROUND((p.current_price - p.price_before_bonus) * 100.0 / NULLIF(p.price_before_bonus, 0), 2) AS discount_pct
FROM products p
JOIN price_history ph_prev ON ph_prev.product_id = p.webshop_id
    AND ph_prev.scrape_run_id = ?
WHERE p.is_bonus = 1
  AND ph_prev.is_bonus = 0
  AND p.price_before_bonus IS NOT NULL
ORDER BY ABS(discount_pct) DESC;
```

### Direct Database Queries

```bash
# Connect to database
sqlite3 data/grocery.db

# Common queries
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM price_history;
SELECT COUNT(DISTINCT brand) FROM products;
SELECT main_category, COUNT(*) FROM products GROUP BY main_category ORDER BY COUNT(*) DESC;

# Price metrics
SELECT * FROM price_metrics WHERE cheapest_price < 1.0 ORDER BY cheapest_price LIMIT 20;

# Unit prices
SELECT p.title, u.base_unit, u.normalized_price FROM unit_prices u JOIN products p ON p.webshop_id = u.product_id WHERE u.base_unit = 'g' ORDER BY u.normalized_price LIMIT 20;
```

### Python Querying

```python
from grocery.db import get_session
from sqlalchemy import text

session = get_session()

# Run custom query
result = session.execute(text("""
    SELECT brand, COUNT(*) as cnt 
    FROM products 
    GROUP BY brand 
    ORDER BY cnt DESC 
    LIMIT 10
"""))

for row in result:
    print(f"{row.brand}: {row.cnt} products")
```

## Maintenance Tasks

### Database Maintenance

**Check migration status:**
```bash
python3 -c "from grocery.migrations import migration_status; print(migration_status())"
```

**Apply pending migrations:**
```bash
python3 -c "from grocery.migrations import migrate; print(migrate())"
```

**Create a backup:**
```bash
cp data/grocery.db data/grocery-$(date +%Y%m%d-%H%M%S).db
```

**Rebuild derived tables:**
```bash
grocery jobs rebuild-derived
```

### Log Management

**Check daily snapshot log:**
```bash
tail -n 50 data/daily-snapshot.log
```

**Check for errors:**
```bash
grep ERROR data/daily-snapshot.log
```

**Clear old logs:**
```bash
# Keep only last 1000 lines
tail -n 1000 data/daily-snapshot.log > data/daily-snapshot.log.tmp
mv data/daily-snapshot.log.tmp data/daily-snapshot.log
```

### Performance Optimization

**Database size check:**
```bash
ls -lh data/grocery.db
```

**Table row counts:**
```bash
sqlite3 data/grocery.db "SELECT 'products' as table_name, COUNT(*) as rows FROM products UNION ALL SELECT 'price_history', COUNT(*) FROM price_history UNION ALL SELECT 'analytics_category_price_rankings', COUNT(*) FROM analytics_category_price_rankings;"
```

**Analyze database:**
```bash
sqlite3 data/grocery.db "ANALYZE;"
```

**Vacuum database:**
```bash
sqlite3 data/grocery.db "VACUUM;"
```

## Troubleshooting

### Common Issues

**1. Database Locked Error**
- Cause: WAL mode with concurrent access
- Fix: Stop the server before running scrapes, or use `grocery jobs daily-snapshot`

**2. AH API Returns 400**
- Cause: Requesting page beyond available results
- Fix: Scraper handles this automatically, continues to next category

**3. Dashboard Shows Stale Data**
- Cause: `/api/viz/price-changes` uses window functions that skip NULL prices
- Fix: Use direct SQL queries with specific scrape_run_id values

**4. Price Changes Endpoint Slow**
- Cause: Heavy window-function query over 247K+ rows
- Fix: Use direct SQL queries instead

**5. Current Price is NULL**
- Cause: AH API only returns currentPrice for bonus products
- Fix: Use `COALESCE(current_price, price_before_bonus)` as `effective_price`
- Impact: Affects ~72% of products without the fix

**6. Import Errors**
- Cause: Importing from wrong module path
- Fix: Use `grocery.db` not `grocery.database`

### Debug Commands

**Check database connection:**
```bash
python3 -c "from grocery.db import get_engine; print(get_engine().execute('SELECT 1').scalar())"
```

**Verify CLI works:**
```bash
python3 -m grocery.cli query stats
```

**Test API locally:**
```bash
curl http://localhost:8000/api/viz/categories
```

**Check migration version:**
```bash
python3 -c "from grocery.migrations import migration_status; print(migration_status())"
```

### Getting Help

- Check `references/` directory for detailed documentation
- Review `SKILL.md` for quick reference
- Check `data/daily-snapshot.log` for error details
- Use `sqlite3 data/grocery.db` for direct database inspection

## Tips and Best Practices

1. **Always use `grocery jobs daily-snapshot`** for full pipeline runs - it handles backup and cleanup automatically
2. **Use `COALESCE(current_price, price_before_bonus)`** for all price queries to get effective prices
3. **Stop the server before running scrapes** to avoid WAL lock contention
4. **Use the intelligence API** for complex queries instead of writing raw SQL
5. **Enable cross-filtering** in the dashboard for powerful data exploration
6. **Check logs regularly** for early detection of issues
7. **Run `ANALYZE` and `VACUUM`** periodically for database health
8. **Use `temp_db` fixture** for tests, not manual session management

## Quick Reference Card

| Task | Command |
|------|---------|
| Full scrape | `grocery jobs daily-snapshot` |
| Quick stats | `python3 -m grocery.cli query stats` |
| Cheapest per gram | `python3 -m grocery.cli query cheapest-unit g` |
| Start server | `python3 -c "from grocery.api.app import create_app; import uvicorn; uvicorn.run(create_app(), host='0.0.0.0', port=8000)"` |
| Rebuild intelligence | `grocery jobs rebuild-derived` |
| Check migrations | `python3 -c "from grocery.migrations import migration_status; print(migration_status())"` |
| Backup DB | `cp data/grocery.db data/grocery-$(date +%Y%m%d-%H%M%S).db` |
| Connect to DB | `sqlite3 data/grocery.db` |
| View logs | `tail -f data/daily-snapshot.log` |
| Test intelligence | `python -m pytest tests/test_intelligence_features.py -v` |
| Recompute intelligence | `curl http://localhost:8000/api/intelligence/recompute` |
| External dashboard | `/tmp/cloudflared tunnel --url http://localhost:8000` |