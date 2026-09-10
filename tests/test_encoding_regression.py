"""Regression tests: reads must not depend on the host's locale encoding.

The bug these guard against is invisible on Linux. ``Path.read_text()`` without
``encoding=`` resolves its codec from the platform locale — UTF-8 on Linux CI,
cp1252 on Windows — so a test that merely reads a non-ASCII file and asserts it
does not crash would pass on CI whether or not the bug is present.

These tests instead run each surface in a subprocess under
``PYTHONWARNDEFAULTENCODING=1`` (PEP 597), which makes CPython emit an
``EncodingWarning`` from the very call that omitted ``encoding=``. That signal
depends on whether the argument was passed, not on what the locale resolves to,
so these fail before the fix and pass after it on every platform.

The filter is scoped to ``llmwiki`` so an encoding-less read inside a
third-party dependency does not fail our suite.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PREAMBLE = """
import warnings
warnings.filterwarnings("ignore", category=EncodingWarning)
warnings.filterwarnings("error", category=EncodingWarning, module=r"llmwiki(\\.|$)")
"""


def _run_probe(body: str) -> subprocess.CompletedProcess:
    """Execute *body* in a subprocess where llmwiki EncodingWarnings are fatal."""
    script = _PREAMBLE + textwrap.dedent(body)
    env = {**os.environ, "PYTHONWARNDEFAULTENCODING": "1"}
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _assert_clean(result: subprocess.CompletedProcess) -> None:
    assert "OK" in result.stdout, (
        "probe did not reach its assertion.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert result.returncode == 0, (
        "an llmwiki read ran without encoding=; see the EncodingWarning below.\n"
        f"--- stderr ---\n{result.stderr}"
    )


def test_kb_stats_does_not_rely_on_default_encoding(tmp_kb):
    result = _run_probe(f"""
        from pathlib import Path
        from llmwiki.operations import dispatch
        stats = dispatch("kb_stats", Path({str(tmp_kb)!r}), {{}})
        assert stats["articles"] == 3, stats
        assert stats["total_words"] > 0, stats
        print("OK")
    """)
    _assert_clean(result)


def test_cli_stats_does_not_rely_on_default_encoding(tmp_kb):
    result = _run_probe(f"""
        import os
        from click.testing import CliRunner
        from llmwiki import cli
        os.chdir({str(tmp_kb)!r})
        res = CliRunner().invoke(cli.cli, ["stats"])
        assert res.exit_code == 0, res.output + str(res.exception)
        print("OK")
    """)
    _assert_clean(result)


def test_web_stats_does_not_rely_on_default_encoding(tmp_kb):
    result = _run_probe(f"""
        from llmwiki.web import create_web_app
        app = create_web_app({str(tmp_kb)!r})
        app.config["TESTING"] = True
        with app.test_client() as c:
            res = c.get("/api/stats")
        assert res.status_code == 200, res.status_code
        print("OK")
    """)
    _assert_clean(result)


def test_stats_counts_articles_outside_cp1252(tmp_kb):
    """Content that cp1252 cannot decode must be counted, not crashed on.

    Unlike the probes above this runs in-process, so on Linux it passes with
    or without the fix. It earns its place on Windows, and it documents which
    characters were actually at stake.
    """
    from llmwiki.operations import dispatch

    concepts = tmp_kb / "wiki" / "concepts"
    (concepts / "unicode-sample.md").write_text(
        "---\ntitle: Unicode\n---\n\n"
        # em dash, curly quotes and CJK all fall outside cp1252's table
        "Un trattino lungo — le virgolette “curve” e 知识库 cinese.\n",
        encoding="utf-8",
    )

    stats = dispatch("kb_stats", tmp_kb, {})

    assert stats["articles"] == 4
    assert stats["total_words"] > 0
