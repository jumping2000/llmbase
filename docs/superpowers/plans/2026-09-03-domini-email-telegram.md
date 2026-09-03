# Domini, Email Ingestion e Bot Telegram — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere a llmbase i domini (faccette su una KB unica), un bot Telegram long-polling e l'ingestione email via IMAP con tag `[dominio]` nel subject.

**Architecture:** Tutto riusa il registro `llmwiki/operations.py` come fonte di verità e le pipeline esistenti (`ingest_file`/`ingest_pdf` → `compile` → `concepts`). Un nuovo modulo `domains.py` aggiunge il campo `domain` al frontmatter e filtri su search/ask/index. Telegram ed Email sono thread dedicati avviati nel lifespan di `asgi.py`, accanto al worker.

**Tech Stack:** Python 3.12 (Flask, a2wsgi/ASGI, `mcp`), `imaplib`+`email` stdlib, `requests`, `markdownify`, PyMuPDF, React + TypeScript (Vite).

**Spec:** `docs/superpowers/specs/2026-09-03-domini-email-telegram-design.md`

**Ordine:** Parte 1 (Domini) → Parte 2 (Telegram) → Parte 3 (Email). Ogni parte produce software testabile e funzionante da sola.

---

# Parte 1 — Domini

## File map (Parte 1)

- Create: `llmwiki/domains.py` — CRUD domini + assegnazione articoli
- Create: `tests/test_domains.py`
- Modify: `llmwiki/ingest.py` — `ingest_file(..., domain=...)`
- Modify: `llmwiki/pdf.py` — `ingest_pdf(..., domain=...)`
- Modify: `llmwiki/search.py` — `search(..., domain=...)`
- Modify: `llmwiki/query.py` — `query(..., domain=...)`, `query_with_search(..., domain=...)`
- Modify: `llmwiki/compile.py` — `rebuild_index` include `domain`; carry/suggest dominio in `compile_new`
- Modify: `llmwiki/operations.py` — param `domain` su `kb_search`/`kb_ask`; nuove op `kb_domains_*`
- Modify: `llmwiki/web.py` — API `/api/domains`, `/api/articles/bulk-domain`, param `domain`
- Modify: frontend (`api.ts`, `lib/domains.tsx`, `components/DomainSelect.tsx`, `components/DomainManager.tsx`, `App.tsx`, `Layout.tsx`)

---

### Task 1: Modulo `llmwiki/domains.py`

**Files:**
- Create: `llmwiki/domains.py`
- Create: `tests/test_domains.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_domains.py
from pathlib import Path

import frontmatter

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domains.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llmwiki.domains'`

- [ ] **Step 3: Write the module**

```python
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
                if isinstance(item, dict) and item.get("id") and item["id"] != DEFAULT_DOMAIN:
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
    return {"deleted": dom_id, "reassigned": DEFAULT_DOMAIN, "reassigned_count": reassigned}


def _set_article_domain(slug: str, domain_id: str, base_dir: Path | None = None) -> bool:
    cfg = load_config(base_dir)
    path = Path(cfg["paths"]["concepts"]) / f"{slug}.md"
    if not path.exists():
        return False
    post = frontmatter.load(str(path))
    post.metadata["domain"] = domain_id
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return True


def _reassign_articles(from_domain: str, to_domain: str, base_dir: Path | None = None) -> int:
    cfg = load_config(base_dir)
    concepts_dir = Path(cfg["paths"]["concepts"])
    count = 0
    if concepts_dir.exists():
        for md_file in sorted(concepts_dir.glob("*.md")):
            post = frontmatter.load(str(md_file))
            if post.metadata.get("domain", DEFAULT_DOMAIN) == from_domain:
                post.metadata["domain"] = to_domain
                md_file.write_text(frontmatter.dumps(post), encoding="utf-8")
                count += 1
    _rebuild(base_dir)
    return count


def bulk_assign_domain(slugs: list[str], domain_id: str, base_dir: Path | None = None) -> dict:
    dom_id = resolve_domain(domain_id, base_dir)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_domains.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add llmwiki/domains.py tests/test_domains.py
git commit -m "feat: modulo domini (CRUD + assegnazione articoli)"
```

---

### Task 2: `ingest_file` e `ingest_pdf` accettano `domain`

**Files:**
- Modify: `llmwiki/ingest.py:220-271` (funzione `ingest_file`)
- Modify: `llmwiki/pdf.py:66-128` (funzione `ingest_pdf`)
- Test: `tests/test_domains_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_domains_ingest.py
import frontmatter

from llmwiki.ingest import ingest_file
from llmwiki.pdf import ingest_pdf


def test_ingest_file_writes_domain(tmp_path):
    src = tmp_path / "note.md"
    src.write_text("# Hello\n", encoding="utf-8")
    dest = ingest_file(str(src), tmp_path, domain="lavoro")
    post = frontmatter.load(str(dest))
    assert post.metadata["domain"] == "lavoro"


def test_ingest_pdf_writes_domain(tmp_path):
    import pytest

    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "test content")
    doc.save(str(pdf_path))
    doc.close()
    paths = ingest_pdf(str(pdf_path), chunk_pages=0, base_dir=tmp_path, domain="studio")
    post = frontmatter.load(str(paths[0]))
    assert post.metadata["domain"] == "studio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domains_ingest.py -v`
Expected: FAIL — `ingest_file()` got an unexpected keyword argument 'domain'

- [ ] **Step 3: Modify `ingest_file`**

In `llmwiki/ingest.py`, change the signature and both frontmatter write sites:

```python
def ingest_file(
    file_path: str,
    base_dir: Path | None = None,
    original_name: str | None = None,
    domain: str | None = None,
) -> Path:
```

Inside the `.md` branch (after `post.metadata["compiled"] = False`):

```python
        post.metadata["type"] = "local_file"
        post.metadata["compiled"] = False
        if domain:
            post.metadata["domain"] = domain
```

Inside the else branch (companion `index.md`, after `meta.metadata["compiled"] = False`):

```python
        meta.metadata["file"] = logical_name
        meta.metadata["compiled"] = False
        if domain:
            meta.metadata["domain"] = domain
```

- [ ] **Step 4: Modify `ingest_pdf`**

In `llmwiki/pdf.py`, change the signature:

```python
def ingest_pdf(
    pdf_path: str,
    chunk_pages: int = 20,
    base_dir: Path | None = None,
    original_name: str | None = None,
    domain: str | None = None,
) -> list[Path]:
```

And in the loop, after `post.metadata["compiled"] = False`:

```python
        post.metadata["compiled"] = False
        if domain:
            post.metadata["domain"] = domain
```

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_domains_ingest.py tests/test_domains.py -v`
Expected: PASS

```bash
git add llmwiki/ingest.py llmwiki/pdf.py tests/test_domains_ingest.py
git commit -m "feat: domain param su ingest_file e ingest_pdf"
```

---

### Task 3: `search()` filtra per dominio

**Files:**
- Modify: `llmwiki/search.py:41-77` (funzione `search`)
- Test: `tests/test_domains_search.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_domains_search.py
import frontmatter

