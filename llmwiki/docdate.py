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


# ─── Regex extraction ──────────────────────────────────────────────
# Priority 1: explicit authoring/validation markers (full date)
_P1_RE = re.compile(
    r"(?:data\s+di\s+(?:emissione|validazione|revisione|stesura|aggiornamento)"
    r"|ultima\s+modifica|last\s+updated|last\s+modified"
    r"|date\s+of\s+issue|revision\s+date)"
    r"\s*[:：\-–]?\s*(\d{4}-\d{2}-\d{2}|[0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
    re.IGNORECASE,
)
_REV_RE = re.compile(
    r"\brev(?:isione)?\.?\s*\d+\s*(?:del|di|–|-|—)?\s*"
    r"([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
    re.IGNORECASE,
)
# Priority 2: edition / year markers
_P2_RE = re.compile(
    r"\b(?:edizione|edition|anno)\s*[:：]?\s*(\d{4})\b|©\s*(\d{4})",
    re.IGNORECASE,
)
# Priority 3: textual dates anywhere in the head
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}
_P3_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b"
    r"|\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)

_HEAD_CHARS = 3000


def _p3_match_to_iso(m: re.Match) -> str | None:
    d1, mon1, y1, mon2, d2, y2 = m.groups()
    if d1:  # "1 marzo 2024"
        return f"{int(y1):04d}-{_MONTHS[mon1.lower()]:02d}-{int(d1):02d}"
    return f"{int(y2):04d}-{_MONTHS[mon2.lower()]:02d}-{int(d2):02d}"


def _docdate_config(base_dir: Path | None) -> dict:
    """Read docdate config with sensible defaults; never raises."""
    try:
        from .config import load_config

        cfg = load_config(base_dir)
        return {
            "enabled": bool(cfg.get("docdate", {}).get("enabled", True)),
            "llm_fallback": bool(cfg.get("docdate", {}).get("llm_fallback", True)),
        }
    except Exception:
        return {"enabled": True, "llm_fallback": True}


_LLM_PROMPT = (
    "Find the authoring, validation, or last-modified date of this document. "
    "Reply ONLY with an ISO date (YYYY-MM-DD, YYYY-MM, or YYYY) or 'none'.\n\n"
)


def _llm_extract(head: str, base_dir: Path | None) -> str | None:
    """Micro LLM call; returns raw answer string or None on any failure."""
    from .llm import chat

    return chat(
        _LLM_PROMPT + head[:_HEAD_CHARS],
        feature="docdate",
        stage="answer",
        base_dir=base_dir,
    )


def extract_doc_date(text: str, base_dir: Path | None = None) -> str | None:
    """Extract the document's authoring/validation date from its opening text.

    Returns ISO "YYYY-MM-DD" | "YYYY-MM" | "YYYY" or None. Never raises.
    """
    try:
        conf = _docdate_config(base_dir)
        if not conf["enabled"]:
            return None
        head = text[:_HEAD_CHARS]
        # Priority 1
        for m in _P1_RE.finditer(head):
            iso = normalize_date(m.group(1))
            if iso:
                return iso
        for m in _REV_RE.finditer(head):
            iso = normalize_date(m.group(1))
            if iso:
                return iso
        # Priority 2
        for m in _P2_RE.finditer(head):
            year = m.group(1) or m.group(2)
            if is_plausible(year):
                return year
        # Priority 3
        for m in _P3_RE.finditer(head):
            iso = _p3_match_to_iso(m)
            if iso and is_plausible(iso):
                return iso
        if not conf["llm_fallback"]:
            return None
        try:
            answer = _llm_extract(head, base_dir=base_dir)
        except Exception:
            return None
        if not answer:
            return None
        return normalize_date(answer.strip())
    except Exception:
        return None


def propagate_doc_date(slug: str, base_dir: Path | None = None) -> int:
    """Push the raw doc's doc_date into the sources[] of citing articles.

    Matches a source_ref to the raw by (plugin, url, title) — the same
    fields _source_key uses in compile._merge_into. Returns the number
    of articles updated. Never overwrites an existing doc_date with None.
    """
    import frontmatter

    from .config import load_config

    try:
        cfg = load_config(base_dir)
        raw_dir = Path(cfg["paths"]["raw"])
        concepts_dir = Path(cfg["paths"]["concepts"])

        idx = raw_dir / slug / "index.md"
        if not idx.exists():
            return 0
        raw_post = frontmatter.load(str(idx))
        doc_date = raw_post.metadata.get("doc_date")
        if not doc_date:
            return 0

        raw_source = str(raw_post.metadata.get("source", "") or "")
        raw_title = str(raw_post.metadata.get("title", "") or slug)
        raw_type = str(raw_post.metadata.get("type", "") or "")

        updated = 0
        for md_file in concepts_dir.glob("*.md"):
            post = frontmatter.load(str(md_file))
            sources = post.metadata.get("sources", [])
            changed = False
            for src in sources:
                if not isinstance(src, dict):
                    continue
                match = (
                    (src.get("url", "") and src.get("url") == raw_source)
                    or (src.get("title", "") and src.get("title") == raw_title)
                    or (
                        raw_type
                        and src.get("plugin", "") == raw_type
                        and src.get("title", "") == raw_title
                    )
                )
                if match and src.get("doc_date") != doc_date:
                    src["doc_date"] = doc_date
                    changed = True
            if changed:
                post.metadata["sources"] = sources
                md_file.write_text(frontmatter.dumps(post), encoding="utf-8")
                updated += 1
        return updated
    except Exception:
        return 0
