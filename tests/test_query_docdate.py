# tests/test_query_docdate.py
import frontmatter

from llmwiki.query import _gather_context, SYSTEM_PROMPT


def test_context_includes_source_dates(tmp_path):
    concepts = tmp_path / "wiki" / "concepts"
    meta = tmp_path / "wiki" / "_meta"
    outputs = tmp_path / "outputs"
    for d in (concepts, meta, outputs):
        d.mkdir(parents=True)
    post = frontmatter.Post("## English\n\nContent about mainframe.\n\n## Italiano\n\nContenuto.")
    post.metadata["title"] = "Mainframe"
    post.metadata["summary"] = "Mainframe architecture"
    post.metadata["tags"] = ["hw"]
    post.metadata["sources"] = [
        {"plugin": "pdf", "url": "a.pdf", "title": "Manuale 2024", "doc_date": "2024-03-01"},
        {"plugin": "pdf", "url": "b.pdf", "title": "Manuale 2022", "doc_date": "2022-01-01"},
    ]
    (concepts / "mainframe.md").write_text(frontmatter.dumps(post), encoding="utf-8")

    cfg = {
        "paths": {
            "concepts": str(concepts),
            "meta": str(meta),
            "outputs": str(outputs),
        }
    }
    ctx = _gather_context("mainframe", cfg)
    joined = "".join(c["content"] for c in ctx)
    assert "2024-03-01" in joined
    assert "2022-01-01" in joined


def test_system_prompt_has_recency_rule():
    assert "most recent" in SYSTEM_PROMPT.lower() or "più recente" in SYSTEM_PROMPT.lower()
