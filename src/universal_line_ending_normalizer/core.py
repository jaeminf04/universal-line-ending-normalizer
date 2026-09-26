"""Detect and convert between CR, LF, CRLF, and Unicode line separators.

Supported line endings
----------------------
* ``CR``   — ``\r``   (classic Mac OS)
* ``LF``   — ``\n``   (Unix)
* ``CRLF`` — ``\r\n`` (Windows, network protocols)
* ``NEL``  — ``\u0085`` (Next Line, used by some IBM mainframe text)
* ``LS``   — ``\u2028`` (Unicode Line Separator)
* ``PS``   — ``\u2029`` (Unicode Paragraph Separator)

Design decisions
----------------

CRLF is treated as a single separator, not as CR followed by LF.  A naive
character-by-character scanner would count ``\r\n`` as two line breaks; this
module scans left-to-right and consumes the pair atomically when it appears.

The detector returns the set of *distinct* line-ending types found.  A document
that mixes ``\n`` and ``\r\n`` therefore reports both, rather than silently
picking one.  Callers who want a single "dominant" ending can inspect the set
themselves; the library does not guess, because any guess discards information
the caller may need.

``normalize_line_endings`` replaces every line separator with the requested
target.  It is a pure string transform; it does not touch trailing data that is
not a line separator.
"""

from __future__ import annotations

from enum import Enum
from typing import Set


class LineEnding(str, Enum):
    """The line-ending types this library recognises.

    Inherits ``str`` so members compare equal to their literal value, which is
    convenient for callers who want to pass a plain string such as ``"\n"``
    instead of ``LineEnding.LF``.
    """

    CR = "\r"
    LF = "\n"
    CRLF = "\r\n"
    NEL = "\u0085"
    LS = "\u2028"
    PS = "\u2029"


# Ordered so that multi-character endings (CRLF) are checked before their
# single-character prefixes (CR, LF).  The scanner relies on this ordering.
_SEPARATORS = (
    LineEnding.CRLF,
    LineEnding.CR,
    LineEnding.LF,
    LineEnding.NEL,
    LineEnding.LS,
    LineEnding.PS,
)


def detect_line_endings(text: str) -> Set[LineEnding]:
    """Return the set of distinct line-ending types present in *text*.

    An empty string or a string with no line separators returns an empty set.
    CRLF is reported as ``LineEnding.CRLF`` only; it does not also report
    ``LineEnding.CR`` and ``LineEnding.LF`` for the same two characters.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")

    found: Set[LineEnding] = set()
    i = 0
    n = len(text)
    while i < n:
        # Try the two-character CRLF first so it is consumed atomically.
        if text[i] == "\r" and i + 1 < n and text[i + 1] == "\n":
            found.add(LineEnding.CRLF)
            i += 2
            continue
        ch = text[i]
        matched = False
        # Skip CRLF here (already handled above); check the single-char endings.
        for sep in _SEPARATORS:
            if sep is LineEnding.CRLF:
                continue
            if ch == sep.value:
                found.add(sep)
                i += 1
                matched = True
                break
        if not matched:
            i += 1
    return found


def normalize_line_endings(text: str, target: "LineEnding | str") -> str:
    """Return *text* with every line separator replaced by *target*.

    *target* may be a :class:`LineEnding` or a plain string.  If a plain string
    is given and it matches a known ending value, the corresponding enum member
    is used; otherwise the string is used verbatim as the replacement.

    CRLF in the input is collapsed to a single *target*, not two.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")

    if isinstance(target, LineEnding):
        target_value = target.value
    elif isinstance(target, str):
        # Map a matching literal back to the enum for clarity, though the value
        # is the same either way.
        target_value = target
    else:
        raise TypeError("target must be a LineEnding or str")

    pieces: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        # CRLF first, as in detect.
        if text[i] == "\r" and i + 1 < n and text[i + 1] == "\n":
            pieces.append(target_value)
            i += 2
            continue
        ch = text[i]
        matched = False
        for sep in _SEPARATORS:
            if sep is LineEnding.CRLF:
                continue
            if ch == sep.value:
                pieces.append(target_value)
                i += 1
                matched = True
                break
        if not matched:
            pieces.append(ch)
            i += 1
    return "".join(pieces)


class LineEndingNormalizer:
    """Streaming normalizer for text that arrives in chunks.

    Some line separators are two characters wide (CRLF).  When a chunk ends
    between the CR and the LF, the normalizer must hold the CR back until the
    next chunk arrives, otherwise it would emit a premature line break.

    Usage::

        norm = LineEndingNormalizer(LineEnding.LF)
        out = norm.feed("hello\r")
        out += norm.feed("\nworld")
        out += norm.flush()

    ``flush`` must be called once after the final chunk to release any retained
    character.  After ``flush``, the normalizer is in a terminal state and must
    not be reused.
    """

    def __init__(self, target: "LineEnding | str") -> None:
        if isinstance(target, LineEnding):
            self._target = target.value
        elif isinstance(target, str):
            self._target = target
        else:
            raise TypeError("target must be a LineEnding or str")
        self._pending_cr = False
        self._closed = False

    def feed(self, chunk: str) -> str:
        """Process *chunk* and return the normalized output for this chunk.

        The returned string may be shorter than *chunk* if a CR at the end of
        the previous chunk turned out to be a bare CR (flushed here as the
        target) or if a CR at the end of this chunk is being held back.
        """
        if self._closed:
            raise ValueError("LineEndingNormalizer is closed")
        if not isinstance(chunk, str):
            raise TypeError("chunk must be a str")

        pieces: list[str] = []
        i = 0
        n = len(chunk)

        # Resolve a CR retained from the previous chunk.
        if self._pending_cr:
            if n > 0 and chunk[0] == "\n":
                # Completed CRLF.
                pieces.append(self._target)
                i = 1
            else:
                # Bare CR.
                pieces.append(self._target)
            self._pending_cr = False

        while i < n:
            ch = chunk[i]
            if ch == "\r":
                if i + 1 < n:
                    if chunk[i + 1] == "\n":
                        pieces.append(self._target)
                        i += 2
                    else:
                        # Bare CR.
                        pieces.append(self._target)
                        i += 1
                else:
                    # CR at the very end of the chunk: hold it back.
                    self._pending_cr = True
                    i += 1
                continue
            if ch == "\n":
                pieces.append(self._target)
                i += 1
                continue
            if ch == "\u0085":
                pieces.append(self._target)
                i += 1
                continue
            if ch == "\u2028":
                pieces.append(self._target)
                i += 1
                continue
            if ch == "\u2029":
                pieces.append(self._target)
                i += 1
                continue
            pieces.append(ch)
            i += 1

        return "".join(pieces)

    def flush(self) -> str:
        """Release any retained character and mark the normalizer as closed.

        Returns the final pending output (the target ending if a CR was held,
        otherwise an empty string).
        """
        if self._closed:
            raise ValueError("LineEndingNormalizer is already closed")
        self._closed = True
        if self._pending_cr:
            self._pending_cr = False
            return self._target
        return ""
