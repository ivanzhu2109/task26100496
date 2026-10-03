"""命中来源：正文中每个归一化字符可追溯到的一个或多个原字符位置。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiteralSource:
    """模板字面量来源：position 为该字符在模板原文中的码点下标。"""

    position: int


@dataclass(frozen=True)
class VariableSource:
    """变量替换来源：placeholder_start 为占位符在模板中的起始码点下标，
    field 为字段名，value_index 为该字符在替换值中的码点下标。"""

    placeholder_start: int
    field: str
    value_index: int
