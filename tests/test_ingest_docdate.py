# tests/test_ingest_docdate.py
import frontmatter
import pytest

from llmwiki.ingest import ingest_file
from llmwiki.pdf import ingest_pdf


@pytest.fixture(autouse=True)
def _no_llm_fallback(monkeypatch):
    monkeypatch.setattr(
        "llmwiki.docdate._docdate_config",
        lambda base_dir: {"enabled": True, "llm_fallback": False},
    )


def test_ingest_file_md_gets_doc_date(tmp_path):
    src = tmp_path / "manuale.md"
    src.write_text(
        "---\ntitle: Manuale\n---\n\n"
        "Data di emissione: 01/03/2024\n\nContenuto del manuale.",
        encoding="utf-8",
    )
    dest = ingest_file(str(src), tmp_path)
    post = frontmatter.load(str(dest))
    assert post.metadata["doc_date"] == "2024-03-01"


def test_ingest_file_no_date_no_field(tmp_path):
    src = tmp_path / "plain.md"
    src.write_text("Nessuna data qui.", encoding="utf-8")
    dest = ingest_file(str(src), tmp_path)
    post = frontmatter.load(str(dest))
    assert "doc_date" not in post.metadata


def test_ingest_pdf_first_chunk_gets_doc_date(tmp_path, monkeypatch):
    import llmwiki.pdf as pdfmod

    def fake_pdf_to_markdown(path, chunk_pages=20):
        return [{
            "title": "Manuale Tecnico",
            "content": "Manuale Tecnico\nData di emissione: 15/01/2024\n...",
            "page_start": 1,
            "page_end": 5,
            "metadata": {"author": None, "total_pages": 5},
        }]

    monkeypatch.setattr(pdfmod, "pdf_to_markdown", fake_pdf_to_markdown)
    src = tmp_path / "manuale.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    paths = ingest_pdf(str(src), base_dir=tmp_path)
    post = frontmatter.load(str(paths[0]))
    assert post.metadata["doc_date"] == "2024-01-15"
