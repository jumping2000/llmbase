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
