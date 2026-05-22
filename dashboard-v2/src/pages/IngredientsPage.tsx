import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useIngredientFlags, useAllergenSummary, useCategories } from '../lib/api';
import { Card, Badge, Loading, ErrorBox, EmptyState, ScoreBar } from '../components/ui';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const TOGGLES = [
  { key: 'vegan', label: 'Vegan', filter: 'possible_vegan' },
  { key: 'vegetarian', label: 'Vegetarian', filter: 'possible_vegetarian' },
  { key: 'addedSugar', label: 'No Added Sugar', filter: 'contains_added_sugar' },
  { key: 'palmOil', label: 'No Palm Oil', filter: 'contains_palm_oil' },
  { key: 'preservatives', label: 'No Preservatives', filter: 'contains_preservatives' },
] as const;

export function IngredientsPage() {
  const [filters, setFilters] = useState<Record<string, boolean>>({
    vegan: false, vegetarian: false, addedSugar: false, palmOil: false, preservatives: false, foodOnly: true,
  });
  const [category, setCategory] = useState<string>('');
  const [brandInput, setBrandInput] = useState<string>('');
  const [brand, setBrand] = useState<string>('');

  // Debounce brand input
  useEffect(() => {
    const t = setTimeout(() => setBrand(brandInput.trim()), 400);
    return () => clearTimeout(t);
  }, [brandInput]);

  const ingredientQ = useQuery(useIngredientFlags({
    vegan: filters.vegan,
    vegetarian: filters.vegetarian,
    addedSugar: filters.addedSugar,
    palmOil: filters.palmOil,
    preservatives: filters.preservatives,
    foodOnly: filters.foodOnly,
    category: category || undefined,
    brand: brand || undefined,
    limit: 50,
  }));

  const allergenQ = useQuery(useAllergenSummary(100));
  const catQ = useQuery(useCategories());

  const categories = catQ.data?.categories ?? [];
  const products = ingredientQ.data?.products ?? [];
  const allergenProducts = allergenQ.data?.products ?? [];

  // Clean label score distribution
  const bins = [0, 20, 40, 60, 80, 100];
  const histogram = bins.slice(0, -1).map((lo, i) => ({
    range: `${lo}-${bins[i + 1]}`,
    count: products.filter(p => (p.cleanLabelScore || 0) >= lo && (p.cleanLabelScore || 0) < bins[i + 1]).length,
  }));

  // Allergen distribution
  const allergenData = [
    { label: 'Gluten', count: allergenProducts.filter(p => p.containsGluten).length, color: '#f0883e' },
    { label: 'Milk', count: allergenProducts.filter(p => p.containsMilk).length, color: '#58a6ff' },
    { label: 'Nuts', count: allergenProducts.filter(p => p.containsNuts).length, color: '#3fb950' },
    { label: 'Peanuts', count: allergenProducts.filter(p => p.containsPeanuts).length, color: '#e3b341' },
    { label: 'Soy', count: allergenProducts.filter(p => p.containsSoy).length, color: '#bc79f9' },
    { label: 'Egg', count: allergenProducts.filter(p => p.containsEgg).length, color: '#f85149' },
    { label: 'Fish', count: allergenProducts.filter(p => p.containsFish).length, color: '#56d4dd' },
  ].filter(d => d.count > 0);

  const hasActiveFilters =
    filters.vegan || filters.vegetarian || filters.addedSugar || filters.palmOil || filters.preservatives ||
    !filters.foodOnly || category || brand;

  function clearAll() {
    setFilters({ vegan: false, vegetarian: false, addedSugar: false, palmOil: false, preservatives: false, foodOnly: true });
    setCategory('');
    setBrandInput('');
    setBrand('');
  }

  return (
    <div className="space-y-6">
      {/* Filter bar */}
      <Card title="">
        <div className="flex flex-col gap-4">
          {/* Row 1: Toggles + Food Only */}
          <div className="flex flex-wrap items-center gap-3">
            {TOGGLES.map(t => (
              <button
                key={t.key}
                onClick={() => setFilters(prev => ({ ...prev, [t.key]: !prev[t.key] }))}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all border ${
                  filters[t.key]
                    ? 'bg-[var(--accent)] text-[#0f1117] border-[var(--accent)]'
                    : 'bg-transparent border-[var(--border)] text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--text)]'
                }`}
              >
                {t.label}
              </button>
            ))}
            <div className="w-px h-6 mx-1" style={{ background: 'var(--border)' }} />
            <button
              onClick={() => setFilters(prev => ({ ...prev, foodOnly: !prev.foodOnly }))}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all border ${
                filters.foodOnly
                  ? 'bg-green-600/20 text-green-400 border-green-600/40'
                  : 'bg-transparent border-[var(--border)] text-[var(--muted)] hover:border-green-600/40 hover:text-green-400'
              }`}
              title="Exclude cleaning, personal care, pet, household, and non-edible items"
            >
              🍽 Food Only
            </button>
          </div>

          {/* Row 2: Category dropdown + Brand input + Clear */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Category select */}
            <div className="flex items-center gap-2">
              <label className="text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Category</label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="px-3 py-1.5 rounded-md text-sm border bg-[#0f1117] outline-none focus:border-[var(--accent)] transition-colors"
                style={{ borderColor: 'var(--border)', color: 'var(--text)', minWidth: 200 }}
              >
                <option value="">All categories</option>
                {categories.map(c => (
                  <option key={c.category} value={c.category}>{c.category} ({c.productCount})</option>
                ))}
              </select>
            </div>

            {/* Brand input */}
            <div className="flex items-center gap-2">
              <label className="text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Brand</label>
              <input
                type="text"
                value={brandInput}
                onChange={e => setBrandInput(e.target.value)}
                placeholder="e.g. AH, Unox, Verstegen..."
                className="px-3 py-1.5 rounded-md text-sm border bg-[#0f1117] outline-none focus:border-[var(--accent)] transition-colors"
                style={{ borderColor: 'var(--border)', color: 'var(--text)', minWidth: 180 }}
              />
              {brand && (
                <button
                  onClick={() => { setBrandInput(''); setBrand(''); }}
                  className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
                >
                  ×
                </button>
              )}
            </div>

            <div className="flex-1" />

            {/* Clear all */}
            {hasActiveFilters && (
              <button
                onClick={clearAll}
                className="px-3 py-1.5 rounded-md text-xs font-medium border hover:bg-white/[0.05] transition-colors"
                style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}
              >
                Clear all filters
              </button>
            )}
          </div>

          {/* Active filter pills */}
          {(category || brand) && (
            <div className="flex flex-wrap items-center gap-2">
              {category && (
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/20">
                  📁 {category}
                </span>
              )}
              {brand && (
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/20">
                  🏷 {brand}
                </span>
              )}
              <span className="text-xs" style={{ color: 'var(--muted)' }}>
                {ingredientQ.data?.total ?? 0} matching products
              </span>
            </div>
          )}
        </div>
      </Card>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Clean Label Score Distribution" metric={`${products.length} products`}>
          {histogram.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={histogram}>
                <XAxis dataKey="range" tick={{ fill: '#8b949e', fontSize: 10 }} />
                <YAxis tick={{ fill: '#8b949e', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" fill="#58a6ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState />}
        </Card>

        <Card title="Allergen Distribution" metric={`${allergenProducts.length} products analyzed`}>
          {allergenData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={allergenData}>
                <XAxis dataKey="label" tick={{ fill: '#8b949e', fontSize: 10 }} />
                <YAxis tick={{ fill: '#8b949e', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {allergenData.map((d, i) => (
                    <Cell key={i} fill={d.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState />}
        </Card>
      </div>

      {/* Products table */}
      <Card title="Ingredient Flags" metric={`${products.length} products`}>
        {ingredientQ.isLoading && <Loading />}
        {ingredientQ.error && <ErrorBox message={ingredientQ.error.message} />}
        {products.length > 0 ? (
          <div className="overflow-x-auto" style={{ maxHeight: 500 }}>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Product</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Category</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Brand</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Flags</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Clean Score</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Ultra-Processed</th>
                </tr>
              </thead>
              <tbody>
                {products.slice(0, 30).map(p => (
                  <tr key={p.productId} className="border-b hover:bg-white/[0.03] transition-colors" style={{ borderColor: 'var(--border)' }}>
                    <td className="py-2 px-2">
                      <a href={p.ahUrl} target="_blank" rel="noopener" className="hover:underline" style={{ color: 'var(--text)' }}>{p.productTitle}</a>
                    </td>
                    <td className="py-2 px-2 text-xs" style={{ color: 'var(--muted)' }}>{p.mainCategory}</td>
                    <td className="py-2 px-2 text-xs" style={{ color: 'var(--muted)' }}>{p.brand}</td>
                    <td className="py-2 px-2">
                      <div className="flex flex-wrap gap-1">
                        {p.possibleVegan && <Badge color="green">Vegan</Badge>}
                        {p.possibleVegetarian && <Badge color="green">Vegetarian</Badge>}
                        {p.containsAddedSugar && <Badge color="red">Sugar</Badge>}
                        {p.containsPalmOil && <Badge color="orange">Palm</Badge>}
                        {p.containsPreservatives && <Badge color="yellow">Preserv</Badge>}
                      </div>
                    </td>
                    <td className="py-2 px-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono">{p.cleanLabelScore?.toFixed(1) ?? '—'}</span>
                        {p.cleanLabelScore != null && <ScoreBar value={p.cleanLabelScore} />}
                      </div>
                    </td>
                    <td className="py-2 px-2 font-mono text-xs">{p.ultraProcessedScore?.toFixed(1) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : !ingredientQ.isLoading ? <EmptyState /> : null}
      </Card>
    </div>
  );
}
