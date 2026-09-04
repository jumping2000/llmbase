"""Extract the authoring/validation date of a source document.

Hybrid pipeline: multilingual regex on the document's opening text,
then an LLM micro-call as fallback. The date is an optional metadata
field (``doc_date``) — extraction must never break ingestion.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

# Output granularity: YYYY, YYYY-MM, YYYY-MM-DD
_ISO_RE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")

# Italian/numeric: 01/03/2024, 01-03-2024, 01.03.2024, 01/03/24
_NUMERIC_RE = re.compile(
    r"^(0?[1-9]|[12]\d|3[01])[./-](0?[1-9]|1[0-2])[./-](\d{2}|\d{4})$"
)

_MIN_YEAR = 1900


def _two_digit_year(yy: str) -> int:
    n = int(yy)
    return 2000 + n if n <= 49 else 1900 + n


def normalize_date(raw: str) -> str | None:
    """Normalize any recognized date string to ISO (YYYY[-MM[-DD]]) or None."""
    if not raw:
        return None
    s = raw.strip()

    m = _ISO_RE.match(s)
    if m:
        y, mo, d = m.groups()
        if not is_plausible(y):
            return None
        if mo is not None and not 1 <= int(mo) <= 12:
            return None
        if d is not None and not 1 <= int(d) <= 31:
            return None
        return s

    m = _NUMERIC_RE.match(s)
    if m:
        dd, mm, yy = m.groups()
        year = _two_digit_year(yy) if len(yy) == 2 else int(yy)
        if not is_plausible(str(year)):
            return None
        # Ambiguity: first number > 12 is certainly the day; otherwise
        # assume Italian DD/MM/YYYY (editorial context of the corpus).
        day, month = int(dd), int(mm)
        if day > 12 and month > 12:
            return None
        if day <= 12 and mm and int(mm) > 12:
            day, month = int(mm), int(dd)
        return f"{year:04d}-{month:02d}-{day:02d}"

    if s.isdigit() and len(s) == 4:
        return s if is_plausible(s) else None
    return None


def is_plausible(iso_date: str) -> bool:
    """True if the year is within [1900, current year + 1]."""
    m = _ISO_RE.match(iso_date)
    if not m:
        return False
    year = int(m.group(1))
    return _MIN_YEAR <= year <= date.today().year + 1
