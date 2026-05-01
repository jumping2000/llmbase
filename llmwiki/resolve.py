"""Wiki-link alias resolution — maps any name to its canonical slug.

Articles may expose bilingual titles while wiki-links use either a title
variant or a slug. This module builds and queries an alias map so that any
known name resolves to the correct article.

Usage:
    from .resolve import load_aliases, resolve_link

    aliases = load_aliases(meta_dir)
    slug = resolve_link("Emptiness", aliases)
    slug = resolve_link("Vacuita", aliases)
"""

import json
import re
from pathlib import Path

import frontmatter


def build_aliases(concepts_dir: Path) -> dict[str, str]:
    """Build alias map from all article metadata.

    For each article, registers these aliases → canonical slug:
    - The slug itself (filename stem)
    - Each part of the title split by "/" (bilingual titles)
    - The full title as-is
    - merged_from slugs (from dedup history)

    All lookups are case-insensitive and whitespace-normalized.
    """
    aliases: dict[str, str] = {}

    if not concepts_dir.exists():
        return aliases

    for md_file in sorted(concepts_dir.glob("*.md")):
        slug = md_file.stem
        post = frontmatter.load(str(md_file))
        title = post.metadata.get("title", slug)

        # Register the slug itself
        _register(aliases, slug, slug)

        # Register the full title
        _register(aliases, title, slug)

        # Register each part of bilingual title "English / Italiano"
        for part in title.split("/"):
            part = part.strip()
            if part:
                _register(aliases, part, slug)

        # Register merged_from aliases (from dedup merges)
        for old_slug in post.metadata.get("merged_from", []):
            _register(aliases, old_slug, slug)

    return aliases


def save_aliases(aliases: dict[str, str], meta_dir: Path):
    """Write aliases.json to the meta directory (atomic)."""
    from .atomic import atomic_write_json
    atomic_write_json(meta_dir / "aliases.json", aliases)


def load_aliases(meta_dir: Path) -> dict[str, str]:
    """Load aliases.json from the meta directory."""
    path = meta_dir / "aliases.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def resolve_link(target: str, aliases: dict[str, str]) -> str | None:
    """Resolve a wiki-link target to a canonical slug.

    Resolution cascade:
    1. Exact match (case-insensitive)
    2. Spaces → hyphens
    3. Stripped whitespace
    4. Fuzzy: strip punctuation and compare

    Returns the canonical slug or None if unresolvable.
    """
    if not target:
        return None

    key = _normalize(target)

    # 1. Direct lookup
    if key in aliases:
        return aliases[key]

    # 2. Spaces → hyphens
    hyphenated = key.replace(" ", "-")
    if hyphenated in aliases:
        return aliases[hyphenated]

    # 3. Stripped whitespace
    stripped = key.replace(" ", "")
    if stripped in aliases:
        return aliases[stripped]

    # 4. Fuzzy: strip punctuation and compare
    fuzzy_key = _fuzzy_normalize(target)
    for alias_key, alias_slug in aliases.items():
        if _fuzzy_normalize(alias_key) == fuzzy_key:
            return alias_slug

    return None


def _normalize(text: str) -> str:
    """Normalize text for alias lookup: lowercase, strip."""
    return text.strip().lower()


def _fuzzy_normalize(text: str) -> str:
    """Aggressive normalization: remove punctuation, spaces, stopwords, case."""
    t = re.sub(r'[^\w]', '', text.strip().lower())
    # Remove English articles/prepositions that cause false mismatches
    for stop in ('the', 'of', 'in', 'on', 'and', 'for', 'its'):
        t = t.replace(stop, '')
    return t


def _register(aliases: dict[str, str], name: str, slug: str):
    """Register a name → slug mapping (normalized)."""
    key = _normalize(name)
    if key and key not in aliases:
        aliases[key] = slug
