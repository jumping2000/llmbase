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
