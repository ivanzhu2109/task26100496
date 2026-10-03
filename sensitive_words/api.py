"""Public inspection API: render templates and locate sensitive words."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Hashable, List, Mapping, Tuple, Union

from sensitive_words.dictionary import CompiledDictionary
from sensitive_words.normalize import normalize_units

_PLACEHOLDER = re.compile(r"\{\{customer\.([A-Za-z0-9_]+)\}\}")


@dataclass(frozen=True)
class LiteralSource:
    """Source span pointing into the template literal text."""

    start: int
    end: int


@dataclass(frozen=True)
class VariableSource:
    """Source span pointing into one placeholder's replacement value."""

    placeholder_start: int
    field: str
    start: int
    end: int


SourceSpan = Union[LiteralSource, VariableSource]


@dataclass(frozen=True)
class Hit:
    """One sensitive-word hit in the normalized rendered text."""

    start: int
    end: int
    word: str
    sources: Tuple[SourceSpan, ...]


def _render_units(
    template: str, values: Mapping[str, str]
) -> List[Tuple[str, Hashable]]:
    """Build ``(char, origin)`` pairs for the rendered template."""
    units: List[Tuple[str, Hashable]] = []
    cursor = 0
    for match in _PLACEHOLDER.finditer(template):
        for index in range(cursor, match.start()):
            units.append((template[index], ("literal", index)))
        field = match.group(1)
        if field not in values:
            raise KeyError(f"missing value for field {field!r}")
        value = values[field]
        for index, char in enumerate(value):
            units.append((char, ("variable", match.start(), field, index)))
        cursor = match.end()
    for index in range(cursor, len(template)):
        units.append((template[index], ("literal", index)))
    return units


def _merge_spans(origins: List[Hashable]) -> Tuple[SourceSpan, ...]:
    """Merge contributing origins into contiguous, non-overlapping spans."""
    literal_indices: set[int] = set()
    variable_indices: Dict[Tuple[int, str], set[int]] = {}
    for origin in origins:
        if origin[0] == "literal":
            literal_indices.add(origin[1])
        else:
            _, placeholder_start, field, index = origin
            variable_indices.setdefault((placeholder_start, field), set()).add(index)
    spans: List[Tuple[tuple, SourceSpan]] = []
    if literal_indices:
        for start, end in _contiguous_ranges(literal_indices):
            spans.append(((0, start), LiteralSource(start, end)))
    for (placeholder_start, field), indices in variable_indices.items():
        for start, end in _contiguous_ranges(indices):
            spans.append(
                ((1, placeholder_start, start), VariableSource(placeholder_start, field, start, end))
            )
    spans.sort(key=lambda item: item[0])
    return tuple(span for _, span in spans)


def _contiguous_ranges(indices: set[int]) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    start = end = None
    for index in sorted(indices):
        if start is None:
            start = end = index
        elif index == end + 1:
            end = index
        else:
            ranges.append((start, end + 1))
            start = end = index
    if start is not None:
        ranges.append((start, end + 1))
    return ranges


def inspect(
    compiled: CompiledDictionary,
    template: str,
    values: Mapping[str, str],
) -> List[Hit]:
    """Render ``template`` with ``values`` and return all hits.

    Positions in each :class:`Hit` index the normalized rendered text;
    sources locate the exact contributing original characters.
    """
    units = _render_units(template, values)
    normalized = normalize_units(units)
    hits: List[Hit] = []
    for match in compiled.search(normalized):
        origins: List[Hashable] = []
        for _, char_origins in normalized[match.start : match.end]:
            origins.extend(char_origins)
        hits.append(
            Hit(
                start=match.start,
                end=match.end,
                word=match.word,
                sources=_merge_spans(origins),
            )
        )
    return hits
