import { useDomains } from '../lib/domains';

export default function DomainSelect() {
  const { domains, current, setCurrent } = useDomains();
  return (
    <select
      value={current}
      onChange={(e) => setCurrent(e.target.value)}
      aria-label="Dominio"
    >
      {domains.map((d) => (
        <option key={d.id} value={d.id}>{d.label}</option>
      ))}
    </select>
  );
}
