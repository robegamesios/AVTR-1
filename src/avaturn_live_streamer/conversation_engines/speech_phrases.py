"""Keep complete sentences together for natural Chatterbox phrasing."""

import re

_ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "st.",
    "jr.",
    "sr.",
    "vs.",
    "etc.",
    "e.g.",
    "i.e.",
}
_SENTENCE_END = re.compile(r"""[.!?]+["'\u201d\u2019)\]]*(?=\s+\S)""")


def phrase_boundary(text: str) -> int | None:
    # Require the next word before treating punctuation as a sentence end.
    # A trailing period might still become a decimal or abbreviation in the
    # next model delta. The final remainder is flushed when generation ends.
    for boundary in _SENTENCE_END.finditer(text):
        prefix = text[: boundary.end()].rstrip("\"\u201d\u2019')]").strip()
        word = prefix.rsplit(maxsplit=1)[-1].casefold()
        if word in _ABBREVIATIONS or re.fullmatch(r"(?:[a-z]\.)+", word):
            continue
        if boundary.end() >= 16:
            return boundary.end()
    return None
