const BASE = '';

export interface Article {
  slug: string;
  title: string;
  summary: string;
  tags: string[];
  domain?: string;
  content?: string;
  sources?: { plugin?: string; url?: string; title?: string; work_id?: string }[];
  backlinks?: { slug: string; title: string }[];
}

export interface SearchResult {
  slug: string;
  title: string;
  summary: string;
  score: number;
  snippet: string;
  matched_terms: string[];
}

export interface Stats {
  raw_count: number;
  article_count: number;
  output_count: number;
  total_words: number;
  link_count: number;
  health_score: number;
}

export interface XiCi {
  text: string;
  themes: string[];
  lang: string;
  generated_at: string | null;
  article_count: number;
}

export interface RawDoc {
  path: string;
  title: string;
  type: string;
  compiled: boolean;
  ingested_at: string;
}

export interface TrailStep {
  type: 'article' | 'query' | 'search';
  slug?: string;
  title?: string;
  question?: string;
  ts: string;
}

export interface Trail {
  id: string;
  name: string;
  created: string;
  updated: string;
  steps: TrailStep[];
}

export interface LintResults {
  structural: string[];
  broken_links: string[];
  orphans: string[];
  missing_metadata: string[];
  total_issues: number;
}

export interface CompileStatus {
  status: 'idle' | 'running' | 'completed' | 'failed' | 'unknown';
  message?: string;
  error?: string;
  articles_created?: number;
  articles?: string[];
  full?: boolean;
  started_at?: string;
  finished_at?: string;
}

export interface LlmUsageTotals {
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
}

export interface LlmUsageGroup extends LlmUsageTotals {
  attempt_count: number;
  success_count: number;
  retry_count: number;
  fallback_count: number;
}

export interface LlmUsageModelGroup extends LlmUsageGroup {
  model: string;
}

export interface LlmUsageStageGroup extends LlmUsageGroup {
  stage: string | null;
}

export interface LlmUsageFeatureGroup extends LlmUsageGroup {
  feature: string;
  by_stage: LlmUsageStageGroup[];
}

export interface LlmUsageRecentRequest {
  request_id: string;
  ts: string | null;
  feature: string;
  stage: string | null;
  requested_model: string | null;
  actual_models: string[];
  attempt_count: number;
  success: boolean;
  retry_count: number;
  fallback_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  last_finish_reason: string | null;
  last_error_type: string | null;
  last_error_message: string | null;
  truncated: boolean;
}

export type LlmUsageWindow = 'all' | '24h' | '7d' | '30d' | '365d' | 'custom';

export interface LlmUsageSummary {
  generated_at: string;
  source_path: string;
  applied_window: LlmUsageWindow;
  from_ts: string | null;
  to_ts: string | null;
  record_count: number;
  malformed_record_count: number;
  missing_usage_count: number;
  skipped_timestamp_count: number;
  totals: LlmUsageTotals;
  successful_totals: LlmUsageTotals;
  retry_fallback_totals: LlmUsageTotals;
  by_model: LlmUsageModelGroup[];
  by_feature: LlmUsageFeatureGroup[];
}

export interface LlmUsageRecentResponse {
  source_path: string;
  applied_window: LlmUsageWindow;
  from_ts: string | null;
  to_ts: string | null;
  skipped_timestamp_count: number;
  requests: LlmUsageRecentRequest[];
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value));
  }
  const out = query.toString();
  return out ? `?${out}` : '';
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(BASE + url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let message = `API error: ${res.status}`;
    try {
      const data = await res.json() as { error?: string; message?: string };
      if (data.error || data.message) message = data.error || data.message || message;
    } catch {
      // Ignore body parse failures and keep the status-based message.
    }
    throw new ApiError(res.status, message);
  }
  return res.json();
}

async function del<T>(url: string): Promise<T> {
  const res = await fetch(BASE + url, { method: 'DELETE' });
  if (!res.ok) throw new ApiError(res.status, `API error: ${res.status}`);
  return res.json();
}

async function postForm<T>(url: string, body: FormData): Promise<T> {
  const res = await fetch(BASE + url, {
    method: 'POST',
    body,
  });
  if (!res.ok) throw new ApiError(res.status, `API error: ${res.status}`);
  return res.json();
}

export interface UploadBatchResult {
  status: 'ok' | 'partial';
  uploaded: Array<{
    filename: string;
    type: string;
    chunks?: number;
    path?: string;
    paths?: string[];
  }>;
  failed: Array<{
    filename: string;
    error: string;
  }>;
  total_files: number;
}

export interface Collection {
  id: string;
  label: string;
  count: number;
  articles: { slug: string; title: string; summary: string }[];
}

export interface TaxonomyCategory {
  id: string;
  label: string;
  count: number;
  total: number;
  articles: { slug: string; title: string }[];
  children: TaxonomyCategory[];
}

export interface Domain {
  id: string;
  label: string;
}

