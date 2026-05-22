import { useQuery } from '@tanstack/react-query';
import { useStats, useCategories, useBonusOverview, useDeals, useBrandIntelligence } from '../lib/api';
import { StatCard, Card, Loading, Badge, ErrorBox } from '../components/ui';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend,
} from 'recharts';

const COLORS = ['#58a6ff', '#3fb950', '#e3b341', '#f85149', '#bc79f9', '#f0883e', '#8b949e', '#79c0ff', '#56d4dd', '#7ee787'];

export function OverviewPage() {
  const statsQ = useQuery(useStats());
  const catQ = useQuery(useCategories());
  useQuery(useBonusOverview());
  const dealsQ = useQuery(useDeals('excellent_deal', 0, 10));
  const brandsQ = useQuery(useBrandIntelligence(10));

  if (statsQ.error) return <ErrorBox message={statsQ.error.message} />;

  const stats = statsQ.data;
  const cats = catQ.data?.categories || [];

  // Top 10 categories by bonus share for radar
  const radarData = cats
    .sort((a, b) => b.bonusSharePct - a.bonusSharePct)
    .slice(0, 10)
    .map(c => ({ category: c.category.length > 12 ? c.category.slice(0, 12) + '…' : c.category, bonusShare: Math.round(c.bonusSharePct), discount: Math.round(c.avgDiscountPct) }));

  // Category pie data
  const pieData = cats.slice(0, 10).map(c => ({ name: c.category, value: c.productCount }));

  // Deal distribution
  const dealDist = dealsQ.data?.deals
    ? Object.entries(
        dealsQ.data.deals.reduce<Record<string, number>>((acc, d) => {
          const label = d.dealLabel.replace(/_/g, ' ');
          acc[label] = (acc[label] || 0) + 1;
          return acc;
        }, {})
      ).map(([label, count]) => ({ label, count }))
    : [];

  return (
    <div className="space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard value={stats?.totalProducts ?? '—'} label="Products Tracked" color="var(--accent)" />
        <StatCard value={stats?.bonusProducts ?? '—'} label="On Bonus Now" color="var(--down)" />
        <StatCard value={dealsQ.data?.total ?? '—'} label="Excellent Deals" color="var(--gold)" />
        <StatCard value={stats?.uniqueBrands ?? '—'} label="Brands" color="var(--purple)" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Bonus Radar */}
        <Card title="Bonus Share by Category" metric={`${cats.length} categories`}>
          {radarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#30363d" />
                <PolarAngleAxis dataKey="category" tick={{ fill: '#8b949e', fontSize: 11 }} />
                <PolarRadiusAxis tick={{ fill: '#8b949e', fontSize: 10 }} />
                <Radar name="Bonus %" dataKey="bonusShare" stroke="#58a6ff" fill="#58a6ff" fillOpacity={0.2} />
                <Radar name="Avg Discount %" dataKey="discount" stroke="#3fb950" fill="#3fb950" fillOpacity={0.1} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </RadarChart>
            </ResponsiveContainer>
          ) : <Loading />}
        </Card>

        {/* Deal Distribution */}
        <Card title="Deal Quality Distribution" metric={`${dealsQ.data?.total ?? 0} total deals`}>
          {dealDist.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={dealDist}>
                <XAxis dataKey="label" tick={{ fill: '#8b949e', fontSize: 10 }} angle={-20} textAnchor="end" />
                <YAxis tick={{ fill: '#8b949e', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#e6edf3' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {dealDist.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <Loading />}
        </Card>
      </div>

      {/* Category Products Pie + Top Deals */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Products by Category" metric="Top 10">
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={120} label={({ name, percent }: any) => `${String(name || '').slice(0, 12)} ${((percent || 0) * 100).toFixed(0)}%`} labelLine={false}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <Loading />}
        </Card>

        <Card title="Top Excellent Deals" metric={`${dealsQ.data?.deals?.length ?? 0} shown`}>
          <div className="space-y-2 overflow-y-auto" style={{ maxHeight: 340 }}>
            {dealsQ.data?.deals?.slice(0, 8).map(d => (
              <div key={d.productId} className="flex items-center justify-between py-2 border-b" style={{ borderColor: 'var(--border)' }}>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate" style={{ color: 'var(--text)' }}>
                    <a href={d.ahUrl} target="_blank" rel="noopener" className="hover:underline" style={{ color: 'var(--text)' }}>
                      {d.productTitle}
                    </a>
                  </div>
                  <div className="text-xs" style={{ color: 'var(--muted)' }}>{d.brand} · {d.mainCategory}</div>
                </div>
                <div className="text-right ml-3 flex-shrink-0">
                  <div className="text-sm font-mono font-semibold" style={{ color: 'var(--down)' }}>
                    {d.currentPrice != null ? `€${d.currentPrice.toFixed(2)}` : '—'}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge color={d.dealLabel === 'historical_low' ? 'green' : d.dealLabel === 'excellent_deal' ? 'blue' : 'yellow'}>
                      {d.dealLabel.replace(/_/g, ' ')}
                    </Badge>
                    <span className="text-xs" style={{ color: 'var(--muted)' }}>
                      {d.discountPct != null ? `−${d.discountPct.toFixed(0)}%` : ''}
                    </span>
                  </div>
                </div>
              </div>
            )) || <Loading />}
          </div>
        </Card>
      </div>

      {/* Top Brands chart */}
      <Card title="Top Brands by Volume" metric={`${brandsQ.data?.brands?.length ?? 0} brands`}>
        {(brandsQ.data?.brands ?? []).length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={(brandsQ.data?.brands ?? []).slice(0, 10).sort((a, b) => a.productCount - b.productCount)} layout="vertical">
              <XAxis type="number" tick={{ fill: '#8b949e', fontSize: 10 }} />
              <YAxis type="category" dataKey="brand" width={100} tick={{ fill: '#e6edf3', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1a1d23', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="productCount" fill="#58a6ff" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : <Loading />}
      </Card>
    </div>
  );
}