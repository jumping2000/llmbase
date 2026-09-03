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
