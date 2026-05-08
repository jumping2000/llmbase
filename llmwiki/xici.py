"""Xi Ci — LLM-generated guided introduction for the knowledge base.

Like a master librarian writing a guided introduction, this module
generates a living overview that ties together all articles into a
coherent intellectual framework. It adapts to the user's language
and regenerates as the knowledge base evolves.

The Xi Ci is NOT a summary — it's a meta-narrative that reveals the
structure, connections, and significance of the collected knowledge.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from .config import load_config, ensure_dirs
from .llm import chat

logger = logging.getLogger("llmbase.xici")

# ─── Customizable constants ──────────────────────────────────────
# Override to change the guided introduction behavior.
#
#     import llmwiki.xici as xici
#     xici.XICI_SYSTEM_PROMPT = "You are a Confucian scholar..."
#     xici.LANG_STYLES["it"] = "Scrivi in un italiano piu piano e contemporaneo."
#

XICI_SYSTEM_PROMPT = """You are a master librarian and intellectual guide. Your task is to write
a guided introduction for a personal knowledge base — a living preface that reveals
the deep structure and significance of the collected knowledge.

Rules:
- Write in the REQUESTED LANGUAGE and STYLE
- Do NOT list articles — weave their themes into a coherent narrative
- Reveal connections between topics that may not be obvious
- Identify the intellectual trajectory: what direction is this knowledge growing toward?
- Keep it concise: 3-5 sentences of elegant prose
- End with a question or insight that invites further exploration
- Do NOT assume any specific domain — derive everything from the actual content
- Do NOT mention "knowledge base" or "wiki" — write as if introducing a body of thought"""

LANG_STYLES = {
    "en": "Write in elegant academic English. Formal but not stiff. Like a well-crafted book preface.",
    "it": "Scrivi in un italiano elegante, saggistico e scorrevole. Tono colto ma naturale, non burocratico.",
    "en-it": "Write two parallel paragraphs: first in English, then in Italian. They should illuminate the same body of knowledge from two close but not identical rhetorical angles.",
}


def generate_xici(base_dir: Path | None = None, lang: str = "en-it") -> dict:
    """Generate Xi Ci for the given language.

    Default behavior is bilingual English/Italian. The English version is
    treated as the base text, and derived variants are translated from it.
    """
    cfg = load_config(base_dir)
    ensure_dirs(cfg)
    concepts_dir = Path(cfg["paths"]["concepts"])

    # Gather article metadata
    articles = []
    for md_file in sorted(concepts_dir.glob("*.md")):
        post = frontmatter.load(str(md_file))
        articles.append({
            "title": post.metadata.get("title", md_file.stem),
            "tags": post.metadata.get("tags", []),
            "summary": post.metadata.get("summary", ""),
        })

    if not articles:
        return {
            "text": "",
            "themes": [],
            "lang": lang,
            "generated_at": None,
            "article_count": 0,
        }

    # Collect top themes from tags
    from collections import Counter
    tag_counter = Counter()
    for a in articles:
        for t in a.get("tags", []):
            tag_counter[t] += 1
    themes = [tag for tag, _ in tag_counter.most_common(7)]

    # Step 1: Get or generate the English base
    en_xici = get_xici(base_dir, "en")
    en_text = en_xici.get("text", "")

    if not en_text or en_xici.get("article_count", 0) != len(articles):
        # Need to (re)generate the English base
        # For large KBs, use compact summary (tag frequencies + sample titles)
        # to avoid token overflow
        if len(articles) <= 80:
            overview = "\n".join(
                f"- {a['title']}: {a['summary']}"
                for a in articles
            )
        else:
            # Compact: top themes + sample titles per theme
            from collections import defaultdict
            theme_articles: dict[str, list[str]] = defaultdict(list)
            for a in articles:
                for t in a.get("tags", [])[:3]:
                    if not t.startswith("category:") and len(theme_articles[t]) < 4:
                        theme_articles[t].append(a["title"])
            top_themes = sorted(theme_articles.items(), key=lambda x: -len(x[1]))[:15]
            overview = f"Knowledge base has {len(articles)} articles across these themes:\n"
            overview += "\n".join(
                f"- {tag} ({len(titles)} articles): {', '.join(titles[:3])}"
                for tag, titles in top_themes
            )
        style = LANG_STYLES["en"]
        prompt = (
            f"Here are {len(articles)} articles in a personal knowledge base:\n\n"
            f"{overview}\n\n"
            f"Write a guided introduction for this knowledge base.\n\n"
            f"Language and style instruction:\n{style}\n\n"
            f"Remember: weave a narrative, don't list. Reveal the hidden structure."
        )
        try:
            en_text = chat(
                prompt,
                system=XICI_SYSTEM_PROMPT,
                max_tokens=1024,
                feature="xici",
                stage="generate",
                base_dir=base_dir,
            ).strip()
        except Exception as e:
            logger.error(f"[xici] English generation failed: {e}")
            en_text = ""

        # Cache the English base
        en_result = {
            "text": en_text,
            "themes": themes,
            "lang": "en",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "article_count": len(articles),
        }
        _save_xici(cfg, "en", en_result)

    # Step 2: If target lang is en, we're done
    if lang == "en":
        from .hooks import emit
        emit("xici_generated", lang="en", article_count=len(articles))
        return {
            "text": en_text,
            "themes": themes,
            "lang": "en",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "article_count": len(articles),
        }

    # Step 3: Translate from English into target language
    translate_instructions = {
        "it": (
            "Translate this guided introduction into elegant Italian. "
            "Preserve the intellectual structure and rhetorical cadence. "
            "Do not flatten it into plain summary prose."
        ),
        "en-it": (
            "Output TWO paragraphs:\n"
            "1. The original English text as-is (do not modify)\n"
            "2. An Italian version that preserves the same intellectual structure\n\n"
            "Separate the two paragraphs with a line containing only ---"
        ),
    }

    instruction = translate_instructions.get(lang, translate_instructions["it"])
    translate_prompt = f"{instruction}\n\nOriginal English:\n\n{en_text}"

    try:
        text = chat(
            translate_prompt,
            max_tokens=1024,
            feature="xici",
            stage="translate",
            base_dir=base_dir,
        ).strip()
    except Exception as e:
        logger.error(f"[xici] Translation to {lang} failed: {e}")
        text = en_text

    result = {
        "text": text,
        "themes": themes,
        "lang": lang,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "article_count": len(articles),
    }

    # Cache to file
    _save_xici(cfg, lang, result)

    from .hooks import emit
    emit("xici_generated", lang=lang, article_count=len(articles))

    return result


def get_xici(base_dir: Path | None = None, lang: str = "en-it") -> dict:
    """Get cached Xi Ci, or empty if not generated yet."""
    cfg = load_config(base_dir)
    meta_dir = Path(cfg["paths"]["meta"])
    path = meta_dir / f"xici-{lang}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {
        "text": "",
        "themes": [],
        "lang": lang,
        "generated_at": None,
        "article_count": 0,
    }


def _save_xici(cfg: dict, lang: str, result: dict):
    """Cache Xi Ci to meta directory."""
    meta_dir = Path(cfg["paths"]["meta"])
    meta_dir.mkdir(parents=True, exist_ok=True)
    path = meta_dir / f"xici-{lang}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
