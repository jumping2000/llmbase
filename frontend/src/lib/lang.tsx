import { createContext, useContext, useState, type ReactNode } from 'react';

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

const LangContext = createContext<{
  lang: Lang;
  setLang: (l: Lang) => void;
}>({ lang: DEFAULT_LANG, setLang: () => {} });

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    if (typeof window === 'undefined') return DEFAULT_LANG;
    const stored = localStorage.getItem('llmbase-lang');
    return isValidLang(stored) ? stored : DEFAULT_LANG;
  });

  const setLang = (l: Lang) => {
    setLangState(l);
    localStorage.setItem('llmbase-lang', l);
  };

  return (
    <LangContext.Provider value={{ lang, setLang }}>
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
