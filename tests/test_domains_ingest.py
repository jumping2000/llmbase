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
