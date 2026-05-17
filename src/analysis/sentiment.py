"""
Sentiment analysis for Hebrew reviews using DictaBERT.

DictaBERT is a Hebrew BERT model from Dicta (https://huggingface.co/dicta-il).
We use the 'dicta-il/dictabert-sentiment' model or compute embeddings from
'dicta-il/dictabert' for downstream classification.

Functions:
    load_sentiment_pipeline()    -> transformers pipeline
    classify_review(text)        -> (label, score)
    classify_batch(texts)        -> list of (label, score) tuples
"""

from typing import List, Tuple, Optional

_pipeline = None  # Cached pipeline instance


def load_sentiment_pipeline():
    """Load and cache the DictaBERT sentiment pipeline."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    try:
        from transformers import pipeline
    except ImportError as e:
        raise ImportError(
            "transformers is required for sentiment analysis. "
            "Run: pip install -r requirements.txt"
        ) from e

    _pipeline = pipeline(
        task="text-classification",
        model="dicta-il/dictabert-sentiment",
        tokenizer="dicta-il/dictabert-sentiment",
    )
    return _pipeline


def classify_review(text: str) -> Tuple[Optional[str], Optional[float]]:
    """Classify a single review. Returns (label, score) or (None, None)."""
    if not text or not text.strip():
        return (None, None)
    pipe = load_sentiment_pipeline()
    result = pipe(text[:512])[0]  # truncate to BERT max length
    return (result["label"], result["score"])


def classify_batch(texts: List[str], batch_size: int = 32) -> List[Tuple]:
    """Classify many reviews. Returns list of (label, score) tuples."""
    pipe = load_sentiment_pipeline()
    truncated = [(t or "")[:512] for t in texts]
    results = pipe(truncated, batch_size=batch_size)
    return [(r["label"], r["score"]) for r in results]
