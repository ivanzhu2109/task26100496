"""Compilation of sensitive-word dictionaries into a reusable matcher."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, FrozenSet, Hashable, Iterable, List, Sequence, Tuple

from sensitive_words.normalize import normalize_text


@dataclass(frozen=True)
class RawMatch:
    """A match over the normalized character stream."""

    start: int
    end: int
    word: str


class _Node:
    __slots__ = ("children", "fail", "outputs")

    def __init__(self) -> None:
        self.children: Dict[str, int] = {}
        self.fail: int = 0
        self.outputs: List[Tuple[int, str]] = []  # (length, normalized word)


class CompiledDictionary:
    """Aho-Corasick matcher over normalized sensitive words."""

    def __init__(self, words: Iterable[str]) -> None:
        normalized_words = sorted({normalize_text(word) for word in words})
        if not normalized_words or any(not word for word in normalized_words):
            raise ValueError("normalized dictionary words must be non-empty")
        self.words: Tuple[str, ...] = tuple(normalized_words)
        nodes = [_Node()]
        for word in normalized_words:
            state = 0
            for char in word:
                nxt = nodes[state].children.get(char)
                if nxt is None:
                    nxt = len(nodes)
                    nodes[state].children[char] = nxt
                    nodes.append(_Node())
                state = nxt
            nodes[state].outputs.append((len(word), word))
        queue: deque[int] = deque()
        for child in nodes[0].children.values():
            nodes[child].fail = 0
            queue.append(child)
        while queue:
            state = queue.popleft()
            for char, nxt in nodes[state].children.items():
                queue.append(nxt)
                fallback = nodes[state].fail
                while fallback and char not in nodes[fallback].children:
                    fallback = nodes[fallback].fail
                nodes[nxt].fail = nodes[fallback].children.get(char, 0)
                nodes[nxt].outputs.extend(nodes[nodes[nxt].fail].outputs)
        self._nodes = nodes

    def search(self, chars: Sequence[Tuple[str, FrozenSet[Hashable]]]) -> List[RawMatch]:
        """Return every (including overlapping) match, ordered by end."""
        nodes = self._nodes
        matches: List[RawMatch] = []
        state = 0
        for index, (char, _) in enumerate(chars):
            while state and char not in nodes[state].children:
                state = nodes[state].fail
            state = nodes[state].children.get(char, 0)
            for length, word in nodes[state].outputs:
                matches.append(RawMatch(index + 1 - length, index + 1, word))
        matches.sort(key=lambda match: (match.start, match.end))
        return matches


def compile_dictionary(words: Iterable[str]) -> CompiledDictionary:
    """Compile a sensitive-word collection for repeated inspections."""
    return CompiledDictionary(words)
