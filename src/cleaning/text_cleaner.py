"""
Text cleaning utilities for reviews.

Phase 1 deliverables:
    - clean_text(text)              normalize whitespace, remove URLs, etc.
    - count_emojis(text)             count emoji characters
    - strip_emojis(text)             remove emojis for downstream NLP
    - normalize_hebrew(text)         basic Hebrew normalization
    - extract_metadata(text)         exclamation/question marks, caps ratio
"""

import re
from typing import Dict

try:
    import emoji as emoji_lib
except ImportError:
    emoji_lib = None


_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Normalize whitespace and strip URLs from a review."""
    if not text:
        return ""
    text = _URL_PATTERN.sub(" ", text)
    text = _WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()


def count_emojis(text: str) -> int:
    """Count emoji characters in a string. Requires the emoji library."""
    if not text or emoji_lib is None:
        return 0
    return emoji_lib.emoji_count(text)


def strip_emojis(text: str) -> str:
    """Remove emoji characters from a string."""
    if not text or emoji_lib is None:
        return text
    return emoji_lib.replace_emoji(text, replace="")


def normalize_hebrew(text: str) -> str:
    """
    Normalize Hebrew text for downstream NLP.

    - Strips nikud (Unicode range U+0591..U+05C7).
    - Replaces Hebrew geresh (U+05F3) and gershayim (U+05F4) with ASCII apostrophe
      and double-quote, which the tokenizer handles more consistently.
    """
    if not text:
        return text

    cleaned = []
    for ch in text:
        code = ord(ch)
        if 0x0591 <= code <= 0x05C7:
            continue  # nikud or cantillation mark, skip
        if ch == "\u05F3":  # geresh
            cleaned.append("'")
        elif ch == "\u05F4":  # gershayim
            cleaned.append('"')
        else:
            cleaned.append(ch)
    return "".join(cleaned)


def extract_metadata(text: str) -> Dict:
    """Extract style indicators from a review."""
    if not text:
        return {
            "text_length": 0,
            "word_count": 0,
            "exclamation_count": 0,
            "question_count": 0,
            "all_caps_ratio": 0.0,
        }

    words = text.split()
    letters = [c for c in text if c.isalpha()]
    caps = [c for c in letters if c.isupper()]

    return {
        "text_length": len(text),
        "word_count": len(words),
        "exclamation_count": text.count("!"),
        "question_count": text.count("?"),
        "all_caps_ratio": (len(caps) / len(letters)) if letters else 0.0,
    }
