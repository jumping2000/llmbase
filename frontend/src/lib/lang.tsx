import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

export type Lang = 'en' | 'it' | 'en-it';

export const LANG_OPTIONS: { value: Lang; label: string; icon: string }[] = [
  { value: 'en', label: 'English', icon: 'EN' },
  { value: 'it', label: 'Italiano', icon: 'IT' },
  { value: 'en-it', label: 'EN / IT', icon: 'BI' },
];

const DEFAULT_LANG: Lang = 'en-it';

function isValidLang(value: string | null): value is Lang {
  return value === 'en' || value === 'it' || value === 'en-it';
}

export function isItalianUI(lang: Lang): boolean {
  return lang === 'it' || lang === 'en-it';
}

type Dict = Record<string, string>;

export type TFunc = (key: string, vars?: Record<string, string | number>) => string;

/**
 * Load the UI strings for a language from `public/translations/<lang>.json`.
 *
 * The Flask SPA fallback answers 200 with index.html for files that do not
 * exist, so a bare `res.json()` would blow up on HTML. Guard on the
 * content-type and degrade to an empty dictionary — `t()` then renders the
 * keys themselves, which is the visible signal that the file is missing.
 *
 * `cache: 'no-cache'` forces revalidation so edits to the deployed JSON show
 * up on a plain browser reload, without a rebuild.
 */
async function loadDict(lang: Lang): Promise<Dict> {
  try {
    const res = await fetch(`/translations/${lang}.json`, { cache: 'no-cache' });
    if (!res.ok) return {};
    if (!(res.headers.get('content-type') || '').includes('json')) return {};
    const data: unknown = await res.json();
    return data && typeof data === 'object' ? (data as Dict) : {};
  } catch {
    return {};
  }
}

const warnedKeys = new Set<string>();

function translate(dict: Dict, key: string, vars?: Record<string, string | number>): string {
  let entry: string | undefined;
  if (vars && typeof vars.count === 'number') {
    entry = dict[`${key}_${vars.count === 1 ? 'one' : 'other'}`];
  }
  if (entry === undefined) entry = dict[key];

  if (entry === undefined) {
    if (!warnedKeys.has(key)) {
      warnedKeys.add(key);
      console.warn(`[i18n] missing translation key: ${key}`);
    }
    return key;
  }

  if (!vars) return entry;
  return entry.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match
  );
}

const LangContext = createContext<{
  lang: Lang;
  setLang: (l: Lang) => void;
  t: TFunc;
}>({ lang: DEFAULT_LANG, setLang: () => {}, t: key => key });

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    if (typeof window === 'undefined') return DEFAULT_LANG;
    const stored = localStorage.getItem('llmbase-lang');
    return isValidLang(stored) ? stored : DEFAULT_LANG;
  });
  const [dict, setDict] = useState<Dict | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadDict(lang).then(d => { if (!cancelled) setDict(d); });
    return () => { cancelled = true; };
  }, [lang]);

  const setLang = (l: Lang) => {
    setLangState(l);
    localStorage.setItem('llmbase-lang', l);
  };

  // Identity is stable per dictionary, so `t` can sit in an effect's
  // dependency array without re-running it on every render — Explore's d3
  // chart relies on that to redraw its labels when the language changes.
  const t = useCallback<TFunc>((key, vars) => translate(dict ?? {}, key, vars), [dict]);

  // Gate only the very first load, so no one sees raw keys flash by. Later
  // language switches keep the previous dictionary on screen until the new
  // one lands, which avoids a flicker on every toggle.
  if (dict === null) return null;

  return (
    <LangContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LangContext.Provider>
  );
}

export const useLang = () => useContext(LangContext);

/**
 * Extract the localized part from a bilingual title like "English Title / Titolo italiano"
 */
export function localizeTitle(title: string, lang: Lang): string {
  if (!title) return '';
  const parts = title.split('/').map(s => s.trim());
  if (parts.length < 2) return title;

  if (lang === 'en-it') return title;
  if (lang === 'it') return parts[1] || parts[parts.length - 1] || parts[0];
  return parts[0];
}

/**
 * Extract the requested section(s) from bilingual article content.
 */
export function extractLangContent(content: string, lang: Lang): string {
  const english = _extractFirstSection(content, ['## English']);
  const italian = _extractFirstSection(content, ['## Italiano', '## Italian']);

  if (lang === 'en-it') {
    if (english && italian) {
      return `## English\n\n${english}\n\n---\n\n## Italiano\n\n${italian}`;
    }
    return content;
  }

  if (lang === 'en' && english) {
    return english;
  }

  if (lang === 'it') {
    if (italian) return italian;
  }

  return content;
}

function _extractSection(content: string, marker: string): string | null {
  const idx = content.indexOf(marker);
  if (idx === -1) return null;
  const start = idx + marker.length;
  const nextH2 = content.indexOf('\n## ', start);
  return (nextH2 === -1 ? content.slice(start) : content.slice(start, nextH2)).trim();
}

function _extractFirstSection(content: string, markers: string[]): string | null {
  for (const marker of markers) {
    const section = _extractSection(content, marker);
    if (section) return section;
  }
  return null;
}
