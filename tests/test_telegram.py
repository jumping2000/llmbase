# tests/test_telegram.py
from llmwiki.telegram import TelegramBot


def test_domain_switch_and_default(tmp_path):
    from llmwiki.domains import create_domain

    create_domain("lavoro", tmp_path)
    bot = TelegramBot(tmp_path, "token", {"42"}, "generale")
    sent = []
    bot._send = lambda chat_id, text: sent.append((chat_id, text))  # noqa: SLF001
    assert bot._domain_for("42") == "generale"  # noqa: SLF001
    bot._handle_command("42", "/dominio lavoro")  # noqa: SLF001
    assert bot._domain_for("42") == "lavoro"  # noqa: SLF001
    bot._handle_command("42", "/dominio")  # noqa: SLF001
    assert any("lavoro" in t for _, t in sent)


def test_domain_unknown_informs_user(tmp_path):
    bot = TelegramBot(tmp_path, "token", {"42"}, "generale")
    sent = []
    bot._send = lambda chat_id, text: sent.append((chat_id, text))  # noqa: SLF001
    bot._handle_command("42", "/dominio tipooo")  # noqa: SLF001
    assert bot._domain_for("42") == "generale"  # noqa: SLF001
    assert any("sconosciuto" in t for _, t in sent)


def test_unauthorized_chat_ignored(tmp_path):
    bot = TelegramBot(tmp_path, "token", {"42"}, "generale")
    handled = []
    bot._answer = lambda chat_id, q: handled.append((chat_id, q))  # noqa: SLF001
    upd = {"message": {"chat": {"id": 999}, "text": "ciao"}}
    bot._handle_update(upd)  # noqa: SLF001
    assert handled == []
