"""带来源追踪的文本归一化：删除零宽字符 -> NFKC -> casefold。"""

from __future__ import annotations

import unicodedata
from typing import Hashable, List, Sequence, Set, Tuple

#: 归一化时被删除、不产生任何贡献的字符
REMOVED_CHARS = frozenset('\u200b\u200c\u200d\ufeff')


def normalize_text(text: str) -> str:
    """对文本应用归一化规则（不追踪来源）。"""
    stripped = "".join(ch for ch in text if ch not in REMOVED_CHARS)
    return unicodedata.normalize("NFKC", stripped).casefold()


def _decompose(char: str) -> List[str]:
    """递归完全分解（兼容 + 规范），等价于 NFKD 对单字符的结果。"""
    result: List[str] = []
    mapping = unicodedata.decomposition(char)
    if mapping:
        for part in mapping.split():
            if part.startswith("<"):
                continue
            result.extend(_decompose(chr(int(part, 16))))
    else:
        result.append(char)
    return result


def _combining_class(char: str) -> int:
    return unicodedata.combining(char)


def _compose(starter: str, char: str) -> str | None:
    """若 starter + char 存在规范组合，返回组合后的单字符，否则返回 None。"""
    merged = unicodedata.normalize("NFC", starter + char)
    return merged if len(merged) == 1 else None


def _is_hangul_l(char: str) -> bool:
    return 0x1100 <= ord(char) <= 0x1112


def _is_hangul_v(char: str) -> bool:
    return 0x1161 <= ord(char) <= 0x1175


def _is_hangul_t(char: str) -> bool:
    return 0x11A8 <= ord(char) <= 0x11C2


def _is_hangul_lv(char: str) -> bool:
    code = ord(char)
    return 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 == 0


def _continues_hangul(segment: List[str], char: str) -> bool:
    """判断 char 是否可与 segment 末尾发生韩文组合（L+V 或 LV+T）。"""
    if _is_hangul_v(char):
        return len(segment) == 1 and _is_hangul_l(segment[0])
    if _is_hangul_t(char):
        if len(segment) == 1 and _is_hangul_lv(segment[0]):
            return True
        return (
            len(segment) == 2
            and _is_hangul_l(segment[0])
            and _is_hangul_v(segment[1])
        )
    return False


def _split_segments(chars: List[str]) -> List[Tuple[int, int]]:
    """把字符序列切成规范化段（组合序列），返回 (start, end) 下标区间。

    每段以一个组合类为 0 的字符开头，后随组合类非 0 的字符；
    韩文组合所需的相邻字母并入同一段。段与段之间不会发生
    重排或组合，因此可逐段独立做 NFKC。
    """
    segments: List[Tuple[int, int]] = []
    start = 0
    for i in range(1, len(chars)):
        if _combining_class(chars[i]) != 0:
            continue
        if _continues_hangul(chars[start:i], chars[i]):
            continue
        segments.append((start, i))
        start = i
    segments.append((start, len(chars)))
    return segments


def _normalize_segment(
    chars: List[str], sources: List[Set[Hashable]]
) -> List[Tuple[str, Set[Hashable]]]:
    """对一个规范化段执行 NFKC，返回 (字符, 来源集合) 列表。"""
    decomposed: List[Tuple[str, Set[Hashable]]] = []
    for char, src in zip(chars, sources):
        for leaf in _decompose(char):
            decomposed.append((leaf, set(src)))

    # 规范重排：按组合类稳定排序，来源随字符移动
    decomposed.sort(key=lambda item: _combining_class(item[0]))

    # 规范组合：来源取参与组合字符来源的并集
    composed: List[List] = []  # [char, sources]
    starter_index: int | None = None
    prev_cc = 0
    for char, src in decomposed:
        cc = _combining_class(char)
        if starter_index is not None and (prev_cc == 0 or prev_cc < cc):
            merged = _compose(composed[starter_index][0], char)
            if merged is not None:
                composed[starter_index][0] = merged
                composed[starter_index][1] |= src
                continue
        if cc == 0:
            starter_index = len(composed)
        prev_cc = cc
        composed.append([char, src])

    return [(char, src) for char, src in composed]


def normalize_with_sources(
    text: str, sources: Sequence[Hashable]
) -> Tuple[str, List[frozenset]]:
    """归一化文本，并返回归一化结果中每个字符对应的来源集合列表。

    sources[i] 是 text[i] 的来源标识；返回值中每个 frozenset 只包含
    实际贡献了该归一化字符的来源。被删除的字符没有贡献。
    """
    if len(text) != len(sources):
        raise ValueError("text 与 sources 长度必须一致")

    kept_chars: List[str] = []
    kept_sources: List[Set[Hashable]] = []
    for char, src in zip(text, sources):
        if char in REMOVED_CHARS:
            continue
        kept_chars.append(char)
        kept_sources.append({src})

    out_chars: List[str] = []
    out_sources: List[frozenset] = []
    for start, end in _split_segments(kept_chars):
        segment = _normalize_segment(
            kept_chars[start:end], kept_sources[start:end]
        )
        for char, src in segment:
            folded = char.casefold()
            for folded_char in folded:
                out_chars.append(folded_char)
                out_sources.append(frozenset(src))

    return "".join(out_chars), out_sources
