"""Normalization pipeline that tracks per-character provenance.

The shared rules are, in order:
1. drop U+200B, U+200C, U+200D, U+FEFF (they contribute nothing),
2. Unicode NFKC (decompose, canonically reorder, canonically compose),
3. ``str.casefold``.

Provenance semantics: decomposed or case-expanded characters inherit the
origin of their source character; canonical reordering keeps origins
attached to their characters; composition unions the origins of the
combined characters.
"""

from __future__ import annotations

import unicodedata
from typing import Dict, FrozenSet, Hashable, List, Sequence, Tuple

Origin = Hashable

_DELETED = frozenset("​‌‍﻿")

_decompose_cache: Dict[str, Tuple[str, ...]] = {}


def _full_decompose(char: str) -> Tuple[str, ...]:
    """Recursively expand the NFKC decomposition of a single character."""
    cached = _decompose_cache.get(char)
    if cached is not None:
        return cached
    decomposition = unicodedata.decomposition(char)
    if not decomposition:
        result: Tuple[str, ...] = (char,)
    else:
        parts: List[str] = []
        for token in decomposition.split():
            if token.startswith("<"):
                continue
            parts.extend(_full_decompose(chr(int(token, 16))))
        result = tuple(parts)
    _decompose_cache[char] = result
    return result


def _reorder(items: List[Tuple[str, FrozenSet[Origin]]]) -> None:
    """Canonical reordering: stable sort by combining class within runs."""
    index = 1
    while index < len(items):
        char, _ = items[index]
        combining_class = unicodedata.combining(char)
        if combining_class == 0:
            index += 1
            continue
        cursor = index
        while cursor > 0:
            prev_class = unicodedata.combining(items[cursor - 1][0])
            if prev_class == 0 or prev_class <= combining_class:
                break
            items[cursor], items[cursor - 1] = items[cursor - 1], items[cursor]
            cursor -= 1
        index += 1


def _compose_pair(starter: str, char: str) -> str | None:
    """Return the canonical composition of two chars, or None."""
    composed = unicodedata.normalize("NFC", starter + char)
    if len(composed) == 1:
        return composed
    return None


def _compose(
    items: List[Tuple[str, FrozenSet[Origin]]],
) -> List[Tuple[str, FrozenSet[Origin]]]:
    """Canonical composition, unioning origins of combined characters."""
    result: List[Tuple[str, FrozenSet[Origin]]] = []
    starter_index = -1
    last_class = 0
    for char, origins in items:
        combining_class = unicodedata.combining(char)
        if starter_index >= 0 and (last_class < combining_class or last_class == 0):
            starter_char, starter_origins = result[starter_index]
            composite = _compose_pair(starter_char, char)
            if composite is not None:
                result[starter_index] = (composite, starter_origins | origins)
                continue
        if combining_class == 0:
            starter_index = len(result)
        result.append((char, origins))
        last_class = combining_class
    return result


def normalize_units(units: Sequence[Tuple[str, Origin]]) -> List[Tuple[str, FrozenSet[Origin]]]:
    """Normalize ``(char, origin)`` pairs, returning ``(char, origins)``."""
    decomposed: List[Tuple[str, FrozenSet[Origin]]] = []
    for char, origin in units:
        if char in _DELETED:
            continue
        for part in _full_decompose(char):
            decomposed.append((part, frozenset((origin,))))
    _reorder(decomposed)
    composed = _compose(decomposed)
    normalized: List[Tuple[str, FrozenSet[Origin]]] = []
    for char, origins in composed:
        for folded in char.casefold():
            normalized.append((folded, origins))
    return normalized


def normalize_text(text: str) -> str:
    """Normalize plain text with the same rules (no provenance needed)."""
    stripped = "".join(char for char in text if char not in _DELETED)
    return unicodedata.normalize("NFKC", stripped).casefold()
