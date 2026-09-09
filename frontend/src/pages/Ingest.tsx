import { useState, useEffect, useRef } from 'react';
import { Icon } from '../components/Icon';
import { Markdown } from '../components/Markdown';
import { ApiError, api, type RawDoc } from '../lib/api';
import { useDomains } from '../lib/domains';
import { useLang, type TFunc } from '../lib/lang';

// Poll the worker status while a job is in flight. 2s is a decent balance
// between recovery latency and request noise — compile jobs typically run
// minutes, so the user will see progress without hammering the backend.
const POLL_MS = 2000;
// Give up after this many consecutive poll failures so a missing/unauth
// status endpoint can't strand the UI in "Compiling…" forever.
const POLL_MAX_CONSECUTIVE_FAILURES = 5;

function isSupportedUploadFile(file: File) {
  const lowerName = file.name.toLowerCase();
  return (
    file.type === 'application/pdf'
    || file.type === 'text/markdown'
    || lowerName.endsWith('.pdf')
    || lowerName.endsWith('.md')
    || lowerName.endsWith('.markdown')
  );
}

function isPdfFile(file: File) {
  const lowerName = file.name.toLowerCase();
  return file.type === 'application/pdf' || lowerName.endsWith('.pdf');
}

function isMarkdownFile(file: File) {
  const lowerName = file.name.toLowerCase();
  return file.type === 'text/markdown' || lowerName.endsWith('.md') || lowerName.endsWith('.markdown');
}

function uploadFileMeta(file: File) {
  if (isPdfFile(file)) {
    return {
      label: 'PDF',
      icon: 'picture_as_pdf',
      badgeClass: 'bg-secondary-container/30 text-secondary',
    };
  }
  return {
    label: 'Markdown',
    icon: 'description',
    badgeClass: 'bg-tertiary-container/30 text-tertiary',
  };
}

function rawDocMeta(rawType: string, t: TFunc) {
  if (rawType === 'pdf') {
    return {
      label: 'PDF',
      icon: 'picture_as_pdf',
      className: 'bg-secondary-container/30 text-secondary',
    };
  }
  if (rawType === 'web_article' || rawType === 'browser_article') {
    return {
      label: 'Web',
      icon: 'language',
      className: 'bg-primary-container/30 text-primary',
    };
  }
  if (rawType === 'local_file') {
    return {
      label: t('ingest.type.file'),
      icon: 'description',
      className: 'bg-tertiary-container/30 text-tertiary',
    };
  }
  return {
    label: rawType || t('ingest.type.unknown'),
    icon: 'draft',
    className: 'bg-surface-high text-on-surface-variant',
  };
}

