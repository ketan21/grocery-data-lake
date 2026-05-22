// API response types for the Grocery Data Lake

// ─── Stats ───
export interface ScrapeRun {
  startedAt: string;
  completedAt: string;
  productsScraped: number;
  status: string;
}

export interface Stats {
  totalProducts: number;
  totalCategories: number;
  uniqueBrands: number;
  bonusProducts: number;
  priceRange: { min: number; max: number; avg: number };
  lastScrapeRun: ScrapeRun;
}

// ─── Categories ───
export interface Category {
  category: string;
  productCount: number;
  bonusCount: number;
  bonusSharePct: number;
  avgDiscountPct: number;
  maxDiscountPct: number;
}

export interface CategoriesResponse {
  categories: Category[];
}

// ─── Brands ───
export interface Brand {
  brand: string;
  productCount: number;
  categoryCount: number;
  avgPrice: number;
  bonusCount?: number;
  avgUnitPrice?: number;
  avgHealthScore: number | null;
  bonusSharePct?: number;
  avgDiscountPct?: number;
  priceVolatility?: number;
  privateLabelCandidate?: boolean;
}

export interface BrandsResponse {
  brands: Brand[];
}

// ─── Bonus Overview ───
export interface BonusOverview {
  categories: Category[];
  topDeals: Deal[];
}

// ─── Deals ───
export interface Deal {
  productId: number;
  productTitle: string;
  brand: string;
  mainCategory: string;
  currentPrice: number;
  priceBeforeBonus: number;
  discountPct: number;
  avgPrice: number;
  historicalLowPrice: number;
  currentVsAvgPct: number;
  currentVsLowPct: number;
  priceVolatility: number | null;
  dealScore: number;
  dealLabel: string;
  ahUrl: string;
}

export interface DealsResponse {
  total: number;
  offset: number;
  limit: number;
  deals: Deal[];
}

// ─── Nutrition ───
export interface NutritionProduct {
  productId: number;
  productTitle: string;
  brand: string;
  mainCategory: string;
  currentPrice: number | null;
  caloriesPer100g: number | null;
  sugarPer100g: number | null;
  saltPer100g: number | null;
  saturatedFatPer100g: number | null;
  proteinPer100g: number | null;
  fiberPer100g: number | null;
  nutriscore: string;
  healthScore: number;
  proteinPerEuro: number | null;
  fiberPerEuro: number | null;
  sugarRiskLevel: string;
  saltRiskLevel: string;
  saturatedFatRiskLevel: string;
  ahUrl: string;
}

export interface NutritionResponse {
  total: number;
  offset: number;
  limit: number;
  products: NutritionProduct[];
}

// ─── Health Value ───
export interface HealthValueRanking {
  productId: number;
  productTitle: string;
  brand: string;
  mainCategory: string;
  subCategory: string;
  currentPrice: number;
  unitPrice: number | null;
  healthScore: number;
  healthValueScore: number;
  nutriscore: string;
  proteinPerEuro: number | null;
  fiberPerEuro: number | null;
  rankInCategory: number;
  ahUrl: string;
}

export interface HealthValueResponse {
  rankingType: string;
  category: string | null;
  total: number;
  rankings: HealthValueRanking[];
}

// ─── Cheapest ───
export interface CheapestRanking {
  rank: number;
  productId: number;
  productTitle: string;
  brand: string;
  mainCategory: string;
  subCategory: string;
  currentPrice: number;
  unitPrice: number | null;
  baseUnit: string;
  ahUrl: string;
}

export interface CheapestResponse {
  rankingType: string;
  category: string | null;
  total: number;
  rankings: CheapestRanking[];
}

