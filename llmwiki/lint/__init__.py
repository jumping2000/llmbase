"""Lint package — health checks, auto-fix, and deduplication.

Re-exports all public functions for backward compatibility:
    from llmwiki.lint import lint, auto_fix, check_broken_links, ...
"""

from .checks import (
    check_broken_links,
    check_dirty_tags,
    check_duplicates,
    check_missing_metadata,
    check_orphans,
    check_structural,
    check_stubs,
    check_uncategorized,
    lint,
    lint_deep,
)
from .dedup import (
    _find_duplicate_candidates,
    merge_duplicates,
)
from .fixes import (
    auto_fix,
    clean_garbage,
    fix_broken_links,
    fix_dirty_tags,
    fix_uncategorized,
    normalize_tags,
)
from .orphans import (
    fix_orphans,
    insert_see_also,
    link_orphan,
    list_orphans,
    orphan_slugs,
    suggest_link_sources,
)

__all__ = [
    "lint", "lint_deep", "auto_fix",
    "check_structural", "check_broken_links", "check_orphans",
    "check_missing_metadata", "check_dirty_tags", "check_stubs",
    "check_uncategorized", "check_duplicates",
    "normalize_tags", "fix_dirty_tags", "clean_garbage",
    "fix_uncategorized", "fix_broken_links",
    "list_orphans", "suggest_link_sources", "insert_see_also",
    "link_orphan", "fix_orphans", "orphan_slugs",
    "merge_duplicates", "_find_duplicate_candidates",
]
