import unittest

from universal_line_ending_normalizer import (
    LineEnding,
    detect_line_endings,
    normalize_line_endings,
    LineEndingNormalizer,
)


class TestDetectLineEndings(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(detect_line_endings(""), set())

    def test_no_line_endings(self):
        self.assertEqual(detect_line_endings("hello world"), set())

    def test_lf_only(self):
        self.assertEqual(detect_line_endings("a\nb\n"), {LineEnding.LF})

    def test_cr_only(self):
        self.assertEqual(detect_line_endings("a\rb\r"), {LineEnding.CR})

    def test_crlf_only(self):
        self.assertEqual(detect_line_endings("a\r\nb\r\n"), {LineEnding.CRLF})

    def test_crlf_does_not_also_report_cr_and_lf(self):
        # The core guarantee: \r\n is one separator, not two.
        self.assertEqual(detect_line_endings("\r\n"), {LineEnding.CRLF})

    def test_mixed_lf_and_crlf(self):
        self.assertEqual(
            detect_line_endings("a\nb\r\nc"),
            {LineEnding.LF, LineEnding.CRLF},
        )

    def test_mixed_cr_and_lf(self):
        # Bare CR and bare LF are distinct endings.
        self.assertEqual(
            detect_line_endings("a\rb\nc"),
            {LineEnding.CR, LineEnding.LF},
        )

    def test_nel(self):
        self.assertEqual(detect_line_endings("a\u0085b"), {LineEnding.NEL})

    def test_line_separator(self):
        self.assertEqual(detect_line_endings("a\u2028b"), {LineEnding.LS})

    def test_paragraph_separator(self):
        self.assertEqual(detect_line_endings("a\u2029b"), {LineEnding.PS})

    def test_all_six_types_in_one_string(self):
        text = "a\nb\rc\r\nd\u0085e\u2028f\u2029g"
        self.assertEqual(
            detect_line_endings(text),
            {LineEnding.LF, LineEnding.CR, LineEnding.CRLF,
             LineEnding.NEL, LineEnding.LS, LineEnding.PS},
        )

    def test_rejects_non_str(self):
        with self.assertRaises(TypeError):
            detect_line_endings(b"hello\n")  # type: ignore[arg-type]


class TestNormalizeLineEndings(unittest.TestCase):
    def test_lf_to_crlf(self):
        self.assertEqual(
            normalize_line_endings("a\nb\n", LineEnding.CRLF),
            "a\r\nb\r\n",
        )

    def test_crlf_to_lf(self):
        self.assertEqual(
            normalize_line_endings("a\r\nb\r\n", LineEnding.LF),
            "a\nb\n",
        )

    def test_crlf_collapses_to_single_target(self):
        # One CRLF in, one LF out — not two.
        self.assertEqual(normalize_line_endings("\r\n", LineEnding.LF), "\n")

    def test_cr_to_lf(self):
        self.assertEqual(
            normalize_line_endings("a\rb\r", LineEnding.LF),
            "a\nb\n",
        )

    def test_unicode_separators_to_lf(self):
        text = "a\u0085b\u2028c\u2029d"
        self.assertEqual(
            normalize_line_endings(text, LineEnding.LF),
            "a\nb\nc\nd",
        )

    def test_all_types_to_cr(self):
        text = "a\nb\rc\r\nd\u0085e\u2028f\u2029g"
        self.assertEqual(
            normalize_line_endings(text, LineEnding.CR),
            "a\rb\rc\rd\re\rf\rg",
        )

    def test_target_as_plain_string(self):
        self.assertEqual(
            normalize_line_endings("a\nb", "\r\n"),
            "a\r\nb",
        )

    def test_no_separators_unchanged(self):
        self.assertEqual(normalize_line_endings("hello", LineEnding.LF), "hello")

    def test_empty_string(self):
        self.assertEqual(normalize_line_endings("", LineEnding.LF), "")

    def test_rejects_non_str_text(self):
        with self.assertRaises(TypeError):
            normalize_line_endings(b"a\n", LineEnding.LF)  # type: ignore[arg-type]

    def test_rejects_non_str_target(self):
        with self.assertRaises(TypeError):
            normalize_line_endings("a\n", 123)  # type: ignore[arg-type]

    def test_preserves_non_separator_data(self):
        # Make sure ordinary characters are not altered.
        text = "  tab\there  "
        self.assertEqual(normalize_line_endings(text, LineEnding.LF), text)


class TestLineEndingNormalizer(unittest.TestCase):
    def test_basic_single_chunk(self):
        norm = LineEndingNormalizer(LineEnding.LF)
        out = norm.feed("a\r\nb")
        out += norm.flush()
        self.assertEqual(out, "a\nb")

    def test_crlf_split_across_chunks(self):
        norm = LineEndingNormalizer(LineEnding.LF)
        out = norm.feed("a\r")
        self.assertEqual(out, "a")  # CR held back, 'a' emitted
        out += norm.feed("\nb")
        out += norm.flush()
        self.assertEqual(out, "a\nb")

    def test_bare_cr_at_chunk_boundary(self):
        norm = LineEndingNormalizer(LineEnding.LF)
        out = norm.feed("a\r")
        self.assertEqual(out, "a")
        out += norm.feed("b")  # not \n, so the CR was bare
        out += norm.flush()
        self.assertEqual(out, "a\nb")

    def test_bare_cr_flushed_at_end(self):
        norm = LineEndingNormalizer(LineEnding.LF)
        out = norm.feed("a\r")
        out += norm.flush()
        self.assertEqual(out, "a\n")

    def test_unicode_separators_streaming(self):
        norm = LineEndingNormalizer(LineEnding.LF)
        out = norm.feed("a\u2028b\u2029c")
        out += norm.flush()
        self.assertEqual(out, "a\nb\nc")

    def test_multiple_chunks(self):
        norm = LineEndingNormalizer(LineEnding.CRLF)
        out = norm.feed("line1\n")
        out += norm.feed("line2\r")
        out += norm.feed("\nline3")
        out += norm.flush()
        self.assertEqual(out, "line1\r\nline2\r\nline3")

    def test_empty_chunks(self):
        norm = LineEndingNormalizer(LineEnding.LF)
        out = norm.feed("")
        out += norm.feed("a\n")
        out += norm.feed("")
        out += norm.flush()
        self.assertEqual(out, "a\n")

    def test_flush_after_flush_raises(self):
        norm = LineEndingNormalizer(LineEnding.LF)
        norm.feed("a")
        norm.flush()
        with self.assertRaises(ValueError):
            norm.flush()

    def test_feed_after_flush_raises(self):
        norm = LineEndingNormalizer(LineEnding.LF)
        norm.feed("a")
        norm.flush()
        with self.assertRaises(ValueError):
            norm.feed("b")

    def test_target_as_plain_string(self):
        norm = LineEndingNormalizer("\r\n")
        out = norm.feed("a\nb")
        out += norm.flush()
        self.assertEqual(out, "a\r\nb")

    def test_rejects_non_str_chunk(self):
        norm = LineEndingNormalizer(LineEnding.LF)
        with self.assertRaises(TypeError):
            norm.feed(b"a\n")  # type: ignore[arg-type]


class TestLineEndingEnum(unittest.TestCase):
    def test_members_compare_equal_to_literals(self):
        self.assertEqual(LineEnding.LF, "\n")
        self.assertEqual(LineEnding.CR, "\r")
        self.assertEqual(LineEnding.CRLF, "\r\n")
        self.assertEqual(LineEnding.NEL, "\u0085")
        self.assertEqual(LineEnding.LS, "\u2028")
        self.assertEqual(LineEnding.PS, "\u2029")


if __name__ == "__main__":
    unittest.main()
