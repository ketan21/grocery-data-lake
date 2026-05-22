# Grocery Data Lake — Business Propositions & Monetization Strategy

**Date:** 14 May 2026  
**Analyst:** Astra (Hermes Agent)  
**Dataset:** Albert Heijn (AH) Netherlands — 28,270 products, 275,047 price snapshots, 10 daily scrape runs (9–14 May 2026)

---

## Executive Summary

This document analyzes the commercial value of the grocery-data-lake dataset and proposes six distinct, monetizable business propositions. The dataset is unique in the Dutch market because it combines **daily pricing granularity** with **structured nutrition, allergen, and ingredient intelligence** at full-catalog scale. No existing market research firm (NielsenIQ, IRI, GfK) offers this combination in real time at product-level detail for the Dutch grocery channel.

**Key findings driving the propositions:**

- 1,940 brands tracked with promotion mechanics, frequency, and depth  
- 8,291 products scored for deal quality (6,508 at historical_low right now)  
- 67,114 product-alternative pairs computed (cheaper / healthier / same-brand)  
- 27,416 products flagged for ingredient composition (ultra-processed, clean label, vegan)  
- 140,760 product images + 371,532 raw API responses (full forensic provenance)  
- Private-label price gap: **3.4x cheaper** than national brands on average  
- Several national brands (Dove, L'Oréal Paris Elvive, Rexona) are on bonus **≥90% of the time**, suggesting inflated reference pricing

---

## 1. Data Estate Overview

### Core Tables & Coverage

| Table | Rows | What It Contains |
|---|---|---|
| `products` | 28,270 | Master catalog: title, brand, category, price, bonus, nutriscore, barcode |
| `price_history` | 275,047 | Daily price snapshots per product per scrape run |
| `raw_json` | 371,532 | Full API response audit trail |
| `images` | 140,760 | Product image URLs (≈5 per product) |
| `nutrition` | 171,909 rows | Per-100g nutrition facts (calories, sugar, salt, fat, protein, fiber) |
| `allergens` | 188,177 rows | Allergen declarations (gluten, milk, nuts, soy, egg, fish, shellfish) |
| `ingredients` | 16,332 | Full ingredient lists |
| `unit_prices` | 17,114 | Normalized €/g, €/ml, €/m², €/stuk |
| `price_metrics` | 8,291 | Cheapest / most expensive / volatility per product |
| `analytics_category_price_rankings` | 44,737 | Cheapest / priciest / best unit / healthiest per category |
| `analytics_deal_quality_scores` | 8,291 | Deal labels: historical_low, excellent_deal, good_deal, normal_promotion, weak_promotion |
| `analytics_product_promotion_frequency` | 28,270 | How often each product goes on bonus, avg/max discount |
| `analytics_ingredient_flags` | 27,416 | Added sugar, palm oil, preservatives, vegan, clean label score, ultra-processed score |
| `analytics_allergen_summary` | 13,153 | Allergen risk scores, free-from flags |
| `analytics_product_alternatives` | 67,114 | Cheaper, healthier, same-brand alternatives with confidence scores |
| `analytics_brand_intelligence` | 1,941 | Brand-level metrics: product count, bonus share, avg discount, price volatility |

### Scrape History

10 meaningful daily runs from 9 May to 14 May 2026. Catalog stability is high (±0.2% day-to-day), confirming data integrity.

---

## 2. Competitive Moat

### What NielsenIQ / IRI / GfK Cannot Easily Replicate

1. **Daily granularity + nutrition linkage** — Market research panels sample weekly or monthly. You sample daily and can answer "What happened to the price of gluten-free bread the day after the news story?"

2. **Promotion mechanic decomposition** — Not just "was it on promotion?" but **how**: 50+ unique mechanics tracked (1+1 gratis, 2e halve prijs, 4 stapelen tot 40%, VOOR €0.99, 10% volume voordeel, etc.). This lets you model *promotion elasticity* per mechanic.

3. **Unit price normalization at scale** — Converting AH's irregular pack sizes ("250g + 50g gratis", "6-pack", "per 100 gram") into clean €/g or €/ml is hard. You do it for 17,114 products.

4. **Full forensic provenance** — 371,532 raw API responses mean you can prove any data point originated from AH's own API, not estimation or scraping. This matters for legal defensibility and client trust.

5. **Health + price in a single query** — "Show me the cheapest NutriScore A product in Zuivel" is a question no existing Dutch data provider answers out of the box.

---

## 3. The Six Business Propositions

### Proposition 1: CPG Price Intelligence SaaS  
*"Nielsen for Niche — real-time competitor tracking for FMCG brand managers"*

**Target customers:** Brand managers and trade marketing teams at Unilever, Henkel, Danone, L'Oréal, P&G, Nestlé, and their Dutch distributors.

**What you sell:**
- Competitor price & promotion tracking across 1,940 brands and 28 categories
- Promotion mechanic benchmarking (e.g. Dove is on bonus 91% of the time with 50% avg discount)
- Historical price trajectory reports with volatility metrics
- Category share-of-shelf and share-of-voice trends
- **Alerting:** "NIVEA Q10 day cream dropped 42% this morning — here is the 10-day timeline"
- **Compliance / consumer protection signals:** Brands on permanent "fake" discount (e.g. Laura Biagiotti perfumes on bonus 100% of runs at 65–73% off) — evidence of inflated reference pricing

**Evidence from the data:**
| Brand | Products | Bonus Share | Avg Discount | Insight |
|---|---|---|---|
| Dove | 116 | 91% | 50% | Nearly always on promo — weak pricing power? |
| L'Oréal Paris Elvive | 103 | 100% | 50% | *Always* on bonus; shelf price is fiction |
| Gillette | 30 | 77% | 50% | High discount depth, low product count |
| Prodent | 22 | 55% | 57% | Highest discount *depth* in personal care |
| Rexona | 43 | 98% | 50% | Effectively a permanent promotion brand |

**Pricing model:**
- €500–2,000 / month / brand (weekly reports + alerts)
- €5,000–15,000 / month / category dashboard (10–20 brands)
- Annual contracts (standard FMCG procurement cycle)

**Go-to-market:** LinkedIn outreach to Dutch trade marketing managers. Open with a personalized "Your brand vs competitor" bonus-share chart.

**Risk / mitigation:** CPG clients may question sample bias (single retailer). Mitigate by adding Jumbo and Dirk data (researched, not yet implemented) and framing as "AH channel intelligence" rather than "total market."

---

### Proposition 2: AH Pro — Procurement Intelligence for Food Service & Institutions

**Target customers:** Hospital procurement teams, caterers (compass, Sodexo), defense kitchens, school meal programs, and independent restaurants buying from AH Business.

**What you sell:**
- **"Best Buy per Unit" engine:** cheapest chicken breast per kg, cheapest rice per kg, cheapest olive oil per liter
- **Nutrition-per-euro optimization:** highest protein per euro, highest fiber per euro for institutional meal planning
- **"Buy now or wait?" engine:** based on promo frequency data, estimate probability a product goes on bonus next week
- **Basket cost tracking:** define a "standard hospital kitchen basket" and track cost inflation over time
- **Price volatility warnings:** flag products with unstable pricing (e.g. NIVEA Q10: €11.99 → €20.38) so procurement can lock contracts

**Evidence from the data:**
- Cheapest per gram in catalog: AH Kristalsuiker (€0.0006/g), AH Witte snelkook rijst (€0.0007/g)
- Private label is 3.4× cheaper than national brand (€4.34 vs €14.90 average)
- 12,427 products go on bonus >30% of the time — there are learnable patterns
- Staple categories (Pasta, Rijst, Wereldkeuken) have the *lowest* bonus penetration (19.3%) — meaning their shelf price is closer to "real"

**Pricing model:**
- €300 / month / location for small caterers
- €2,000–5,000 / month for institutional procurement teams
- €50 for one-time "Best Buy" category reports

**Go-to-market:** Partner with Dutch foodservice platforms (Bidfood, Hanos, Sligro) or AH Zakelijk itself as a data layer.

---

### Proposition 3: Deal Engineer — Consumer Subscription App

**Target customers:** Price-conscious Dutch households, students, young families, and people with dietary restrictions (vegan, gluten-free, allergen-sensitive).

**What you sell:**
- **Deal Score on any product:** historical_low (green), normal_promotion (yellow), weak_promotion (red)
- **Nutrition + Allergen filters with price:** "gluten-free pasta under €2" or "vegan cheese on bonus"
- **Promotion prediction:** "This product goes on bonus every 14 days. Last bonus ended 11 May. Expected next bonus: ~18 May."
- **Shopping list price tracker:** add items, get push notification when they hit historical low
- **Alternative suggestions:** "AH Kabeljauwhaas is €9.89 now but was €2.69 on bonus 73% of the time. Consider the Provencaals variant at €6.49 instead."

**Evidence from the data:**
- 6,508 products at historical_low *right now* (e.g. Bonduelle beans at €1.49, was €2.99–€4.79)
- 67,114 alternative pairs already computed with confidence scores
- Product alternatives cover cheaper, healthier, and same-brand options
- 488 vegan products; 16,216 vegetarian products; 13,153 with full allergen data

**Pricing model:**
- **Free tier:** search + basic deal scores
- **€4.99 / month:** shopping list alerts, promotion predictions, nutrition filters
- **Affiliate revenue:** AH.nl referral links (Dutch consumers click through to buy)
- **Sponsored placement:** brands pay for featured placement when users search their category

**Go-to-market:** Dutch personal-finance bloggers, Reddit r/thenetherlands, TikTok "AH hack" creators.

**Risk / mitigation:** AH may block scraping if consumer app scales. Mitigate by using the app as a marketing engine that feeds leads into the higher-margin B2B products.

---

### Proposition 4: Shelf Intelligence — Private Label & Hard Discounter Consulting

**Target customers:** Aldi, Lidl, Action, Plus, and their private-label suppliers (e.g. Royal A-ware, Vezet, HAK).

**What you sell:**
- **Private Label Gap Reports:** categories where AH private label dominates but quality (NutriScore) is low — opportunity for a competitor
- **National Brand Premium Analysis:** by category, the premium national brands command over private label
- **Brand Vulnerability Index:** brands with high bonus share (weak pricing power) + low health scores = easy to undercut
- **Packaging / Positioning Intelligence:** same product, different mechanics across subcategories

**Evidence from the data:**
- Private label (AH brands): 7,553 products, avg €4.34, 27% good NutriScore (A/B)
- National brands: 20,717 products, avg €14.90, only 11% good NutriScore
- Baby en kind: allergen-free products €2.88, with-allergen €6.52 (+126% premium!) — a massive avoidable cost for parents
- Drogisterij: NIVEA, Dove, L'Oréal sit on perpetual 50–100% promo — their "real" price is inflated, exactly where a no-nonsense discounter can undercut permanently

**Pricing model:**
- €10,000–50,000 per engagement for custom category reports
- €500 / month subscription for updated quarterly reports
- Board-room consulting, not mass-market

**Go-to-market:** Cold outreach to category managers at Aldi Nederland and Lidl Nederland. Lead with a single shocking chart (e.g. "Dove is on bonus 91% of the time — here is the 10-day price chart").

---

### Proposition 5: Green Receipt — Sustainability & Nutrition Policy Intelligence

**Target customers:** Voedingscentrum, RIVM, Dutch Diabetes Federation, university food research groups, health insurers (Zilveren Kruis, VGZ), and municipal health services (GGD).

**What you sell:**
- **"Health Tax" report:** how much more does a healthy shopping basket cost per week?
- **Ultra-Processed Food Tracker:** share of AH catalog that is ultra-processed, by category
- **Vegan Premium analysis:** is plant-based actually more expensive? Where is the gap closing?
- **Allergy Cost Burden:** allergen-free baby products cost 126% more than standard equivalents — quantify the "tax on being allergic"
- **Annual State of Nutrition report:** publishable dataset for policy makers

**Evidence from the data:**
- Top health categories: Groente (69.2/100), Vis (66.2/100), Vlees (60.4/100)
- Bottom health: Koek / Snoep / Chocolade (17.5/100)
- 488 vegan products, avg €4.57; 16,216 vegetarian products
- Clean label vs ultra-processed scores computed for 27,416 products
- Allergen-free price premiums vary wildly by category (Bakkerij +32%, Baby +126%, Frisdrank +9.5%)

**Pricing model:**
- €15,000–30,000 / year for annual state-of-nutrition reports
- €3,000–5,000 for custom policy briefings
- Grant-funded research co-productions with universities

**Go-to-market:** Publish one headline report first (e.g. "The Real Cost of Healthy Food in the Netherlands, May 2026"). Press coverage drives inbound leads.

---

### Proposition 6: Grocery API — Developer Platform

**Target customers:** Dutch meal-planning apps, price-comparison sites, diet apps, and food-tech startups.

**What you sell:**
- REST API with search, filters, price history, nutrition, allergens
- Webhook alerts when products change price or go on/off bonus
- Bulk exports for ML training (images + labels + prices)
- SDKs for Python and JavaScript

**Pricing model:**
- $0.02 / API call, or freemium (1,000 calls/month free)
- $500 / month for high-volume access
- $5,000 / month for white-label data licensing

**Go-to-market:** Launch on Product Hunt, Hacker News, and Dutch tech Slack groups. The API already exists (FastAPI at `localhost:8000`); it needs rate limiting, auth keys, and documentation.

---

## 4. Revenue Model Summary

| Proposition | Model | Est. ACV | Sales Motion |
|---|---|---|---|
| 1. CPG SaaS | Monthly / annual subscription | €6K–180K | Outbound B2B, LinkedIn |
| 2. AH Pro | Monthly per location | €3.6K–60K | Channel partners |
| 3. Deal Engineer | Freemium + subscription + affiliate | €60 / user / yr | Inbound, content marketing |
| 4. Shelf Intelligence | Project + retainer | €10K–50K + €6K / yr | Board-room consulting |
| 5. Green Receipt | Annual report + custom | €15K–30K / yr | Grant + inbound |
| 6. Grocery API | Usage-based / licensing | €6K–60K / yr | Developer community |

**Realistic Year-1 revenue scenario:**
- 2 CPG clients at €5K/month = €120K
- 1 institutional client at €3K/month = €36K
- 500 consumer subscribers at €4.99/month = €30K
- 2 policy / research engagements = €20K
- **Total Year 1: ~€206K** with one-person operation and existing infrastructure

---

## 5. Recommended Priority Order

### Phase 1 (Now — Month 1–2): CPG SaaS
**Why first:** Highest revenue per customer, data is already perfect for this use case, and FMCG decision-makers have budget. Build one polished "Brand Battlecard" report (e.g. Dove vs Rexona vs NIVEA in Drogisterij) and use it as a sales asset.

**Deliverable:** A single-page PDF report + a live dashboard URL showing bonus share, discount depth, and price volatility for a target brand.

### Phase 2 (Month 2–3): Consumer App as Marketing Engine
**Why second:** It creates brand awareness, generates backlinks, surfaces new insights you can feed into B2B reports, and provides social proof ("10,000 Dutch households use our deal scores").

**Deliverable:** A minimal web app at `dealengine.nl` with search, deal scores, and a "weekly best deals" email.

### Phase 3 (Month 3–4): Policy Report for Credibility
**Why third:** A published report gets press coverage, inbound leads, and positions you as a thought leader. It also opens grant funding.

**Deliverable:** A 20-page PDF report: "The Real Cost of Healthy Food in the Netherlands — May 2026."

### Phase 4 (Month 4–6): Multi-Retailer Expansion
**Why fourth:** Once revenue from AH-only data proves the model, add Jumbo and Dirk data to remove the "sample bias" objection from CPG clients.

**Deliverable:** Jumbo and Dirk scrapers integrated into the same pipeline.

---

## 6. Immediate Next Steps

1. **Build the "Brand Battlecard" prototype** — choose 3 competing brands in one category, produce a one-page chart + bullet insights
2. **Set up cloudflared tunnel** for remote demo access to the dashboard (`https://xxx.trycloudflare.com/dashboard/`)
3. **Draft 10 LinkedIn outreach messages** targeting Dutch trade marketing managers
4. **Register domain name** for the consumer app (dealengine.nl, ahcheck.nl, or similar)
5. **Create a pricing page** with 3 tiers (Free / Pro / Enterprise)
6. **Add Jumbo & Dirk scrapers** to the pipeline (research already completed in `references/multi-retailer-api-research.md`)

---

## Appendix A: Notable Data Anomalies Worth Investigating

These anomalies surfaced during analysis and may become reportable insights:

1. **Permanent fake discounts:** Several perfume brands (Laura Biagiotti, Elie Saab, Cacharel) are on bonus 100% of observed runs with 65–73% discount. This suggests inflated reference pricing and may be of interest to consumer protection authorities (ACM).

2. **National brand "promotion addiction":** Dove (91%), Rexona (98%), L'Oréal Paris Elvive (100%) are on bonus so frequently that their shelf price is effectively never paid. This is either a pricing strategy or a sign of channel conflict.

3. **Allergen-free premium varies wildly by category:** Baby products +126%, Groente +96%, but Diepvries is -49.9% (allergen-free frozen products are *cheaper*). This suggests category-specific supply-chain dynamics worth exploring.

4. **Private label health paradox:** AH private label has *better* NutriScore distribution (27% A/B) than national brands (11% A/B) despite being 3.4× cheaper. This is a strong consumer story.

5. **Staple categories resist promotion:** Pasta/Rijst/Wereldkeuken (19.3% on bonus) and Bakkerij (12.7%) have the lowest bonus penetration — meaning their shelf price is closer to "real" and less inflated.

---

*End of document.*
