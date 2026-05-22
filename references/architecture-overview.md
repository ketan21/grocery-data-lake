# Architecture Overview

## System Architecture

The Grocery Data Lake project follows a **data pipeline architecture** with clear separation of concerns across extraction, processing, storage, and serving layers.

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Extraction    │    │    Processing    │    │     Storage     │    │     Serving     │
│                 │    │                  │    │                 │    │                 │
│ • AH API Client │───▶│ • Scraper Engine │───▶│   SQLite DB     │───▶│   FastAPI API   │
│ • Rate Limiting │    │ • Data Cleaners  │    │ • 16 Tables     │    │ • Viz Endpoints │
│ • Retry Logic   │    │ • Transformers   │    │ • Intelligence  │    │ • Intelligence  │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └─────────────────┘
                               │                                               │
                               ▼                                               ▼
                       ┌──────────────────┐                            ┌─────────────────┐
                       │   Analytics      │                            │   Dashboard     │
                       │                  │                            │ (D3.js + API)   │
                       │ • Price Metrics  │                            │                 │
                       │ • Brand Analysis │                            │ • Real-time     │
                       │ • Nutrition      │                            │ • Interactive     │
                       │ • Intelligence   │                            │ • Cross-filter  │
                       └──────────────────┘                            └─────────────────┘
