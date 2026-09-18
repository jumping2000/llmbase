import { useState, useEffect } from 'react';
import { Icon } from '../components/Icon';
import { Markdown } from '../components/Markdown';
import { Shimmer } from '../components/Loading';
import { OrphanFixList } from '../components/OrphanFixList';
import { useLang } from '../lib/lang';
import { api, ApiError, type LintResults, type OrphanEntry } from '../lib/api';

export function Health() {
  const { t } = useLang();
  const [results, setResults] = useState<LintResults | null>(null);
  const [deepReport, setDeepReport] = useState('');
  const [fixes, setFixes] = useState<string[]>([]);
  const [lastCheck, setLastCheck] = useState<string | null>(null);
  const [loadingBasic, setLoadingBasic] = useState(false);
  const [loadingDeep, setLoadingDeep] = useState(false);
  const [loadingFix, setLoadingFix] = useState(false);
  const [loadingClean, setLoadingClean] = useState(false);
  const [cleanResult, setCleanResult] = useState<{ removed: number; slugs: string[] } | null>(null);
  const [orphans, setOrphans] = useState<OrphanEntry[]>([]);
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [orphanMsg, setOrphanMsg] = useState('');
  const [fixingOrphans, setFixingOrphans] = useState(false);

  async function loadOrphans() {
    try {
      const res = await api.getOrphans();
      setOrphans(res.orphans);
    } catch { /* */ }
  }

  /** Store lint results, and fetch linking candidates only if orphans exist —
   *  they cost a full corpus scan. */
  function applyResults(r: LintResults) {
    setResults(r);
    if (r.orphans?.length) loadOrphans();
    else setOrphans([]);
  }

  // Load cached health report on mount
  useEffect(() => {
    api.getHealth().then(res => {
      if (res.report) {
        applyResults(res.report.results);
        setFixes(res.report.fixes_applied || []);
        setLastCheck(res.report.checked_at);
      }
    }).catch(() => {});
  }, []);

  /** Refresh both the counters and the orphan list after a write. */
  async function refreshAfterLink() {
    try {
      const check = await api.lint(false);
      if (check.results) applyResults(check.results);
    } catch { /* */ }
  }

  async function handleLink(slug: string, source?: string) {
    setBusySlug(slug);
    setOrphanMsg('');
    try {
      const res = await api.linkOrphan(slug, source);
      setOrphanMsg(
        res.changed
          ? t('health.orphans.linked', { slug, source: res.source ?? '' })
          : t(`health.orphans.reason.${res.reason}`)
      );
      await refreshAfterLink();
    } catch (e) {
      setOrphanMsg(
        e instanceof ApiError && e.status === 409
          ? t('health.orphans.busy')
          : t('health.orphans.error')
      );
    }
    setBusySlug(null);
  }

  async function handleFixOrphans() {
    setFixingOrphans(true);
    setOrphanMsg('');
    try {
      const res = await api.fixOrphans(10);
      setOrphanMsg(t('health.orphans.fixed', { count: res.fix_count }));
      await refreshAfterLink();
    } catch (e) {
      setOrphanMsg(
        e instanceof ApiError && e.status === 409
          ? t('health.orphans.busy')
          : t('health.orphans.error')
      );
    }
    setFixingOrphans(false);
  }

  async function runBasic() {
    setLoadingBasic(true);
    try {
      const res = await api.lint(false);
      if (res.results) applyResults(res.results);
    } catch { /* */ }
    setLoadingBasic(false);
  }

  async function runDeep() {
    setLoadingDeep(true);
    try {
      const res = await api.lint(true);
      if (res.report) setDeepReport(res.report);
    } catch { /* */ }
    setLoadingDeep(false);
  }

  async function runFix() {
    setLoadingFix(true);
    try {
      const res = await api.lintFix();
      if (res.fixes) {
        // Synchronous response (local dev)
        setFixes(res.fixes);
        const check = await api.lint(false);
        if (check.results) applyResults(check.results);
      } else {
        // Async response (production) — pipeline running in background
        setFixes([res.message || 'Auto-fix pipeline started in background. Refresh in 1-2 minutes.']);
        // Poll for results after delay
        setTimeout(async () => {
          try {
            const check = await api.lint(false);
            if (check.results) applyResults(check.results);
            const health = await api.getHealth();
            if (health.report?.fixes_applied) setFixes(health.report.fixes_applied);
          } catch { /* */ }
          setLoadingFix(false);
        }, 60000);
        return;
      }
    } catch { /* */ }
    setLoadingFix(false);
  }

  async function runClean() {
    setLoadingClean(true);
    try {
      const res = await api.cleanWiki();
      setCleanResult(res);
      // Re-run check
      const check = await api.lint(false);
      if (check.results) applyResults(check.results);
    } catch { /* */ }
    setLoadingClean(false);
  }

  const allCategories = results ? [
    { key: 'structural', label: t('health.cat.structural'), icon: 'architecture', issues: results.structural, color: 'text-primary' },
    { key: 'broken_links', label: t('health.cat.brokenLinks'), icon: 'link_off', issues: results.broken_links, color: 'text-error' },
    { key: 'orphans', label: t('health.cat.orphans'), icon: 'visibility_off', issues: results.orphans, color: 'text-secondary' },
    { key: 'missing_metadata', label: t('health.cat.missingMetadata'), icon: 'label_off', issues: results.missing_metadata, color: 'text-on-surface-variant' },
    { key: 'duplicates', label: t('health.cat.duplicates'), icon: 'content_copy', issues: results.duplicates || [], color: 'text-tertiary' },
    { key: 'stubs', label: t('health.cat.stubs'), icon: 'delete_sweep', issues: results.stubs || [], color: 'text-error' },
    { key: 'uncategorized', label: t('health.cat.uncategorized'), icon: 'category', issues: results.uncategorized || [], color: 'text-on-surface-variant' },
  ] : [];

  const categories = allCategories.filter(c => c.issues && c.issues.length > 0);

  return (
    <div className="p-8 max-w-[900px] mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-headline text-3xl font-bold">{t('health.title')}</h1>
        {lastCheck && (
          <span className="text-[11px] text-outline">
            {t('health.lastCheck')}: {new Date(lastCheck).toLocaleString()}
          </span>
        )}
      </div>

      {/* Actions — Diagnose + Repair */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        <button onClick={runBasic} disabled={loadingBasic}
          className="flex items-center gap-2 px-4 py-3 bg-surface-container border border-outline-variant/30 rounded-xl text-sm hover:border-primary/50 transition-colors disabled:opacity-50">
          <Icon name="health_and_safety" className="text-primary text-[18px]" />
          {loadingBasic ? t('health.checking') : t('health.check')}
        </button>
        <button onClick={runClean} disabled={loadingClean}
          className="flex items-center gap-2 px-4 py-3 bg-surface-container border border-outline-variant/30 rounded-xl text-sm hover:border-error/50 transition-colors disabled:opacity-50">
          <Icon name="delete_sweep" className="text-error text-[18px]" />
          {loadingClean ? t('health.cleaning') : t('health.clean')}
        </button>
        <button onClick={runFix} disabled={loadingFix}
          className="flex items-center gap-2 px-4 py-3 bg-primary/10 border border-primary/20 rounded-xl text-sm hover:bg-primary/20 transition-colors disabled:opacity-50">
          <Icon name="auto_fix_high" className="text-primary text-[18px]" />
          {loadingFix ? t('health.fixing') : t('health.autoFix')}
        </button>
        <button onClick={runDeep} disabled={loadingDeep}
          className="flex items-center gap-2 px-4 py-3 bg-surface-container border border-outline-variant/30 rounded-xl text-sm hover:border-secondary/50 transition-colors disabled:opacity-50">
          <Icon name="psychology" className="text-secondary text-[18px]" />
          {loadingDeep ? t('health.analyzing') : t('health.deepAnalysis')}
        </button>
      </div>

      {/* Clean result */}
      {cleanResult && (
        <div className="bg-tertiary-container/20 border border-tertiary/20 rounded-xl px-5 py-3 mb-6 text-sm">
          <Icon name="check_circle" className="text-tertiary text-[16px] mr-2" />
          {t('health.cleaned', { count: cleanResult.removed })}
          {cleanResult.slugs.length > 0 && (
            <span className="text-outline ml-2">({cleanResult.slugs.slice(0, 5).join(', ')})</span>
          )}
        </div>
      )}

      {/* Fix results */}
      {fixes.length > 0 && (
        <div className="bg-surface-container rounded-xl border border-outline-variant/20 mb-6 p-4">
          <h3 className="text-xs uppercase tracking-widest text-on-surface-variant mb-2">
            {t('health.fixesApplied')} ({fixes.length})
          </h3>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {fixes.map((f, i) => (
              <div key={i} className="text-sm text-on-surface-variant flex items-start gap-2">
                <Icon name="check" className="text-tertiary text-[14px] mt-0.5 flex-shrink-0" />
                {f}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Overview cards */}
      {results && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {allCategories.slice(0, 4).map(c => (
              <div key={c.key} className="bg-surface-container rounded-xl p-4 border border-outline-variant/20 text-center">
                <Icon name={c.icon} className={`text-2xl ${c.color} mb-1`} />
                <div className="text-2xl font-bold">{c.issues?.length ?? 0}</div>
                <div className="text-xs text-on-surface-variant">{c.label}</div>
              </div>
            ))}
          </div>

          {/* Overall status */}
          <div className={`rounded-xl px-5 py-4 mb-8 flex items-center gap-3 ${
            results.total_issues === 0
              ? 'bg-tertiary-container/20 border border-tertiary/20'
              : 'bg-surface-container border border-outline-variant/20'
          }`}>
            <Icon
              name={results.total_issues === 0 ? 'check_circle' : 'warning'}
              className={`text-2xl ${results.total_issues === 0 ? 'text-tertiary' : 'text-error'}`}
            />
            <span className="text-sm">
              {results.total_issues === 0
                ? t('health.allPassed')
                : t('health.issuesFound', { count: results.total_issues })
              }
            </span>
          </div>

          {/* Issue details */}
          {categories.map(c => (
            <div key={c.key} className="mb-6">
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                <Icon name={c.icon} className={`text-[16px] ${c.color}`} />
                {c.label} ({c.issues.length})
              </h3>
              {c.key === 'orphans' ? (
                <>
                  <div className="flex items-center gap-3 mb-2">
                    <button
                      onClick={handleFixOrphans}
                      disabled={fixingOrphans || orphans.length === 0}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-secondary/10 text-secondary hover:bg-secondary/20 transition-colors disabled:opacity-40"
                    >
                      <Icon name="bolt" className="text-[15px]" />
                      {fixingOrphans ? t('health.orphans.working') : t('health.orphans.autoAll', { count: 10 })}
                    </button>
                    {orphanMsg && <span className="text-xs text-on-surface-variant">{orphanMsg}</span>}
                  </div>
                  <OrphanFixList orphans={orphans} busySlug={busySlug} onLink={handleLink} />
                </>
              ) : (
                <div className="bg-surface-container rounded-xl border border-outline-variant/20 divide-y divide-outline-variant/10 max-h-60 overflow-y-auto">
                  {c.issues.slice(0, 50).map((issue: string, i: number) => (
                    <div key={i} className="px-5 py-2.5 text-sm text-on-surface-variant">{issue}</div>
                  ))}
                  {c.issues.length > 50 && (
                    <div className="px-5 py-2.5 text-xs text-outline">{t('health.andMore', { count: c.issues.length - 50 })}</div>
                  )}
                </div>
              )}
            </div>
          ))}
        </>
      )}

      {loadingBasic && <Shimmer lines={4} />}

      {/* Deep report */}
      {loadingDeep && (
        <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/20 mt-6">
          <Shimmer lines={8} />
        </div>
      )}

      {deepReport && !loadingDeep && (
        <div className="mt-6">
          <h2 className="font-headline text-xl font-semibold mb-3 flex items-center gap-2">
            <Icon name="psychology" className="text-secondary" />
            {t('health.deepAnalysis')}
          </h2>
          <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/20">
            <Markdown content={deepReport} />
          </div>
        </div>
      )}

      {!results && !loadingBasic && !deepReport && !loadingDeep && (
        <div className="text-center py-16 text-on-surface-variant">
          <Icon name="health_and_safety" className="text-5xl mb-3 block" />
          <p>{t('health.empty')}</p>
        </div>
      )}
    </div>
  );
}
