import { useState } from 'react';
import { Icon } from './Icon';
import { useLang } from '../lib/lang';
import type { OrphanEntry } from '../lib/api';

interface Props {
  orphans: OrphanEntry[];
  busySlug: string | null;
  onLink: (slug: string, source?: string) => void;
}

/**
 * One row per orphan article, with the two ways to give it an incoming link:
 * pick the source yourself, or let the server take the best candidate.
 */
export function OrphanFixList({ orphans, busySlug, onLink }: Props) {
  const { t } = useLang();
  // Only the rows the user actually touched; the rest fall back to the top candidate.
  const [chosen, setChosen] = useState<Record<string, string>>({});

  return (
    <div className="bg-surface-container rounded-xl border border-outline-variant/20 divide-y divide-outline-variant/10 max-h-96 overflow-y-auto">
      {orphans.slice(0, 50).map(o => {
        const source = chosen[o.slug] ?? o.candidates[0]?.slug;
        const busy = busySlug === o.slug;
        const disabled = busy || o.candidates.length === 0;

        return (
          <div key={o.slug} className={`px-5 py-3 ${busy ? 'opacity-50' : ''}`}>
            <div className="flex items-center gap-2 mb-2">
              <a href={`/wiki/${o.slug}`} className="text-sm text-on-surface hover:text-primary truncate">
                {o.title}
              </a>
              {o.is_stub && (
                <span
                  title={t('health.orphans.stubWarning')}
                  className="px-1.5 py-0.5 text-[10px] rounded bg-error/10 text-error flex-shrink-0"
                >
                  stub
                </span>
              )}
            </div>

            {o.candidates.length === 0 ? (
              <p className="text-xs text-outline">{t('health.orphans.noCandidates')}</p>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={source}
                  disabled={busy}
                  aria-label={t('health.orphans.chooseSource')}
                  onChange={e => setChosen(prev => ({ ...prev, [o.slug]: e.target.value }))}
                  className="text-xs bg-surface-low border border-outline-variant/30 rounded-lg px-2 py-1 max-w-[280px]"
                >
                  {o.candidates.map(c => (
                    <option key={c.slug} value={c.slug}>
                      {c.title} — {c.shared_tags.join(', ')}
                    </option>
                  ))}
                </select>

                <button
                  onClick={() => onLink(o.slug, source)}
                  disabled={disabled}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors disabled:opacity-40"
                >
                  <Icon name="link" className="text-[14px]" />
                  {t('health.orphans.apply')}
                </button>

                <button
                  onClick={() => onLink(o.slug)}
                  disabled={disabled}
                  title={t('health.orphans.autoOne')}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg text-on-surface-variant hover:text-primary transition-colors disabled:opacity-40"
                >
                  <Icon name="bolt" className="text-[14px]" />
                  {t('health.orphans.auto')}
                </button>
              </div>
            )}
          </div>
        );
      })}
      {orphans.length > 50 && (
        <div className="px-5 py-2.5 text-xs text-outline">
          {t('health.andMore', { count: orphans.length - 50 })}
        </div>
      )}
    </div>
  );
}
