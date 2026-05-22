import { type ReactNode } from 'react';

interface CardProps {
  title: string;
  metric?: string;
  children: ReactNode;
  className?: string;
}

export function Card({ title, metric, children, className = '' }: CardProps) {
  return (
    <div className={`rounded-xl border p-4 ${className}`} style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{title}</h2>
        {metric && <span className="text-xs" style={{ color: 'var(--muted)' }}>{metric}</span>}
      </div>
      {children}
    </div>
  );
}

export function StatCard({ value, label, color }: { value: string | number; label: string; color?: string }) {
  return (
    <div className="rounded-xl border p-4" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
      <div className="text-2xl font-bold" style={{ color: color || 'var(--text)' }}>
        {typeof value === 'number' ? value.toLocaleString('nl-NL') : value}
      </div>
      <div className="text-xs uppercase tracking-wide mt-1" style={{ color: 'var(--muted)' }}>{label}</div>
    </div>
  );
}

export function Badge({ children, color = 'blue' }: { children: ReactNode; color?: string }) {
  const colors: Record<string, string> = {
    green: 'bg-green-500/15 text-green-400',
    blue: 'bg-blue-500/15 text-blue-400',
    yellow: 'bg-yellow-500/15 text-yellow-400',
    orange: 'bg-orange-500/15 text-orange-400',
    red: 'bg-red-500/15 text-red-400',
    purple: 'bg-purple-500/15 text-purple-400',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase whitespace-nowrap ${colors[color] || colors.blue}`}>
      {children}
    </span>
  );
}

export function NutriScoreBadge({ score }: { score: string }) {
  const colors: Record<string, string> = {
    A: 'bg-green-600 text-white',
    B: 'bg-lime-500 text-black',
    C: 'bg-yellow-500 text-black',
    D: 'bg-orange-500 text-white',
    E: 'bg-red-500 text-white',
  };
  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-sm font-bold ${colors[score] || 'bg-gray-500 text-white'}`}>
      {score}
    </span>
  );
}

export function ScoreBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100);
  const fill = value >= 70 ? 'bg-green-500' : value >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg)' }}>
      <div className={`h-full rounded-full ${fill}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

interface TableProps {
  headers: string[];
  children: ReactNode;
}

export function Table({ headers, children }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
            {headers.map(h => (
              <th key={h} className="text-left py-2.5 px-3 text-xs uppercase tracking-wide font-medium" style={{ color: 'var(--muted)' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function TableRow({ children }: { children: ReactNode }) {
  return (
    <tr className="border-b hover:bg-white/[0.03] transition-colors" style={{ borderColor: 'var(--border)' }}>
      {children}
    </tr>
  );
}

export function Cell({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <td className={`py-2.5 px-3 ${className}`}>{children}</td>;
}

export function Loading() {
  return (
    <div className="flex items-center justify-center py-12" style={{ color: 'var(--muted)' }}>
      <div className="animate-spin h-5 w-5 border-2 border-current border-t-transparent rounded-full mr-2" />
      Loading...
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
      ⚠️ {message}
    </div>
  );
}

export function EmptyState({ message = 'No data available' }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-12 text-sm" style={{ color: 'var(--muted)' }}>
      {message}
    </div>
  );
}