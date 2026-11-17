"""Gitignore-style patterns for extra shadow-repo exclusions.

The add-on option is a comma-separated list. Rules follow .gitignore:

- A pattern with no ``/`` (a trailing slash does not count) matches that
  name at any directory depth.
- A pattern that contains a ``/`` is anchored at the config root. A leading
  ``/`` is only an anchor, not part of the path.
- ``**`` matches any number of directories, including zero.
- A trailing ``/`` matches directories only. A matching directory also
  excludes everything inside it.
- Whitespace around entries is trimmed. Empty entries are ignored.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass


@dataclass(frozen=True)
class IgnoreRule:
    """One compiled pattern from ``git_versioning_ignore``."""

    segments: tuple[str, ...]
    dir_only: bool
    anchored: bool

    def matches(self, parts: tuple[str, ...], is_dir: bool) -> bool:
        if self.dir_only and not is_dir:
            return False
        if self.anchored:
            return _segments_match(parts, self.segments)
        # No slash in the pattern: it matches the name in any directory.
        return any(_segments_match((part,), self.segments) for part in parts)


def compile_ignore_rules(raw: str | None) -> tuple[IgnoreRule, ...]:
    """Compile a comma-separated pattern list. Blank input yields no rules."""
    if not raw:
        return ()
    rules: list[IgnoreRule] = []
    for entry in raw.split(","):
        rule = _compile_entry(entry)
        if rule is not None:
            rules.append(rule)
    return tuple(rules)


def path_is_ignored(
    rel_path: str,
    is_dir: bool,
    rules: tuple[IgnoreRule, ...] | list[IgnoreRule],
) -> bool:
    """Return True when ``rel_path`` (relative to /config) matches a rule.

    A directory match excludes the directory and every path inside it.
    """
    if not rules:
        return False
    normalized = rel_path.replace("\\", "/").strip("/")
    if not normalized or normalized == ".":
        return False
    parts = tuple(part for part in normalized.split("/") if part not in ("", "."))
    if not parts:
        return False

    # Check the path itself, then each ancestor. Ancestors are directories,
    # so a directory-only rule excludes everything underneath it.
    for end in range(len(parts), 0, -1):
        sub = parts[:end]
        sub_is_dir = is_dir if end == len(parts) else True
        for rule in rules:
            if rule.matches(sub, sub_is_dir):
                return True
    return False


def _compile_entry(entry: str) -> IgnoreRule | None:
    pattern = entry.strip()
    if not pattern or pattern == "/":
        return None
    dir_only = pattern.endswith("/")
    pattern = pattern.rstrip("/")
    if pattern.startswith("/"):
        anchored = True
        pattern = pattern.lstrip("/")
    else:
        anchored = "/" in pattern
    if not pattern:
        return None
    segments = tuple(part for part in pattern.split("/") if part)
    if not segments:
        return None
    return IgnoreRule(segments=segments, dir_only=dir_only, anchored=anchored)


def _segments_match(path: tuple[str, ...], pattern: tuple[str, ...]) -> bool:
    return _match(path, pattern, 0, 0)


def _match(path: tuple[str, ...], pattern: tuple[str, ...], pi: int, pj: int) -> bool:
    """Match path segments. A ``**`` segment matches zero or more segments.

    ``*`` and ``?`` are applied to a single segment and never cross a ``/``.
    """
    while pj < len(pattern):
        token = pattern[pj]
        if token == "**":
            if pj == len(pattern) - 1:
                return True
            for skip in range(pi, len(path) + 1):
                if _match(path, pattern, skip, pj + 1):
                    return True
            return False
        if pi >= len(path):
            return False
        if not fnmatch.fnmatchcase(path[pi], token):
            return False
        pi += 1
        pj += 1
    return pi == len(path)