// ─── Ingredient Flags ───
export interface IngredientFlags {
  productId: number;
  productTitle: string;
  brand: string;
  mainCategory?: string;
  ingredientCount: number;
  containsAddedSugar: boolean;
  containsPalmOil: boolean;
  containsSweeteners: boolean;
  containsPreservatives: boolean;
  containsEmulsifiers: boolean;
  containsColourants: boolean;
  containsSeedOils: boolean;
  containsCaffeine: boolean;
  possibleVegan: boolean;
  possibleVegetarian: boolean;
  cleanLabelScore: number;
  ultraProcessedScore: number;
  ahUrl: string;
}

export interface IngredientFlagsResponse {
  total: number;
  offset: number;
  limit: number;
  products: IngredientFlags[];
}

// ─── Allergen Summary ───
export interface AllergenSummary {
  productId: number;
  productTitle: string;
  brand: string;
  containsGluten: boolean;
  containsMilk: boolean;
  containsNuts: boolean;
  containsPeanuts: boolean;
  containsSoy: boolean;
  containsEgg: boolean;
  containsFish: boolean;
  containsShellfish: boolean;
  containsCount: number;
  allergenRiskScore: number;
  ahUrl: string;
}

export interface AllergenResponse {
  total: number;
  offset: number;
  limit: number;
  products: AllergenSummary[];
}

// ─── Brand Intelligence ───
export interface BrandIntelligence {
  brand: string;
  productCount: number;
  categoryCount: number;
  avgPrice: number;
  avgUnitPrice: number;
  avgHealthScore: number | null;
  bonusSharePct: number;
  avgDiscountPct: number;
  priceVolatility: number;
  privateLabelCandidate: boolean;
}

export interface BrandIntelligenceResponse {
  total: number;
  offset: number;
  limit: number;
  brands: BrandIntelligence[];
}

// ─── Product Alternatives ───
export interface Alternative {
  alternativeProductId: number;
  alternativeTitle: string;
  alternativeBrand: string;
  alternativeType: string;
  alternativeCategory: string;
  alternativePrice: number;
  priceSavingPct: number;
  unitPriceSavingPct: number | null;
  healthScoreDelta: number | null;
  confidence: number;
  explanation: string;
}

export interface AlternativesResponse {
  productId: number;
  total: number;
  alternatives: Alternative[];
}

// ─── Price Changes (for main dashboard) ───
export interface PriceChange {
  productId: number;
  name: string;
  brand: string;
  category: string;
  isBonus: boolean;
  previousPrice: number;
  effectivePrice: number;
  priceChange: number;
  priceChangePct: number;
  ahUrl: string;
}

export interface PriceChangesResponse {
  changes: PriceChange[];
}

// ─── Volatility ───
export interface VolatilityProduct {
  productId: number;
  name: string;
  brand: string;
  category: string;
  currentPrice: number;
  avgPrice: number;
  volatility: number;
  totalChanges: number;
}

export interface VolatilityResponse {
  products: VolatilityProduct[];
}

// ─── Timeline ───
export interface TimelinePoint {
  category: string;
  runId: number;
  avgPrice: number;
}

export interface TimelineResponse {
  points: TimelinePoint[];
}

// ─── Unit Prices ───
export interface UnitPrice {
  productId: number;
  name: string;
  brand: string;
  category: string;
  currentPrice: number;
  unitPrice: number;
  baseUnit: string;
}

export interface UnitPricesResponse {
  products: UnitPrice[];
}

// ─── Price Distribution ───
export interface PriceDistribution {
  category: string;
  productCount: number;
  bonusCount: number;
  bonusSharePct: number;
  avgDiscountPct: number;
  maxDiscountPct: number;
}

// ─── Search ───
export interface ProductSearchResult {
  webshopId: number;
  title: string;
  brand: string;
  mainCategory: string;
  subCategory: string;
  currentPrice: number;
  priceBeforeBonus: number | null;
  isBonus: boolean;
  ahUrl: string;
}

export interface SearchResponse {
  total: number;
  products: ProductSearchResult[];
}

// ─── Viz brands (lighter) ───
export interface VizBrand {
  brand: string;
  productCount: number;
  categoryCount: number;
  avgPrice: number;
  bonusCount: number;
}