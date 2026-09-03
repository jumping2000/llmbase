# llmwiki/mail.py
"""Email ingestion — poll an IMAP mailbox and ingest messages as wiki docs.

Config (env):
  LLMBASE_MAIL_HOST              IMAP host (required to enable)
  LLMBASE_MAIL_USER              login user
  LLMBASE_MAIL_PASSWORD          login password
  LLMBASE_MAIL_PORT              default 993
  LLMBASE_MAIL_FOLDER            default "INBOX"
  LLMBASE_MAIL_PROCESSED_FOLDER  default "Processed"
  LLMBASE_MAIL_POLL_MINUTES      default 1
  LLMBASE_MAIL_DEFAULT_DOMAIN    default "generale"

Subject tag routing: ``[lavoro] ...`` sets the domain; unknown tag → default.
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
import re
import tempfile
import threading
from email.header import decode_header
from pathlib import Path

from markdownify import markdownify as md

from .domains import resolve_domain

logger = logging.getLogger("llmbase.mail")

_SUBJECT_TAG_RE = re.compile(r"\[([^\]]+)\]")


def extract_domain_from_subject(
    subject: str, base_dir: Path | None = None
) -> str | None:
    """Return the ``[tag]`` from a subject line, or None."""
    m = _SUBJECT_TAG_RE.search(subject or "")
    return m.group(1).strip() if m else None


def _decode_header_value(value) -> str:
    if value is None:
        return ""
    parts = decode_header(value)
    out = []
    for data, enc in parts:
        if isinstance(data, bytes):
            out.append(data.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(data)
    return "".join(out)


def _part_text(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _body_to_markdown(msg: email.message.Message) -> str:
    plain: list[str] = []
    html: list[str] = []
    parts = [msg] if not msg.is_multipart() else msg.walk()
    for part in parts:
        ctype = part.get_content_type()
        if ctype == "text/plain":
            plain.append(_part_text(part))
        elif ctype == "text/html":
            html.append(_part_text(part))
    if plain:
        return "\n\n".join(p for p in plain if p.strip())
    if html:
        return md("\n\n".join(p for p in html if p.strip()))
    return ""


def _extract_attachments(msg: email.message.Message) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for part in msg.walk():
        if part.get_content_disposition() != "attachment":
            continue
        name = _decode_header_value(part.get_filename())
        payload = part.get_payload(decode=True)
        if name and payload:
            out.append((name, payload))
    return out


class MailPoller:
    def __init__(
        self,
        base_dir: Path,
        host: str,
        user: str,
        password: str,
        port: int = 993,
        folder: str = "INBOX",
        processed_folder: str = "Processed",
        poll_minutes: int = 1,
        default_domain: str = "generale",
    ):
        self.base_dir = base_dir
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.folder = folder
        self.processed_folder = processed_folder
        self.poll_minutes = poll_minutes
        self.default_domain = default_domain
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="mail-poller", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                n = self.poll_once()
                if n:
                    logger.info(f"[mail] ingested {n} messages")
            except Exception as e:
                logger.warning(f"[mail] poll failed: {e}")
            self._stop.wait(self.poll_minutes * 60)

    def poll_once(self) -> int:
        mail = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            mail.login(self.user, self.password)
            mail.select(self.folder, readonly=False)
            typ, data = mail.search(None, "UNSEEN")
            if typ != "OK":
                return 0
            ids = data[0].split() if data and data[0] else []
            processed = 0
            # Reverse order: expunge renumbers higher sequence numbers only,
            # so descending iteration keeps unprocessed ids stable.
            for num in reversed(ids):
                try:
                    if self._process_message(mail, num):
                        processed += 1
                except Exception as e:
                    logger.warning(f"[mail] error processing msg {num}: {e}")
            return processed
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    def _process_message(self, mail, num) -> bool:
        typ, data = mail.fetch(num, "(RFC822)")
        if typ != "OK" or not data or not data[0]:
            return False
        raw = data[0][1] if isinstance(data[0], tuple) else data[0]
        msg = email.message_from_bytes(raw)
        subject = _decode_header_value(msg.get("Subject", ""))
        tag = extract_domain_from_subject(subject, self.base_dir)
        domain = self.default_domain
        if tag:
            domain = resolve_domain(tag, self.base_dir)
            if domain == "generale" and tag.strip().lower() != "generale":
                logger.warning(f"[mail] tag '{tag}' non riconosciuto, uso 'generale'")

        body = _body_to_markdown(msg)
        if body.strip():
            with tempfile.NamedTemporaryFile(
                "w", suffix=".md", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(body)
                body_path = tmp.name
            try:
                from .ingest import ingest_file

                ingest_file(
                    body_path,
                    self.base_dir,
                    original_name=f"{subject or 'email'}.md",
                    domain=domain,
                )
            except Exception as e:
                logger.warning(f"[mail] body ingest failed: {e}")
            finally:
                Path(body_path).unlink(missing_ok=True)

        for name, payload in _extract_attachments(msg):
            suffix = Path(name).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(payload)
                att_path = tmp.name
            try:
                if suffix == ".pdf":
                    from .pdf import ingest_pdf

                    ingest_pdf(
                        att_path,
                        base_dir=self.base_dir,
                        original_name=name,
                        domain=domain,
                    )
                else:
                    from .ingest import ingest_file

                    ingest_file(
                        att_path, self.base_dir, original_name=name, domain=domain
                    )
            except Exception as e:
                logger.warning(f"[mail] allegato '{name}' saltato: {e}")
            finally:
                Path(att_path).unlink(missing_ok=True)

        self._mark_processed(mail, num)
        return True

    def _mark_processed(self, mail, num) -> None:
        try:
            mail.copy(num, self.processed_folder)
            mail.store(num, "+FLAGS", "\\Deleted")
            mail.expunge()
        except Exception as e:
            logger.warning(
                f"[mail] move to {self.processed_folder} failed ({e}); marking seen"
            )
            mail.store(num, "+FLAGS", "\\Seen")


def resolve_mail_poller(base_dir: Path) -> MailPoller | None:
    """Build a poller from env vars, or None if not configured."""
    host = os.environ.get("LLMBASE_MAIL_HOST", "").strip()
    user = os.environ.get("LLMBASE_MAIL_USER", "").strip()
    password = os.environ.get("LLMBASE_MAIL_PASSWORD", "")
    if not (host and user and password):
        return None
    port = int(os.environ.get("LLMBASE_MAIL_PORT", "993"))
    folder = os.environ.get("LLMBASE_MAIL_FOLDER", "INBOX")
    processed = os.environ.get("LLMBASE_MAIL_PROCESSED_FOLDER", "Processed")
    poll_minutes = max(1, int(os.environ.get("LLMBASE_MAIL_POLL_MINUTES", "1")))
    default_domain = os.environ.get("LLMBASE_MAIL_DEFAULT_DOMAIN", "generale")
    return MailPoller(
        base_dir,
        host,
        user,
        password,
        port=port,
        folder=folder,
        processed_folder=processed,
        poll_minutes=poll_minutes,
        default_domain=default_domain,
    )
