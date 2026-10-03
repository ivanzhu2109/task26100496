import unittest

from sensitive_words import (
    LiteralSource,
    VariableSource,
    compile_dictionary,
    inspect,
)


class CrossSegmentHitTest(unittest.TestCase):
    def test_hit_spans_literal_variable_literal(self):
        compiled = compile_dictionary(["bad"])
        template = "b{{customer.x}}d"
        hits = inspect(compiled, template, {"x": "​A"})
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual((hit.start, hit.end, hit.word), (0, 3, "bad"))
        self.assertEqual(
            hit.sources,
            (
                LiteralSource(start=0, end=1),
                LiteralSource(start=15, end=16),
                VariableSource(placeholder_start=1, field="x", start=1, end=2),
            ),
        )

    def test_deleted_char_contributes_nothing(self):
        compiled = compile_dictionary(["bad"])
        hits = inspect(compiled, "b{{customer.x}}d", {"x": "​A"})
        variable_spans = [s for s in hits[0].sources if isinstance(s, VariableSource)]
        self.assertEqual(len(variable_spans), 1)
        # U+200B at value index 0 must not appear; only "A" at index 1.
        self.assertEqual((variable_spans[0].start, variable_spans[0].end), (1, 2))

    def test_repeated_field_distinguishes_placeholder_positions(self):
        compiled = compile_dictionary(["a a"])
        template = "{{customer.x}} {{customer.x}}"
        hits = inspect(compiled, template, {"x": "a"})
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual((hit.start, hit.end), (0, 3))
        self.assertEqual(
            hit.sources,
            (
                LiteralSource(start=14, end=15),
                VariableSource(placeholder_start=0, field="x", start=0, end=1),
                VariableSource(placeholder_start=15, field="x", start=0, end=1),
            ),
        )

    def test_same_expanded_char_joins_multiple_hits(self):
        compiled = compile_dictionary(["aa"])
        template = "{{customer.x}}{{customer.x}}"
        hits = inspect(compiled, template, {"x": "a"})
        self.assertEqual(len(hits), 1)
        self.assertEqual(
            hits[0].sources,
            (
                VariableSource(placeholder_start=0, field="x", start=0, end=1),
                VariableSource(placeholder_start=14, field="x", start=0, end=1),
            ),
        )


class CompositionHitTest(unittest.TestCase):
    def test_ring_above_composes_across_placeholder_boundary(self):
        compiled = compile_dictionary(["å"])
        hits = inspect(compiled, "A{{customer.mark}}", {"mark": "̊"})
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual((hit.start, hit.end, hit.word), (0, 1, "å"))
        self.assertEqual(
            hit.sources,
            (
                LiteralSource(start=0, end=1),
                VariableSource(placeholder_start=1, field="mark", start=0, end=1),
            ),
        )

    def test_reordered_combining_marks_hit_excludes_non_contributor(self):
        compiled = compile_dictionary(["à"])
        # U+0061 U+0315 U+0300: canonical reordering moves U+0300 next to
        # "a" and composes to "à"; U+0315 must not be part of the source.
        hits = inspect(compiled, "à̕", {})
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual((hit.start, hit.end, hit.word), (0, 1, "à"))
        self.assertEqual(
            hit.sources,
            (
                LiteralSource(start=0, end=1),
                LiteralSource(start=2, end=3),
            ),
        )


class OverlapAndReuseTest(unittest.TestCase):
    def test_overlapping_hits_are_all_reported(self):
        compiled = compile_dictionary(["aba", "bab"])
        hits = inspect(compiled, "abab", {})
        self.assertEqual(
            [(hit.start, hit.end, hit.word) for hit in hits],
            [(0, 3, "aba"), (1, 4, "bab")],
        )

    def test_compiled_dictionary_is_reusable(self):
        compiled = compile_dictionary(["bad"])
        self.assertEqual(len(inspect(compiled, "bad", {})), 1)
        self.assertEqual(len(inspect(compiled, "good", {})), 0)
        self.assertEqual(len(inspect(compiled, "b{{customer.x}}d", {"x": "a"})), 1)


if __name__ == "__main__":
    unittest.main()
