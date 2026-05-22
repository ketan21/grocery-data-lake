const API_BASE = import.meta.env.DEV
  ? 'http://localhost:8000'
  : '';

// In production mode, API is at same origin (FastAPI serves both)
// The dashboard is at /dashboard/ but API is at /api/

const INT_API = `${API_BASE}/api/intelligence`;
const VIZ_API = `${API_BASE}/api/viz`;
const STATS_API = `${API_BASE}/api/stats`;

// Generic fetch helper with error handling
async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText} — ${url}`);
  return res.json();
}

// ─── Stats ───
export function useStats() {
  return { queryKey: ['stats'], queryFn: () => fetchJson<import('./types').Stats>(STATS_API) };
}

// ─── Categories ───
export function useCategories() {
  return { queryKey: ['categories'], queryFn: () => fetchJson<import('./types').CategoriesResponse>(`${VIZ_API}/categories`) };
}

// ─── Brands (viz) ───
export function useBrands(limit = 100) {
  return { queryKey: ['brands', limit], queryFn: () => fetchJson<import('./types').BrandsResponse>(`${VIZ_API}/brands?limit=${limit}`) };
}

// ─── Bonus Overview ───
export function useBonusOverview() {
  return { queryKey: ['bonus-overview'], queryFn: () => fetchJson<import('./types').BonusOverview>(`${VIZ_API}/bonus-overview`) };
}

// ─── Deals ───
export function useDeals(label?: string, minScore?: number, limit = 50) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (label) params.set('label', label);
  if (minScore && minScore > 0) params.set('min_score', String(minScore));
  return {
    queryKey: ['deals', label, minScore, limit],
    queryFn: () => fetchJson<import('./types').DealsResponse>(`${INT_API}/deals?${params}`),
  };
}

// ─── Nutrition Scores ───
export function useNutritionScores(minHealthScore = 0, limit = 20, nutriscores?: string[]) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (minHealthScore > 0) params.set('min_health_score', String(minHealthScore));
  if (nutriscores && nutriscores.length > 0) params.set('nutriscore', nutriscores.join(','));
  return {
    queryKey: ['nutrition-scores', minHealthScore, limit, nutriscores],
    queryFn: () => fetchJson<import('./types').NutritionResponse>(`${INT_API}/nutrition-scores?${params}`),
  };
}

// ─── Health Value ───
export function useHealthValue(limit = 30, rankLimit = 5) {
  return {
    queryKey: ['health-value', limit, rankLimit],
    queryFn: () => fetchJson<import('./types').HealthValueResponse>(`${INT_API}/health-value?limit=${limit}&rank_limit=${rankLimit}`),
  };
}

// ─── Cheapest by Category ───
export function useCheapest(rankingType: string, category?: string, subCategory?: string, rankLimit = 10) {
  const params = new URLSearchParams({ ranking_type: rankingType, rank_limit: String(rankLimit) });
  if (category) params.set('category', category);
  if (subCategory) params.set('sub_category', subCategory);
  return {
    queryKey: ['cheapest', rankingType, category, subCategory, rankLimit],
    queryFn: () => fetchJson<import('./types').CheapestResponse>(`${INT_API}/cheapest-by-category?${params}`),
  };
}

// ─── Ingredient Flags ───
export function useIngredientFlags(filters: {
  vegan?: boolean; vegetarian?: boolean; addedSugar?: boolean;
  palmOil?: boolean; preservatives?: boolean; glutenFree?: boolean;
  foodOnly?: boolean;
  category?: string;
  brand?: string;
  limit?: number;
} = {}) {
  const params = new URLSearchParams({ limit: String(filters.limit || 50) });
  if (filters.vegan) params.set('possible_vegan', 'true');
  if (filters.vegetarian) params.set('possible_vegetarian', 'true');
  if (filters.addedSugar) params.set('contains_added_sugar', 'false');
  if (filters.palmOil) params.set('contains_palm_oil', 'false');
  if (filters.preservatives) params.set('contains_preservatives', 'false');
  if (filters.glutenFree) params.set('gluten_free', 'true');
  if (filters.foodOnly) params.set('food_only', 'true');
  if (filters.category) params.set('category', filters.category);
  if (filters.brand) params.set('brand', filters.brand);
  return {
    queryKey: ['ingredient-flags', filters],
    queryFn: () => fetchJson<import('./types').IngredientFlagsResponse>(`${INT_API}/ingredient-flags?${params}`),
  };
}

// ─── Allergen Summary ───
export function useAllergenSummary(limit = 50) {
  return {
    queryKey: ['allergen-summary', limit],
    queryFn: () => fetchJson<import('./types').AllergenResponse>(`${INT_API}/allergen-summary?limit=${limit}`),
  };
}

// ─── Brand Intelligence ───
export function useBrandIntelligence(limit = 50) {
  return {
    queryKey: ['brand-intelligence', limit],
    queryFn: () => fetchJson<import('./types').BrandIntelligenceResponse>(`${INT_API}/brand-intelligence?limit=${limit}`),
  };
}

// ─── Product Alternatives ───
export function useProductAlternatives(productId: number | null) {
  return {
    queryKey: ['alternatives', productId],
    queryFn: () => fetchJson<import('./types').AlternativesResponse>(`${INT_API}/product-alternatives/${productId}`),
    enabled: productId !== null,
  };
}

// ─── Price Changes ───
export function usePriceChanges(limit = 180) {
  return {
    queryKey: ['price-changes', limit],
    queryFn: () => fetchJson<import('./types').PriceChangesResponse>(`${VIZ_API}/price-changes?limit=${limit}`),
  };
}

// ─── Volatility ───
export function useVolatility() {
  return {
    queryKey: ['volatility'],
    queryFn: () => fetchJson<import('./types').VolatilityResponse>(`${VIZ_API}/volatility`),
  };
}

// ─── Timeline ───
export function useTimeline() {
  return {
    queryKey: ['timeline'],
    queryFn: () => fetchJson<import('./types').TimelineResponse>(`${VIZ_API}/price-timeline`),
  };
}

// ─── Unit Prices ───
export function useUnitPrices(unit = 'g', limit = 180) {
  return {
    queryKey: ['unit-prices', unit, limit],
    queryFn: () => fetchJson<import('./types').UnitPricesResponse>(`${VIZ_API}/unit-prices?unit=${unit}&limit=${limit}`),
  };
}

// ─── Price Distribution ───
export function usePriceDistribution() {
  return {
    queryKey: ['price-distribution'],
    queryFn: () => fetchJson<import('./types').PriceDistribution[]>(`${VIZ_API}/price-distribution`),
  };
}

// ─── Search ───
export function searchProducts(query: string, limit = 20) {
  return fetchJson<import('./types').SearchResponse>(`${API_BASE}/api/products?search=${encodeURIComponent(query)}&limit=${limit}`);
}

// ─── Baskets ───
export function useBaskets() {
  return {
    queryKey: ['baskets'],
    queryFn: () => fetchJson<{ baskets: any[] }>(`${INT_API}/baskets`),
  };
}

export { API_BASE, INT_API, VIZ_API, STATS_API };