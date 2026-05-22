import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useCheapest, useCategories } from '../lib/api';
import { Card, Loading, ErrorBox, EmptyState, Badge } from '../components/ui';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export function CheapestPage() {
  const [rankType, setRankType] = useState('cheapest_price');
  const [category, setCategory] = useState('');
  const [limit, setLimit] = useState(15);

  const catQ = useQuery(useCategories());
  const cheapQ = useQuery(useCheapest(rankType, category || undefined, undefined, limit));

  const rankings = cheapQ.data?.rankings ?? [];
  const categories = catQ.data?.categories ?? [];

  return (
    <div className="space-y-6">
      {/* Filters */}
      <Card title="">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Ranking</label>
            <select
              className="rounded-lg border px-3 py-1.5 text-sm"
              style={{ background: 'var(--card-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
              value={rankType} onChange={e => setRankType(e.target.value)}
            >
              <option value="cheapest_price">Cheapest Price</option>
              <option value="most_expensive_price">Most Expensive Price</option>
              <option value="cheapest_unit_price">Cheapest Unit Price</option>
              <option value="cheapest_healthy">Cheapest Healthy</option>
              <option value="best_deal">Best Deal</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Category</label>
            <select
              className="rounded-lg border px-3 py-1.5 text-sm"
              style={{ background: 'var(--card-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
              value={category} onChange={e => setCategory(e.target.value)}
            >
              <option value="">All Categories</option>
              {categories.map(c => (
                <option key={c.category} value={c.category}>{c.category}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Top</label>
            <select
              className="rounded-lg border px-3 py-1.5 text-sm"
              style={{ background: 'var(--card-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
              value={limit} onChange={e => setLimit(Number(e.target.value))}
            >
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>
          <span className="text-sm" style={{ color: 'var(--muted)' }}>{rankings.length} results</span>
        </div>
      </Card>

      {/* Top cheapest chart */}
      <Card title="Cheapest Products" metric={`by ${rankType.replace(/_/g, ' ')}`}>
        {rankings.length > 0 ? (
          <ResponsiveContainer width="100%" height={Math.min(rankings.length * 28, 400)}>
            <BarChart data={rankings.slice().sort((a, b) => a.currentPrice - b.currentPrice)} layout="vertical">
              <XAxis type="number" tick={{ fill: '#8b949e', fontSize: 10 }} tickFormatter={v => `€${v}`} />
              <YAxis type="category" dataKey="productTitle" width={160} tick={{ fill: '#e6edf3', fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }}
                formatter={(v: any) => [`€${Number(v).toFixed(2)}`, 'Price']}
              />
              <Bar dataKey="currentPrice" fill="#3fb950" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : cheapQ.isLoading ? <Loading /> : <EmptyState />}
      </Card>

      {/* Table */}
      <Card title="Rankings" metric={`${rankings.length} products`}>
        {cheapQ.error && <ErrorBox message={cheapQ.error.message} />}
        {rankings.length > 0 ? (
          <div className="overflow-x-auto" style={{ maxHeight: 500 }}>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>#</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Product</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Brand</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Category</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Price</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Unit Price</th>
                </tr>
              </thead>
              <tbody>
                {rankings.map(r => (
                  <tr key={r.productId} className="border-b hover:bg-white/[0.03] transition-colors" style={{ borderColor: 'var(--border)' }}>
                    <td className="py-2 px-2">
                      {r.rank <= 3 ? <Badge color={r.rank === 1 ? 'green' : r.rank === 2 ? 'blue' : 'purple'}>#{r.rank}</Badge> : <span className="text-xs" style={{ color: 'var(--muted)' }}>#{r.rank}</span>}
                    </td>
                    <td className="py-2 px-2">
                      <a href={r.ahUrl} target="_blank" rel="noopener" className="hover:underline" style={{ color: 'var(--text)' }}>{r.productTitle}</a>
                    </td>
                    <td className="py-2 px-2 text-xs" style={{ color: 'var(--muted)' }}>{r.brand}</td>
                    <td className="py-2 px-2 text-xs" style={{ color: 'var(--muted)' }}>{r.mainCategory} / {r.subCategory}</td>
                    <td className="py-2 px-2 text-right font-mono font-medium" style={{ color: 'var(--down)' }}>€{r.currentPrice?.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono text-xs" style={{ color: 'var(--muted)' }}>{r.unitPrice ? `€${r.unitPrice.toFixed(2)}/${r.baseUnit}` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : !cheapQ.isLoading ? <EmptyState /> : null}
      </Card>
    </div>
  );
}