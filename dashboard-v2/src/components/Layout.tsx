import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, Tag, Heart, Leaf, Building2, ArrowDownNarrowWide,
  ArrowLeftRight, RefreshCw
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useStats } from '../lib/api';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/deals', label: 'Deals', icon: Tag },
  { to: '/health', label: 'Health', icon: Heart },
  { to: '/ingredients', label: 'Ingredients', icon: Leaf },
  { to: '/brands', label: 'Brands', icon: Building2 },
  { to: '/cheapest', label: 'Cheapest', icon: ArrowDownNarrowWide },
  { to: '/alternatives', label: 'Alternatives', icon: ArrowLeftRight },
];

export function Layout() {
  const statsQuery = useQuery(useStats());

  const formatNum = (n: number) => n.toLocaleString('nl-NL');

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 border-r flex flex-col" style={{ borderColor: 'var(--border)', background: 'var(--card)' }}>
        <div className="p-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <h1 className="text-lg font-bold tracking-tight" style={{ color: 'var(--text)' }}>
            Grocery Intel
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
            {statsQuery.data
              ? `${formatNum(statsQuery.data.totalProducts)} products · ${formatNum(statsQuery.data.bonusProducts)} on bonus`
              : 'Loading...'
            }
          </p>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-[var(--accent)] text-[#0f1117] font-semibold'
                    : 'text-[var(--muted)] hover:bg-[var(--card-2)] hover:text-[var(--text)]'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t" style={{ borderColor: 'var(--border)' }}>
          <button
            onClick={() => statsQuery.refetch()}
            className="flex items-center gap-2 text-xs w-full px-3 py-1.5 rounded-md transition-colors"
            style={{ color: 'var(--muted)' }}
          >
            <RefreshCw size={12} className={statsQuery.isFetching ? 'animate-spin' : ''} />
            {statsQuery.isFetching ? 'Refreshing...' : 'Refresh data'}
          </button>
          {statsQuery.data?.lastScrapeRun && (
            <p className="text-[10px] mt-1 px-3" style={{ color: 'var(--muted)' }}>
              Last: {new Date(statsQuery.data.lastScrapeRun.completedAt).toLocaleString('nl-NL')}
            </p>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1440px] mx-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}