```

## Component Architecture

### 1. Data Extraction Layer

**Albert Heijn API Integration**
- **Location:** `grocery/client.py`
- **Pattern:** HTTP client with exponential backoff retry
- **Features:** Automatic token refresh, rate limiting (1.5s between searches, 0.5s between details)
- **Error Handling:** 3 retries with 1/2/4s delays, handles transient failures
- **API Endpoint:** Custom search API with pagination support

**Scraper Components**
- `grocery/scraper.py` - Full catalog and category scrapers
- `grocery/bonus_scraper.py` - Bonus/promotion data scraper
- `grocery/unit_price.py` - Unit price normalization (g, ml, m, m2, stuk)

### 2. Data Processing Layer

**Processing Engine**
- **Location:** `grocery/analytics.py`, `grocery/category_analytics.py`, `grocery/intelligence.py`
- **Pattern:** Modular processors with SQL-based analytics
- **Features:** 
  - Price metrics computation (cheapest, most expensive, volatility)
  - Category and brand inflation analysis
  - Unit price normalization
  - Intelligence analytics (10 different metrics)

**Transformation Pipeline**
1. **Raw Data Cleaning** - Parse API responses, normalize units
2. **Price History Deduplication** - Skip identical snapshots
3. **Analytics Computation** - Generate derived metrics
4. **Intelligence Generation** - Compute advanced analytics

### 3. Data Storage Layer

**Database Design**
- **Engine:** SQLite (27K+ products, 230K+ price snapshots)
- **Location:** `data/grocery.db` (~1.3 GB)
- **Schema:** 16 tables with proper foreign key relationships
- **Migration System:** Custom lightweight migration engine (NOT Alembic)

**Table Structure**
```
products (PK: webshop_id)          ← Main product catalog
price_history (FK: products, scrape_runs) ← Price snapshots
scrape_runs                        ← Scraping run metadata
categories                        ← AH category definitions
nutrition, allergens, ingredients   ← Enriched product data
unit_prices                       ← Normalized unit prices
price_metrics                     ← Computed price statistics
analytics_* (5 tables)            ← Basic analytics
basket_* (3 tables)               ← Basket intelligence
analytics_per_* (4 tables)        ← Intelligence analytics
```

### 4. API Serving Layer

**FastAPI Application**
- **Location:** `grocery/api/app.py`
- **Pattern:** Factory pattern with modular router registration
- **Endpoints:**
  - `/api/viz/*` - Visualization endpoints (8 endpoints)
  - `/api/intelligence/*` - Intelligence endpoints (10 endpoints)

**API Design Principles**
- RESTful design with query parameter filtering
- Consistent response schemas
- Error handling with proper HTTP status codes
- Database connection pooling

### 5. Visualization Layer

**Dashboard Architecture**
- **Technology:** D3.js v7 single-page application
- **Location:** `dashboard/index.html`
- **Features:**
  - 8 interactive charts with cross-filtering
  - Real-time data updates
  - Dark theme design
  - Responsive grid layout
  - Auto-refresh every 5 minutes

**Chart Components**
1. Category breakdown (heatmap)
2. Brand distribution (treemap)
3. Price distribution (histogram)
4. Price timeline (line chart)
5. Price changes (scatter plot)
6. Unit prices (bar chart)
7. Bonus overview (pie chart)
8. Price volatility (bar chart)

## Technical Implementation Details

### Data Flow

1. **Extraction:** 
   - AH API client fetches product data with rate limiting
   - Scraper creates scrape runs and populates products/price_history
   - Bonus scraper updates promotional data

2. **Processing:**
   - Analytics engine reads from products and price_history
   - Computes price metrics and stores in analytics tables
   - Intelligence engine generates advanced analytics

3. **Serving:**
   - FastAPI serves data through REST endpoints
   - Dashboard fetches data via AJAX calls
   - Intelligence endpoints provide filtered queries

4. **Visualization:**
   - D3.js renders charts based on API data
   - Cross-filtering updates all charts simultaneously
   - Real-time updates via periodic data refresh

### Key Design Decisions

**1. SQLite vs PostgreSQL**
- **Choice:** SQLite for simplicity and zero-config deployment
- **Trade-offs:** Limited concurrent access, but sufficient for single-user analysis
- **Scaling Path:** Easy migration path to PostgreSQL if needed

**2. Custom Migrations vs Alembic**
- **Choice:** Custom lightweight migration engine
- **Rationale:** Avoids external dependencies, fully controllable
- **Implementation:** Version-based migrations with rollback capability

**3. Modular Analytics vs Monolithic Processing**
- **Choice:** Modular approach with separate intelligence features
- **Benefits:** Independent computation, easier testing and debugging
- **Pattern:** Each intelligence feature in separate function/table

**4. SQL-based Analytics vs In-Memory Processing**
- **Choice:** SQL-based computation for analytics
- **Rationale:** Leverages database optimizations, handles large datasets efficiently
- **Pattern:** Complex queries with proper indexing

### Performance Considerations

**Database Performance**
- Proper indexing on frequently queried columns
- Pagination for large result sets
- Connection pooling in FastAPI

**API Performance**
- Efficient query patterns with proper joins
- Prepared statements for repeated queries
- Response caching for static data

**Dashboard Performance**
- Lazy loading of chart data
- Debounced filtering to prevent excessive updates
- Optimized D3.js rendering patterns

### Error Handling Strategy

**Graceful Degradation**
- API continues serving partial data on errors
- Dashboard shows error states without breaking
- Analytics computation continues on individual failures

**Retry Logic**
- Exponential backoff for API calls
- Circuit breaker pattern for external services
- Dead letter queue for failed items

## Integration Points

### External Dependencies

**Albert Heijn API**
- Primary data source
- Rate limiting and authentication handled internally
- No external API keys required

**Service Integration**
- Daily cron job via system crontab
- Cloudflared for external dashboard access
- No external service dependencies

### Internal Dependencies

**Database Schema Evolution**
- Additive migrations only
- Backward compatibility maintained
- All code paths handle missing columns gracefully

**API Versioning**
- Forward-compatible API design
- New features added as optional parameters
- No breaking changes to existing endpoints

## Scalability Considerations

### Current Capacity
- **Products:** 27K+ (tested)
- **Price Snapshots:** 230K+ (tested)
- **Database Size:** 1.3GB (current)
- **Response Times:** Sub-second for all endpoints

### Future Scaling Paths

**1. Database Scaling**
- Migration to PostgreSQL for concurrent access
- Partitioning for price_history table
- Read replicas for analytics workloads

**2. API Scaling**
- Caching layer (Redis) for frequent queries
- Load balancing for multiple API instances
- CDN for dashboard static assets

**3. Processing Scaling**
- Asynchronous processing for analytics
- Message queue for large batch operations
- Parallel processing for category scraping

## Security Architecture

### Data Security
- **Local Storage:** All data stored locally
- **No External Transfer:** Data never leaves the system
- **Encryption:** SQLite encryption available if needed

### API Security
- **Access Control:** Local network access only
- **Rate Limiting:** Built into client
- **Input Validation:** SQL injection protection

### Infrastructure Security
- **Process Isolation:** Runs in isolated Python environment
- **Network Isolation:** No external network dependencies
- **File System:** Restricted file permissions