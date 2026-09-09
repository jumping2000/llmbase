# tests/test_translations.py
"""Guard the UI translation files against drift.

The three files under ``frontend/public/translations/`` are hand-edited (that
is the point — they can be changed without a rebuild), so nothing else stops
one language from silently losing a key. A missing key renders as the raw key
string in the UI, which is easy to ship unnoticed.
"""

import json
from pathlib import Path

import pytest

TRANSLATIONS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public" / "translations"
LANGS = ("en", "it", "en-it")
REFERENCE = "en"


def _load(lang: str) -> dict:
    path = TRANSLATIONS_DIR / f"{lang}.json"
    assert path.exists(), f"missing translation file: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} must hold a JSON object"
    return data


@pytest.mark.parametrize("lang", LANGS)
def test_translation_file_is_a_flat_string_map(lang):
    data = _load(lang)
    assert data, f"{lang}.json is empty"
    bad = {k: v for k, v in data.items() if not isinstance(v, str)}
    assert not bad, f"{lang}.json has non-string values: {sorted(bad)}"


@pytest.mark.parametrize("lang", [x for x in LANGS if x != REFERENCE])
def test_languages_share_the_same_keys(lang):
    reference = set(_load(REFERENCE))
    other = set(_load(lang))
    missing = sorted(reference - other)
    extra = sorted(other - reference)
    assert not missing and not extra, (
        f"{lang}.json is out of sync with {REFERENCE}.json — "
        f"missing: {missing or 'none'}; unexpected: {extra or 'none'}"
    )


@pytest.mark.parametrize("lang", LANGS)
def test_plural_keys_come_in_pairs(lang):
    """`t(key, {count})` looks up `key_one` / `key_other`; a lone half is dead."""
    data = _load(lang)
    for suffix, twin in (("_one", "_other"), ("_other", "_one")):
        for key in data:
            if key.endswith(suffix):
                expected = key[: -len(suffix)] + twin
                assert expected in data, f"{lang}.json: {key} has no {expected}"
