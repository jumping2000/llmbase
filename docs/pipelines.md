# Pipelines — Composing the Primitives

LLMBase v0.7.7 ships five primitives for multi-stage LLM workflows. They are
designed for **one direction only**: upstream provides atomic pieces; downstream
composes them as plain Python. No DAG, no scheduler, no retry framework — the
assumption is that a `for` loop, a `with` block, and a few function calls are
enough to orchestrate an ingest → chunk → LLM → normalize → sync flow.

This page walks through how the five pieces fit together, using siwen's 5-stage
wenguan pipeline (62 太虛 books + 14 判教原經) as the worked example. The code
is illustrative — siwen's real pipeline will differ in details — but the
composition pattern is the intended one.

> **See also:** [customization.md](customization.md) for the per-module constant
> and hook surface these primitives sit inside.

## The Primitives

| Primitive | Module | One-line |
|-----------|--------|----------|
| `normalize_paragraphs` / `normalize_heads` | [`llmwiki/normalize.py`](../llmwiki/normalize.py) | CommonMark-safe pre/post passes: merge broken OCR paragraphs, re-level ATX headings by rule pack. |
| `split_by_heading` | [`llmwiki/split.py`](../llmwiki/split.py) | Flat section cut at a chosen ATX depth — one `Section` per LLM call. |
| `ChunkCache` | [`llmwiki/chunk_cache.py`](../llmwiki/chunk_cache.py) | `(cid, content_hash) → output` cache; content changes at a slot automatically miss. |
| `api_key=` / `X-LLM-Key` | [`llmwiki/llm.py`](../llmwiki/llm.py) | Per-call credential override — pin a tenant/persona key without leaking into the module singleton. |
| `run_stage` + `rebuild_state` | [`llmwiki/pipeline/`](../llmwiki/pipeline/) | Stage driver with guaranteed terminal event (`ok` / `failed` / `partial`); log-as-truth state replay. |

Full API in each module's docstring.

---

## Canonical recipe: siwen 5-stage wenguan

Each stage is one `with run_stage(...)` block. The stages communicate through
files on disk, not through handed-off Python objects — that is what makes any
stage independently re-runnable and the whole pipeline crash-resumable.

