# tests/test_domains.py
from pathlib import Path

import frontmatter
import pytest

from llmwiki.domains import (
    DEFAULT_DOMAIN,
    bulk_assign_domain,
    create_domain,
    delete_domain,
    list_domains,
    normalize_domain_id,
    rename_domain,
    resolve_domain,
)


def _write_concept(base: Path, slug: str, domain: str | None = None) -> Path:
    concepts = base / "wiki" / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post("# Content")
    post.metadata["title"] = slug
    if domain:
        post.metadata["domain"] = domain
    p = concepts / f"{slug}.md"
    p.write_text(frontmatter.dumps(post), encoding="utf-8")
    return p


def test_normalize_domain_id():
    assert normalize_domain_id("  Lavoro ") == "lavoro"
    assert normalize_domain_id("Casa & Studio") == "casa-studio"
    assert normalize_domain_id(None) == DEFAULT_DOMAIN
    assert normalize_domain_id("") == DEFAULT_DOMAIN


def test_list_domains_always_includes_default(tmp_path):
    assert list_domains(tmp_path) == [{"id": DEFAULT_DOMAIN, "label": "Generale"}]


def test_create_and_rename_domain(tmp_path):
    create_domain("Lavoro", tmp_path)
    ids = [d["id"] for d in list_domains(tmp_path)]
    assert "lavoro" in ids
    rename_domain("lavoro", "Ufficio", tmp_path)
    entry = next(d for d in list_domains(tmp_path) if d["id"] == "lavoro")
    assert entry["label"] == "Ufficio"


def test_resolve_domain_unknown_falls_back(tmp_path):
    assert resolve_domain("inesistente", tmp_path) == DEFAULT_DOMAIN
    create_domain("Studio", tmp_path)
    assert resolve_domain("studio", tmp_path) == "studio"


def test_delete_domain_reassigns_articles(tmp_path):
    create_domain("Casa", tmp_path)
    _write_concept(tmp_path, "ricetta", "casa")
    delete_domain("casa", tmp_path)
    p = tmp_path / "wiki" / "concepts" / "ricetta.md"
    post = frontmatter.load(str(p))
    assert post.metadata.get("domain") == DEFAULT_DOMAIN
    assert "casa" not in [d["id"] for d in list_domains(tmp_path)]


def test_bulk_assign_domain(tmp_path):
    create_domain("Lavoro", tmp_path)
    _write_concept(tmp_path, "a")
    _write_concept(tmp_path, "b")
    result = bulk_assign_domain(["a", "b", "missing"], "lavoro", tmp_path)
    assert result["domain"] == "lavoro"
    assert set(result["updated"]) == {"a", "b"}
    assert result["missing"] == ["missing"]
    for slug in ("a", "b"):
        post = frontmatter.load(str(tmp_path / "wiki" / "concepts" / f"{slug}.md"))
        assert post.metadata.get("domain") == "lavoro"


def test_bulk_assign_unknown_domain_raises(tmp_path):
    _write_concept(tmp_path, "a")
    with pytest.raises(ValueError):
        bulk_assign_domain(["a"], "tipooo", tmp_path)


def test_rename_default_domain_raises(tmp_path):
    with pytest.raises(ValueError):
        rename_domain("generale", "X", tmp_path)
