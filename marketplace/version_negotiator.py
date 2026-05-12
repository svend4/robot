"""ETD Version Negotiator — semver constraint resolution for the skill marketplace.

Given a skill ID and a runtime version, finds the highest skill version that
satisfies the runtime constraint declared in the skill's manifest.

Supported constraint operators: ``>=``, ``>``, ``<=``, ``<``, ``==``, ``~=``
(compatible-release: ``~=1.2`` → ``>=1.2, <2.0``; ``~=1.2.3`` → ``>=1.2.3, <1.3``).

Usage::

    from marketplace.version_negotiator import best_version, satisfies

    # Single constraint
    satisfies('0.5.0', '>=0.1.0')   # True
    satisfies('0.0.9', '>=0.1.0')   # False

    # Find the best entry for a runtime
    entry = best_version(store.get_versions('etd.pickplace.basic'), '0.5.0')
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple


# ── Semver parsing ────────────────────────────────────────────────────────────

def parse_version(v: str) -> Tuple[int, int, int]:
    """Parse a ``major.minor.patch`` version string into a tuple.

    Returns ``(0, 0, 0)`` for unparseable strings so comparisons degrade
    gracefully rather than raising.
    """
    try:
        parts = v.strip().split('.')
        return (int(parts[0]), int(parts[1] if len(parts) > 1 else 0),
                int(parts[2] if len(parts) > 2 else 0))
    except Exception:
        return (0, 0, 0)


# ── Single-constraint evaluation ──────────────────────────────────────────────

def satisfies(version: str, constraint: str) -> bool:
    """Return True if *version* satisfies the semver *constraint*.

    *constraint* may be a single specifier (``>=0.1.0``) or a comma-separated
    conjunction (``>=0.1.0, <1.0.0``).  Whitespace around each specifier is
    stripped.  Unknown or empty constraints always return True.
    """
    if not constraint or constraint.strip() == '*':
        return True
    for spec in constraint.split(','):
        if not _satisfies_single(version, spec.strip()):
            return False
    return True


def _satisfies_single(version: str, spec: str) -> bool:
    spec = spec.strip()
    if not spec:
        return True

    # Compatible-release: ~=1.2 → >=1.2, <2.0; ~=1.2.3 → >=1.2.3, <1.3
    if spec.startswith('~='):
        base = spec[2:].strip()
        return _compatible_release(version, base)

    m = re.match(r'^(>=|>|<=|<|==|!=)\s*(.+)$', spec)
    if m is None:
        # Bare version: treat as ==
        return parse_version(version) == parse_version(spec)

    op, req_str = m.group(1), m.group(2).strip()
    v = parse_version(version)
    r = parse_version(req_str)

    if op == '>=': return v >= r
    if op == '>':  return v > r
    if op == '<=': return v <= r
    if op == '<':  return v < r
    if op == '==': return v == r
    if op == '!=': return v != r
    return True


def _compatible_release(version: str, base: str) -> bool:
    """``~=major.minor`` → ``>=major.minor, <(major+1).0``
       ``~=major.minor.patch`` → ``>=major.minor.patch, <major.(minor+1).0``
    """
    parts = base.split('.')
    if len(parts) < 2:
        return parse_version(version) >= parse_version(base)
    lower = parse_version(base)
    if len(parts) == 2:
        upper = (lower[0] + 1, 0, 0)
    else:
        upper = (lower[0], lower[1] + 1, 0)
    v = parse_version(version)
    return lower <= v < upper


# ── Multi-version selection ───────────────────────────────────────────────────

def best_version(entries, runtime_version: str = '0.0.0'):
    """Return the highest-versioned entry whose runtime constraint is satisfied.

    Parameters
    ----------
    entries:
        Iterable of objects with a ``.version`` attribute (e.g. ``StoreEntry``).
        All entries are assumed to be for the same ``skill_id``.
    runtime_version:
        The ETD runtime version currently running (e.g. ``"0.5.0"``).

    Returns
    -------
    The entry with the highest ``.version`` whose constraint is met, or None.
    """
    compatible = []
    for entry in entries:
        constraint = getattr(entry, 'runtimeConstraint', '') or ''
        if satisfies(runtime_version, constraint):
            compatible.append(entry)
    if not compatible:
        return None
    return max(compatible, key=lambda e: parse_version(getattr(e, 'version', '0.0.0')))


def sort_versions(entries, descending: bool = True):
    """Return entries sorted by version (descending by default)."""
    return sorted(
        entries,
        key=lambda e: parse_version(getattr(e, 'version', '0.0.0')),
        reverse=descending,
    )
