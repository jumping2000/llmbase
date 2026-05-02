import sys
import types

import frontmatter


def test_ingest_file_preserves_original_uploaded_name(tmp_kb, tmp_path):
    sys.modules.setdefault("requests", types.SimpleNamespace())
    sys.modules.setdefault("bs4", types.SimpleNamespace(BeautifulSoup=object))
    sys.modules.setdefault("markdownify", types.SimpleNamespace(markdownify=lambda *args, **kwargs: ""))
    from llmwiki.ingest import ingest_file

    src = tmp_path / "upload-tmp-123.txt"
    src.write_text("body", encoding="utf-8")

    dest = ingest_file(str(src), base_dir=tmp_kb, original_name="Quarterly Report.txt")

    assert dest.name == "Quarterly Report.txt"
    assert dest.parent.name == "quarterly-report"

    meta_path = dest.parent / "index.md"
    post = frontmatter.load(str(meta_path))
    assert post.metadata["title"] == "Quarterly Report"
    assert post.metadata["source"] == "Quarterly Report.txt"
    assert post.metadata["file"] == "Quarterly Report.txt"


def test_ingest_pdf_preserves_original_uploaded_name(tmp_kb, tmp_path, monkeypatch):
    from llmwiki.pdf import ingest_pdf

    src = tmp_path / "upload-tmp-456.pdf"
    src.write_bytes(b"%PDF-1.4\n")

    def fake_pdf_to_markdown(_pdf_path, _chunk_pages):
        return [{
            "title": "Board Report",
            "content": "Converted content",
            "page_start": 1,
            "page_end": 3,
            "metadata": {"author": "A", "total_pages": 3},
        }]

    monkeypatch.setattr("llmwiki.pdf.pdf_to_markdown", fake_pdf_to_markdown)

    paths = ingest_pdf(str(src), chunk_pages=20, base_dir=tmp_kb, original_name="Board Report.pdf")

    assert len(paths) == 1
    out = paths[0]
    assert out.parent.name == "board-report"

    post = frontmatter.load(str(out))
    assert post.metadata["source"] == "Board Report.pdf"