export function Ingest() {
  const [url, setUrl] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [docs, setDocs] = useState<RawDoc[]>([]);
  const [ingesting, setIngesting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [compiling, setCompiling] = useState(false);
  const [chunkPages, setChunkPages] = useState(20);
  const [message, setMessage] = useState('');
  // Tracked explicitly: the banner styling used to sniff an English "Error" prefix.
  const [messageIsError, setMessageIsError] = useState(false);
  const [ingestErrorDetail, setIngestErrorDetail] = useState('');
  const [blockedUrl, setBlockedUrl] = useState('');
  const [browserRetrying, setBrowserRetrying] = useState(false);
  const [preview, setPreview] = useState<{ slug: string; title: string; content: string; metadata: Record<string, string> } | null>(null);
  const { current } = useDomains();
  const { t } = useLang();
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollFailures = useRef(0);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  // Guard against async work resolving after unmount — any setState or
  // startPolling call guarded by this ref becomes a no-op once cleanup ran.
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    loadDocs();
    // Recover in-flight state across route changes / reloads.
    (async () => {
      try {
        const status = await api.compileStatus();
        if (!mounted.current) return;
        if (status.status === 'running') {
          setCompiling(true);
          setMessage(t('ingest.msg.compileAlreadyRunning'));
          startPolling();
        }
      } catch { /* ignore — endpoint absent on old backend or unauth */ }
    })();
    return () => {
      mounted.current = false;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stopPolling() {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
    pollFailures.current = 0;
  }

  function startPolling() {
    stopPolling();
    pollFailures.current = 0;
    pollTimer.current = setInterval(async () => {
      try {
        const status = await api.compileStatus();
        if (!mounted.current) return;
        pollFailures.current = 0;
        if (status.status === 'running') {
          return;
        }
        if (status.status === 'failed') {
          stopPolling();
          setCompiling(false);
          setMessageIsError(true);
          setMessage(t('ingest.msg.compileFailedDetail', { error: status.error ?? t('ingest.msg.unknownError') }));
          return;
        }
        if (status.status === 'completed') {
          stopPolling();
          setCompiling(false);
          setMessage(t('ingest.msg.compileFinished', { count: status.articles_created ?? 0 }));
          await loadDocs();
          return;
        }
        stopPolling();
        setCompiling(false);
        setMessage(t('ingest.msg.compileIdle'));
      } catch {
        if (!mounted.current) return;
        pollFailures.current += 1;
        if (pollFailures.current >= POLL_MAX_CONSECUTIVE_FAILURES) {
          stopPolling();
          setCompiling(false);
          setMessageIsError(true);
          setMessage(t('ingest.msg.workerUnreachable'));
        }
      }
    }, POLL_MS);
  }

  async function loadDocs() {
    try {
      const sources = await api.getSources();
      if (mounted.current) setDocs(sources);
    } catch { /* */ }
  }

  async function handleIngest() {
    const target = url.trim();
    if (!target) return;
    setIngesting(true);
    setMessage('');
    setMessageIsError(false);
    setIngestErrorDetail('');
    setBlockedUrl('');
    try {
      await api.ingest(target);
      if (!mounted.current) return;
      setMessageIsError(false);
      setMessage(t('ingest.msg.ingestOk'));
      setIngestErrorDetail('');
      setBlockedUrl('');
      setUrl('');
      await loadDocs();
    } catch (err) {
      if (!mounted.current) return;
      const detail = err instanceof ApiError ? err.message : t('ingest.msg.ingestFailed');
      const blocked = err instanceof ApiError && err.status === 400 && /blocked automated access/i.test(detail);
      setIngestErrorDetail(detail);
      setBlockedUrl(blocked ? target : '');
      setMessageIsError(true);
      if (blocked) {
        setMessage(t('ingest.msg.blocked'));
      } else {
        setMessage(t('ingest.msg.errorPrefix', { detail }));
      }
    }
    if (mounted.current) setIngesting(false);
  }

  async function handleBrowserRetry() {
    const target = blockedUrl || url.trim();
    if (!target) return;
    setBrowserRetrying(true);
    setMessage('');
    try {
      await api.ingestBrowser(target);
      if (!mounted.current) return;
      setMessageIsError(false);
      setMessage(t('ingest.msg.browserIngestOk'));
      setIngestErrorDetail('');
      setBlockedUrl('');
      setUrl('');
      await loadDocs();
    } catch (err) {
      if (!mounted.current) return;
      const detail = err instanceof ApiError ? err.message : t('ingest.msg.browserIngestFailed');
      setIngestErrorDetail(detail);
      setMessageIsError(true);
      setMessage(t('ingest.msg.errorPrefix', { detail }));
    }
    if (mounted.current) setBrowserRetrying(false);
  }

  async function handleFileUpload() {
    if (selectedFiles.length === 0) return;
    setUploading(true);
    setMessage('');

    try {
      const result = await api.uploadFiles(selectedFiles, chunkPages, current);
      if (!mounted.current) return;

      const okCount = result.uploaded.length;
      const uploadedPdfCount = result.uploaded.filter(file => file.type === 'pdf').length;
      const uploadedMarkdownCount = result.uploaded.filter(file => file.type === 'md' || file.type === 'markdown').length;
      const otherUploadedCount = okCount - uploadedPdfCount - uploadedMarkdownCount;
      const failCount = result.failed.length;
      const detailParts = [];
      if (uploadedPdfCount > 0) {
        detailParts.push(t('ingest.msg.pdfProcessed', { count: uploadedPdfCount }));
      }
      if (uploadedMarkdownCount > 0) {
        detailParts.push(t('ingest.msg.markdownIngested', { count: uploadedMarkdownCount }));
      }
      if (otherUploadedCount > 0) {
        detailParts.push(t('ingest.msg.filesIngested', { count: otherUploadedCount }));
      }
      if (failCount === 0) {
        setMessageIsError(false);
        setMessage(detailParts.length > 0 ? detailParts.join(', ') + '.' : t('ingest.msg.uploadOk', { count: okCount }));
      } else {
        const detail = detailParts.length > 0 ? `${detailParts.join(', ')}. ` : '';
        setMessageIsError(true);
        setMessage(detail + t('ingest.msg.filesFailed', { count: failCount }));
      }

      setSelectedFiles([]);
      if (uploadInputRef.current) uploadInputRef.current.value = '';
      await loadDocs();
    } catch {
      if (!mounted.current) return;
      setMessageIsError(true);
      setMessage(t('ingest.msg.uploadFailed'));
    }

    if (mounted.current) setUploading(false);
  }

  async function handleCompile() {
    setCompiling(true);
    setMessage('');
    try {
      const res = await api.compile();
      if (!mounted.current) return;
      if (res.status === 'ok') {
        setMessageIsError(false);
        setMessage(t('ingest.msg.compiled', { count: res.articles_created ?? 0 }));
        await loadDocs();
        if (mounted.current) setCompiling(false);
        return;
      }
      setMessage(res.message ?? t('ingest.msg.compileBackground'));
      startPolling();
    } catch (err) {
      if (!mounted.current) return;
      if (err instanceof ApiError && err.status === 409) {
        // Another job already holds the lock — don't flash "failed";
        // fall back to the same polling path as the on-mount recovery.
        setMessage(t('ingest.msg.compileWaiting'));
        startPolling();
      } else {
        setMessageIsError(true);
        setMessage(t('ingest.msg.compileFailed'));
        setCompiling(false);
      }
    }
  }

  async function viewRaw(slug: string) {
    try {
      const res = await fetch(`/api/sources/${slug}`);
      const data = await res.json();
      if (mounted.current && data.content) setPreview(data);
    } catch { /* */ }
  }

  async function handleDocDateChange(docDate: string | null) {
    if (!preview) return;
    try {
      await api.patchDocDate(preview.slug, docDate);
      setPreview({ ...preview, metadata: { ...preview.metadata, doc_date: docDate ?? '' } });
    } catch {
      setMessageIsError(true);
      setMessage(t('ingest.msg.docDateFailed'));
    }
  }

  const uncompiled = docs.filter(d => !d.compiled).length;
  const hasPdfSelection = selectedFiles.some(isPdfFile);
  const pdfCount = selectedFiles.filter(isPdfFile).length;
  const markdownCount = selectedFiles.filter(isMarkdownFile).length;

  return (
    <div className="p-8 max-w-[900px] mx-auto">
      <h1 className="font-headline text-3xl font-bold mb-6">{t('ingest.title')}</h1>

      {/* URL Ingest */}
      <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/20 mb-6 card-shadow">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Icon name="add_link" className="text-secondary text-[18px]" /> {t('ingest.fromUrl')}
        </h3>
        <div className="flex gap-3">
          <input type="text" placeholder={t('ingest.urlPlaceholder')}
            className="flex-1 bg-surface-high border border-outline-variant/40 rounded-lg px-4 py-2.5 text-sm text-on-surface placeholder:text-outline outline-none focus:border-primary/60"
            value={url} onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleIngest()} />
          <button onClick={handleIngest} disabled={ingesting}
            className="px-5 py-2.5 bg-secondary text-on-secondary rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50">
            {ingesting ? t('ingest.ingesting') : t('ingest.ingest')}
          </button>
        </div>
      </div>

      <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/20 mb-6 card-shadow">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Icon name="upload_file" className="text-secondary text-[18px]" /> {t('ingest.uploadFiles')}
        </h3>
        <div className="flex flex-col gap-3">
          <p className="text-sm text-on-surface-variant">
            {t('ingest.uploadHint')}
          </p>
          <input
            ref={uploadInputRef}
            type="file"
            accept=".pdf,.md,.markdown,text/markdown,application/pdf"
            multiple
            onChange={e => {
              const files = Array.from(e.target.files ?? []).filter(isSupportedUploadFile);
              setSelectedFiles(files);
            }}
            className="block w-full text-sm text-on-surface"
          />

          {selectedFiles.length > 0 && (
            <div className="flex flex-col gap-2">
              <div className="text-xs text-on-surface-variant">
                {t('ingest.filesSelected', { pdf: pdfCount, markdown: markdownCount })}
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedFiles.map(file => {
                  const meta = uploadFileMeta(file);
                  return (
                    <div
                      key={`${file.name}-${file.size}-${file.lastModified}`}
                      className="inline-flex max-w-full items-center gap-2 rounded-full border border-outline-variant/30 bg-surface-high px-3 py-1 text-xs text-on-surface"
                    >
                      <Icon name={meta.icon} className="text-[14px]" />
                      <span className="max-w-[260px] truncate">{file.name}</span>
                      <span className={`rounded-full px-2 py-0.5 font-medium ${meta.badgeClass}`}>
                        {meta.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {hasPdfSelection && (
            <div className="flex items-center gap-3">
              <label className="text-sm text-on-surface-variant" htmlFor="chunk-pages-input">{t('ingest.pagesPerChunk')}</label>
              <input
                id="chunk-pages-input"
                type="number"
                min={0}
                value={chunkPages}
                onChange={e => setChunkPages(Number(e.target.value) || 0)}
                className="w-28 bg-surface-high border border-outline-variant/40 rounded-lg px-3 py-2 text-sm text-on-surface"
              />
            </div>
          )}

          {!hasPdfSelection && selectedFiles.length > 0 && (
            <div className="text-xs text-on-surface-variant">
              {t('ingest.noPdfSelected')}
            </div>
          )}

          <button
            onClick={handleFileUpload}
            disabled={uploading || selectedFiles.length === 0}
            className="self-start px-5 py-2.5 bg-secondary text-on-secondary rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50"
          >
            {uploading ? t('ingest.uploading') : t('ingest.uploadFiles')}
          </button>
        </div>
      </div>

      {/* Compile Action */}
      {uncompiled > 0 && (
        <div className="bg-primary-container/15 rounded-xl p-5 border border-primary/20 mb-6 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-primary">{t('ingest.uncompiled', { count: uncompiled })}</p>
            <p className="text-xs text-on-surface-variant mt-0.5">{t('ingest.compileThem')}</p>
          </div>
          <button onClick={handleCompile} disabled={compiling}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary text-on-primary rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50">
            <Icon name="auto_awesome" className="text-[16px]" />
            {compiling ? t('ingest.compiling') : t('ingest.compileAll')}
          </button>
        </div>
      )}

      {message && (
        <div className={`rounded-lg px-4 py-3 mb-6 text-sm ${messageIsError ? 'bg-error-container/20 text-error' : 'bg-tertiary-container/20 text-tertiary'}`}>
          <div>{message}</div>
          {ingestErrorDetail && !message.includes(ingestErrorDetail) && (
            <div className="mt-1 text-xs opacity-90 break-words">{ingestErrorDetail}</div>
          )}
          {blockedUrl && (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                onClick={handleBrowserRetry}
                disabled={browserRetrying}
                className="inline-flex items-center gap-2 rounded-lg border border-current/20 px-3 py-1.5 text-xs font-medium hover:bg-surface-high/40 disabled:opacity-50"
              >
                <Icon name={browserRetrying ? 'hourglass_empty' : 'language'} className="text-[14px]" />
                {browserRetrying ? t('ingest.browserFetching') : t('ingest.tryBrowserFetch')}
              </button>
              <span className="text-xs opacity-90">
                {t('ingest.browserFetchNote')}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Raw Document Preview Modal */}
      {preview && (
        <div className="fixed inset-0 bg-bg/80 z-50 flex items-center justify-center p-8" onClick={() => setPreview(null)}>
          <div className="bg-surface-container border border-outline-variant/30 rounded-2xl max-w-[700px] w-full max-h-[80vh] overflow-hidden flex flex-col card-shadow-lg"
            onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b border-outline-variant/20">
              <div>
                <h2 className="font-headline font-semibold text-on-surface">{preview.title}</h2>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  {preview.metadata.type} | {preview.metadata.compiled === 'True' ? t('ingest.compiled') : t('ingest.pending')}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <label className="text-xs text-on-surface-variant">{t('ingest.docDate')}</label>
                  <input
                    type="date"
                    value={preview.metadata.doc_date && /^\d{4}-\d{2}-\d{2}$/.test(preview.metadata.doc_date) ? preview.metadata.doc_date : ''}
                    onChange={e => handleDocDateChange(e.target.value || null)}
                    className="bg-surface-high border border-outline-variant/40 rounded-lg px-2 py-1 text-xs text-on-surface"
                  />
                  {preview.metadata.doc_date && !/^\d{4}-\d{2}-\d{2}$/.test(preview.metadata.doc_date) && (
                    <span className="text-xs text-on-surface-variant">{preview.metadata.doc_date}</span>
                  )}
                </div>
              </div>
              <button onClick={() => setPreview(null)}
                className="p-2 rounded-lg hover:bg-surface-high text-on-surface-variant">
                <Icon name="close" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <Markdown content={preview.content} />
            </div>
          </div>
        </div>
      )}

      {/* Documents list */}
      <h2 className="font-headline text-xl font-semibold mb-4">{t('ingest.rawDocuments')}</h2>
      {docs.length === 0 ? (
        <div className="text-center py-12 text-on-surface-variant">
          <Icon name="folder_open" className="text-5xl mb-3 block" />
          <p>{t('ingest.noDocuments')}</p>
        </div>
      ) : (
        <div className="bg-surface-container rounded-xl border border-outline-variant/20 overflow-hidden card-shadow">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-outline-variant/30">
                <th className="text-left px-5 py-3 text-on-surface-variant font-medium">{t('ingest.col.title')}</th>
                <th className="text-left px-5 py-3 text-on-surface-variant font-medium">{t('ingest.col.type')}</th>
                <th className="text-left px-5 py-3 text-on-surface-variant font-medium">{t('ingest.col.status')}</th>
                <th className="text-left px-5 py-3 text-on-surface-variant font-medium">{t('ingest.col.date')}</th>
                <th className="text-left px-5 py-3 text-on-surface-variant font-medium w-16"></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d, i) => (
                <tr key={i} className="border-b border-outline-variant/10 last:border-b-0 hover:bg-surface-high/50 transition-colors">
                  <td className="px-5 py-3 text-on-surface">{d.title}</td>
                  <td className="px-5 py-3 text-on-surface-variant">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${rawDocMeta(d.type, t).className}`}>
                      <Icon name={rawDocMeta(d.type, t).icon} className="text-[14px]" />
                      {rawDocMeta(d.type, t).label}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${
                      d.compiled ? 'bg-tertiary-container/30 text-tertiary' : 'bg-surface-high text-on-surface-variant'
                    }`}>
                      <Icon name={d.compiled ? 'check_circle' : 'pending'} className="text-[14px]" />
                      {d.compiled ? t('ingest.compiled') : t('ingest.pending')}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-on-surface-variant">{d.ingested_at?.slice(0, 10)}</td>
                  <td className="px-5 py-3">
                    <button onClick={() => viewRaw(d.path.includes('/raw/') ? d.path.split('/raw/')[1] : d.path || d.title)}
                      className="p-1.5 rounded-lg hover:bg-surface-highest text-on-surface-variant hover:text-primary transition-colors"
                      title={t('ingest.previewTooltip')}>
                      <Icon name="visibility" className="text-[16px]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
