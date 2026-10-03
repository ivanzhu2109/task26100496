"""公告发布前的本地敏感词检查库。"""

from .dictionary import CompiledDictionary, Hit, compile_dictionary, inspect
from .sources import LiteralSource, VariableSource

__all__ = [
    "CompiledDictionary",
    "Hit",
    "LiteralSource",
    "VariableSource",
    "compile_dictionary",
    "inspect",
]
