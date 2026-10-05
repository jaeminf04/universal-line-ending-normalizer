# universal-line-ending-normalizer

Detects and converts between CR, LF, CRLF, and the Unicode line separators (NEL, LS, PS) on Python strings.

```python
from universal_line_ending_normalizer import (
    LineEnding,
    detect_line_endings,
    normalize_line_endings,
    LineEndingNormalizer,
)

# Detect which line endings are present
endings = detect_line_endings("hello\r\nworld\n")  # {LineEnding.CRLF, LineEnding.LF}

# Normalize everything to LF
print(normalize_line_endings("hello\r\nworld\r", LineEnding.LF))  # hello\nworld\n
# Streaming use (handles CRLF split across chunk boundaries)
norm = LineEndingNormalizer(LineEnding.LF)
out = norm.feed("hello\r")
out += norm.feed("\nworld")
out += norm.flush()
print(repr(out))  # 'hello\nworld'
```

## Why this exists

Text arrives with mixed line endings: a file edited on Windows, a patch from a Unix system, a protocol that mandates CRLF. Most normalizers only handle CR, LF, and CRLF. This one also covers the Unicode separators `NEL` (`\u0085`), `LS` (`\u2028`), and `PS` (`\u2029`), which appear in some mainframe exports and in text that round-tripped through XML or JSON.

The trade-off: the detector returns the **set** of distinct endings found, not a single "dominant" ending. Any guess discards information the caller may need. If you want the dominant ending, inspect the set yourself.

## The awkward edge

CRLF is two characters. When text arrives in chunks and a chunk ends with `\r` but the next chunk starts with `\n`, that is a single CRLF separator, not a bare CR followed by a bare LF. `LineEndingNormalizer` holds the trailing `\r` back until the next `feed` call (or `flush`) resolves it. You **must** call `flush` once after the final chunk; otherwise a trailing bare CR is silently dropped.

## API

- `LineEnding` — `str` enum with members `CR`, `LF`, `CRLF`, `NEL`, `LS`, `PS`. Members compare equal to their literal string value.
- `detect_line_endings(text: str) -> set[LineEnding]` — returns the set of distinct line-ending types found. CRLF is reported as `CRLF` only, not also as `CR` and `LF`.
- `normalize_line_endings(text: str, target: LineEnding | str) -> str` — replaces every line separator with `target`.
- `LineEndingNormalizer(target)` — streaming normalizer with `.feed(chunk) -> str` and `.flush() -> str`. After `flush`, the instance is closed and must not be reused.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

## Limitations

Values are coerced to floats, so very large integers lose precision. If you need
exact integer aggregates over a window, this is the wrong tool.

