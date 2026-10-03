"""Local sensitive-word inspection library with provenance tracking."""

from sensitive_words.api import (
    Hit,
    LiteralSource,
    SourceSpan,
    VariableSource,
    inspect,
)
from sensitive_words.dictionary import CompiledDictionary, compile_dictionary

__all__ = [
    "CompiledDictionary",
    "Hit",
    "LiteralSource",
    "SourceSpan",
    "VariableSource",
    "compile_dictionary",
    "inspect",
]
