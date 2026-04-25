import { useState, useEffect } from 'react';
import { Icon } from '../components/Icon';
import { Markdown } from '../components/Markdown';
import { Shimmer } from '../components/Loading';
import { api } from '../lib/api';
import { useLang } from '../lib/lang';
import { useTrail } from '../lib/trail';

interface PromotionInfo {
  promoted: boolean;
  reason?: string;
  slug?: string;
  title?: string;
  path?: string;
  merged?: boolean;
}
interface QAPair { question: string; answer: string; promotion?: PromotionInfo; }
interface ToneOption { id: string; label: string; label_zh: string; icon: string; }

const FALLBACK_TONES: ToneOption[] = [
  { id: 'default', label: 'Default', label_zh: '默认', icon: 'chat' },
  { id: 'caveman', label: 'Caveman', label_zh: '原始人', icon: 'pets' },
  { id: 'wenyan', label: '文言文', label_zh: '文言文', icon: 'history_edu' },
  { id: 'scholar', label: 'Scholar', label_zh: '学术', icon: 'school' },
  { id: 'eli5', label: 'ELI5', label_zh: '幼儿园', icon: 'child_care' },
];

export function QA() {
  const { lang } = useLang();
  const it = lang === 'it' || lang === 'en-it';
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [promotion, setPromotion] = useState<PromotionInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [fileBack, setFileBack] = useState(true);
  const [promote, setPromote] = useState(true);
  const [tone, setTone] = useState(() => 'default');
  const [tones, setTones] = useState<ToneOption[]>(FALLBACK_TONES);
  const [history, setHistory] = useState<QAPair[]>([]);

  useEffect(() => {
    api.getTones().then(setTones).catch(() => setTones(FALLBACK_TONES));
  }, []);

  const { recording, recordStep, startTrailAndRecord } = useTrail();

  async function ask(deep: boolean) {
    if (!question.trim() || loading) return;
    setLoading(true);
    setAnswer('');
    setPromotion(null);
    try {
      const res = await api.ask(question, deep, fileBack, tone, promote);
      setAnswer(res.answer);
      const promo = res.promotion ?? null;
      setPromotion(promo);
      setHistory(prev => [{ question, answer: res.answer, promotion: promo ?? undefined }, ...prev]);

      // Trail recording: deep research or regular question
      if (deep && res.consulted && res.consulted.length > 0) {
        if (recording) {
          // Already recording → append to current trail
          recordStep({ type: 'query', question });
          for (const a of res.consulted) {
            recordStep({ type: 'article', slug: a.slug, title: a.title });
          }
        } else {
          // Not recording → start new trail from this research
          const trailName = question.length > 30 ? question.slice(0, 30) + '…' : question;
          const steps = [
            { type: 'query' as const, question },
            ...res.consulted.map(a => ({ type: 'article' as const, slug: a.slug, title: a.title })),
          ];
          startTrailAndRecord(trailName, steps);
        }
      } else if (recording) {
        recordStep({ type: 'query', question });
      }
    } catch (e) {
      setAnswer(it ? 'Errore: impossibile ottenere una risposta. Controlla la connessione API.' : 'Error: Failed to get response. Check API connection.');
    }
    setLoading(false);
  }

  return (
    <div className="p-8 max-w-[800px] mx-auto">
      <div className="mb-6">
        <p className="text-xs uppercase tracking-widest text-on-surface-variant mb-1">Editorial Intelligence</p>
        <h1 className="font-headline text-3xl font-bold">{it ? 'Cura le intuizioni.' : 'Curate Insights.'}</h1>
      </div>

      {/* Input */}
      <div className="bg-surface-container rounded-xl border border-outline-variant/30 p-5 mb-6">
        <textarea
          placeholder={it ? 'Chiedi a LLMBase qualcosa sulla tua wiki curata...' : 'Ask LLMBase anything about your curated wiki...'}
          className="w-full bg-transparent text-on-surface placeholder:text-outline outline-none resize-none text-base font-body"
          rows={3}
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(true); } }}
        />
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-outline-variant/20">
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-on-surface-variant cursor-pointer">
              <input
                type="checkbox"
                checked={fileBack}
                onChange={e => setFileBack(e.target.checked)}
                className="rounded border-outline-variant"
              />
              {it ? 'Archivia negli output' : 'File to wiki'}
            </label>
            <label
              className="flex items-center gap-2 text-sm text-on-surface-variant cursor-pointer"
              title={it ? 'L\'LLM decide se vale la pena promuovere la risposta a nuovo concetto' : 'LLM decides whether to promote into a new concept'}
            >
              <input
                type="checkbox"
                checked={promote}
                onChange={e => setPromote(e.target.checked)}
                className="rounded border-outline-variant"
              />
              {it ? 'Promuovi a concetto' : 'Promote to concept'}
            </label>
            {/* Tone selector */}
            <div className="flex items-center gap-1">
              {tones.map(t => (
                <button
                  key={t.id}
                  onClick={() => setTone(t.id)}
                  title={t.label}
                  className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors ${
                    tone === t.id
                      ? 'bg-primary/15 text-primary font-medium'
                      : 'text-on-surface-variant hover:bg-surface-container-highest/50'
                  }`}
                >
                  <Icon name={t.icon} className="text-[14px]" />
                  <span className="hidden sm:inline">{t.label}</span>
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={() => ask(true)}
            disabled={loading}
            className="flex items-center gap-1.5 px-5 py-2 bg-primary text-on-primary rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <Icon name="psychology" className="text-[16px]" />
            {loading ? (it ? 'Ricerca in corso...' : 'Researching...') : (it ? 'Chiedi' : 'Ask')}
          </button>
        </div>
      </div>

      {/* Answer */}
      {loading && (
        <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/20">
          <Shimmer lines={6} />
        </div>
      )}

      {answer && !loading && (
        <div className="bg-surface-container rounded-xl p-6 border border-outline-variant/20 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Icon name="auto_awesome" className="text-primary text-[18px]" />
            <span className="text-xs uppercase tracking-widest text-on-surface-variant">The Synthesis</span>
          </div>
          <Markdown content={answer} />
          {promotion && (
            <div className="mt-5 pt-4 border-t border-outline-variant/20">
              {promotion.promoted ? (
                <div className="flex items-start gap-2 text-sm">
                  <Icon name="bookmark_added" className="text-primary text-[16px] mt-0.5" />
                  <div>
                    <div className="text-on-surface">
                      {it ? 'Promosso a concetto' : 'Promoted to concept'}
                      {': '}
                      <a
                        href={`/wiki/${promotion.slug}`}
                        className="text-primary hover:underline font-medium"
                      >
                        {promotion.title || promotion.slug}
                      </a>
                      {promotion.merged && (
                        <span className="ml-2 text-xs text-on-surface-variant">
                          {it ? '(unito a un concetto esistente)' : '(merged into existing)'}
                        </span>
                      )}
                    </div>
                    {promotion.reason && (
                      <div className="text-xs text-on-surface-variant mt-1">{promotion.reason}</div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-2 text-sm text-on-surface-variant">
                  <Icon name="info" className="text-[16px] mt-0.5" />
                  <div>
                    {it ? 'Non promosso' : 'Not promoted'}
                    {promotion.reason && <span>: {promotion.reason}</span>}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* History */}
      {history.length > 1 && (
        <div className="mt-8">
          <h3 className="text-xs uppercase tracking-widest text-on-surface-variant mb-3">Previous Queries</h3>
          <div className="space-y-2">
            {history.slice(1).map((h, i) => (
              <div
                key={i}
                className="bg-surface-low rounded-lg p-3 cursor-pointer hover:bg-surface-container transition-colors"
                onClick={() => { setQuestion(h.question); setAnswer(h.answer); }}
              >
                <p className="text-sm text-on-surface truncate">{h.question}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
