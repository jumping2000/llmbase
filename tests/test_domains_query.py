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
