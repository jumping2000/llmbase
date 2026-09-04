# tests/test_compile_docdate.py
import frontmatter

from llmwiki.compile import _merge_into


def test_source_ref_carries_doc_date(tmp_path, monkeypatch):
    # Drive compile_new with a mocked chat response
    import llmwiki.compile as cmod

    raw_dir = tmp_path / "raw" / "doc-a"
    raw_dir.mkdir(parents=True)
    post = frontmatter.Post("Contenuto del documento A")
    post.metadata["title"] = "Doc A"
    post.metadata["source"] = "doc-a.pdf"
    post.metadata["type"] = "pdf"
    post.metadata["doc_date"] = "2024-03-01"
    post.metadata["compiled"] = False
    (raw_dir / "index.md").write_text(frontmatter.dumps(post), encoding="utf-8")

    def fake_chat(prompt, **kwargs):
        return (
            "===ARTICLE===\nslug: concept-a\ntitle: Concept A / Concetto A\n"
            "summary: A concept\n tags: t1\ndomain: generale\n---\n"
            "## English\n\nContent A.\n\n## Italiano\n\nContenuto A.\n===END==="
        )

    monkeypatch.setattr(cmod, "chat", fake_chat)
    articles = cmod.compile_new(base_dir=tmp_path)
    assert articles
    art = frontmatter.load(str(tmp_path / "wiki" / "concepts" / "concept-a.md"))
    assert art.metadata["sources"][0]["doc_date"] == "2024-03-01"


def test_merge_dedup_key_includes_doc_date(tmp_path):
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    existing = frontmatter.Post("## English\n\nOld content.\n\n## Italiano\n\nVecchio.")
    existing.metadata["sources"] = [
        {"plugin": "pdf", "url": "doc.pdf", "title": "Doc", "doc_date": "2022-01-01"}
    ]
    p = concepts / "concept-b.md"
    p.write_text(frontmatter.dumps(existing), encoding="utf-8")

    _merge_into(
        p,
        {
            "slug": "concept-b",
            "content": "## English\n\nNew longer content that is definitely longer.\n\n## Italiano\n\nNuovo contenuto piu lungo.",
            "sources": [
                {
                    "plugin": "pdf",
                    "url": "doc.pdf",
                    "title": "Doc",
                    "doc_date": "2024-05-01",
                }
            ],
        },
    )
    merged = frontmatter.load(str(p))
    dates = sorted(s["doc_date"] for s in merged.metadata["sources"])
    assert dates == ["2022-01-01", "2024-05-01"]
