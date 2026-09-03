import { useNavigate } from 'react-router-dom';
import { Tag } from './Tag';
import { Icon } from './Icon';
import { useLang, localizeTitle } from '../lib/lang';
import type { Article } from '../lib/api';

export function ArticleCard({ article }: { article: Article }) {
  const navigate = useNavigate();
  const { lang } = useLang();
  return (
    <div
      className="bg-surface-container rounded-xl p-5 cursor-pointer border border-outline-variant/30 hover:border-primary/50 transition-all card-shadow hover:card-shadow-lg"
      onClick={() => navigate(`/wiki/${article.slug}`)}
    >
      <h3 className="font-headline text-base font-semibold mb-2 text-on-surface">{localizeTitle(article.title, lang)}</h3>
      {article.summary && (
        <p className="text-sm text-on-surface-variant line-clamp-2 mb-3">{article.summary}</p>
      )}
      <div className="flex flex-wrap gap-1.5">
        {article.domain && (
          <span className="flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-full bg-secondary/10 text-secondary border border-secondary/20">
            <Icon name="category" className="text-[12px]" />
            {article.domain}
          </span>
        )}
        {article.tags?.map(t => <Tag key={t} label={t} />)}
      </div>
    </div>
  );
}