from llmwiki.search import search


def _write_concept(tmp_path, slug, title, domain):
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(f"# {title}")
    post.metadata["title"] = title
    post.metadata["summary"] = "unico termine comune"
    post.metadata["tags"] = []
    post.metadata["domain"] = domain
    (concepts / f"{slug}.md").write_text(frontmatter.dumps(post), encoding="utf-8")


def test_search_filters_by_domain(tmp_path):
    _write_concept(tmp_path, "lavoro-doc", "Contratto", "lavoro")
    _write_concept(tmp_path, "studio-doc", "Esame", "studio")
    all_res = search("comune", base_dir=tmp_path)
    assert len(all_res) == 2
    work_res = search("comune", base_dir=tmp_path, domain="lavoro")
    assert [r["slug"] for r in work_res] == ["lavoro-doc"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domains_search.py -v`
Expected: FAIL — `search() got an unexpected keyword argument 'domain'`

- [ ] **Step 3: Modify `search()`**

In `llmwiki/search.py`, change the signature and add the filter inside the corpus loop:

```python
def search(query: str, top_k: int = 10, base_dir: Path | None = None, domain: str | None = None) -> list[dict]:
```

Inside the loop `for md_file in list(concepts_dir.glob("*.md")) + list(outputs_dir.glob("*.md")):`, right after `post = frontmatter.load(str(md_file))`:

```python
        post = frontmatter.load(str(md_file))
        if domain and post.metadata.get("domain", "generale") != domain:
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_domains_search.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add llmwiki/search.py tests/test_domains_search.py
git commit -m "feat: filtro per dominio in search()"
```

---

### Task 4: `query()` e `query_with_search()` filtrano per dominio

**Files:**
- Modify: `llmwiki/query.py:68-127` (`query`), `:131-168` (`query_with_search`), `:522-560` (`_gather_context`)
- Test: `tests/test_domains_query.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_domains_query.py
from llmwiki.query import _filter_index_by_domain


def test_filter_index_by_domain():
    index = [
        {"slug": "a", "title": "A", "domain": "lavoro"},
        {"slug": "b", "title": "B", "domain": "studio"},
        {"slug": "c", "title": "C"},
    ]
    assert _filter_index_by_domain(index, None) == index
    assert [e["slug"] for e in _filter_index_by_domain(index, "lavoro")] == ["a"]
    assert [e["slug"] for e in _filter_index_by_domain(index, "generale")] == ["c"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domains_query.py -v`
Expected: FAIL — `ImportError: cannot import name '_filter_index_by_domain'`

- [ ] **Step 3: Add helper and thread `domain` through `query.py`**

Add this module-level function (e.g. just above `_gather_context`):

```python
def _filter_index_by_domain(index: list[dict], domain: str | None) -> list[dict]:
    """Filter index entries to a single domain. ``domain=None`` = no filter."""
    if not domain:
        return index
    return [e for e in index if e.get("domain", "generale") == domain]
```

Change `query()` signature to accept `domain: str | None = None`, and pass it to `_gather_context`:

```python
    context_files = _gather_context(question, cfg, domain)
```

Change `_gather_context` signature and filter inside the article loop:

```python
def _gather_context(question: str, cfg: dict, domain: str | None = None) -> list[dict]:
```

Right after `post = frontmatter.load(str(md_file))` inside the `for md_file in concepts_dir.glob("*.md"):` loop:

```python
        post = frontmatter.load(str(md_file))
        if domain and post.metadata.get("domain", "generale") != domain:
            continue
```

Change `query_with_search()` signature to accept `domain: str | None = None`, and filter right after the index is loaded:

```python
    index = _load_index(meta_dir)
    if not index:
        return "Wiki is empty. Run `llmbase compile` first."

    index = _filter_index_by_domain(index, domain)
    if not index:
        return f"No articles found for domain '{domain}'. Run `llmbase compile` first."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_domains_query.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add llmwiki/query.py tests/test_domains_query.py
git commit -m "feat: filtro per dominio in query e query_with_search"
```

---

### Task 5: `rebuild_index` include `domain`

**Files:**
- Modify: `llmwiki/compile.py:340-371` (funzione `rebuild_index`)
- Test: `tests/test_domains_index.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_domains_index.py
import json

import frontmatter

from llmwiki.compile import rebuild_index


def test_rebuild_index_includes_domain(tmp_path):
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post("# T")
    post.metadata["title"] = "T"
    post.metadata["domain"] = "lavoro"
    (concepts / "t.md").write_text(frontmatter.dumps(post), encoding="utf-8")
    rebuild_index(tmp_path)
    index = json.loads((tmp_path / "wiki" / "_meta" / "index.json").read_text(encoding="utf-8"))
    assert index[0]["domain"] == "lavoro"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domains_index.py -v`
Expected: FAIL — `KeyError: 'domain'`

- [ ] **Step 3: Modify `rebuild_index`**

In `llmwiki/compile.py`, inside `rebuild_index`, add `domain` to each entry:

```python
        entry = {
            "slug": md_file.stem,
            "title": post.metadata.get("title", md_file.stem),
            "summary": post.metadata.get("summary", ""),
            "tags": post.metadata.get("tags", []),
            "sources": post.metadata.get("sources", []),
            "domain": post.metadata.get("domain", "generale"),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_domains_index.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add llmwiki/compile.py tests/test_domains_index.py
git commit -m "feat: campo domain in index.json"
```

---

### Task 6: `compile_new` porta il dominio raw → articolo (suggerimento LLM se assente)

**Files:**
- Modify: `llmwiki/compile.py:443-481` (`_parse_article_block`), `:529-561` (`_write_article`), `:210-300` (`compile_new` loop + prompt)
- Test: `tests/test_domains_compile.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_domains_compile.py
import frontmatter

from llmwiki.compile import _parse_article_block, _write_article


def test_parse_article_block_reads_domain():
    block = "slug: x\n---\n# Body"
    assert "domain" not in _parse_article_block(block)
    block2 = "slug: x\ndomain: lavoro\n---\n# Body"
    assert _parse_article_block(block2)["domain"] == "lavoro"


def test_write_article_persists_domain(tmp_path):
    concepts = tmp_path / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    p = _write_article({"slug": "x", "title": "X", "summary": "", "tags": [],
                        "sources": [], "content": "# Body", "domain": "studio"}, concepts)
    post = frontmatter.load(str(p))
    assert post.metadata["domain"] == "studio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domains_compile.py -v`
Expected: FAIL — second assertion in `test_parse_article_block_reads_domain` (`KeyError`)

- [ ] **Step 3: Modify parsing and writing**

In `_parse_article_block`, add `domain` to the parsed metadata keys:

```python
            if key in ("slug", "title", "summary"):
                meta[key] = value
            elif key == "tags":
                meta["tags"] = [t.strip() for t in value.split(",")]
            elif key == "domain":
                meta["domain"] = value
```

In `_write_article`, persist `domain` in the new-article frontmatter (after `post.metadata["sources"] = ...`):

```python
    post.metadata["sources"] = article.get("sources", [])
    post.metadata["domain"] = article.get("domain") or "generale"
```

- [ ] **Step 4: Modify `compile_new` to carry/suggest domain**

In `llmwiki/compile.py`, in `compile_new`'s loop, right after `articles = _parse_compile_response(response)`:

```python
        articles = _parse_compile_response(response)
        raw_domain = post.metadata.get("domain")
        for article in articles:
            article["domain"] = raw_domain or resolve_domain(article.get("domain"), base_dir)
```

Add the import at the top of the function body (or module import): `from .domains import resolve_domain` (lazy import inside the loop is fine to avoid import cycles):

```python
        from .domains import resolve_domain
        articles = _parse_compile_response(response)
        raw_domain = post.metadata.get("domain")
        for article in articles:
            article["domain"] = raw_domain or resolve_domain(article.get("domain"), base_dir)
```

Then, to let the LLM *suggest* a domain, extend `COMPILE_USER_PROMPT`. Add a `{domains}` placeholder:

- In `COMPILE_USER_PROMPT`, after the `Please:` line and before item 1, insert:

```
Available domains: {domains}
Assign each article a `domain:` field from this list. If unsure, use `generale`.
```

- In `compile_new`, where the prompt is formatted, add the domains value:

```python
        from .domains import list_domains
        domains_text = ", ".join(d["id"] for d in list_domains(base_dir))
        prompt = COMPILE_USER_PROMPT.format(
            title=title,
            content=content[:15000],
            existing=existing_text,
            article_format=COMPILE_ARTICLE_FORMAT,
            domains=domains_text,
        )
```

And in `COMPILE_ARTICLE_FORMAT`, add a `domain:` example line after the frontmatter examples. The exact text inside `COMPILE_USER_PROMPT`'s `===ARTICLE===` block currently shows:

```
===ARTICLE===
slug: concept-name-here
title: English Title / Titolo italiano
summary: One-line summary in English
tags: tag1, tag2, tag3
---
```

Change to:

```
===ARTICLE===
slug: concept-name-here
title: English Title / Titolo italiano
summary: One-line summary in English
tags: tag1, tag2, tag3
domain: generale
---
```

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_domains_compile.py -v`
Expected: PASS

```bash
git add llmwiki/compile.py tests/test_domains_compile.py
git commit -m "feat: dominio raw→articolo al compile, suggerimento LLM se assente"
```

---

### Task 7: `operations.py` — param `domain` e nuove op `kb_domains_*`

**Files:**
- Modify: `llmwiki/operations.py` (`_op_search`, `_op_ask`, registry)
- Test: `tests/test_domains_operations.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_domains_operations.py
from llmwiki.operations import dispatch, get


def test_kb_domains_list(tmp_path):
    result = dispatch("kb_domains_list", tmp_path, {})
    assert {"id": "generale", "label": "Generale"} in result["domains"]


def test_kb_domains_create_and_bulk_assign(tmp_path):
    dispatch("kb_domains_create", tmp_path, {"label": "Casa"})
    ids = [d["id"] for d in dispatch("kb_domains_list", tmp_path, {})["domains"]]
    assert "casa" in ids
    result = dispatch("kb_domains_bulk_assign", tmp_path, {"slugs": [], "domain": "casa"})
    assert result["domain"] == "casa"


def test_kb_search_schema_has_domain():
    op = get("kb_search")
    assert "domain" in op.params["properties"]
    op_ask = get("kb_ask")
    assert "domain" in op_ask.params["properties"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domains_operations.py -v`
Expected: FAIL — `KeyError: 'unknown operation: kb_domains_list'`

- [ ] **Step 3: Modify `_op_search` and `_op_ask`**

In `llmwiki/operations.py`:

```python
def _op_search(base_dir: Path, query: str, top_k: int = 10, domain: str | None = None) -> dict:
    from .search import search
    return {"results": search(query, top_k=top_k, base_dir=base_dir, domain=domain)}
```

Add `domain: str | None = None` to `_op_ask` and forward it:

```python
def _op_ask(
    base_dir: Path,
    question: str,
    tone: str = "default",
    file_back: bool = False,
    deep: bool = True,
    promote: bool = False,
    model: str | None = None,
    api_key: str | None = None,
    domain: str | None = None,
) -> dict:
    from .query import query, query_with_search
    if deep:
        result = query_with_search(
            question,
            base_dir=base_dir,
            tone=tone,
            file_back=file_back,
            return_context=True,
            promote=promote,
            model=model,
            api_key=api_key,
            domain=domain,
        )
        if isinstance(result, dict):
            return result
        return {"answer": result}
    answer = query(
        question,
        file_back=file_back,
        base_dir=base_dir,
        tone=tone,
        model=model,
        api_key=api_key,
        domain=domain,
    )
    return {"answer": answer}
```

- [ ] **Step 4: Add domain handlers and register new ops**

Add these handler functions (near the other `_op_*` handlers):

```python
def _op_domains_list(base_dir: Path) -> dict:
    from .domains import list_domains
    return {"domains": list_domains(base_dir)}


def _op_domains_create(base_dir: Path, label: str) -> dict:
    from .domains import create_domain
    return {"domain": create_domain(label, base_dir)}


def _op_domains_rename(base_dir: Path, domain_id: str, label: str) -> dict:
    from .domains import rename_domain
    return {"domain": rename_domain(domain_id, label, base_dir)}


def _op_domains_delete(base_dir: Path, domain_id: str) -> dict:
    from .domains import delete_domain
    return delete_domain(domain_id, base_dir)


def _op_domains_bulk_assign(base_dir: Path, slugs: list, domain: str) -> dict:
    from .domains import bulk_assign_domain
    return bulk_assign_domain(slugs, domain, base_dir)
```

Add `"domain": {"type": "string"}` to the `properties` of both `kb_search` and `kb_ask` Operation definitions.

Append these Operations to `_CANONICAL` (before the closing `]`):

```python
    Operation(
        name="kb_domains_list",
        description="List all wiki domains (including the implicit default).",
        handler=_op_domains_list,
        params={"type": "object", "properties": {}},
        category="read",
    ),
    Operation(
        name="kb_domains_create",
        description="Create a new wiki domain from a label.",
        handler=_op_domains_create,
        params={
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "required": ["label"],
        },
        writes=True,
        category="write",
    ),
    Operation(
        name="kb_domains_rename",
        description="Rename a wiki domain's display label.",
        handler=_op_domains_rename,
        params={
            "type": "object",
            "properties": {
                "domain_id": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["domain_id", "label"],
        },
        writes=True,
        category="write",
    ),
    Operation(
        name="kb_domains_delete",
        description="Delete a domain, reassigning its articles to the default.",
        handler=_op_domains_delete,
        params={
            "type": "object",
            "properties": {"domain_id": {"type": "string"}},
            "required": ["domain_id"],
        },
        writes=True,
        category="write",
    ),
    Operation(
        name="kb_domains_bulk_assign",
        description="Assign a domain to a list of article slugs.",
        handler=_op_domains_bulk_assign,
        params={
            "type": "object",
            "properties": {
                "slugs": {"type": "array", "items": {"type": "string"}},
                "domain": {"type": "string"},
            },
            "required": ["slugs", "domain"],
        },
        writes=True,
        category="write",
    ),
```

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_domains_operations.py -v`
Expected: PASS

```bash
git add llmwiki/operations.py tests/test_domains_operations.py
git commit -m "feat: op kb_domains_* e param domain su kb_search/kb_ask"
```

---

### Task 8: API web — domini, bulk assign, param `domain`

**Files:**
- Modify: `llmwiki/web.py` (`api_search`, `api_ask`, `api_upload`; nuove route)
- Test: `tests/test_domains_web.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_domains_web.py
import pytest

from llmwiki.web import create_web_app


@pytest.fixture()
def client(tmp_path):
    app = create_web_app(tmp_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_domains_crud(client):
    r = client.get("/api/domains")
    assert r.status_code == 200
    assert {"id": "generale", "label": "Generale"} in r.get_json()["domains"]
    r = client.post("/api/domains", json={"label": "Lavoro"})
    assert r.status_code == 200
    assert r.get_json()["domain"]["id"] == "lavoro"


def test_bulk_domain_endpoint(client):
    r = client.post("/api/articles/bulk-domain", json={"slugs": [], "domain": "lavoro"})
    assert r.status_code == 200
    assert r.get_json()["domain"] == "lavoro"


def test_search_accepts_domain_param(client):
    r = client.get("/api/search?q=x&domain=lavoro")
    assert r.status_code == 200
    assert r.get_json()["query"] == "x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domains_web.py -v`
Expected: FAIL — 404 on `/api/domains`

- [ ] **Step 3: Add routes**

In `llmwiki/web.py`, place these near `api_upload`:

```python
    @app.route("/api/domains", methods=["GET"])
    def api_domains():
        from . import operations as _ops

        return jsonify(_ops.dispatch("kb_domains_list", base, {}))

    @app.route("/api/domains", methods=["POST"])
    @require_auth
    def api_domains_create():
        data = request.json or {}
        label = (data.get("label") or "").strip()
        if not label:
            return jsonify({"status": "error", "message": "label required"}), 400
        from . import operations as _ops

        return jsonify({"domain": _ops.dispatch("kb_domains_create", base, {"label": label})})

    @app.route("/api/domains/<domain_id>/rename", methods=["POST"])
    @require_auth
    def api_domains_rename(domain_id):
        data = request.json or {}
        label = (data.get("label") or "").strip()
        if not label:
            return jsonify({"status": "error", "message": "label required"}), 400
        from . import operations as _ops

        try:
            result = _ops.dispatch("kb_domains_rename", base, {"domain_id": domain_id, "label": label})
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        return jsonify({"domain": result})

    @app.route("/api/domains/<domain_id>", methods=["DELETE"])
    @require_auth
    def api_domains_delete(domain_id):
        from . import operations as _ops

        try:
            result = _ops.dispatch("kb_domains_delete", base, {"domain_id": domain_id})
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        return jsonify(result)

    @app.route("/api/articles/bulk-domain", methods=["POST"])
    @require_auth
    def api_articles_bulk_domain():
        data = request.json or {}
        slugs = data.get("slugs") or []
        domain = (data.get("domain") or "").strip()
        if not isinstance(slugs, list) or not domain:
            return jsonify({"status": "error", "message": "slugs and domain required"}), 400
        from . import operations as _ops

        try:
            result = _ops.dispatch("kb_domains_bulk_assign", base, {"slugs": slugs, "domain": domain})
        except RuntimeError as e:
            return jsonify({"status": "busy", "error": str(e)}), 409
        return jsonify(result)
```

- [ ] **Step 4: Thread `domain` through search/ask/upload**

In `api_search`, add the domain param:

```python
    @app.route("/api/search")
    def api_search():
        q = request.args.get("q", "")
        top_k = int(request.args.get("top_k", 10))
        domain = request.args.get("domain") or None
        results = search(q, top_k=top_k, base_dir=base, domain=domain)
        return jsonify({"query": q, "results": results})
```

In `api_ask`, read and forward `domain` (both deep and non-deep branches):

```python
        tone = data.get("tone", "default")
        promote = data.get("promote", False)
        domain = data.get("domain") or None
```

Deep branch — add to `ask_args`:

```python
            ask_args = {
                "question": q,
                "tone": tone,
                "file_back": file_back,
                "deep": True,
                "promote": promote,
            }
            if domain:
                ask_args["domain"] = domain
```

Non-deep branch:

```python
            result = query(
                q,
                file_back=file_back,
                base_dir=base,
                tone=tone,
                return_path=True,
                model=model,
                api_key=api_key,
                domain=domain,
            )
```

In `api_upload`, read the domain form field and pass it to both ingest paths:

```python
        try:
            chunk_pages = int(request.form.get("chunk_pages", "20"))
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid chunk_pages"}), 400
        domain = request.form.get("domain") or None
```

PDF branch:

```python
                    paths = ingest_pdf(
                        tmp_path,
                        chunk_pages=chunk_pages,
                        base_dir=base,
                        original_name=f.filename,
                        domain=domain,
                    )
```

Non-PDF branch:

```python
                    path = ingest_file(tmp_path, base, original_name=f.filename, domain=domain)
```

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_domains_web.py -v`
Expected: PASS

```bash
git add llmwiki/web.py tests/test_domains_web.py
git commit -m "feat: API domini, bulk assign e param domain su search/ask/upload"
```

---

### Task 9: Frontend — selettore dominio, manager, filtri

**Files:**
- Create: `frontend/src/lib/domains.tsx`
- Create: `frontend/src/components/DomainSelect.tsx`
- Create: `frontend/src/components/DomainManager.tsx`
- Modify: `frontend/src/lib/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx`, `frontend/src/pages/Search.tsx`, `frontend/src/pages/QA.tsx`

- [ ] **Step 1: Add domain API client methods**

In `frontend/src/lib/api.ts`, add the interface and methods. Add after the `Collection` interface:

```ts
export interface Domain {
  id: string;
  label: string;
}
```

Extend `search` and `ask` to accept an optional domain:

```ts
  search: (q: string, topK = 10, domain?: string) =>
    get<{ results: SearchResult[] }>(
      `/api/search?q=${encodeURIComponent(q)}&top_k=${topK}${domain ? `&domain=${encodeURIComponent(domain)}` : ''}`
    ).then(d => d.results),
  ask: (
    question: string,
    deep = false,
    fileBack = true,
    tone = 'default',
    promote = false,
    domain?: string,
  ) =>
    post<{
      answer: string;
      consulted?: { slug: string; title: string }[];
      promotion?: { promoted: boolean; reason?: string };
      output_path?: string;
    }>('/api/ask', { question, deep, file_back: fileBack, tone, promote, ...(domain ? { domain } : {}) }),
```

Add domain methods to the `api` object (near `getStats`):

```ts
  listDomains: () => get<{ domains: Domain[] }>('/api/domains').then(d => d.domains),
  createDomain: (label: string) => post<{ domain: Domain }>('/api/domains', { label }).then(d => d.domain),
  renameDomain: (id: string, label: string) =>
    post<{ domain: Domain }>(`/api/domains/${id}/rename`, { label }).then(d => d.domain),
  deleteDomain: (id: string) => del<{ deleted: string }>(`/api/domains/${id}`),
```

Nota: `deleteDomain` usa `DELETE`; aggiungi un helper `del` se non esiste. Se il client non ha un helper DELETE, aggiungine uno accanto a `post`:

```ts
async function del<T>(url: string): Promise<T> {
  const res = await fetch(BASE + url, { method: 'DELETE' });
  if (!res.ok) throw new ApiError(res.status, `API error: ${res.status}`);
  return res.json();
}
```

e usa `deleteDomain: (id: string) => del<{ deleted: string }>(`/api/domains/${id}`)`.

Aggiungi `bulkAssignDomain`:

```ts
  bulkAssignDomain: (slugs: string[], domain: string) =>
    post<{ domain: string; updated: string[]; missing: string[] }>('/api/articles/bulk-domain', { slugs, domain }),
```

- [ ] **Step 2: Create the shared domain context/hook**

```tsx
// frontend/src/lib/domains.tsx
import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { api, Domain } from './api';

const DEFAULT_DOMAIN = 'generale';

interface DomainsContextValue {
  domains: Domain[];
  current: string;
  setCurrent: (id: string) => void;
  reload: () => void;
}

const DomainsContext = createContext<DomainsContextValue>({
  domains: [],
  current: DEFAULT_DOMAIN,
  setCurrent: () => {},
  reload: () => {},
});

export function DomainsProvider({ children }: { children: ReactNode }) {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [current, setCurrent] = useState<string>(DEFAULT_DOMAIN);

  const reload = () => {
    api.listDomains()
      .then(setDomains)
      .catch(() => setDomains([]));
  };

  useEffect(() => {
    reload();
  }, []);

  return (
    <DomainsContext.Provider value={{ domains, current, setCurrent, reload }}>
      {children}
    </DomainsContext.Provider>
  );
}

export function useDomains() {
  return useContext(DomainsContext);
}
```

- [ ] **Step 3: Create the domain selector**

```tsx
// frontend/src/components/DomainSelect.tsx
import { useDomains } from '../lib/domains';

export default function DomainSelect() {
  const { domains, current, setCurrent } = useDomains();
  return (
    <select
      value={current}
      onChange={(e) => setCurrent(e.target.value)}
      aria-label="Dominio"
    >
      {domains.map((d) => (
        <option key={d.id} value={d.id}>{d.label}</option>
      ))}
    </select>
  );
}
```

- [ ] **Step 4: Create the domain manager panel**

```tsx
// frontend/src/components/DomainManager.tsx
import { useState } from 'react';
import { api } from '../lib/api';
import { useDomains } from '../lib/domains';

export default function DomainManager() {
  const { domains, reload } = useDomains();
  const [label, setLabel] = useState('');
  const [error, setError] = useState('');

  const create = async () => {
    if (!label.trim()) return;
    setError('');
    try {
      await api.createDomain(label.trim());
      setLabel('');
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm(`Eliminare il dominio "${id}"? I documenti tornano a "generale".`)) return;
    setError('');
    try {
      await api.deleteDomain(id);
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div>
      <h2>Domini</h2>
      <ul>
        {domains.map((d) => (
          <li key={d.id}>
            {d.label} <code>{d.id}</code>
            {d.id !== 'generale' && (
              <button onClick={() => remove(d.id)}>Elimina</button>
            )}
          </li>
        ))}
      </ul>
      <input
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="Nuovo dominio (es. Lavoro)"
      />
      <button onClick={create}>Crea</button>
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  );
}
```

- [ ] **Step 5: Wire provider + selector, thread domain into search/ask**

In `frontend/src/App.tsx`, wrap the app in the provider:

```tsx
import { DomainsProvider } from './lib/domains';
// ...
return <DomainsProvider>{/* existing tree */}</DomainsProvider>;
```

In `frontend/src/components/Layout.tsx`, import and render `<DomainSelect />` in the toolbar/header area (next to the existing navigation):

```tsx
import DomainSelect from './DomainSelect';
// ... inside the header/nav JSX:
<DomainSelect />
```

In `frontend/src/pages/Search.tsx`, read the domain from the hook and pass it to `api.search`:

```tsx
import { useDomains } from '../lib/domains';
// inside the component:
const { current } = useDomains();
// in the search handler:
api.search(q, 10, current).then(setResults);
```

In `frontend/src/pages/QA.tsx`, do the same for `api.ask`:

```tsx
import { useDomains } from '../lib/domains';
const { current } = useDomains();
// in the ask handler:
api.ask(question, deep, fileBack, tone, promote, current).then(...);
```

Add `<DomainManager />` to the appropriate settings page (reuse the existing settings/health page pattern; e.g. render it in `Health.tsx` or a new settings section).

- [ ] **Step 6: Build and verify**

Run: `npm run build` (in `frontend/`)
Expected: BUILD SUCCESS (no TS errors)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/domains.tsx frontend/src/components/DomainSelect.tsx frontend/src/components/DomainManager.tsx frontend/src/lib/api.ts frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/pages/Search.tsx frontend/src/pages/QA.tsx
git commit -m "feat(frontend): selettore e manager domini, filtri su search/ask"
```

---

### Verifica Parte 1 (criterio spec 1)

Run: `pytest tests/test_domains*.py -v`
Expected: ALL PASS

Manuale: avvia `docker compose -f compose.build.yaml up -d --build`, poi:

```powershell
curl.exe -s http://localhost:5555/api/domains
curl.exe -s -X POST http://localhost:5555/api/domains -H "Content-Type: application/json" -d '{\"label\":\"Lavoro\"}'
curl.exe -s "http://localhost:5555/api/search?q=x&domain=lavoro"
```

Expected: la lista domini include `generale`; la creazione restituisce `{"domain":{"id":"lavoro",...}}`; search accetta `domain`.

---

# Parte 2 — Bot Telegram

## File map (Parte 2)

- Create: `llmwiki/telegram.py`
- Create: `tests/test_telegram.py`
- Modify: `llmwiki/web.py` (`create_asgi_app` lifespan — avvia/ferma il bot)

---

### Task 10: Modulo `llmwiki/telegram.py` (long-polling + comandi)

**Files:**
- Create: `llmwiki/telegram.py`
- Create: `tests/test_telegram.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_telegram.py
from pathlib import Path

from llmwiki.telegram import TelegramBot


def test_domain_switch_and_default(tmp_path):
    bot = TelegramBot(tmp_path, "token", {"42"}, "generale")
    sent = []
    bot._send = lambda chat_id, text: sent.append((chat_id, text))  # noqa: SLF001
    assert bot._domain_for("42") == "generale"  # noqa: SLF001
    bot._handle_command("42", "/dominio lavoro")  # noqa: SLF001
    assert bot._domain_for("42") == "lavoro"  # noqa: SLF001
    bot._handle_command("42", "/dominio")  # noqa: SLF001
    assert any("lavoro" in t for _, t in sent)


def test_unauthorized_chat_ignored(tmp_path):
    bot = TelegramBot(tmp_path, "token", {"42"}, "generale")
    handled = []
    bot._answer = lambda chat_id, q: handled.append((chat_id, q))  # noqa: SLF001
    upd = {"message": {"chat": {"id": 999}, "text": "ciao"}}
    bot._handle_update(upd)  # noqa: SLF001
    assert handled == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_telegram.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llmwiki.telegram'`

- [ ] **Step 3: Write the module**

```python
# llmwiki/telegram.py
"""Telegram bot — long-polling gateway to query and feed the wiki.

Config (env):
  LLMBASE_TG_TOKEN            bot token (required to enable)
  LLMBASE_TG_ALLOWED_CHAT_IDS comma-separated chat ids allowed to talk
  LLMBASE_TG_DEFAULT_DOMAIN   default domain (default "generale")
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from pathlib import Path

import requests

from . import operations as ops
from .domains import resolve_domain

logger = logging.getLogger("llmbase.telegram")

_API = "https://api.telegram.org/bot{token}/{method}"

HELP_TEXT = (
    "Comandi:\n"
    "/ask <domanda> — fai una domanda alla wiki\n"
    "/cerca <testo> — cerca nella wiki\n"
    "/dominio <nome> — cambia il dominio attivo\n"
    "/dominio — mostra il dominio attivo\n"
    "Invia un PDF o un file per inserirlo nella wiki (dominio attivo).\n"
    "Qualsiasi altro messaggio viene trattato come domanda."
)


class TelegramBot:
    def __init__(self, base_dir: Path, token: str, allowed_chat_ids: set[str], default_domain: str):
        self.base_dir = base_dir
        self.token = token
        self.allowed = allowed_chat_ids
        self.default_domain = default_domain
        self._chat_domain: dict[str, str] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ── lifecycle ──────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="telegram-bot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        offset = 0
        while not self._stop.is_set():
            try:
                updates = self._call("getUpdates", timeout=30, offset=offset)
                if isinstance(updates, list):
                    for upd in updates:
                        offset = max(offset, int(upd.get("update_id", 0)) + 1)
                        self._handle_update(upd)
            except requests.RequestException as e:
                logger.warning(f"[telegram] network error: {e}")
                self._stop.wait(5)
            except Exception as e:
                logger.error(f"[telegram] unexpected error: {e}")
                self._stop.wait(5)

    # ── telegram API ───────────────────────────────────────────
    def _call(self, method: str, **params):
        url = _API.format(token=self.token, method=method)
        resp = requests.post(url, json=params, timeout=45)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram {method} failed: {data}")
        return data.get("result", {})

    def _send(self, chat_id: str, text: str) -> None:
        self._call("sendMessage", chat_id=chat_id, text=text[:4000])

    # ── update handling ────────────────────────────────────────
    def _handle_update(self, upd: dict) -> None:
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id not in self.allowed:
            logger.debug(f"[telegram] ignored chat {chat_id}")
            return
        text = msg.get("text") or ""
        if text.startswith("/"):
            self._handle_command(chat_id, text)
            return
        if msg.get("document"):
            self._handle_document(chat_id, msg["document"])
            return
        if text.strip():
            self._answer(chat_id, text.strip())

    def _handle_command(self, chat_id: str, text: str) -> None:
        parts = text.split(maxsplit=1)
        cmd = parts[0].split("@")[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd in ("/aiuto", "/help", "/start"):
            self._send(chat_id, HELP_TEXT)
        elif cmd == "/dominio":
            if arg:
                dom = resolve_domain(arg, self.base_dir)
                self._chat_domain[chat_id] = dom
                self._send(chat_id, f"Dominio attivo: {dom}")
            else:
                self._send(chat_id, f"Dominio attivo: {self._domain_for(chat_id)}")
        elif cmd == "/cerca":
            if not arg:
                self._send(chat_id, "Uso: /cerca <testo>")
                return
            self._search(chat_id, arg)
        elif cmd == "/ask":
            if not arg:
                self._send(chat_id, "Uso: /ask <domanda>")
                return
            self._answer(chat_id, arg)
        else:
            self._send(chat_id, "Comando sconosciuto. /aiuto")

    def _domain_for(self, chat_id: str) -> str:
        return self._chat_domain.get(chat_id, self.default_domain)

    def _search(self, chat_id: str, query: str) -> None:
        try:
            res = ops.dispatch(
                "kb_search",
                self.base_dir,
                {"query": query, "top_k": 5, "domain": self._domain_for(chat_id)},
            )
        except Exception as e:
            self._send(chat_id, f"Errore: {e}")
            return
        results = res.get("results", []) if isinstance(res, dict) else []
        if not results:
            self._send(chat_id, "Nessun risultato.")
            return
        lines = [f"• {r.get('title')} ({r.get('slug')})" for r in results[:5]]
        self._send(chat_id, "\n".join(lines))

    def _answer(self, chat_id: str, question: str) -> None:
        self._send(chat_id, "Cerco nella wiki…")
        try:
            res = ops.dispatch(
                "kb_ask",
                self.base_dir,
                {"question": question, "domain": self._domain_for(chat_id)},
            )
        except Exception as e:
            self._send(chat_id, f"Errore: {e}")
            return
        answer = res.get("answer", str(res)) if isinstance(res, dict) else str(res)
        self._send(chat_id, answer)

    def _handle_document(self, chat_id: str, doc: dict) -> None:
        file_id = doc.get("file_id")
        file_name = doc.get("file_name") or "upload"
        if not file_id:
            self._send(chat_id, "Documento senza file_id.")
            return
        try:
            file_info = self._call("getFile", file_id=file_id)
            file_path = file_info.get("file_path")
            if not file_path:
                self._send(chat_id, "Impossibile scaricare il file.")
                return
            url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            suffix = Path(file_name).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            domain = self._domain_for(chat_id)
            if suffix == ".pdf":
                from .pdf import ingest_pdf

                paths = ingest_pdf(tmp_path, base_dir=self.base_dir, original_name=file_name, domain=domain)
                n = len(paths)
            else:
                from .ingest import ingest_file

                ingest_file(tmp_path, self.base_dir, original_name=file_name, domain=domain)
                n = 1
            Path(tmp_path).unlink(missing_ok=True)
            self._send(chat_id, f"Ingerito {n} documento/i nel dominio {domain}. Compila per aggiornare la wiki.")
        except Exception as e:
            logger.error(f"[telegram] document error: {e}")
            self._send(chat_id, f"Errore ingest: {e}")


def resolve_telegram_bot(base_dir: Path) -> TelegramBot | None:
    """Build a bot from env vars, or None if not configured."""
    token = os.environ.get("LLMBASE_TG_TOKEN", "").strip()
    if not token:
        return None
    allowed_raw = os.environ.get("LLMBASE_TG_ALLOWED_CHAT_IDS", "")
    allowed = {c.strip() for c in allowed_raw.split(",") if c.strip()}
    default_domain = os.environ.get("LLMBASE_TG_DEFAULT_DOMAIN", "generale").strip() or "generale"
    return TelegramBot(base_dir, token, allowed, default_domain)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_telegram.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add llmwiki/telegram.py tests/test_telegram.py
git commit -m "feat: bot telegram long-polling (ask/cerca/dominio/upload)"
```

---

### Task 11: Avvio/arresto del bot nel lifespan di `create_asgi_app`

**Files:**
- Modify: `llmwiki/web.py:1640-1712` (`create_asgi_app`)

- [ ] **Step 1: Modify the lifespan**

In `llmwiki/web.py`, in `create_asgi_app`, after creating `mcp_manager`, resolve the bot:

```python
    mcp_manager = create_mcp_session_manager(base)

    from .telegram import resolve_telegram_bot

    tg_bot = resolve_telegram_bot(base)
```

Inside the lifespan `lifespan.startup` branch, after `await _cm.__aenter__()`:

```python
                if message["type"] == "lifespan.startup":
                    _cm = mcp_manager.run()
                    await _cm.__aenter__()
                    if tg_bot is not None:
                        tg_bot.start()
                    await send({"type": "lifespan.startup.complete"})
```

Inside the `lifespan.shutdown` branch, before `await send(...)`:

```python
                elif message["type"] == "lifespan.shutdown":
                    if tg_bot is not None:
                        tg_bot.stop()
                    if _cm is not None:
                        await _cm.__aexit__(None, None, None)
                        _cm = None
                    await send({"type": "lifespan.shutdown.complete"})
                    return
```

- [ ] **Step 2: Verify import and lint**

Run: `python -c "import llmwiki.web"` (in the project env)
Expected: EXIT 0 (no import errors)

- [ ] **Step 3: Commit**

```bash
git add llmwiki/web.py
git commit -m "feat: avvio/arresto bot telegram nel lifespan ASGI"
```

---

### Verifica Parte 2 (criterio spec 3)

Config in `.env`:

```
LLMBASE_TG_TOKEN=<token bot>
LLMBASE_TG_ALLOWED_CHAT_IDS=<tuo chat_id>
LLMBASE_TG_DEFAULT_DOMAIN=generale
```

Riavvia lo stack, poi da Telegram:
- `/aiuto` → risponde con l'help
- `/dominio lavoro` → "Dominio attivo: lavoro"
- `/ask <domanda>` → risposta attingendo alla wiki
- invio di un PDF → "Ingerito N documento/i nel dominio lavoro"
- un `chat_id` non whitelisted non riceve risposta.

---

# Parte 3 — Email ingestion (IMAP)

## File map (Parte 3)

- Create: `llmwiki/mail.py`
- Create: `tests/test_mail.py`
- Modify: `llmwiki/web.py` (`create_asgi_app` lifespan — avvia/ferma il poller)

---

### Task 12: Modulo `llmwiki/mail.py` (parsing + poll IMAP)

**Files:**
- Create: `llmwiki/mail.py`
- Create: `tests/test_mail.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mail.py
import email

from llmwiki.mail import (
    _body_to_markdown,
    _decode_header_value,
    _extract_attachments,
    extract_domain_from_subject,
)


def test_extract_domain_from_subject():
    assert extract_domain_from_subject("[lavoro] Report") == "lavoro"
    assert extract_domain_from_subject("Report senza tag") is None


def test_decode_header_value():
    raw = "=?utf-8?b?Q2lhbw==?="
    assert _decode_header_value(raw) == "Ciao"


def test_body_to_markdown_plain():
    msg = email.message.EmailMessage()
    msg["Subject"] = "Test"
    msg.set_content("Ciao mondo")
    assert "Ciao mondo" in _body_to_markdown(msg)


def test_extract_attachments():
    msg = email.message.EmailMessage()
    msg["Subject"] = "Test"
    msg.set_content("body")
    msg.add_attachment(b"PDFDATA", maintype="application", subtype="pdf", filename="doc.pdf")
    atts = _extract_attachments(msg)
    assert len(atts) == 1
    assert atts[0][0] == "doc.pdf"
    assert atts[0][1] == b"PDFDATA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mail.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llmwiki.mail'`

- [ ] **Step 3: Write the module**

```python
# llmwiki/mail.py
"""Email ingestion — poll an IMAP mailbox and ingest messages as wiki docs.

Config (env):
  LLMBASE_MAIL_HOST              IMAP host (required to enable)
  LLMBASE_MAIL_USER              login user
  LLMBASE_MAIL_PASSWORD          login password
  LLMBASE_MAIL_PORT              default 993
  LLMBASE_MAIL_FOLDER            default "INBOX"
  LLMBASE_MAIL_PROCESSED_FOLDER  default "Processed"
  LLMBASE_MAIL_POLL_MINUTES      default 1
  LLMBASE_MAIL_DEFAULT_DOMAIN    default "generale"

Subject tag routing: ``[lavoro] ...`` sets the domain; unknown tag → default.
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
import re
import tempfile
import threading
from email.header import decode_header
from pathlib import Path

from markdownify import markdownify as md

from .domains import resolve_domain

logger = logging.getLogger("llmbase.mail")

_SUBJECT_TAG_RE = re.compile(r"\[([^\]]+)\]")


def extract_domain_from_subject(subject: str, base_dir: Path | None = None) -> str | None:
    """Return the ``[tag]`` from a subject line, or None."""
    m = _SUBJECT_TAG_RE.search(subject or "")
    return m.group(1).strip() if m else None


def _decode_header_value(value) -> str:
    if value is None:
        return ""
    parts = decode_header(value)
    out = []
    for data, enc in parts:
        if isinstance(data, bytes):
            out.append(data.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(data)
    return "".join(out)


def _part_text(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _body_to_markdown(msg: email.message.Message) -> str:
    plain: list[str] = []
    html: list[str] = []
    parts = [msg] if not msg.is_multipart() else msg.walk()
    for part in parts:
        ctype = part.get_content_type()
        if ctype == "text/plain":
            plain.append(_part_text(part))
        elif ctype == "text/html":
            html.append(_part_text(part))
    if plain:
        return "\n\n".join(p for p in plain if p.strip())
    if html:
        return md("\n\n".join(p for p in html if p.strip()))
    return ""


def _extract_attachments(msg: email.message.Message) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for part in msg.walk():
        if part.get_content_disposition() != "attachment":
            continue
        name = _decode_header_value(part.get_filename())
        payload = part.get_payload(decode=True)
        if name and payload:
            out.append((name, payload))
    return out


class MailPoller:
    def __init__(
        self,
        base_dir: Path,
        host: str,
        user: str,
        password: str,
        port: int = 993,
        folder: str = "INBOX",
        processed_folder: str = "Processed",
        poll_minutes: int = 1,
        default_domain: str = "generale",
    ):
        self.base_dir = base_dir
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.folder = folder
        self.processed_folder = processed_folder
        self.poll_minutes = poll_minutes
        self.default_domain = default_domain
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="mail-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                n = self.poll_once()
                if n:
                    logger.info(f"[mail] ingested {n} messages")
            except Exception as e:
                logger.warning(f"[mail] poll failed: {e}")
            self._stop.wait(self.poll_minutes * 60)

    def poll_once(self) -> int:
        mail = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            mail.login(self.user, self.password)
            mail.select(self.folder, readonly=False)
            typ, data = mail.search(None, "UNSEEN")
            if typ != "OK":
                return 0
            ids = data[0].split() if data and data[0] else []
            processed = 0
            for num in ids:
                try:
                    if self._process_message(mail, num):
                        processed += 1
                except Exception as e:
                    logger.warning(f"[mail] error processing msg {num}: {e}")
            return processed
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    def _process_message(self, mail, num) -> bool:
        typ, data = mail.fetch(num, "(RFC822)")
        if typ != "OK" or not data or not data[0]:
            return False
        raw = data[0][1] if isinstance(data[0], tuple) else data[0]
        msg = email.message_from_bytes(raw)
        subject = _decode_header_value(msg.get("Subject", ""))
        tag = extract_domain_from_subject(subject, self.base_dir)
        domain = resolve_domain(tag, self.base_dir) if tag else self.default_domain

        body = _body_to_markdown(msg)
        if body.strip():
            with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
                tmp.write(body)
                body_path = tmp.name
            try:
                from .ingest import ingest_file

                ingest_file(body_path, self.base_dir, original_name=f"{subject or 'email'}.md", domain=domain)
            finally:
                Path(body_path).unlink(missing_ok=True)

        for name, payload in _extract_attachments(msg):
            suffix = Path(name).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(payload)
                att_path = tmp.name
            try:
                if suffix == ".pdf":
                    from .pdf import ingest_pdf

                    ingest_pdf(att_path, base_dir=self.base_dir, original_name=name, domain=domain)
                else:
                    from .ingest import ingest_file

                    ingest_file(att_path, self.base_dir, original_name=name, domain=domain)
            finally:
                Path(att_path).unlink(missing_ok=True)

        self._mark_processed(mail, num)
        return True

    def _mark_processed(self, mail, num) -> None:
        try:
            mail.copy(num, self.processed_folder)
            mail.store(num, "+FLAGS", "\\Deleted")
            mail.expunge()
        except Exception as e:
            logger.warning(f"[mail] move to {self.processed_folder} failed ({e}); marking seen")
            mail.store(num, "+FLAGS", "\\Seen")


def resolve_mail_poller(base_dir: Path) -> MailPoller | None:
    """Build a poller from env vars, or None if not configured."""
    host = os.environ.get("LLMBASE_MAIL_HOST", "").strip()
    user = os.environ.get("LLMBASE_MAIL_USER", "").strip()
    password = os.environ.get("LLMBASE_MAIL_PASSWORD", "")
    if not (host and user and password):
        return None
    port = int(os.environ.get("LLMBASE_MAIL_PORT", "993"))
    folder = os.environ.get("LLMBASE_MAIL_FOLDER", "INBOX")
    processed = os.environ.get("LLMBASE_MAIL_PROCESSED_FOLDER", "Processed")
    poll_minutes = int(os.environ.get("LLMBASE_MAIL_POLL_MINUTES", "1"))
    default_domain = os.environ.get("LLMBASE_MAIL_DEFAULT_DOMAIN", "generale")
    return MailPoller(
        base_dir,
        host,
        user,
        password,
        port=port,
        folder=folder,
        processed_folder=processed,
        poll_minutes=poll_minutes,
        default_domain=default_domain,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mail.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add llmwiki/mail.py tests/test_mail.py
git commit -m "feat: modulo email IMAP (subject tag, body, allegati PDF)"
```

---

### Task 13: Avvio/arresto del poller nel lifespan di `create_asgi_app`

**Files:**
- Modify: `llmwiki/web.py:1640-1712` (`create_asgi_app`)

- [ ] **Step 1: Modify the lifespan**

In `create_asgi_app`, resolve the poller next to the bot:

```python
    from .telegram import resolve_telegram_bot
    from .mail import resolve_mail_poller

    tg_bot = resolve_telegram_bot(base)
    mail_poller = resolve_mail_poller(base)
```

Startup branch:

```python
                    if tg_bot is not None:
                        tg_bot.start()
                    if mail_poller is not None:
                        mail_poller.start()
                    await send({"type": "lifespan.startup.complete"})
```

Shutdown branch:

```python
                elif message["type"] == "lifespan.shutdown":
                    if tg_bot is not None:
                        tg_bot.stop()
                    if mail_poller is not None:
                        mail_poller.stop()
                    if _cm is not None:
```

- [ ] **Step 2: Verify import**

Run: `python -c "import llmwiki.web"`
Expected: EXIT 0

- [ ] **Step 3: Commit**

```bash
git add llmwiki/web.py
git commit -m "feat: avvio/arresto poller email nel lifespan ASGI"
```

---

### Verifica Parte 3 (criterio spec 2)

Config in `.env`:

```
LLMBASE_MAIL_HOST=imap.example.com
LLMBASE_MAIL_USER=wiki@example.com
LLMBASE_MAIL_PASSWORD=<password>
LLMBASE_MAIL_POLL_MINUTES=1
```

Riavvia lo stack, invia una mail con subject `[lavoro] Report trimestrale` + allegato PDF. Entro ~1 min:
- il body appare come doc markdown in `raw/` con `domain: lavoro`
- il PDF appare chunkato con `domain: lavoro`
- una mail con tag `[sconosciuto]` atterra su `generale`.

---

## Self-review

**Spec coverage:**
- Domini: Task 1-9 (campo, CRUD UI, filtro search/ask/index, bulk assign, suggerimento LLM, backfill `generale` via default) ✓
- Telegram: Task 10-11 (long-polling, whitelist, `/dominio`, upload, ask/cerca) ✓
- Email: Task 12-13 (IMAP, subject tag, body+PDF, dedup via cartella processed) ✓

**Placeholder scan:** nessun TBD/TODO; ogni step contiene codice o comandi esatti.

**Type consistency:** `domain` è `str | None` ovunque; `resolve_domain`/`bulk_assign_domain`/`list_domains` usati con le firme definite in Task 1; `ingest_file`/`ingest_pdf` firme estese in Task 2 coerenti con gli usi in Task 10/12; `kb_domains_*` nomi coerenti tra handler, registry e route.
