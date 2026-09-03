import { useState } from 'react';
import { api } from '../lib/api';
import { useDomains } from '../lib/domains';

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
      <h2>Domini</h2>
      <ul>
        {domains.map((d) => (
          <li key={d.id}>
            {d.label} <code>{d.id}</code>
            {d.id !== 'generale' && (
              <>
                <button onClick={() => rename(d.id, d.label)}>Rinomina</button>
                <button onClick={() => remove(d.id)}>Elimina</button>
              </>
            )}
          </li>
        ))}
      </ul>
      <input
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="Nuovo dominio (es. Lavoro)"
      />
      <button onClick={create}>Crea</button>
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  );
}