export const api = {
  getCollections: () => get<{ collections: Collection[] }>('/api/collections').then(d => d.collections),
  getTaxonomy: (lang: string) => get<{ categories: TaxonomyCategory[] }>(`/api/taxonomy?lang=${lang}`).then(d => d.categories),
  getStats: () => get<Stats>('/api/stats'),
  getArticles: () => get<{ articles: Article[] }>('/api/articles').then(d => d.articles),
  getArticle: (slug: string) => get<Article>('/api/articles/' + slug),
  listDomains: () => get<{ domains: Domain[] }>('/api/domains').then(d => d.domains),
  createDomain: (label: string) => post<{ domain: Domain }>('/api/domains', { label }).then(d => d.domain),
  renameDomain: (id: string, label: string) =>
    post<{ domain: Domain }>(`/api/domains/${id}/rename`, { label }).then(d => d.domain),
  deleteDomain: (id: string) => del<{ deleted: string }>(`/api/domains/${id}`),
  bulkAssignDomain: (slugs: string[], domain: string) =>
    post<{ domain: string; updated: string[]; missing: string[] }>('/api/articles/bulk-domain', { slugs, domain }),
  search: (q: string, topK = 10, domain?: string) =>
    get<{ results: SearchResult[] }>(
      `/api/search?q=${encodeURIComponent(q)}&top_k=${topK}${domain ? `&domain=${encodeURIComponent(domain)}` : ''}`
    ).then(d => d.results),
  ask: (
    question: string,
    deep = false,
    fileBack = true,
    tone = 'default',
    promote = false,
    domain?: string,
  ) =>
    post<{
      answer: string;
      consulted?: { slug: string; title: string }[];
      promotion?: {
        promoted: boolean;
        reason?: string;
        slug?: string;
        title?: string;
        path?: string;
        merged?: boolean;
      };
    }>('/api/ask', { question, deep, file_back: fileBack, tone, promote, ...(domain ? { domain } : {}) }),
  getTones: () => get<{ tones: { id: string; label: string; label_zh: string; icon: string }[] }>('/api/tones').then(d => d.tones),
  getAliases: () => get<{ aliases: Record<string, string> }>('/api/aliases').then(d => d.aliases),
  getTrails: () => get<{ trails: Trail[] }>('/api/trails').then(d => d.trails),
  saveTrailStep: (trailId: string | null, step: TrailStep, name?: string) =>
    post<{ trail: Trail }>('/api/trails', { trail_id: trailId, step, name }),
  deleteTrail: (id: string) => post<{ status: string }>(`/api/trails/${id}/delete`, {}),
  getEntities: () => get<{ people: any[]; events: any[]; places: any[]; article_count?: number }>('/api/entities'),
  extractEntities: () => post<{ people: any[]; events: any[]; places: any[] }>('/api/entities/extract', {}),
  getXiCi: (lang: string) => get<XiCi>(`/api/xici?lang=${lang}`),
  generateXiCi: (lang: string) => post<XiCi>('/api/xici/generate', { lang }),
  getSources: () => get<{ documents: RawDoc[] }>('/api/sources').then(d => d.documents),
  ingest: (source: string) => post<{ status: string; path: string }>('/api/ingest', { source }),
  ingestBrowser: (source: string) => post<{ status: string; path: string }>('/api/ingest/browser', { source }),
  uploadFiles: (files: File[], chunkPages = 20, domain?: string) => {
    const form = new FormData();
    for (const file of files) form.append('file', file);
    form.append('chunk_pages', String(chunkPages));
    if (domain) form.append('domain', domain);
    return postForm<UploadBatchResult>('/api/upload', form);
  },
  compile: () => post<{ status: string; message?: string; articles_created?: number }>('/api/compile', {}),
  compileStatus: () => get<CompileStatus>('/api/compile/status'),
  getLlmUsageSummary: (window?: Exclude<LlmUsageWindow, 'custom'>) =>
    get<LlmUsageSummary>(`/api/llm/usage/summary${buildQuery({ last: window && window !== 'all' ? window : undefined })}`),
  getLlmUsageRecent: (limit = 1, window?: Exclude<LlmUsageWindow, 'custom'>) =>
    get<LlmUsageRecentResponse>(`/api/llm/usage/recent${buildQuery({ limit, last: window && window !== 'all' ? window : undefined })}`),
  getWorkerStatus: () => get<{ busy: boolean }>('/api/worker/status'),
  lint: (deep = false) => post<{ results?: LintResults; report?: string }>('/api/lint', { deep }),
  lintFix: () => post<{ fixes?: string[]; fix_count?: number; status?: string; message?: string }>('/api/lint/fix', {}),
  cleanWiki: () => post<{ removed: number; slugs: string[] }>('/api/wiki/clean', {}),
  getHealth: () => get<{ report: { checked_at: string; results: LintResults; fixes_applied: string[] } | null }>('/api/health'),
  rebuildIndex: () => post<{ article_count: number }>('/api/index/rebuild', {}),
};
