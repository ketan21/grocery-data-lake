# Grocery Data Lake — Albert Heijn

Scrapes, stores, and serves Albert Heijn product catalog data (pricing, nutrition, allergens, promotions) via a local SQLite database and FastAPI server.

## Quick Start

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run the CLI
grocery --help
```

## Safe Scrape / Enrich Commands

### First-time full scrape (all 28 categories, ~27 700 products)

```bash
# Step 1: Scrape categories (populates the categories table)
grocery scrape categories

# Step 2: Scrape all products (no details — fast, ~5 min)
grocery scrape full

# Step 3: Enrich with nutrition/allergens (slower, ~15 min)
grocery enrich all
```

### Incremental daily scrape (price tracking)

```bash
# Re-scrape all categories; upserts products and records price snapshots
grocery scrape full
```

### Single-category scrape (testing or targeted updates)

```bash
# Scrape one category (e.g. 6401 = Groente, aardappelen)
grocery scrape category 6401

# With detail enrichment
grocery scrape category 6401 --details
```

### Bonus / promotions

```bash
# Scrape current bonus metadata
grocery bonus scrape
```

### Querying data

```bash
# Database statistics
grocery query stats

# Search products
grocery query search "volkoren brood"

# Product detail
grocery query product 6401

# Enrichment stats
grocery query enrich-stats

# Price history overview
grocery query price-history

# Price history for a specific product
grocery query price-history 6401
```

### Serving the API

```bash
# Start FastAPI server (default port 8000)
grocery serve run-server

# Custom port
grocery serve run-server -p 18765
```

## Architecture

```
grocery/
├── api/            # FastAPI routes (products, categories, stats, price-history)
├── cli/            # Typer CLI commands (scrape, query, enrich, bonus, serve)
├── client.py       # AH REST/GraphQL API client
├── config.py       # Configuration (delays, rate limits)
├── db.py           # SQLAlchemy models + SQLite connection
├── migrations.py   # Additive SQLite migrations with version tracking
├── scraper.py      # Full catalog scraper (category-based)
├── enrich.py       # Nutrition/allergen enrichment pipeline
├── bonus_scraper.py # Bonus/promotion scraper
└── models.py       # Pydantic API response models
```

## Database Schema

| Table | Purpose |
|---|---|
| `categories` | 28 AH top-level categories |
| `products` | Product catalog (title, brand, pricing, bonus, images) |
| `nutrition` | Per-product nutrition facts |
| `allergens` | Per-product allergen info (CONTAINS / MAY_CONTAIN / FREE_FROM) |
| `ingredients` | Ingredient statements |
| `price_history` | Price snapshots per scrape run |
| `scrape_runs` | Scrape run metadata |
| `raw_json` | Raw API responses for debugging |

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/products` | Search/filter products |
| `GET /api/products/{id}` | Product detail with nutrition/allergens |
| `GET /api/categories` | List all categories |
| `GET /api/stats` | Database statistics |
| `GET /api/price-history` | Price history overview |
| `GET /api/price-history/{id}` | Per-product price history |
| `GET /api/price-history/{id}/inflation` | Inflation calculation |
| `GET /api/raw-json/{source}/{product_id}` | Raw API response |
| `GET /api/bonus` | Current bonus metadata |

## Rate Limiting

AH API rate-limits global search after ~10 pages. The scraper uses category-based browsing (`taxonomyId`) to avoid this. Default delays:

- Search: 0.3s between requests
- Detail: 0.1s between requests

## Scheduled Scrapes

Set up a daily cron job for automatic price tracking:

```bash
# Via the built-in CLI
hermes cronjob create --prompt "Run 'grocery scrape full' in /home/ubuntu/grocery-data-lake" --schedule "0 9 * * *"
```
