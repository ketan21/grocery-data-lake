import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNutritionScores, useHealthValue } from '../lib/api';
import { Card, NutriScoreBadge, Loading, ErrorBox, EmptyState } from '../components/ui';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const NUTRI_COLORS: Record<string, string> = {
  A: '#2da44e', B: '#7bc043', C: '#f2c94c', D: '#f2994a', E: '#eb5757',
};

export function HealthPage() {
  const [minScore, setMinScore] = useState(60);
  const [nutriFilters, setNutriFilters] = useState<string[]>([]);

  const nutritionQ = useQuery(useNutritionScores(minScore, 50, nutriFilters));
  const healthQ = useQuery(useHealthValue(30, 5));

  const products = nutritionQ.data?.products ?? [];
  const rankings = healthQ.data?.rankings ?? [];

  // Nutri-Score distribution
  const scoreCounts = products.reduce<Record<string, number>>((acc, p) => {
    if (p.nutriscore) acc[p.nutriscore] = (acc[p.nutriscore] || 0) + 1;
    return acc;
  }, {});
  const nutriData = ['A', 'B', 'C', 'D', 'E'].map(s => ({
    score: s,
    count: scoreCounts[s] || 0,
    fill: NUTRI_COLORS[s],
  }));

  // Filter by nutri if toggles active
  const filteredProducts = nutriFilters.length > 0
    ? products.filter(p => nutriFilters.includes(p.nutriscore))
    : products;

  return (
    <div className="space-y-6">
      {/* Filters */}
      <Card title="">
        <div className="flex flex-wrap items-center gap-4">
          <span className="text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Nutri-Score</span>
          <div className="flex gap-2">
            {['A', 'B', 'C', 'D', 'E'].map(s => (
              <button
                key={s}
                onClick={() => setNutriFilters(prev =>
                  prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
                )}
                className={`w-8 h-8 rounded-full font-bold text-sm transition-all ${
                  nutriFilters.includes(s) ? 'ring-2 ring-offset-1 ring-white scale-110' : 'opacity-60 hover:opacity-100'
                }`}
                style={{ background: NUTRI_COLORS[s], color: s === 'B' || s === 'C' ? '#000' : '#fff' }}
              >
                {s}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 ml-4">
            <label className="text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Min Health Score: {minScore}</label>
            <input type="range" min={0} max={100} value={minScore} onChange={e => setMinScore(Number(e.target.value))} className="w-24" />
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Nutri-Score Distribution */}
        <Card title="Nutri-Score Distribution" metric={`${products.length} products`}>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={nutriData}>
              <XAxis dataKey="score" tick={{ fill: '#8b949e', fontSize: 12 }} />
              <YAxis tick={{ fill: '#8b949e', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {nutriData.map((d, i) => <Cell key={i} fill={d.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Health Value Rankings */}
        <Card title="Health Value Rankings" metric={`${rankings.length} categories`} className="lg:col-span-2">
          {healthQ.isLoading && <Loading />}
          {healthQ.error && <ErrorBox message={healthQ.error.message} />}
          {rankings.length > 0 ? (
            <div className="overflow-x-auto" style={{ maxHeight: 400 }}>
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                    <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Rank</th>
                    <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Product</th>
                    <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Category</th>
                    <th className="text-center py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Nutri</th>
                    <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Health</th>
                    <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Price</th>
                  </tr>
                </thead>
                <tbody>
                  {rankings.slice(0, 20).map(r => (
                    <tr key={r.productId} className="border-b hover:bg-white/[0.03] transition-colors" style={{ borderColor: 'var(--border)' }}>
                      <td className="py-2 px-2 text-xs">#{r.rankInCategory}</td>
                      <td className="py-2 px-2">
                        <a href={r.ahUrl} target="_blank" rel="noopener" className="hover:underline" style={{ color: 'var(--text)' }}>{r.productTitle}</a>
                      </td>
                      <td className="py-2 px-2 text-xs" style={{ color: 'var(--muted)' }}>{r.mainCategory}</td>
                      <td className="py-2 px-2 text-center">{r.nutriscore && <NutriScoreBadge score={r.nutriscore} />}</td>
                      <td className="py-2 px-2 text-right font-mono">{r.healthScore?.toFixed(1)}</td>
                      <td className="py-2 px-2 text-right font-mono">€{r.currentPrice?.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : !healthQ.isLoading ? <EmptyState /> : null}
        </Card>
      </div>

      {/* Nutrition products table */}
      <Card title="Nutrition Scores" metric={`${filteredProducts.length} products (min score: ${minScore})`}>
        {nutritionQ.isLoading && <Loading />}
        {filteredProducts.length > 0 ? (
          <div className="overflow-x-auto" style={{ maxHeight: 500 }}>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Product</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Brand</th>
                  <th className="text-center py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Nutri</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Health</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Cal/100g</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Sugar</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Salt</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Price</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.slice(0, 30).map(p => (
                  <tr key={p.productId} className="border-b hover:bg-white/[0.03] transition-colors" style={{ borderColor: 'var(--border)' }}>
                    <td className="py-2 px-2"><a href={p.ahUrl} target="_blank" rel="noopener" className="hover:underline" style={{ color: 'var(--text)' }}>{p.productTitle}</a></td>
                    <td className="py-2 px-2 text-xs" style={{ color: 'var(--muted)' }}>{p.brand}</td>
                    <td className="py-2 px-2 text-center">{p.nutriscore && <NutriScoreBadge score={p.nutriscore} />}</td>
                    <td className="py-2 px-2 text-right font-mono">{p.healthScore?.toFixed(1)}</td>
                    <td className="py-2 px-2 text-right font-mono text-xs" style={{ color: 'var(--muted)' }}>{p.caloriesPer100g?.toFixed(0) ?? '—'}</td>
                    <td className="py-2 px-2 text-right font-mono text-xs" style={{ color: 'var(--muted)' }}>{p.sugarPer100g?.toFixed(1) ?? '—'}g</td>
                    <td className="py-2 px-2 text-right font-mono text-xs" style={{ color: 'var(--muted)' }}>{p.saltPer100g?.toFixed(2) ?? '—'}g</td>
                    <td className="py-2 px-2 text-right font-mono" style={{ color: p.currentPrice ? 'var(--down)' : 'var(--muted)' }}>{p.currentPrice ? `€${p.currentPrice.toFixed(2)}` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : !nutritionQ.isLoading ? <EmptyState /> : null}
      </Card>
    </div>
  );
}