import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useDeals } from '../lib/api';
import { Card, Badge, ScoreBar, Loading, ErrorBox, EmptyState } from '../components/ui';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const DEAL_LABELS: Record<string, string> = {
  '': 'All Deals',
  historical_low: 'Historical Low',
  excellent_deal: 'Excellent Deal',
  good_deal: 'Good Deal',
  normal_promotion: 'Normal Promotion',
  weak_promotion: 'Weak Promotion',
};

const DEAL_COLORS: Record<string, string> = {
  historical_low: '#3fb950',
  excellent_deal: '#58a6ff',
  good_deal: '#e3b341',
  normal_promotion: '#d29922',
  weak_promotion: '#f2994a',
  not_a_deal: '#f85149',
};

export function DealsPage() {
  const [label, setLabel] = useState('');
  const [minScore, setMinScore] = useState(0);
  const dealsQ = useQuery(useDeals(label || undefined, minScore, 50));

  const deals = dealsQ.data?.deals ?? [];
  const total = dealsQ.data?.total ?? 0;

  // Distribution data
  const distData = Object.entries(
    deals.reduce<Record<string, number>>((acc, d) => {
      const l = d.dealLabel.replace(/_/g, ' ');
      acc[l] = (acc[l] || 0) + 1;
      return acc;
    }, {})
  ).map(([label, count]) => ({ label, count }));

  return (
    <div className="space-y-6">
      {/* Filters */}
      <Card title="" className="">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex items-center gap-2">
            <label className="text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Deal Quality</label>
            <select
              className="rounded-lg border px-3 py-1.5 text-sm"
              style={{ background: 'var(--card-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
              value={label}
              onChange={e => setLabel(e.target.value)}
            >
              {Object.entries(DEAL_LABELS).map(([val, lbl]) => (
                <option key={val} value={val}>{lbl}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Min Score: {minScore}</label>
            <input
              type="range" min={0} max={100} value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
              className="w-24"
            />
          </div>
          <div className="text-sm" style={{ color: 'var(--muted)' }}>
            {dealsQ.isLoading ? 'Loading...' : `${total.toLocaleString('nl-NL')} deals found`}
          </div>
        </div>
      </Card>

      {/* Distribution chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Deal Quality Distribution">
          {distData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={distData}>
                <XAxis dataKey="label" tick={{ fill: '#8b949e', fontSize: 10 }} angle={-15} textAnchor="end" />
                <YAxis tick={{ fill: '#8b949e', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {distData.map((d, i) => (
                    <Cell key={i} fill={DEAL_COLORS[d.label.replace(/ /g, '_')] || '#58a6ff'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState />}
        </Card>

        <Card title="Best Deals" metric={`${Math.min(deals.length, 25)} shown`} className="lg:col-span-2">
          {dealsQ.error && <ErrorBox message={dealsQ.error.message} />}
          {dealsQ.isLoading && <Loading />}
          {deals.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                    <th className="text-left py-2 px-3 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Product</th>
                    <th className="text-left py-2 px-3 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Brand</th>
                    <th className="text-right py-2 px-3 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Price</th>
                    <th className="text-right py-2 px-3 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Discount</th>
                    <th className="text-left py-2 px-3 text-xs uppercase font-medium" style={{ color: 'var(--muted)' }}>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {deals.slice(0, 25).map(d => (
                    <tr key={d.productId} className="border-b hover:bg-white/[0.03] transition-colors" style={{ borderColor: 'var(--border)' }}>
                      <td className="py-2.5 px-3">
                        <a href={d.ahUrl} target="_blank" rel="noopener" className="hover:underline" style={{ color: 'var(--text)' }}>
                          {d.productTitle}
                        </a>
                      </td>
                      <td className="py-2.5 px-3" style={{ color: 'var(--muted)' }}>{d.brand}</td>
                      <td className="py-2.5 px-3 text-right font-mono font-medium" style={{ color: 'var(--down)' }}>€{d.currentPrice.toFixed(2)}</td>
                      <td className="py-2.5 px-3 text-right" style={{ color: 'var(--muted)' }}>−{d.discountPct.toFixed(1)}%</td>
                      <td className="py-2.5 px-3">
                        <div className="flex items-center gap-2">
                          <Badge color={d.dealLabel === 'historical_low' ? 'green' : d.dealLabel === 'excellent_deal' ? 'blue' : 'yellow'}>
                            {d.dealScore.toFixed(0)}
                          </Badge>
                          <ScoreBar value={d.dealScore} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : !dealsQ.isLoading ? <EmptyState /> : null}
        </Card>
      </div>
    </div>
  );
}