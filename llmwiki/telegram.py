# llmwiki/telegram.py
"""Telegram bot — long-polling gateway to query and feed the wiki.

Config (env):
  LLMBASE_TG_TOKEN            bot token (required to enable)
  LLMBASE_TG_ALLOWED_CHAT_IDS comma-separated chat ids allowed to talk
  LLMBASE_TG_DEFAULT_DOMAIN   default domain (default "generale")
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from pathlib import Path

import requests

from . import operations as ops
from .domains import create_domain

logger = logging.getLogger("llmbase.telegram")

_API = "https://api.telegram.org/bot{token}/{method}"

HELP_TEXT = (
    "Comandi:\n"
    "/ask <domanda> — fai una domanda alla wiki\n"
    "/cerca <testo> — cerca nella wiki\n"
    "/dominio <nome> — cambia il dominio attivo\n"
    "/dominio — mostra il dominio attivo\n"
    "Invia un PDF o un file per inserirlo nella wiki (dominio attivo).\n"
    "Qualsiasi altro messaggio viene trattato come domanda."
)


class TelegramBot:
    def __init__(self, base_dir: Path, token: str, allowed_chat_ids: set[str], default_domain: str):
        self.base_dir = base_dir
        self.token = token
        self.allowed = allowed_chat_ids
        self.default_domain = default_domain
        self._chat_domain: dict[str, str] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="telegram-bot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        offset = 0
        while not self._stop.is_set():
            try:
                updates = self._call("getUpdates", timeout=30, offset=offset)
                if isinstance(updates, list):
                    for upd in updates:
                        offset = max(offset, int(upd.get("update_id", 0)) + 1)
                        self._handle_update(upd)
            except requests.RequestException as e:
                logger.warning(f"[telegram] network error: {e}")
                self._stop.wait(5)
            except Exception as e:
                logger.error(f"[telegram] unexpected error: {e}")
                self._stop.wait(5)

    def _call(self, method: str, **params):
        url = _API.format(token=self.token, method=method)
        resp = requests.post(url, json=params, timeout=45)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram {method} failed: {data}")
        return data.get("result", {})

    def _send(self, chat_id: str, text: str) -> None:
        self._call("sendMessage", chat_id=chat_id, text=text[:4000])

    def _handle_update(self, upd: dict) -> None:
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id not in self.allowed:
            logger.debug(f"[telegram] ignored chat {chat_id}")
            return
        text = msg.get("text") or ""
        if text.startswith("/"):
            self._handle_command(chat_id, text)
            return
        if msg.get("document"):
            self._handle_document(chat_id, msg["document"])
            return
        if text.strip():
            self._answer(chat_id, text.strip())

    def _handle_command(self, chat_id: str, text: str) -> None:
        parts = text.split(maxsplit=1)
        cmd = parts[0].split("@")[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd in ("/aiuto", "/help", "/start"):
            self._send(chat_id, HELP_TEXT)
        elif cmd == "/dominio":
            if arg:
                dom = create_domain(arg, self.base_dir)["id"]
                self._chat_domain[chat_id] = dom
                self._send(chat_id, f"Dominio attivo: {dom}")
            else:
                self._send(chat_id, f"Dominio attivo: {self._domain_for(chat_id)}")
        elif cmd == "/cerca":
            if not arg:
                self._send(chat_id, "Uso: /cerca <testo>")
                return
            self._search(chat_id, arg)
        elif cmd == "/ask":
            if not arg:
                self._send(chat_id, "Uso: /ask <domanda>")
                return
            self._answer(chat_id, arg)
        else:
            self._send(chat_id, "Comando sconosciuto. /aiuto")

    def _domain_for(self, chat_id: str) -> str:
        return self._chat_domain.get(chat_id, self.default_domain)

    def _search(self, chat_id: str, query: str) -> None:
        try:
            res = ops.dispatch(
                "kb_search",
                self.base_dir,
                {"query": query, "top_k": 5, "domain": self._domain_for(chat_id)},
            )
        except Exception as e:
            self._send(chat_id, f"Errore: {e}")
            return
        results = res.get("results", []) if isinstance(res, dict) else []
        if not results:
            self._send(chat_id, "Nessun risultato.")
            return
        lines = [f"• {r.get('title')} ({r.get('slug')})" for r in results[:5]]
        self._send(chat_id, "\n".join(lines))

    def _answer(self, chat_id: str, question: str) -> None:
        self._send(chat_id, "Cerco nella wiki…")
        try:
            res = ops.dispatch(
                "kb_ask",
                self.base_dir,
                {"question": question, "domain": self._domain_for(chat_id)},
            )
        except Exception as e:
            self._send(chat_id, f"Errore: {e}")
            return
        answer = res.get("answer", str(res)) if isinstance(res, dict) else str(res)
        self._send(chat_id, answer)

    def _handle_document(self, chat_id: str, doc: dict) -> None:
        file_id = doc.get("file_id")
        file_name = doc.get("file_name") or "upload"
        if not file_id:
            self._send(chat_id, "Documento senza file_id.")
            return
        try:
            file_info = self._call("getFile", file_id=file_id)
            file_path = file_info.get("file_path")
            if not file_path:
                self._send(chat_id, "Impossibile scaricare il file.")
                return
            url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            suffix = Path(file_name).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            domain = self._domain_for(chat_id)
            if suffix == ".pdf":
                from .pdf import ingest_pdf

                paths = ingest_pdf(tmp_path, base_dir=self.base_dir, original_name=file_name, domain=domain)
                n = len(paths)
            else:
                from .ingest import ingest_file

                ingest_file(tmp_path, self.base_dir, original_name=file_name, domain=domain)
                n = 1
            Path(tmp_path).unlink(missing_ok=True)
            self._send(chat_id, f"Ingerito {n} documento/i nel dominio {domain}. Compila per aggiornare la wiki.")
        except Exception as e:
            logger.error(f"[telegram] document error: {e}")
            self._send(chat_id, f"Errore ingest: {e}")


def resolve_telegram_bot(base_dir: Path) -> TelegramBot | None:
    """Build a bot from env vars, or None if not configured."""
    token = os.environ.get("LLMBASE_TG_TOKEN", "").strip()
    if not token:
        return None
    allowed_raw = os.environ.get("LLMBASE_TG_ALLOWED_CHAT_IDS", "")
    allowed = {c.strip() for c in allowed_raw.split(",") if c.strip()}
    default_domain = os.environ.get("LLMBASE_TG_DEFAULT_DOMAIN", "generale").strip() or "generale"
    return TelegramBot(base_dir, token, allowed, default_domain)
