"""模板渲染：仅支持 {{customer.field}} 占位符，替换值不再递归解释。"""

from __future__ import annotations

import re
from typing import List, Mapping, Tuple, Union

from .sources import LiteralSource, VariableSource

Source = Union[LiteralSource, VariableSource]

_PLACEHOLDER = re.compile(r"\{\{customer\.([A-Za-z0-9_]+)\}\}")


def render(template: str, values: Mapping[str, str]) -> Tuple[str, List[Source]]:
    """渲染模板，返回 (渲染后原文, 每个字符对应的来源)。

    - 字面量字符的来源为 LiteralSource(模板中的码点下标)。
    - 替换值字符的来源为 VariableSource(占位符起始下标, 字段名, 值内下标)。
    - 未在 values 中出现的字段按空字符串处理。
    - 不匹配 {{customer.field}} 形式的文本一律按字面量处理。
    """
    chars: List[str] = []
    sources: List[Source] = []
    pos = 0
    for match in _PLACEHOLDER.finditer(template):
        for i in range(pos, match.start()):
            chars.append(template[i])
            sources.append(LiteralSource(i))
        field = match.group(1)
        value = values.get(field, "")
        if not isinstance(value, str):
            raise TypeError(f"字段 {field!r} 的替换值必须是字符串")
        for index, char in enumerate(value):
            chars.append(char)
            sources.append(VariableSource(match.start(), field, index))
        pos = match.end()
    for i in range(pos, len(template)):
        chars.append(template[i])
        sources.append(LiteralSource(i))
    return "".join(chars), sources
