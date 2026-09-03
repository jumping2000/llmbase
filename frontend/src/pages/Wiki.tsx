import { useState, useEffect, useMemo } from 'react';
import { Icon } from '../components/Icon';
import { ArticleCard } from '../components/ArticleCard';
import { Shimmer } from '../components/Loading';
import { api, type Article, type Collection } from '../lib/api';
import { useDomains } from '../lib/domains';

export function Wiki() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [filter, setFilter] = useState('');
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [assignDomain, setAssignDomain] = useState('');
  const [assignMessage, setAssignMessage] = useState('');
  const { domains } = useDomains();

  const loadArticles = async () => {
    try {
      const [a, c] = await Promise.all([
        api.getArticles(),
        api.getCollections(),
      ]);
      setArticles(a);
      setCollections(c);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadArticles();
  }, []);

  const toggleSelect = (slug: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(slug)) {
        next.delete(slug);
      } else {
        next.add(slug);
      }
      return next;
    });
  };

  const handleBulkAssign = async () => {
    if (selected.size === 0 || !assignDomain) return;
    setAssignMessage('');
    try {
      const res = await api.bulkAssignDomain([...selected], assignDomain);
      setSelected(new Set());
      setAssignMessage(`Aggiornati ${res.updated.length} articoli al dominio "${assignDomain}".`);
      await loadArticles();
    } catch (e) {
      setAssignMessage(`Errore: ${e}`);
    }
  };

  const filtered = useMemo(() => {
    return articles.filter(a => {
      const matchesFilter = !filter ||
        a.title.toLowerCase().includes(filter.toLowerCase()) ||
        a.summary?.toLowerCase().includes(filter.toLowerCase());
      const matchesCollection = !selectedCollection ||
        a.tags?.includes(selectedCollection);
      return matchesFilter && matchesCollection;
    });
  }, [articles, filter, selectedCollection]);

  const activeCollection = collections.find(c => c.id === selectedCollection);

  return (
    <div className="flex h-full">
      {/* Collection sidebar */}
      <div className="w-[220px] border-r border-outline-variant/30 p-4 flex-shrink-0 overflow-y-auto hidden md:block">
        <h3 className="text-xs uppercase tracking-widest text-on-surface-variant mb-3">Collections</h3>
        <div
          className={`px-3 py-2 rounded-lg text-sm cursor-pointer mb-1 transition-colors ${
            !selectedCollection ? 'bg-primary-container/30 text-primary font-medium' : 'text-on-surface-variant hover:bg-surface-high'
          }`}
          onClick={() => setSelectedCollection(null)}
        >
          <Icon name="apps" className="text-[16px] mr-2 align-middle" />
          All ({articles.length})
        </div>
        {collections.map(c => (
          <div
            key={c.id}
            className={`px-3 py-2 rounded-lg text-sm cursor-pointer mb-0.5 transition-colors ${
              selectedCollection === c.id ? 'bg-primary-container/30 text-primary font-medium' : 'text-on-surface-variant hover:bg-surface-high'
            }`}
            onClick={() => setSelectedCollection(c.id)}
          >
            {c.label} ({c.count})
          </div>
        ))}
      </div>

      {/* Main content */}
      <div className="flex-1 p-8 overflow-y-auto">
        <div className="max-w-[900px] mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="font-headline text-3xl font-bold">
                {activeCollection ? activeCollection.label : 'Wiki'}
              </h1>
              {activeCollection && (
                <p className="text-sm text-on-surface-variant mt-1">{activeCollection.count} articles</p>
              )}
            </div>

            {/* Mobile collection dropdown */}
            <div className="md:hidden">
              <select
                className="bg-surface-high border border-outline-variant/40 rounded-lg px-3 py-2 text-sm"
                value={selectedCollection || ''}
                onChange={e => setSelectedCollection(e.target.value || null)}
              >
                <option value="">All</option>
                {collections.map(c => (
                  <option key={c.id} value={c.id}>{c.label} ({c.count})</option>
                ))}
              </select>
            </div>
          </div>

          {/* Filter */}
          <div className="relative mb-6">
            <Icon name="filter_list" className="absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[18px]" />
            <input
              type="text"
              placeholder="Filter articles..."
              className="w-full bg-surface-container border border-outline-variant/40 rounded-lg pl-10 pr-4 py-2 text-sm text-on-surface placeholder:text-outline outline-none focus:border-primary/60"
              value={filter}
              onChange={e => setFilter(e.target.value)}
            />
          </div>

          {/* Bulk domain assignment */}
          {selected.size > 0 && (
            <div className="flex flex-wrap items-center gap-3 mb-4 p-3 rounded-lg bg-primary-container/15 border border-primary/20">
              <span className="text-sm text-on-surface-variant">
                {selected.size} selezionat{selected.size === 1 ? 'o' : 'i'}
              </span>
              <select
                value={assignDomain}
                onChange={e => setAssignDomain(e.target.value)}
                className="bg-surface-high border border-outline-variant/40 rounded-lg px-3 py-2 text-sm"
              >
                <option value="">Scegli dominio…</option>
                {domains.map(d => (
                  <option key={d.id} value={d.id}>{d.label}</option>
                ))}
              </select>
              <button
                onClick={handleBulkAssign}
                disabled={!assignDomain}
                className="px-4 py-2 bg-primary text-on-primary rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50"
              >
                Assegna a dominio
              </button>
              <button
                onClick={() => setSelected(new Set())}
                className="text-sm text-on-surface-variant hover:text-on-surface"
              >
                Annulla
              </button>
            </div>
          )}

          {assignMessage && (
            <div className={`rounded-lg px-4 py-3 mb-4 text-sm ${assignMessage.startsWith('Errore') ? 'bg-error-container/20 text-error' : 'bg-tertiary-container/20 text-tertiary'}`}>
              {assignMessage}
            </div>
          )}

          {/* Results */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {loading && Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-surface-container rounded-xl p-5 border border-outline-variant/20">
                <Shimmer lines={3} />
              </div>
            ))}
            {filtered.map(a => (
              <div key={a.slug} className="relative">
                <ArticleCard article={a} />
                <input
                  type="checkbox"
                  checked={selected.has(a.slug)}
                  onChange={() => toggleSelect(a.slug)}
                  className="absolute top-3 right-3 w-4 h-4 accent-primary cursor-pointer"
                  aria-label={`Seleziona ${a.title}`}
                />
              </div>
            ))}
          </div>

          {!loading && filtered.length === 0 && (
            <div className="text-center py-16 text-on-surface-variant">
              <Icon name="search_off" className="text-5xl mb-3 block" />
              <p>No articles match your filter.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
