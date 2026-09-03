# llmwiki/domains.py
"""Domain management — first-class facets on wiki articles.

A ``domain`` is a single frontmatter field on raw docs and compiled
articles. Domains live in ``wiki/_meta/domains.json`` and are managed
from the web UI. The implicit default domain is ``generale``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import frontmatter

from .atomic import atomic_write_json
from .config import load_config

DEFAULT_DOMAIN = "generale"


def _domains_path(base_dir: Path | None) -> Path:
    cfg = load_config(base_dir)
    meta_dir = Path(cfg["paths"]["meta"])
    meta_dir.mkdir(parents=True, exist_ok=True)
    return meta_dir / "domains.json"


def list_domains(base_dir: Path | None = None) -> list[dict]:
    """Return ``[{"id": ..., "label": ...}, ...]``, always including the default."""
    domains: list[dict] = [{"id": DEFAULT_DOMAIN, "label": "Generale"}]
    path = _domains_path(base_dir)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = []
        if isinstance(data, list):
            for item in data:
                if (
                    isinstance(item, dict)
                    and item.get("id")
                    and item["id"] != DEFAULT_DOMAIN
                ):
                    domains.append(item)
    return domains


def _save_domains(domains: list[dict], base_dir: Path | None = None) -> None:
    custom = [d for d in domains if d.get("id") != DEFAULT_DOMAIN]
    atomic_write_json(_domains_path(base_dir), custom, ensure_ascii=False)


def normalize_domain_id(value: str | None) -> str:
    """Slugify an arbitrary label/input into a domain id."""
    if not value:
        return DEFAULT_DOMAIN
    s = re.sub(r"[^\w]+", "-", value.strip().lower()).strip("-")
    return s or DEFAULT_DOMAIN


def domain_exists(domain_id: str, base_dir: Path | None = None) -> bool:
    return any(d["id"] == domain_id for d in list_domains(base_dir))


def resolve_domain(value: str | None, base_dir: Path | None = None) -> str:
    """Map user input to an existing domain id, falling back to the default."""
    dom_id = normalize_domain_id(value)
    return dom_id if domain_exists(dom_id, base_dir) else DEFAULT_DOMAIN


def create_domain(label: str, base_dir: Path | None = None) -> dict:
    dom_id = normalize_domain_id(label)
    if domain_exists(dom_id, base_dir):
        return next(d for d in list_domains(base_dir) if d["id"] == dom_id)
    entry = {"id": dom_id, "label": label.strip() or dom_id}
    domains = list_domains(base_dir)
    domains.append(entry)
    _save_domains(domains, base_dir)
    return entry


def rename_domain(domain_id: str, new_label: str, base_dir: Path | None = None) -> dict:
    dom_id = normalize_domain_id(domain_id)
    if dom_id == DEFAULT_DOMAIN:
        raise ValueError("cannot rename the default domain")
    if not domain_exists(dom_id, base_dir):
        raise ValueError(f"unknown domain: {dom_id}")
    domains = list_domains(base_dir)
    for d in domains:
        if d["id"] == dom_id:
            d["label"] = new_label.strip() or d["id"]
    _save_domains(domains, base_dir)
    return next(d for d in domains if d["id"] == dom_id)


def delete_domain(domain_id: str, base_dir: Path | None = None) -> dict:
    dom_id = normalize_domain_id(domain_id)
    if dom_id == DEFAULT_DOMAIN:
        raise ValueError("cannot delete the default domain")
    if not domain_exists(dom_id, base_dir):
        raise ValueError(f"unknown domain: {dom_id}")
    domains = [d for d in list_domains(base_dir) if d["id"] != dom_id]
    _save_domains(domains, base_dir)
    reassigned = _reassign_articles(dom_id, DEFAULT_DOMAIN, base_dir)
    return {
        "deleted": dom_id,
        "reassigned": DEFAULT_DOMAIN,
        "reassigned_count": reassigned,
    }


def _set_article_domain(
    slug: str, domain_id: str, base_dir: Path | None = None
) -> bool:
    cfg = load_config(base_dir)
    path = Path(cfg["paths"]["concepts"]) / f"{slug}.md"
    if not path.exists():
        return False
    post = frontmatter.load(str(path))
    post.metadata["domain"] = domain_id
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return True


def _reassign_articles(
    from_domain: str, to_domain: str, base_dir: Path | None = None
) -> int:
    cfg = load_config(base_dir)
    concepts_dir = Path(cfg["paths"]["concepts"])
    raw_dir = Path(cfg["paths"]["raw"])
    count = 0
    if concepts_dir.exists():
        for md_file in sorted(concepts_dir.glob("*.md")):
            post = frontmatter.load(str(md_file))
            if post.metadata.get("domain", DEFAULT_DOMAIN) == from_domain:
                post.metadata["domain"] = to_domain
                md_file.write_text(frontmatter.dumps(post), encoding="utf-8")
                count += 1
    if raw_dir.exists():
        for md_file in raw_dir.rglob("*.md"):
            post = frontmatter.load(str(md_file))
            if post.metadata.get("domain") == from_domain:
                post.metadata["domain"] = to_domain
                md_file.write_text(frontmatter.dumps(post), encoding="utf-8")
                count += 1
    _rebuild(base_dir)
    return count


def bulk_assign_domain(
    slugs: list[str], domain_id: str, base_dir: Path | None = None
) -> dict:
    dom_id = normalize_domain_id(domain_id)
    if not domain_exists(dom_id, base_dir):
        raise ValueError(f"unknown domain: {dom_id}")
    updated, missing = [], []
    for slug in slugs:
        if _set_article_domain(slug, dom_id, base_dir):
            updated.append(slug)
        else:
            missing.append(slug)
    _rebuild(base_dir)
    return {"domain": dom_id, "updated": updated, "missing": missing}


def _rebuild(base_dir: Path | None) -> None:
    from .compile import rebuild_index

    rebuild_index(base_dir)
