import io
from pathlib import Path

import pytest

pytest.importorskip("flask")


def _client(tmp_kb):
    from llmwiki.web import create_web_app

    app = create_web_app(tmp_kb)
    app.config["TESTING"] = True
    return app.test_client()


def test_api_upload_accepts_multiple_files_and_preserves_names(tmp_kb, monkeypatch):
    calls = []

    def fake_ingest_pdf(pdf_path, chunk_pages=20, base_dir=None, original_name=None):
        calls.append({
            "pdf_path": pdf_path,
            "chunk_pages": chunk_pages,
            "base_dir": base_dir,
            "original_name": original_name,
        })
        return [Path(base_dir) / "raw" / Path(original_name).stem / "index.md"]

    monkeypatch.setenv("LLMBASE_API_SECRET", "secret-abc")
    monkeypatch.setattr("llmwiki.pdf.ingest_pdf", fake_ingest_pdf)

    c = _client(tmp_kb)
    r = c.post(
        "/api/upload",
        data={
            "file": [
                (io.BytesIO(b"%PDF-1.4\nfirst"), "First Report.pdf"),
                (io.BytesIO(b"%PDF-1.4\nsecond"), "Second Report.pdf"),
            ],
            "chunk_pages": "7",
        },
        headers={"Authorization": "Bearer secret-abc"},
        content_type="multipart/form-data",
    )

    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["total_files"] == 2
    assert len(data["uploaded"]) == 2
    assert data["failed"] == []
    assert [call["original_name"] for call in calls] == ["First Report.pdf", "Second Report.pdf"]
    assert all(call["chunk_pages"] == 7 for call in calls)