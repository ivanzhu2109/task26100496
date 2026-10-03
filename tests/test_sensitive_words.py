# -*- coding: utf-8 -*-
"""敏感词检查库的自动化测试。

注意：涉及组合字符 / 零宽字符的用例一律使用 \\u 转义书写，
避免源码规范化（NFC）改变测试意图。
"""

import pytest

from sensitive_words import (
    Hit,
    LiteralSource,
    VariableSource,
    compile_dictionary,
    inspect,
)


class TestCrossFragmentHit:
    """场景一：模板 b{{customer.x}}d，替换值为 U+200B + "A"，词典含 bad。"""

    def setup_method(self):
        self.dictionary = compile_dictionary(["bad"])
        self.hits = inspect(
            self.dictionary, "b{{customer.x}}d", {"x": "\u200bA"}
        )

    def test_single_hit_spanning_three_fragments(self):
        assert len(self.hits) == 1
        hit = self.hits[0]
        assert hit.word == "bad"
        # 归一化后正文为 "bad"，命中覆盖整个正文
        assert (hit.start, hit.end) == (0, 3)

    def test_sources_exclude_deleted_char(self):
        hit = self.hits[0]
        assert set(hit.sources) == {
            LiteralSource(0),               # 模板中的 'b'
            VariableSource(1, "x", 1),      # 替换值中的 'A'（下标 1）
            LiteralSource(15),              # 模板中的 'd'
        }
        # 被删除的 U+200B（替换值下标 0）不得出现在来源中
        assert VariableSource(1, "x", 0) not in hit.sources

    def test_repeated_field_sources_are_distinguished(self):
        hits = inspect(
            self.dictionary,
            "{{customer.x}}{{customer.x}}d",
            {"x": "\u200bba"},  # 每次替换渲染为 "ba"（U+200B 被删除）
        )
        # 归一化后正文 "babad"，"bad" 只在第二处替换与字面量 d 交界处命中
        assert len(hits) == 1
        hit = hits[0]
        assert (hit.start, hit.end) == (2, 5)
        second = len("{{customer.x}}")  # 第二处占位符起点 = 14
        assert set(hit.sources) == {
            VariableSource(second, "x", 1),   # 第二处替换值中的 'b'
            VariableSource(second, "x", 2),   # 第二处替换值中的 'a'
            LiteralSource(2 * second),        # 模板末尾的 'd'
        }
        # 第一处占位符（起点 0）的字符不参与该命中
        assert all(
            not (isinstance(s, VariableSource) and s.placeholder_start == 0)
            for s in hit.sources
        )

    def test_same_field_twice_two_independent_hits(self):
        dictionary = compile_dictionary(["ab"])
        hits = inspect(
            dictionary, "{{customer.x}}{{customer.x}}", {"x": "ab"}
        )
        assert len(hits) == 2
        first, second = hits
        assert (first.start, first.end) == (0, 2)
        assert (second.start, second.end) == (2, 4)
        assert set(first.sources) == {
            VariableSource(0, "x", 0),
            VariableSource(0, "x", 1),
        }
        assert set(second.sources) == {
            VariableSource(14, "x", 0),
            VariableSource(14, "x", 1),
        }


class TestCompositionAcrossBoundary:
    """场景二：模板 A{{customer.mark}}，替换值为 U+030A，词典含 å。"""

    def test_compose_across_literal_and_variable(self):
        hits = inspect(
            compile_dictionary(["å"]),
            "A{{customer.mark}}",
            {"mark": "\u030a"},
        )
        assert len(hits) == 1
        hit = hits[0]
        assert hit.word == "å"
        assert (hit.start, hit.end) == (0, 1)
        # 'A'（字面量）与 U+030A（替换值）组合为 Å，再 casefold 为 å
        assert set(hit.sources) == {
            LiteralSource(0),
            VariableSource(1, "mark", 0),
        }

    def test_canonical_reordering_exact_sources(self):
        # 正文 U+0061 U+0315 U+0300：重排后 a+U+0300 组合为 à
        hits = inspect(compile_dictionary(["à"]), "a\u0315\u0300", {})
        assert len(hits) == 1
        hit = hits[0]
        assert (hit.start, hit.end) == (0, 1)
        # 来源必须恰为第 0 和第 2 个原字符，不含第 1 个（U+0315）
        assert set(hit.sources) == {
            LiteralSource(0),
            LiteralSource(2),
        }
        assert LiteralSource(1) not in hit.sources


class TestOverlappingHits:
    def test_overlapping_and_nested_hits(self):
        hits = inspect(compile_dictionary(["aba", "ab", "ba"]), "aba", {})
        assert [(h.word, h.start, h.end) for h in hits] == [
            ("ab", 0, 2),
            ("aba", 0, 3),
            ("ba", 1, 3),
        ]

    def test_one_source_char_joins_multiple_hits(self):
        # 原字符 'b'（下标 1）同时参与 "ab" 与 "ba" 两个命中
        hits = inspect(compile_dictionary(["ab", "ba"]), "ab{{customer.x}}", {"x": "a"})
        words = {(h.word, tuple(sorted(type(s).__name__ for s in h.sources))) for h in hits}
        assert len(hits) == 2
        for hit in hits:
            if hit.word == "ab":
                assert set(hit.sources) == {LiteralSource(0), LiteralSource(1)}
            else:
                assert set(hit.sources) == {
                    LiteralSource(1),
                    VariableSource(2, "x", 0),
                }


class TestDictionaryCompile:
    def test_normalized_words_must_be_nonempty(self):
        with pytest.raises(ValueError):
            compile_dictionary(["\u200b"])  # 仅含零宽字符，归一化后为空

    def test_normalized_words_must_be_distinct(self):
        with pytest.raises(ValueError):
            compile_dictionary(["Å", "å"])  # 归一化后相同

    def test_casefold_and_nfkc_matching(self):
        dictionary = compile_dictionary(["ﬀ", "straße"])
        hits = inspect(dictionary, "FFICE 的 STRASSE", {})
        assert [(h.word, h.start, h.end) for h in hits] == [
            ("ﬀ", 0, 2),
            ("straße", 8, 15),
        ]

    def test_no_hit(self):
        assert inspect(compile_dictionary(["xyz"]), "hello", {}) == []

    def test_missing_field_renders_empty(self):
        assert inspect(compile_dictionary(["bd"]), "b{{customer.x}}d", {})[0].word == "bd"

    def test_hit_type(self):
        hits = inspect(compile_dictionary(["bad"]), "bad", {})
        assert isinstance(hits[0], Hit)
