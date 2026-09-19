"""Orphan articles — suggest and insert the missing incoming links.

`check_orphans` in checks.py only reports articles nobody links to. This
module turns that report into an action: it proposes which existing article
should cite an orphan (tag overlap, no LLM) and writes the wiki-link into it.

Deliberately separate from fixes.py: that module owns the LLM-driven
`auto_fix` pipeline, and orphan linking must stay out of it so the global
"Repair" button never rewrites articles in bulk on its own.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from ..config import ensure_dirs, load_config

# Labels used when CREATING a new see-also line, per section key.
SEE_ALSO_LABELS: dict[str, str] = {
    "english": "See also:",
    "italian": "Vedi anche:",
}

# Labels RECOGNISED on an existing line — the wiki already carries a
# "Vedasi anche:" variant, and an existing label is never rewritten.
SEE_ALSO_PATTERNS: dict[str, str] = {
    "english": r"See\s+also",
    "italian": r"Ved(?:i|asi)\s+anche",
}

DEFAULT_MAX_ORPHAN_LINKS = 10

_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_H2_RE = re.compile(r"^##(?!#)[ \t]*(.+?)[ \t]*$", re.MULTILINE)
# Rejects whitespace, wiki-link metacharacters and path separators.
_SAFE_SLUG_RE = re.compile(r"^[^\s\[\]|/\\]+$")


def _resolve_target(raw: str, aliases: dict) -> str:
    """Normalize a wiki-link target exactly like _build_backlinks does."""
    from ..resolve import resolve_link

    return resolve_link(raw, aliases) or raw.strip().lower().replace(" ", "-")


def _is_safe_slug(slug: str) -> bool:
    if not slug or not _SAFE_SLUG_RE.match(slug):
        return False
    if ".." in slug:
        return False
    return Path(slug).name == slug


def scan_corpus(cfg: dict) -> dict[str, dict]:
    """Parse every article once.

    {slug: {"title", "tags": set[str], "stub": bool, "outgoing": set[str]}}

    export.py:91-107 computes the same tag overlap per article, re-parsing the
    whole corpus each time; this is the single-pass extraction of it.
    """
    from ..resolve import load_aliases

    concepts_dir = Path(cfg["paths"]["concepts"])
    meta_dir = Path(cfg["paths"]["meta"])
    aliases = load_aliases(meta_dir)

    corpus: dict[str, dict] = {}
    if not concepts_dir.exists():
        return corpus

    for md_file in sorted(concepts_dir.glob("*.md")):
        try:
            post = frontmatter.load(str(md_file))
        except Exception:
            # A single malformed file must not take the whole endpoint down.
            continue
        tags = {
            t.lower()
            for t in (post.metadata.get("tags") or [])
            if isinstance(t, str) and not t.lower().startswith("category:")
        }
        corpus[md_file.stem] = {
            "title": post.metadata.get("title", md_file.stem),
            "tags": tags,
            "stub": bool(post.metadata.get("stub")),
            "outgoing": {
                _resolve_target(m.group(1), aliases)
                for m in _LINK_RE.finditer(post.content)
            },
        }
    return corpus


def orphan_slugs(cfg: dict, base_dir: Path | None = None) -> list[str]:
    """Slugs with no incoming links, read from backlinks.json.

    Returns slugs, never the human-readable strings check_orphans produces —
    parsing those would turn "Backlinks map not built yet" into a slug.
    """
    concepts_dir = Path(cfg["paths"]["concepts"])
    backlinks_path = Path(cfg["paths"]["meta"]) / "backlinks.json"

    if not backlinks_path.exists():
        from ..compile import rebuild_index

        rebuild_index(base_dir)
        if not backlinks_path.exists():
            return []

    try:
        backlinks = json.loads(backlinks_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    linked = set(backlinks.keys())
    return sorted(
        f.stem for f in concepts_dir.glob("*.md") if f.stem.lower() not in linked
    )


def suggest_link_sources(target: str, corpus: dict, limit: int = 5) -> list[dict]:
    """Articles that could plausibly cite `target`, best first.

    Ranked by number of shared tags, like export.py's related_by_tags, with an
    alphabetical tie-break so the order does not depend on the filesystem.
    """
    entry = corpus.get(target)
    if not entry or not entry["tags"]:
        return []

    candidates = []
    for slug, other in corpus.items():
        if slug == target:
            continue
        # Already links the orphan: adding another link fixes nothing.
        if target in other["outgoing"]:
            continue
        # clean_garbage deletes stubs, so a link placed there would break.
        if other["stub"]:
            continue
        shared = entry["tags"] & other["tags"]
        if not shared:
            continue
        candidates.append({
            "slug": slug,
            "title": other["title"],
            "shared_tags": sorted(shared),
        })

    candidates.sort(key=lambda c: (-len(c["shared_tags"]), c["slug"]))
    return candidates[:limit]


def list_orphans(
    base_dir: Path | None = None,
    limit: int | None = None,
    candidates: int = 5,
) -> list[dict]:
    """Orphans with their suggested linking sources, from a single corpus scan."""
    cfg = load_config(base_dir)
    ensure_dirs(cfg)
    corpus = scan_corpus(cfg)

    slugs = orphan_slugs(cfg, base_dir)
    if limit is not None:
        slugs = slugs[:limit]

    return [
        {
            "slug": slug,
            "title": corpus.get(slug, {}).get("title", slug),
            "is_stub": corpus.get(slug, {}).get("stub", False),
            "candidates": suggest_link_sources(slug, corpus, limit=candidates),
        }
        for slug in slugs
    ]


def _section_spans(content: str) -> list[tuple[str, int, int]]:
    """Locate each configured language section as (key, body_start, body_end).

    The body runs to the next h2 of any kind — stopping only at the next
    *configured* header would swallow an intervening "## Notes".
    """
    from ..compile import SECTION_HEADERS

    headings = [
        (m.group(1), m.end(), m.start()) for m in _H2_RE.finditer(content)
    ]
    spans = []
    for i, (text, body_start, _) in enumerate(headings):
        body_end = headings[i + 1][2] if i + 1 < len(headings) else len(content)
        for key, header in SECTION_HEADERS:
            want = header.lstrip("#").strip()
            hit = text == want or (want.isascii() and text.lower() == want.lower())
            if hit:
                spans.append((key, body_start, body_end))
                break
    return spans


def _append_link(section: str, key: str, target: str) -> str:
    """Add [[target]] to a section body, reusing its see-also line if present."""
    pattern = re.compile(
        rf"^[ \t]*({SEE_ALSO_PATTERNS[key]})[ \t]*:[ \t]*(.*)$",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(pattern.finditer(section))
    if matches:
        # Last occurrence: the convention puts the line at the end.
        m = matches[-1]
        existing = m.group(2).strip()
        label = m.group(1)
        line = (
            f"{label}: {existing}, [[{target}]]"
            if existing
            else f"{label}: [[{target}]]"
        )
        return section[: m.start()] + line + section[m.end():]

    label = SEE_ALSO_LABELS.get(key, "See also:")
    return f"{section.rstrip()}\n\n{label} [[{target}]]\n"


def insert_see_also(
    source: str,
    target: str,
    base_dir: Path | None = None,
    cfg: dict | None = None,
) -> dict:
    """Insert a [[target]] wiki-link into `source`, one file, no reindex.

    Edits post.content with a targeted regex rather than going through
    compile._split_sections/_assemble_sections, whose round-trip drops `---`
    lines inside sections and renormalizes spacing and section order.
    """
    result = {
        "source": source,
        "target": target,
        "changed": False,
        "sections": [],
        "reason": None,
    }

    if not _is_safe_slug(source) or not _is_safe_slug(target):
        result["reason"] = "invalid_slug"
        return result
    if source == target:
        result["reason"] = "self_link"
        return result

    cfg = cfg or load_config(base_dir)
    concepts_dir = Path(cfg["paths"]["concepts"])
    source_path = concepts_dir / f"{source}.md"
    if not source_path.exists():
        result["reason"] = "source_not_found"
        return result
    if not (concepts_dir / f"{target}.md").exists():
        result["reason"] = "target_not_found"
        return result

    from ..resolve import load_aliases

    aliases = load_aliases(Path(cfg["paths"]["meta"]))
    post = frontmatter.load(str(source_path))
    content = post.content

    # Idempotency: catches [[Title]] and [[slug|Alias]], not just the literal.
    for m in _LINK_RE.finditer(content):
        if _resolve_target(m.group(1), aliases) == target:
            result["reason"] = "already_linked"
            return result

    spans = _section_spans(content)
    if spans:
        # Apply back to front so earlier offsets stay valid.
        for key, start, end in sorted(spans, key=lambda s: -s[1]):
            content = (
                content[:start]
                + _append_link(content[start:end], key, target)
                + content[end:]
            )
            result["sections"].insert(0, key)
    else:
        # Legacy articles with no bilingual structure: append to the document.
        # A synthesized header would create a section _merge_into would then
        # normalize unpredictably.
        content = f"{content.rstrip()}\n\n{SEE_ALSO_LABELS['english']} [[{target}]]\n"
        result["sections"] = ["_document"]

    post.content = content
    post.metadata["updated"] = datetime.now(UTC).isoformat()
    source_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    result["changed"] = True
    return result


def link_orphan(
    target: str,
    source: str | None = None,
    base_dir: Path | None = None,
) -> dict:
    """Link one orphan. `source=None` picks the best candidate automatically."""
    cfg = load_config(base_dir)
    ensure_dirs(cfg)

    considered = 0
    if source is None:
        corpus = scan_corpus(cfg)
        candidates = suggest_link_sources(target, corpus, limit=1)
        considered = len(candidates)
        if not candidates:
            return {
                "source": None,
                "target": target,
                "changed": False,
                "sections": [],
                "reason": "no_candidate",
                "candidates_considered": 0,
            }
        source = candidates[0]["slug"]

    result = insert_see_also(source, target, base_dir, cfg=cfg)
    result["candidates_considered"] = considered
    if result["changed"]:
        from ..compile import rebuild_index

        rebuild_index(base_dir)
    return result


def fix_orphans(
    base_dir: Path | None = None,
    max_links: int = DEFAULT_MAX_ORPHAN_LINKS,
) -> dict:
    """Link as many orphans as possible, up to max_links, in one pass.

    Returns a dict rather than the list[str] the other fix_* functions use:
    with dozens of orphans, "skipped and why" matters as much as "fixed".
    """
    cfg = load_config(base_dir)
    ensure_dirs(cfg)
    corpus = scan_corpus(cfg)

    fixes: list[str] = []
    skipped: list[dict] = []
    capped = False

    for target in orphan_slugs(cfg, base_dir):
        if len(fixes) >= max_links:
            # Stop rather than tagging every remaining orphan: the caller sees
            # what is left from the refreshed orphan list.
            capped = True
            break
        candidates = suggest_link_sources(target, corpus, limit=1)
        if not candidates:
            skipped.append({"slug": target, "reason": "no_candidate"})
            continue
        source = candidates[0]["slug"]
        result = insert_see_also(source, target, base_dir, cfg=cfg)
        if result["changed"]:
            # Keep the in-memory corpus consistent within this run.
            corpus[source]["outgoing"].add(target)
            shared = ", ".join(candidates[0]["shared_tags"])
            fixes.append(f"Linked orphan {target} from {source} (shared tags: {shared})")
        else:
            skipped.append({"slug": target, "reason": result["reason"]})

    if fixes:
        from ..compile import rebuild_index

        rebuild_index(base_dir)

    return {
        "fixes": fixes,
        "fix_count": len(fixes),
        "skipped": skipped,
        "capped": capped,
    }
