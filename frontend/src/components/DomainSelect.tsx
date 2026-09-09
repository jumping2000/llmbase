import { ALL_DOMAINS, useDomains } from '../lib/domains';
import { useLang } from '../lib/lang';

export default function DomainSelect() {
  const { domains, current, setCurrent } = useDomains();
  const { t } = useLang();
  return (
    <select
      value={current}
      onChange={(e) => setCurrent(e.target.value)}
      aria-label={t('domains.selectLabel')}
    >
      <option value={ALL_DOMAINS}>{t('domains.all')}</option>
      {domains.map((d) => (
        <option key={d.id} value={d.id}>{d.label}</option>
      ))}
    </select>
  );
}
