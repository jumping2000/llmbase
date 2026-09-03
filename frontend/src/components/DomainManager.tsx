import { useState } from 'react';
import { api } from '../lib/api';
import { useDomains } from '../lib/domains';
import { Icon } from './Icon';

export default function DomainManager() {
  const { domains, reload } = useDomains();
  const [selected, setSelected] = useState('generale');
  const [label, setLabel] = useState('');
  const [error, setError] = useState('');

  const isDefault = selected === 'generale';
  const selectedDomain = domains.find((d) => d.id === selected);

  const create = async () => {
    if (!label.trim()) return;
    setError('');
    try {
      const created = await api.createDomain(label.trim());
      setLabel('');
      setSelected(created.id);
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const remove = async () => {
    if (!window.confirm(`Eliminare il dominio "${selected}"? I documenti tornano a "generale".`)) return;
    setError('');
    try {
      await api.deleteDomain(selected);
      setSelected('generale');
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const rename = async () => {
    const next = window.prompt('Nuovo nome', selectedDomain?.label ?? selected);
    if (next === null || !next.trim()) return;
    setError('');
    try {
      await api.renameDomain(selected, next.trim());
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="flex-1 min-w-[140px] bg-surface-high border border-outline-variant/30 rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary/50"
        >
          {domains.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label} ({d.id})
            </option>
          ))}
        </select>
        <button
          onClick={rename}
          disabled={isDefault}
          className="flex items-center gap-1 px-2.5 py-2 text-xs rounded-lg border border-outline-variant/30 bg-surface-container text-on-surface-variant hover:text-primary hover:border-primary/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Icon name="edit" className="text-[14px]" />
          Rinomina
        </button>
        <button
          onClick={remove}
          disabled={isDefault}
          className="flex items-center gap-1 px-2.5 py-2 text-xs rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 hover:bg-rose-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Icon name="delete" className="text-[14px]" />
          Elimina
        </button>
      </div>

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
