"""
Language detection for reviews.

Uses langdetect with a deterministic seed for reproducibility.
Maps low-confidence or short reviews to "unknown".
"""

from typing import Optional

try:
    from langdetect import detect, DetectorFactory, LangDetectException
    DetectorFactory.seed = 42
except ImportError:
    detect = None
    LangDetectException = Exception


MIN_LENGTH_FOR_DETECTION = 3


def detect_language(text: str) -> Optional[str]:
    """
    Return an ISO 639-1 language code, or 'unknown' if detection fails.

    Short texts (under MIN_LENGTH_FOR_DETECTION chars) return 'unknown'.
    """
    if detect is None:
        return None
    if not text or len(text.strip()) < MIN_LENGTH_FOR_DETECTION:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def is_hebrew(text: str) -> bool:
    """Quick check: does the text contain any Hebrew characters?"""
    if not text:
        return False
    return any("\u0590" <= ch <= "\u05FF" for ch in text)