```python
from __future__ import annotations

import hashlib
from pathlib import Path

from llmwiki import chunk_cache, normalize, split
from llmwiki.llm import chat
from llmwiki.pipeline import run_stage, rebuild_state

BASE_DIR      = Path("/var/siwen")
PIPELINE_KEY  = "taixu_quanshu"              # stable per source × pipeline version
SOURCE        = BASE_DIR / "raw" / "taixu.md"
WORK          = BASE_DIR / "work" / PIPELINE_KEY

# Rule pack lives next to the pipeline, not in upstream.
TAIXU_HEAD_RULES = [
    {"pattern": r"^第[一二三四五六七八九十百千]+[編篇]", "level": 1},
    {"pattern": r"^第[一二三四五六七八九十百千]+[章卷]", "level": 2},
    {"pattern": r"^[甲乙丙丁戊己庚辛壬癸]、",          "level": 3},
]

cache = chunk_cache.ChunkCache(BASE_DIR, subdir=".wenguan_cache")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ── Stage 1: ingest — fetch raw into a stable path ─────────────
with run_stage(BASE_DIR, "ingest", PIPELINE_KEY, ttl=600) as ctx:
    raw = SOURCE.read_text(encoding="utf-8")
    (WORK / "raw.md").parent.mkdir(parents=True, exist_ok=True)
    (WORK / "raw.md").write_text(raw, encoding="utf-8")
    ctx.meta_update(bytes=len(raw), source=str(SOURCE))
    ctx.artifact(str((WORK / "raw.md").relative_to(BASE_DIR)))

# ── Stage 2: split — re-level headings, cut at level-2 ─────────
with run_stage(BASE_DIR, "split", PIPELINE_KEY, ttl=300,
               meta_init={"rules_hash": _sha(repr(TAIXU_HEAD_RULES))}) as ctx:
    body = (WORK / "raw.md").read_text(encoding="utf-8")
    body = normalize.normalize_heads(body, TAIXU_HEAD_RULES)
    sections = split.split_by_heading(body, level=2)
    ctx.meta_update(n_chunks=len(sections))
    # Hand chunk text to stage 3 via files — keeps the log small and
    # makes each chunk independently recoverable.
    (WORK / "chunks").mkdir(parents=True, exist_ok=True)
    for s in sections:
        (WORK / "chunks" / f"{_sha(s.title)[:16]}.md").write_text(
            f"# {s.title}\n\n{s.content}\n", encoding="utf-8")
    ctx.artifact(str((WORK / "chunks").relative_to(BASE_DIR)))

# ── Stage 3: wenguan — LLM per chunk, cache-guarded ────────────
WENGUAN_PROMPT = "…"  # downstream's system prompt

with run_stage(BASE_DIR, "wenguan", PIPELINE_KEY, ttl=7200,
               meta_init={"prompt_v": "wenguan.2026-04-20"}) as ctx:
    body = normalize.normalize_heads(
        (WORK / "raw.md").read_text(encoding="utf-8"),
        TAIXU_HEAD_RULES,
    )
    sections = split.split_by_heading(body, level=2)
    ctx.meta_update(chunks_total=len(sections))

    for i, s in enumerate(sections):
        cid = s.title
        h   = _sha(s.content)
        if (hit := cache.get(cid, h)) is not None:
            ctx.log({"event": "chunk_hit", "i": i, "cid": cid})
            continue
        try:
            out = chat(s.content, system=WENGUAN_PROMPT)
        except Exception as e:
            # LLM quota / upstream failure / network. `chat()` with
            # `api_key=None` re-raises the original exception type
            # (openai, httpx, …), so we catch broadly here. Record
            # progress and stop; next acquire reads the cache and
            # resumes from this chunk.
            ctx.mark_partial(f"{type(e).__name__} at {i}/{len(sections)}")
            break
        cache.put(cid, h, out)
        ctx.log({"event": "chunk_ok", "i": i, "cid": cid,
                 "in": len(s.content), "out": len(out)})

# ── Stage 4: normalize — assemble + paragraph merge ────────────
with run_stage(BASE_DIR, "normalize", PIPELINE_KEY, ttl=600) as ctx:
    body = normalize.normalize_heads(
        (WORK / "raw.md").read_text(encoding="utf-8"),
        TAIXU_HEAD_RULES,
    )
    sections = split.split_by_heading(body, level=2)
    parts: list[str] = []
    for s in sections:
        out = cache.get(s.title, _sha(s.content))
        if out is None:
            raise RuntimeError(
                f"wenguan cache miss for {s.title!r} — "
                "run wenguan stage to completion first"
            )
        parts.append(out)
    assembled = normalize.normalize_paragraphs("\n\n".join(parts))
    (WORK / "assembled.md").write_text(assembled, encoding="utf-8")
    ctx.artifact(str((WORK / "assembled.md").relative_to(BASE_DIR)))

# ── Stage 5: sync — push to downstream store ───────────────────
with run_stage(BASE_DIR, "sync", PIPELINE_KEY, ttl=900) as ctx:
    push_to_siwen_ink((WORK / "assembled.md").read_text(encoding="utf-8"))
```

Two things to notice:

- **Each stage reads its predecessor's artifact from disk.** Stage 3 re-derives
  `sections` from `raw.md` rather than taking them from stage 2's Python state.
  Cheap (split is milliseconds); buys full recoverability.
- **Cache key is `(section.title, sha256(section.content))`.** If stage 2's
  rule pack changes and a chunk's boundaries shift, stage 3 sees a miss for
  that chunk only — everything else still hits.

---

## Anatomy of a single stage

`run_stage`'s signature (see [`llmwiki/pipeline/driver.py`](../llmwiki/pipeline/driver.py)):

```python
run_stage(base_dir, stage, key, *, ttl=3600, meta_init=None) -> StageContext
```

Inside the `with` block, the `ctx` handle gives you four handler-facing moves.
Zooming into stage 3:

