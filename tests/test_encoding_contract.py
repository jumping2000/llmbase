"""Guard: every text-mode file read in llmwiki/ must pass encoding=.

Python resolves an omitted ``encoding=`` from the platform locale: UTF-8 on
Linux, cp1252 on Windows. The package writes UTF-8 everywhere, so an
encoding-less read is a latent Windows failure — and in the lint fix paths,
which read and then write back, a source of permanent content corruption.

The scan is AST-based, not regex-based: a regex cannot see a call whose
arguments are wrapped across lines, and would match ``.read_text()`` written
inside a docstring (llmwiki/atomic.py does exactly that).
"""

import ast
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1] / "llmwiki"

_TEXT_METHODS = {"read_text", "write_text"}


def _is_binary_open(call: ast.Call) -> bool:
    """True when an open() call's mode argument selects binary mode.

    Binary reads decode nothing, so they are exempt by construction rather
    than by an exemption list.
    """
    mode = None
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        mode = call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    return isinstance(mode, str) and "b" in mode


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        has_encoding = any(kw.arg == "encoding" for kw in node.keywords)
        if has_encoding:
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in _TEXT_METHODS:
            found.append(f"line {node.lineno}: .{node.func.attr}() without encoding=")
        elif isinstance(node.func, ast.Name) and node.func.id == "open":
            if not _is_binary_open(node):
                found.append(f"line {node.lineno}: open() without encoding=")
    return found


@pytest.mark.parametrize(
    "path",
    sorted(PKG_ROOT.rglob("*.py")),
    ids=lambda p: str(p.relative_to(PKG_ROOT)),
)
def test_text_io_declares_encoding(path):
    found = _violations(path)
    assert not found, (
        f"{path.relative_to(PKG_ROOT)} performs text I/O without encoding=\"utf-8\":\n"
        + "\n".join(f"  {v}" for v in found)
        + "\n\nAn omitted encoding= resolves from the platform locale, which is "
        "not UTF-8 on Windows. Pass encoding=\"utf-8\" explicitly. If a call "
        "genuinely must follow the locale, this guard has no exemption "
        "mechanism yet — add one deliberately rather than working around it."
    )
