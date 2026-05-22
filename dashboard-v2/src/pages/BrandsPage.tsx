import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useBrandIntelligence } from '../lib/api';
import { Card, Badge, Loading, ErrorBox, EmptyState } from '../components/ui';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ScatterChart, Scatter, CartesianGrid } from 'recharts';

export function BrandsPage() {
  const [showPrivate, setShowPrivate] = useState(false);
  const [minHealth, setMinHealth] = useState(0);

  const brandsQ = useQuery(useBrandIntelligence(100));
  const brands = brandsQ.data?.brands ?? [];

  const filtered = brands
    .filter(b => !showPrivate || b.privateLabelCandidate)
    .filter(b => (b.avgHealthScore ?? 0) >= minHealth);

  const topByVolume = [...filtered].sort((a, b) => b.productCount - a.productCount).slice(0, 10);

  const scatterData = filtered
    .filter(b => b.avgHealthScore != null)
    .map(b => ({
      brand: b.brand,
      products: b.productCount,
      health: b.avgHealthScore!,
      bonusShare: b.bonusSharePct,
    }));

  return (
    <div className="space-y-6">
      {/* Filters */}
      <Card title="">
        <div className="flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox" checked={showPrivate}
              onChange={e => setShowPrivate(e.target.checked)}
              className="rounded"
            />
            <span style={{ color: 'var(--text)' }}>Private labels only</span>
          </label>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Min Health:</span>
            <input type="range" min={0} max={100} value={minHealth} onChange={e => setMinHealth(Number(e.target.value))} className="w-24" />
            <span className="text-sm font-mono" style={{ color: 'var(--text)' }}>{minHealth}</span>
          </div>
          <span className="text-sm" style={{ color: 'var(--muted)' }}>{filtered.length} brands</span>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top brands by volume */}
        <Card title="Top Brands by Volume">
          {topByVolume.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={topByVolume.slice().sort((a, b) => a.productCount - b.productCount)} layout="vertical">
                <XAxis type="number" tick={{ fill: '#8b949e', fontSize: 10 }} />
                <YAxis type="category" dataKey="brand" width={100} tick={{ fill: '#e6edf3', fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="productCount" fill="#58a6ff" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState />}
        </Card>

        {/* Health vs Volume scatter */}
        <Card title="Health vs Market Presence">
          {scatterData.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
                <XAxis type="number" dataKey="products" name="Products" tick={{ fill: '#8b949e', fontSize: 10 }} label={{ value: 'Product Count', position: 'insideBottom', offset: -5, style: { fill: '#8b949e', fontSize: 11 } }} />
                <YAxis type="number" dataKey="health" name="Health" tick={{ fill: '#8b949e', fontSize: 10 }} label={{ value: 'Health Score', angle: -90, position: 'insideLeft', style: { fill: '#8b949e', fontSize: 11 } }} />
                <Tooltip
                  contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }}
                  formatter={(value: any, name: any) => [name === 'Products' ? value : Number(value).toFixed(1), name]}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.brand || ''}
                />
                <Scatter data={scatterData} fill="#58a6ff" />
              </ScatterChart>
            </ResponsiveContainer>
          ) : <EmptyState />}
        </Card>
      </div>

      {/* Full brands table */}
      <Card title="Brand Intelligence" metric={`${filtered.length} brands`}>
        {brandsQ.isLoading && <Loading />}
        {brandsQ.error && <ErrorBox message={brandsQ.error.message} />}
        {filtered.length > 0 ? (
          <div className="overflow-x-auto" style={{ maxHeight: 500 }}>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Brand</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Products</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Categories</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Avg Price</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Avg Health</th>
                  <th className="text-right py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Bonus %</th>
                  <th className="text-left py-2 px-2 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Type</th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, 40).map(b => (
                  <tr key={b.brand} className="border-b hover:bg-white/[0.03] transition-colors" style={{ borderColor: 'var(--border)' }}>
                    <td className="py-2 px-2 font-medium" style={{ color: 'var(--text)' }}>{b.brand}</td>
                    <td className="py-2 px-2 text-right font-mono">{b.productCount}</td>
                    <td className="py-2 px-2 text-right font-mono">{b.categoryCount}</td>
                    <td className="py-2 px-2 text-right font-mono">€{b.avgPrice?.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{b.avgHealthScore?.toFixed(1) ?? '—'}</td>
                    <td className="py-2 px-2 text-right font-mono">{b.bonusSharePct?.toFixed(1) ?? 0}%</td>
                    <td className="py-2 px-2">
                      {b.privateLabelCandidate
                        ? <Badge color="blue">Private Label</Badge>
                        : <Badge color="purple">Brand</Badge>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : !brandsQ.isLoading ? <EmptyState /> : null}
      </Card>
    </div>
  );
}