```python
with run_stage(BASE_DIR, "wenguan", PIPELINE_KEY, ttl=7200,
               meta_init={"prompt_v": "wenguan.2026-04-20"}) as ctx:
    # 1. Seed round metadata. meta_init is frozen in the start event;
    #    overlay with meta_update during the run. rebuild_state
    #    returns the last round's cumulative meta — use it for
    #    config fingerprints worth surfacing without scanning the log.
    ctx.meta_update(chunks_total=len(sections), model="llm-xl")

    for i, s in enumerate(sections):
        # 2. Custom events. Anything EXCEPT the reserved names (start,
        #    ok, failed, partial, interrupted, artifact, meta_update).
        #    Prefix with chunk_ / cache_ / your-own-namespace.
        ctx.log({"event": "chunk_ok", "i": i, "cid": s.title})

        # 3. Artifacts. Paths you produced. rebuild_state unions these
        #    across all rounds, dedupes, sorts — useful as a GC hint.
        ctx.artifact(f"work/{PIPELINE_KEY}/chunks/{s.title}.md")

        # 4. Partial exit. The run did work but did not finish.
        #    Terminal event becomes "partial" instead of "ok" (last
        #    call wins). Alternatively raise StagePartialExit(reason)
        #    to unwind.
        if quota_exhausted(i):
            ctx.mark_partial(f"quota at {i}/{len(sections)}")
            break
```

On every exit path of the `with` block — clean return, `mark_partial`, or a
raised exception — the driver writes exactly one of `ok` / `failed` / `partial`
to the log. After a `SIGKILL` leaves no terminal event behind, the *next*
`run_stage` acquire writes `interrupted` on a best-effort basis before breaking
the stale lock; a catastrophic I/O failure during that recovery can still leave
a dead round without a terminal event, so treat `interrupted` as a recovery
signal rather than a second absolute guarantee.

What `rebuild_state` returns:

```python
>>> s = rebuild_state(BASE_DIR, "wenguan", "taixu_quanshu")
>>> s.status          # pending | running | ok | failed | partial | interrupted
'partial'
>>> s.last_err        # one-line summary for non-ok terminals
'partial: RuntimeError at 50/62'
>>> s.attempts        # number of start events ever written
3
>>> s.meta            # last round's meta_init + meta_updates
{'prompt_v': 'wenguan.2026-04-20', 'chunks_total': 62, 'model': 'llm-xl'}
>>> s.artifacts       # union across all rounds, deduped, sorted
['work/taixu_quanshu/chunks/']
```

---

## Patterns

### Choosing the `key`

`key` decides which runs share a log file. Rule of thumb:

- **One book per run** → `key = slug(book_title)`.
- **One pipeline version per book** → `key = f"{slug(book)}__{pipeline_version}"`.
  Bump `pipeline_version` when a prompt overhaul deserves a fresh history; the
  prior log stays on disk as an audit trail.
- **Multi-tenant** → `key = f"{tenant}/{slug(book)}"`. Slashes are fine — `key`
  is sha256'd before hitting disk, and the stage-name regex is separate.

What you put in `key` is a contract with your future self: changing it makes
`rebuild_state` see a fresh run with no prior history.

### Choosing the `cid` (ChunkCache slot identity)

`cid` is the *slot identity* — what this chunk **is**, not how big it was cut.
Bind it to content身份 (H3 title, 本位 id, line-range of a stable heading),
never to input-size knobs like `CHUNK_MAX` or splitter version. The
`content_hash` already handles content drift at a fixed slot; `cid` handles
"which slot is this."

Counter-example (learned the hard way, 2026-04-21): a downstream pipeline set
`cid = f"{prompt_name}:{chunk_index}/{CHUNK_MAX}"`. When the team retuned
`CHUNK_MAX` after a length-cut incident, every `cid` shifted, every `get`
missed, and the entire prior cache was wasted even for chunks whose content
hadn't changed at all. Binding `cid` to content identity would have kept most
of the cache warm across the retune.

Rule: if a downstream knob shifts your `cid`, you have the wrong `cid`.

### Sizing chunks against the model's output budget

When stage 3 hits `finish_reason == "length"`, the fix is upstream from the
cache — the chunk was too big for the model's output budget. Use
`chat_with_meta` + `reasoning_budget` (both v0.7.8) to detect and prevent:

