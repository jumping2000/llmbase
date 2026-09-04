# tests/test_docdate.py
import pytest

from llmwiki.docdate import normalize_date, is_plausible


def test_normalize_iso_full():
    assert normalize_date("2024-03-01") == "2024-03-01"

def test_normalize_iso_year_month():
    assert normalize_date("2024-03") == "2024-03"

def test_normalize_italian_slash():
    assert normalize_date("01/03/2024") == "2024-03-01"

def test_normalize_italian_dash():
    assert normalize_date("01-03-2024") == "2024-03-01"

def test_normalize_italian_dot():
    assert normalize_date("01.03.2024") == "2024-03-01"

def test_normalize_two_digit_year_24():
    assert normalize_date("01/03/24") == "2024-03-01"

def test_normalize_two_digit_year_85():
    assert normalize_date("01/03/85") == "1985-03-01"

def test_normalize_day_gt12_is_day():
    # 25 cannot be a month → unambiguous day-first
    assert normalize_date("25/01/2024") == "2024-01-25"

def test_normalize_ambiguous_assumes_italian():
    # both ≤12 → assume DD/MM (Italian editorial context)
    assert normalize_date("01/03/2024") == "2024-03-01"

def test_normalize_year_only():
    assert normalize_date("2024") == "2024"

def test_normalize_invalid_returns_none():
    assert normalize_date("not a date") is None
    assert normalize_date("32/13/2024") is None

def test_is_plausible_rejects_old():
    assert not is_plausible("1899")

def test_is_plausible_rejects_future():
    assert not is_plausible("2099-01-01")

def test_is_plausible_accepts_recent():
    assert is_plausible("2024-03-01")
    assert is_plausible("2024")
