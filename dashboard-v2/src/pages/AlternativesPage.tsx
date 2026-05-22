import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useProductAlternatives } from '../lib/api';
import { searchProducts } from '../lib/api';
import { Card, Loading, ErrorBox, EmptyState } from '../components/ui';
import type { ProductSearchResult } from '../lib/types';

export function AlternativesPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ProductSearchResult[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedName, setSelectedName] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');

  const altQ = useQuery({
    ...useProductAlternatives(selectedId),
    enabled: selectedId !== null,
  });

  async function handleSearch() {
    if (!query || query.length < 2) return;
    setSearching(true);
    setSearchError('');
    try {
      const data = await searchProducts(query, 10);
      setResults(data.products || []);
    } catch (e: any) {
      setSearchError(e.message);
    } finally {
      setSearching(false);
    }
  }

  const alternatives = altQ.data?.alternatives ?? [];
  const cheaper = alternatives.filter(a => a.alternativeType === 'cheaper_alternative').slice(0, 8);
  const healthier = alternatives.filter(a => a.alternativeType === 'healthier_alternative').slice(0, 8);
  const sameBrand = alternatives.filter(a => a.alternativeType === 'same_brand').slice(0, 8);

  return (
    <div className="space-y-6">
      {/* Search */}
      <Card title="Find Alternatives">
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Search for a product..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            className="flex-1 rounded-lg border px-4 py-2 text-sm"
            style={{ background: 'var(--card-2)', borderColor: 'var(--border)', color: 'var(--text)' }}
          />
          <button
            onClick={handleSearch}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{ background: 'var(--accent)', color: '#0f1117' }}
          >
            Search
          </button>
        </div>

        {/* Results */}
        {searchError && <ErrorBox message={searchError} />}
        {searching && <Loading />}
        {results.length > 0 && !searching && (
          <div className="mt-3 rounded-lg border divide-y" style={{ borderColor: 'var(--border)' }}>
            {results.map(p => (
              <button
                key={p.webshopId}
                onClick={() => { setSelectedId(p.webshopId); setSelectedName(p.title); }}
                className={`w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-white/[0.05] transition-colors ${selectedId === p.webshopId ? 'bg-[var(--accent)]/10' : ''}`}
              >
                <div>
                  <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>{p.title}</div>
                  <div className="text-xs" style={{ color: 'var(--muted)' }}>{p.brand} · €{p.currentPrice?.toFixed(2)} · {p.mainCategory}</div>
                </div>
                <a href={p.ahUrl} target="_blank" rel="noopener" onClick={e => e.stopPropagation()} className="text-xs" style={{ color: 'var(--accent)' }}>AH →</a>
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* Alternatives */}
      {selectedId && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Alternatives for: <span style={{ color: 'var(--accent)' }}>{selectedName}</span>
          </h2>

          {altQ.error && <ErrorBox message={altQ.error.message} />}
          {altQ.isLoading && <Loading />}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Cheaper */}
            <Card title={`Cheaper (${cheaper.length})`}>
              {cheaper.length > 0 ? (
                <div className="space-y-2">
                  {cheaper.map(a => (
                    <div key={a.alternativeProductId} className="p-2 rounded-lg" style={{ background: 'var(--bg)' }}>
                      <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>{a.alternativeTitle}</div>
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>{a.alternativeBrand} · Confidence {a.confidence?.toFixed(0)}%</div>
                      {a.priceSavingPct != null && (
                        <div className="text-xs font-medium" style={{ color: 'var(--down)' }}>
                          {a.priceSavingPct.toFixed(1)}% cheaper
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : !altQ.isLoading ? <EmptyState message="No cheaper alternatives" /> : null}
            </Card>

            {/* Healthier */}
            <Card title={`Healthier (${healthier.length})`}>
              {healthier.length > 0 ? (
                <div className="space-y-2">
                  {healthier.map(a => (
                    <div key={a.alternativeProductId} className="p-2 rounded-lg" style={{ background: 'var(--bg)' }}>
                      <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>{a.alternativeTitle}</div>
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>{a.alternativeBrand} · Confidence {a.confidence?.toFixed(0)}%</div>
                      {a.healthScoreDelta != null && (
                        <div className="text-xs font-medium" style={{ color: 'var(--accent)' }}>
                          +{a.healthScoreDelta.toFixed(1)} health points
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : !altQ.isLoading ? <EmptyState message="No healthier alternatives" /> : null}
            </Card>

            {/* Same brand */}
            <Card title={`Same Brand (${sameBrand.length})`}>
              {sameBrand.length > 0 ? (
                <div className="space-y-2">
                  {sameBrand.map(a => (
                    <div key={a.alternativeProductId} className="p-2 rounded-lg" style={{ background: 'var(--bg)' }}>
                      <div className="text-sm font-medium" style={{ color: 'var(--text)' }}>{a.alternativeTitle}</div>
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>{a.alternativeBrand} · {a.alternativeCategory}</div>
                      {a.priceSavingPct != null && (
                        <div className="text-xs font-medium" style={{ color: 'var(--down)' }}>
                          {a.priceSavingPct.toFixed(1)}% {a.priceSavingPct > 0 ? 'cheaper' : 'more expensive'}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : !altQ.isLoading ? <EmptyState message="No same-brand alternatives" /> : null}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}