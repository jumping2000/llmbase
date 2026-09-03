# tests/test_mail.py
import email

from llmwiki.mail import (
    _body_to_markdown,
    _decode_header_value,
    _extract_attachments,
    extract_domain_from_subject,
)


def test_extract_domain_from_subject():
    assert extract_domain_from_subject("[lavoro] Report") == "lavoro"
    assert extract_domain_from_subject("Report senza tag") is None


def test_decode_header_value():
    raw = "=?utf-8?b?Q2lhbw==?="
    assert _decode_header_value(raw) == "Ciao"


def test_body_to_markdown_plain():
    msg = email.message.EmailMessage()
    msg["Subject"] = "Test"
    msg.set_content("Ciao mondo")
    assert "Ciao mondo" in _body_to_markdown(msg)


def test_extract_attachments():
    msg = email.message.EmailMessage()
    msg["Subject"] = "Test"
    msg.set_content("body")
    msg.add_attachment(b"PDFDATA", maintype="application", subtype="pdf", filename="doc.pdf")
    atts = _extract_attachments(msg)
    assert len(atts) == 1
    assert atts[0][0] == "doc.pdf"
    assert atts[0][1] == b"PDFDATA"