```python
from llmwiki.llm import chat_with_meta, reasoning_budget

# One-time empirical tuning against a sample of real chunks:
#   TOKENS_PER_CHAR ≈ mean(meta.usage["completion_tokens"] / len(chunk))
# For CJK reasoning-model output with mild normalization prompts, ~15-20.
TOKENS_PER_CHAR = 17
MAX_TOKENS      = 32000
SAFE_CHARS      = reasoning_budget(MAX_TOKENS, TOKENS_PER_CHAR)   # 1505

for i, s in enumerate(sections):
    if len(s.content) > SAFE_CHARS:
        # Downstream's fallback split — not an upstream primitive yet (v0.7.8).
        chunks = hard_split(s.content, max_chars=SAFE_CHARS)
    else:
        chunks = [s.content]
    for chunk in chunks:
        text, meta = chat_with_meta(chunk, system=WENGUAN_PROMPT,
                                    max_tokens=MAX_TOKENS)
        if meta.truncated:
            # Length-cut caught explicitly — the 11-hour loss of 2026-04-21
            # happened precisely because this branch did not exist.
            ctx.mark_partial(f"length-cut at chunk {i}; shrink SAFE_CHARS")
            break
        # meta.usage["reasoning_tokens"] is now available for budget tuning.
```

### Invalidating the ChunkCache

Three levels:

| Scope | How |
|-------|-----|
| One chunk, same slot (content drift) | Automatic — `content_hash` changes, `get` misses. |
| Every cached hash for one slot | `cache.clear(cid)` — idempotent on unknown cids. |
| Every slot (prompt / model rev) | Use a versioned `subdir`: `ChunkCache(base, subdir=f".wenguan_cache_{prompt_v}")`. |

Prefer versioned `subdir` over deleting the cache root: old caches linger at
near-zero cost and let you A/B prompts without re-paying the LLM bill.

### Per-request LLM key

`llmwiki.llm.chat(..., api_key="sk-…")` returns output from a fresh un-cached
client; the module singleton is never mutated. Useful for per-chunk tenant /
persona identity inside a stage:

```python
out = chat(
    s.content,
    system=WENGUAN_PROMPT,
    api_key=tenant_key_for(s.title),   # resolved per chunk
)
```

The key never reaches the log — `ctx.log` records chunk ids, not secrets — and
`llmwiki.llm._redact_key` scrubs it from any error string that bubbles out. Over
HTTP the same credential arrives as `X-LLM-Key`; see the v0.7.4 security
posture in the [CHANGELOG](../CHANGELOG.md).

### Status without a CLI

`rebuild_state` is the one-liner that substitutes for a status CLI (议 G is
still open):

```bash
python -c "from pathlib import Path; from llmwiki.pipeline import rebuild_state; \
  s = rebuild_state(Path('/var/siwen'), 'wenguan', 'taixu_quanshu'); \
  print(s.status, s.attempts, s.last_err or '', s.meta)"
```

Pipe it into cron / a Grafana exporter if you need a dashboard. The log is the
source of truth — any other view is a cache you invalidate on the log's mtime.

---

## Non-goals

Intentional absences. If you find yourself reaching for any of these, re-read
the composition pattern above first.

- **No DAG.** You sequence stages by writing them in Python. Branching is an
  `if`, fan-out is a `for`. `run_stage` knows nothing about predecessors or
  successors.
- **No retry policy.** A failed stage raises; your runner decides whether to
  retry, bail, or alert. A `partial` exit is not a failure — re-enter the same
  `with run_stage(...)` and the cache makes the second run cheap.
- **No cross-host mutex.** `StageLock` uses `socket.gethostname()` +
  `os.kill(pid, 0)`, which presupposes one machine owns `base_dir`. On shared
  storage with multiple writing hosts, wrap with etcd / consul / NFSv4 flock.
- **No status CLI (yet).** 议 G in the backlog. The `rebuild_state` snippet
  above is the deliberate interim — it forces downstream to consume the
  structured return rather than scraping CLI output.

---

## Where this fits

| If you want to | Go to |
|----------------|-------|
| Customize per-module constants (`SYSTEM_PROMPT`, taxonomy, tones, …) | [customization.md](customization.md) |
| Register a lifecycle hook (`ingested`, `compiled`, …) | [customization.md § Lifecycle Hooks](customization.md#lifecycle-hooks) |
| Build a new pipeline on top of these primitives | You are here |
| Read the driver's three laws and terminal guarantee | [`llmwiki/pipeline/__init__.py`](../llmwiki/pipeline/__init__.py) |
