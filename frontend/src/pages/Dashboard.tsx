import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Shimmer } from '../components/Loading';
import { Markdown } from '../components/Markdown';
import { useLang } from '../lib/lang';
import { api, type CompileStatus, type LlmUsageRecentRequest, type LlmUsageSummary, type LlmUsageWindow, type Stats, type XiCi } from '../lib/api';
import DomainManager from '../components/DomainManager';

const COMPILE_POLL_MS = 3000;
const LLM_USAGE_WINDOWS: Array<{ value: Exclude<LlmUsageWindow, 'custom'>; label: string }> = [
  { value: 'all', label: 'All' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
  { value: '365d', label: '365d' },
];

export function Dashboard() {
  const navigate = useNavigate();
  const { lang } = useLang();
  const it = lang === 'it' || lang === 'en-it';
  const [stats, setStats] = useState<Stats | null>(null);
  const [xici, setXiCi] = useState<XiCi | null>(null);
  const [generating, setGenerating] = useState(false);
  const [compileStatus, setCompileStatus] = useState<CompileStatus>({ status: 'idle' });
  const [llmUsage, setLlmUsage] = useState<LlmUsageSummary | null>(null);
  const [lastLlmRequest, setLastLlmRequest] = useState<LlmUsageRecentRequest | null>(null);
  const [usageWindow, setUsageWindow] = useState<Exclude<LlmUsageWindow, 'custom'>>('all');
  const compilePrevStatus = useRef<CompileStatus['status']>('idle');

  function loadLlmUsage(window: Exclude<LlmUsageWindow, 'custom'> = usageWindow) {
    api.getLlmUsageSummary(window).then(setLlmUsage).catch(() => {});
    api.getLlmUsageRecent(1, window).then(result => setLastLlmRequest(result.requests[0] ?? null)).catch(() => {});
  }

  useEffect(() => {
    api.getStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    api.compileStatus().then(setCompileStatus).catch(() => {});
  }, []);

  useEffect(() => {
    loadLlmUsage(usageWindow);
  }, [usageWindow]);

  useEffect(() => {
    api.getXiCi(lang).then(setXiCi).catch(() => {});
  }, [lang]);

  useEffect(() => {
    if (compilePrevStatus.current === 'running' && compileStatus.status === 'completed') {
      api.getStats().then(setStats).catch(() => {});
      loadLlmUsage(usageWindow);
    }
    compilePrevStatus.current = compileStatus.status;
  }, [compileStatus.status, usageWindow]);

  useEffect(() => {
    if (compileStatus.status !== 'running') return;
    const timer = setInterval(() => {
      api.compileStatus().then(setCompileStatus).catch(() => {});
      loadLlmUsage(usageWindow);
    }, COMPILE_POLL_MS);
    return () => clearInterval(timer);
  }, [compileStatus.status, usageWindow]);

  async function regenerate() {
    setGenerating(true);
    try {
      const result = await api.generateXiCi(lang);
      setXiCi(result);
      loadLlmUsage(usageWindow);
    } catch {}
    setGenerating(false);
  }

  const timeAgo = (iso: string | null) => {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  const compileCard = (() => {
    if (compileStatus.status === 'running') {
      return {
        icon: 'hourglass_top',
        title: it ? 'Compilazione in corso' : 'Compile running',
        detail: compileStatus.started_at ? timeAgo(compileStatus.started_at) : '',
        tone: 'text-primary bg-primary/10 border-primary/20',
        body: it
          ? 'Il job sta aggiornando la knowledge base in background.'
          : 'The job is updating the knowledge base in the background.',
      };
    }
    if (compileStatus.status === 'completed') {
      const count = compileStatus.articles_created ?? 0;
      return {
        icon: 'check_circle',
        title: it ? 'Ultimo compile completato' : 'Last compile completed',
        detail: compileStatus.finished_at ? timeAgo(compileStatus.finished_at) : '',
        tone: 'text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/20',
        body: it
          ? `${count} nuovi articoli creati nell'ultimo run.`
          : `${count} new articles created in the last run.`,
      };
    }
    if (compileStatus.status === 'failed') {
      return {
        icon: 'error',
        title: it ? 'Ultimo compile fallito' : 'Last compile failed',
        detail: compileStatus.finished_at ? timeAgo(compileStatus.finished_at) : '',
        tone: 'text-rose-700 dark:text-rose-300 bg-rose-500/10 border-rose-500/20',
        body: compileStatus.error || (it ? 'Errore sconosciuto.' : 'Unknown error.'),
      };
    }
    return {
      icon: 'schedule',
      title: it ? 'Nessun job in esecuzione' : 'No active background jobs',
      detail: '',
      tone: 'text-on-surface-variant bg-surface-high border-outline-variant/20',
      body: it
        ? 'La pipeline e inattiva. Avvia un compile dalla barra superiore o dalla pagina ingest.'
        : 'The pipeline is idle. Start a compile from the top bar or the ingest page.',
    };
  })();

  const usageTopModel = llmUsage?.by_model[0] ?? null;
  const usageTopFeatures = llmUsage?.by_feature.slice(0, 3) ?? [];
  const usageRetryTokens = llmUsage?.retry_fallback_totals.total_tokens ?? 0;
  const usageSuccessTokens = llmUsage?.successful_totals.total_tokens ?? 0;
  const usageTotalTokens = llmUsage?.totals.total_tokens ?? 0;
  const usageSuccessRate = usageTotalTokens > 0 ? Math.round((usageSuccessTokens / usageTotalTokens) * 100) : 0;
  const lastLlmModels = lastLlmRequest?.actual_models.join(', ') ?? '';

  return (
    <div className="p-8 max-w-[1100px] mx-auto">

      {/* Xi Ci — Guided Introduction */}
      <div className="mb-8 bg-surface-container rounded-xl border border-outline-variant/20 overflow-hidden">
        <div className="p-6 pb-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Icon name="auto_stories" className="text-primary text-[20px]" />
              <span className="text-xs uppercase tracking-widest text-on-surface-variant">
                {it ? 'Lettura guidata' : 'Guided Reading'}
              </span>
            </div>
            <div className="flex items-center gap-3">
              {xici?.generated_at && (
                <span className="text-[11px] text-outline">{timeAgo(xici.generated_at)}</span>
              )}
              <button
                onClick={regenerate}
                disabled={generating}
                className="flex items-center gap-1 px-2.5 py-1 text-xs text-on-surface-variant hover:text-primary rounded-lg hover:bg-surface-container-highest/50 transition-colors disabled:opacity-50"
              >
                <Icon name={generating ? 'hourglass_empty' : 'refresh'} className="text-[14px]" />
                {generating ? (it ? 'Generazione...' : 'Generating...') : ''}
              </button>
            </div>
          </div>

          {/* The prose */}
          {generating ? (
            <Shimmer lines={4} />
          ) : xici?.text ? (
            <div className="font-serif text-[15px] leading-relaxed text-on-surface/90 mb-4">
              <Markdown content={xici.text} />
            </div>
          ) : (
            <div className="text-sm text-on-surface-variant italic py-4">
              {stats?.article_count
                ? (it
                    ? 'Premi aggiorna per generare una lettura guidata della base di conoscenza'
                    : 'Click refresh to generate a guided introduction')
                : (it
                    ? 'La base di conoscenza e vuota. Importa documenti e compila prima.'
                    : 'Knowledge base is empty. Ingest and compile documents first.')}
            </div>
          )}

          {/* Theme tags */}
          {xici?.themes && xici.themes.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {xici.themes.map(t => (
                <span key={t} className="px-2.5 py-0.5 text-[11px] bg-primary/10 text-primary rounded-full">
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { icon: 'description', label: it ? 'Documenti grezzi' : 'Raw Documents', value: stats?.raw_count, color: 'text-secondary' },
          { icon: 'article', label: it ? 'Articoli wiki' : 'Wiki Articles', value: stats?.article_count, color: 'text-primary' },
          { icon: 'link', label: it ? 'Collegamenti' : 'Knowledge Links', value: stats?.link_count, color: 'text-tertiary' },
          { icon: 'health_and_safety', label: it ? 'Stato di salute' : 'Health Score',
            value: stats ? `${stats.health_score}%` : undefined, color: 'text-on-surface' },
        ].map(s => (
          <div key={s.label} className="bg-surface-container rounded-xl p-5 border border-outline-variant/20">
            <div className="flex items-center gap-2 mb-2">
              <Icon name={s.icon} className={`text-[20px] ${s.color}`} />
              <span className="text-xs text-on-surface-variant uppercase tracking-wider">{s.label}</span>
            </div>
            <div className={`text-3xl font-bold font-label ${s.color}`}>
              {stats ? (s.value ?? '-') : <Shimmer lines={1} />}
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3 mb-8">
          <button onClick={() => navigate('/qa')} className="flex items-center gap-2 px-5 py-3 bg-primary/10 border border-primary/20 rounded-xl text-sm hover:bg-primary/20 transition-colors">
            <Icon name="forum" className="text-primary text-[18px]" /> {it ? 'Fai una domanda' : 'Ask a Question'}
          </button>
          <button onClick={() => navigate('/ingest')} className="flex items-center gap-2 px-5 py-3 bg-surface-container border border-outline-variant/30 rounded-xl text-sm hover:border-secondary/50 transition-colors">
            <Icon name="add_link" className="text-secondary text-[18px]" /> {it ? 'Importa' : 'Ingest'}
          </button>
          <button onClick={() => navigate('/health')} className="flex items-center gap-2 px-5 py-3 bg-surface-container border border-outline-variant/30 rounded-xl text-sm hover:border-tertiary/50 transition-colors">
            <Icon name="health_and_safety" className="text-tertiary text-[18px]" /> {it ? 'Controllo salute' : 'Health Check'}
          </button>
      </div>

      {/* Domains */}
      <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/20 mb-8">
        <DomainManager />
      </div>

      {/* Background Jobs + Agent API */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/20">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-2">
              <Icon name="motion_photos_auto" className="text-primary text-[16px]" />
              <span className="text-xs uppercase tracking-widest text-on-surface-variant">
                {it ? 'Background Jobs' : 'Background Jobs'}
              </span>
            </div>
            {compileCard.detail && (
              <span className="text-[11px] text-outline">{compileCard.detail}</span>
            )}
          </div>

          <div className={`rounded-xl border px-4 py-3 ${compileCard.tone}`}>
            <div className="flex items-center gap-2 mb-2">
              <Icon name={compileCard.icon} className={`text-[18px] ${compileStatus.status === 'running' ? 'animate-pulse' : ''}`} />
              <span className="text-sm font-medium">{compileCard.title}</span>
            </div>
            <p className="text-sm leading-relaxed opacity-90 break-words">{compileCard.body}</p>
            {compileStatus.status === 'failed' && (
              <button
                onClick={() => navigate('/ingest')}
                className="mt-3 inline-flex items-center gap-1 text-xs font-medium hover:underline">
                <Icon name="open_in_new" className="text-[14px]" />
                {it ? 'Apri Ingest' : 'Open Ingest'}
              </button>
            )}
          </div>
        </div>

        <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/20">
          <div className="flex items-center gap-2 mb-2">
            <Icon name="api" className="text-primary text-[16px]" />
            <span className="text-xs uppercase tracking-widest text-on-surface-variant">Agent API</span>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <code className="text-xs text-on-surface-variant">:5556</code>
            </div>
            <div className="flex items-center gap-1.5 text-outline">
              <span className="w-2 h-2 rounded-full bg-outline/30" />
              <span className="text-[11px]">mem9 <span className="text-[10px] opacity-60">soon</span></span>
            </div>
            <div className="flex items-center gap-1.5 text-outline">
              <span className="w-2 h-2 rounded-full bg-outline/30" />
              <span className="text-[11px]">db9 <span className="text-[10px] opacity-60">soon</span></span>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-surface-container rounded-xl p-4 border border-outline-variant/20 mb-8">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Icon name="toll" className="text-primary text-[16px]" />
            <span className="text-xs uppercase tracking-widest text-on-surface-variant">
              {it ? 'LLM Usage' : 'LLM Usage'}
            </span>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {LLM_USAGE_WINDOWS.map(window => (
              <button
                key={window.value}
                onClick={() => setUsageWindow(window.value)}
                className={`rounded-full px-2.5 py-1 text-[11px] border transition-colors ${usageWindow === window.value
                  ? 'bg-primary/10 text-primary border-primary/30'
                  : 'bg-surface-high text-on-surface-variant border-outline-variant/20 hover:border-primary/20 hover:text-primary'}`}
              >
                {window.label}
              </button>
            ))}
            <span className="text-[11px] text-outline">
              {llmUsage?.record_count ? `${llmUsage.record_count} attempts` : (it ? 'Nessun dato' : 'No data')}
            </span>
          </div>
        </div>

        {llmUsage ? (
          <div className="grid grid-cols-1 xl:grid-cols-[1.4fr_1fr] gap-4">
            <div className="rounded-xl border border-outline-variant/20 bg-surface-high p-4">
              <div className="flex items-end justify-between gap-4 mb-3">
                <div>
                  <div className="text-[11px] uppercase tracking-wider text-on-surface-variant">
                    {it ? 'Token totali' : 'Total tokens'}
                  </div>
                  <div className="text-3xl font-bold font-label text-primary">
                    {usageTotalTokens.toLocaleString()}
                  </div>
                </div>
                <div className="text-right text-xs text-on-surface-variant">
                  <div>{it ? 'Riusciti' : 'Successful'}: {usageSuccessRate}%</div>
                  <div>{it ? 'Retry/Fallback' : 'Retry/Fallback'}: {usageRetryTokens.toLocaleString()}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
                <div className="rounded-lg bg-surface-container px-3 py-2 border border-outline-variant/20">
                  <div className="text-on-surface-variant uppercase tracking-wide mb-1">{it ? 'Prompt' : 'Prompt'}</div>
                  <div className="font-medium text-on-surface">{llmUsage.totals.prompt_tokens.toLocaleString()}</div>
                </div>
                <div className="rounded-lg bg-surface-container px-3 py-2 border border-outline-variant/20">
                  <div className="text-on-surface-variant uppercase tracking-wide mb-1">{it ? 'Output' : 'Output'}</div>
                  <div className="font-medium text-on-surface">{llmUsage.totals.completion_tokens.toLocaleString()}</div>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-on-surface-variant">{it ? 'Modello principale' : 'Top model'}</span>
                  <span className="font-medium text-on-surface">{usageTopModel ? `${usageTopModel.model} · ${usageTopModel.total_tokens.toLocaleString()}` : '-'}</span>
                </div>
                {usageTopFeatures.map(feature => (
                  <div key={feature.feature} className="flex items-center justify-between gap-3">
                    <span className="text-on-surface-variant capitalize">{feature.feature}</span>
                    <span className="font-medium text-on-surface">{feature.total_tokens.toLocaleString()}</span>
                  </div>
                ))}
              </div>

              {llmUsage.malformed_record_count > 0 && (
                <p className="mt-3 text-[11px] text-amber-700 dark:text-amber-300">
                  {it
                    ? `${llmUsage.malformed_record_count} record non validi ignorati nel log.`
                    : `${llmUsage.malformed_record_count} malformed log records were ignored.`}
                </p>
              )}

              {llmUsage.skipped_timestamp_count > 0 && llmUsage.applied_window !== 'all' && (
                <p className="mt-2 text-[11px] text-amber-700 dark:text-amber-300">
                  {it
                    ? `${llmUsage.skipped_timestamp_count} record esclusi dal filtro temporale per timestamp mancante o non valido.`
                    : `${llmUsage.skipped_timestamp_count} records were excluded from this time filter because their timestamps were missing or invalid.`}
                </p>
              )}
            </div>

            <div className="rounded-xl border border-outline-variant/20 bg-surface-high p-4">
              <div className="flex items-center justify-between gap-3 mb-3">
                <span className="text-[11px] uppercase tracking-wider text-on-surface-variant">
                  {it ? 'Ultima chiamata LLM' : 'Last LLM call'}
                </span>
                <span className="text-[11px] text-outline">
                  {lastLlmRequest?.ts ? timeAgo(lastLlmRequest.ts) : ''}
                </span>
              </div>

              {lastLlmRequest ? (
                <>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div>
                      <div className="text-sm font-medium text-on-surface capitalize">
                        {lastLlmRequest.feature}
                        {lastLlmRequest.stage ? ` · ${lastLlmRequest.stage}` : ''}
                      </div>
                      <div className="text-xs text-on-surface-variant mt-1 break-words">
                        {lastLlmModels || lastLlmRequest.requested_model || '-'}
                      </div>
                    </div>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] ${lastLlmRequest.success ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'bg-rose-500/10 text-rose-700 dark:text-rose-300'}`}>
                      {lastLlmRequest.success ? (it ? 'ok' : 'ok') : (it ? 'failed' : 'failed')}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                    <div className="rounded-lg bg-surface-container px-3 py-2 border border-outline-variant/20">
                      <div className="text-on-surface-variant uppercase tracking-wide mb-1">{it ? 'Token totali' : 'Total tokens'}</div>
                      <div className="font-medium text-on-surface">{lastLlmRequest.total_tokens.toLocaleString()}</div>
                    </div>
                    <div className="rounded-lg bg-surface-container px-3 py-2 border border-outline-variant/20">
                      <div className="text-on-surface-variant uppercase tracking-wide mb-1">{it ? 'Tentativi' : 'Attempts'}</div>
                      <div className="font-medium text-on-surface">{lastLlmRequest.attempt_count}</div>
                    </div>
                    <div className="rounded-lg bg-surface-container px-3 py-2 border border-outline-variant/20">
                      <div className="text-on-surface-variant uppercase tracking-wide mb-1">Prompt</div>
                      <div className="font-medium text-on-surface">{lastLlmRequest.prompt_tokens.toLocaleString()}</div>
                    </div>
                    <div className="rounded-lg bg-surface-container px-3 py-2 border border-outline-variant/20">
                      <div className="text-on-surface-variant uppercase tracking-wide mb-1">Output</div>
                      <div className="font-medium text-on-surface">{lastLlmRequest.completion_tokens.toLocaleString()}</div>
                    </div>
                    {lastLlmRequest.reasoning_tokens > 0 && (
                      <div className="rounded-lg bg-surface-container px-3 py-2 border border-outline-variant/20 col-span-2">
                        <div className="text-on-surface-variant uppercase tracking-wide mb-1">Reasoning</div>
                        <div className="font-medium text-on-surface">{lastLlmRequest.reasoning_tokens.toLocaleString()}</div>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2 text-[11px] text-on-surface-variant">
                    {lastLlmRequest.retry_count > 0 && (
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-primary">retry {lastLlmRequest.retry_count}</span>
                    )}
                    {lastLlmRequest.fallback_count > 0 && (
                      <span className="rounded-full bg-secondary/10 px-2 py-0.5 text-secondary">fallback {lastLlmRequest.fallback_count}</span>
                    )}
                    {lastLlmRequest.truncated && (
                      <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-700 dark:text-amber-300">truncated</span>
                    )}
                    {lastLlmRequest.last_error_type && !lastLlmRequest.success && (
                      <span className="rounded-full bg-rose-500/10 px-2 py-0.5 text-rose-700 dark:text-rose-300">{lastLlmRequest.last_error_type}</span>
                    )}
                  </div>

                  {lastLlmRequest.last_error_message && !lastLlmRequest.success && (
                    <p className="mt-3 text-xs text-rose-700 dark:text-rose-300 break-words">{lastLlmRequest.last_error_message}</p>
                  )}
                </>
              ) : (
                <div className="py-4 text-sm text-on-surface-variant italic">
                  {usageWindow === 'all'
                    ? (it ? 'Nessuna chiamata LLM registrata finora.' : 'No LLM calls recorded yet.')
                    : (it ? 'Nessuna chiamata LLM trovata nella finestra temporale selezionata.' : 'No LLM calls found in the selected time window.')}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="py-4">
            <Shimmer lines={4} />
          </div>
        )}
      </div>

      {/* Quick link to wiki */}
      {stats && stats.article_count > 0 && (
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-widest text-on-surface-variant">
            {stats.article_count} articles &middot; {stats.total_words.toLocaleString()} words
          </span>
          <button onClick={() => navigate('/wiki')} className="text-sm text-primary hover:underline">
            Browse Wiki &rarr;
          </button>
        </div>
      )}
    </div>
  );
}
