"""敏感词词典编译与正文检查。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Set, Tuple

from .normalize import normalize_text, normalize_with_sources
from .sources import LiteralSource, VariableSource
from .template import Source, render


@dataclass(frozen=True)
class CompiledDictionary:
    """compile_dictionary 的产物，可复用于多次 inspect。

    words 为 (归一化后的词, 原词) 元组，按归一化词长降序排列。
    """

    words: Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class Hit:
    """一次敏感词命中。

    - word: 命中的词典原词。
    - start / end: 命中在归一化后正文中的码点区间 [start, end)。
    - sources: 实际贡献该命中的全部原字符来源，按来源位置排序。
    """

    word: str
    start: int
    end: int
    sources: Tuple[Source, ...]


def compile_dictionary(words: Iterable[str]) -> CompiledDictionary:
    """编译敏感词集合，供多次检查复用。

    词典与正文使用相同的归一化规则。归一化后为空或重复的词会被拒绝。
    """
    compiled: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for word in words:
        normalized = normalize_text(word)
        if not normalized:
            raise ValueError(f"敏感词归一化后为空: {word!r}")
        if normalized in seen:
            raise ValueError(f"敏感词归一化后重复: {word!r}")
        seen.add(normalized)
        compiled.append((normalized, word))
    compiled.sort(key=lambda item: (-len(item[0]), item[0]))
    return CompiledDictionary(words=tuple(compiled))


def _source_sort_key(source: Source) -> Tuple:
    if isinstance(source, LiteralSource):
        return (0, source.position, "", 0)
    if isinstance(source, VariableSource):
        return (1, source.placeholder_start, source.field, source.value_index)
    raise TypeError(f"未知来源类型: {source!r}")


def inspect(
    compiled: CompiledDictionary, template: str, values: Mapping[str, str]
) -> List[Hit]:
    """渲染模板并返回全部敏感词命中（含重叠命中）。

    命中位置基于归一化后的正文；每个命中的 sources 精确覆盖
    贡献该命中的原字符，不含无关字符。
    """
    text, char_sources = render(template, values)
    normalized, provenance = normalize_with_sources(text, char_sources)

    hits: List[Hit] = []
    for normalized_word, word in compiled.words:
        start = normalized.find(normalized_word)
        while start != -1:
            end = start + len(normalized_word)
            merged: Set[Source] = set()
            for piece in provenance[start:end]:
                merged.update(piece)
            hits.append(
                Hit(
                    word=word,
                    start=start,
                    end=end,
                    sources=tuple(sorted(merged, key=_source_sort_key)),
                )
            )
            start = normalized.find(normalized_word, start + 1)

    hits.sort(key=lambda hit: (hit.start, hit.end, hit.word))
    return hits
