import { useState } from 'react';
import { api } from '../lib/api';
import { useDomains } from '../lib/domains';
import { Icon } from './Icon';

export default function DomainManager() {
  const { domains, reload } = useDomains();
  const [label, setLabel] = useState('');
  const [error, setError] = useState('');

  const create = async () => {
    if (!label.trim()) return;
    setError('');
    try {
      await api.createDomain(label.trim());
      setLabel('');
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm(`Eliminare il dominio "${id}"? I documenti tornano a "generale".`)) return;
    setError('');
    try {
      await api.deleteDomain(id);
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const rename = async (id: string, currentLabel: string) => {
    const next = window.prompt('Nuovo nome', currentLabel);
    if (next === null || !next.trim()) return;
    setError('');
    try {
      await api.renameDomain(id, next.trim());
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div>
      <ul className="space-y-2 mb-4">
        {domains.map((d) => (
          <li
            key={d.id}
            className="flex items-center justify-between gap-3 rounded-lg bg-surface-high border border-outline-variant/20 px-3 py-2"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm font-medium text-on-surface truncate">{d.label}</span>
              <code className="text-xs text-on-surface-variant">{d.id}</code>
            </div>
            {d.id !== 'generale' ? (
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => rename(d.id, d.label)}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg border border-outline-variant/30 bg-surface-container text-on-surface-variant hover:text-primary hover:border-primary/40 transition-colors"
                >
                  <Icon name="edit" className="text-[14px]" />
                  Rinomina
                </button>
                <button
                  onClick={() => remove(d.id)}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 hover:bg-rose-500/20 transition-colors"
                >
                  <Icon name="delete" className="text-[14px]" />
                  Elimina
                </button>
              </div>
            ) : (
              <span className="text-[11px] uppercase tracking-wider text-outline">default</span>
            )}
          </li>
        ))}
      </ul>

      <div className="flex items-center gap-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') create();
          }}
          placeholder="Nuovo dominio (es. Lavoro)"
          className="flex-1 bg-surface-high border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface placeholder:text-outline focus:outline-none focus:border-primary/50"
        />
        <button
          onClick={create}
          disabled={!label.trim()}
          className="flex items-center gap-1 px-4 py-2 rounded-lg text-sm bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Icon name="add" className="text-[16px]" />
          Crea
        </button>
      </div>

      {error && <p className="mt-2 text-xs text-rose-700 dark:text-rose-300">{error}</p>}
    </div>
  );
}
