/**
 * Client-side file downloads.
 *
 * The markdown we hand out already lives in the browser — the article body
 * arrives verbatim from /api/articles/<slug>, an answer is markdown in React
 * state — so no server round-trip is needed to save it.
 */

/** Trigger a browser download of `content` as `filename`. */
export function downloadText(filename: string, content: string): void {
  // charset=utf-8 matters: the wiki is bilingual EN/IT.
  const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }));
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Turn free text (a question) into a safe, readable file name stem. */
export function slugifyFilename(text: string, maxLen = 60): string {
  const slug = text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, maxLen)
    .replace(/-+$/, '');
  return slug || 'untitled';
}
