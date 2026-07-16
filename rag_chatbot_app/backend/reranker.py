"""
Cross-encoder reranking.

Hybrid search (BM25 + vector, see vectorstore.query) scores the query
and a chunk independently, then fuses the two scores - fast, and good
enough to build a candidate pool, but neither signal ever lets the
model actually attend across the query and the chunk together. A
cross-encoder does: the (query, chunk) pair is fed through the same
transformer jointly, so it can weigh how they relate to each other,
not just how similar their separate embeddings/keyword-overlap are.
That's meaningfully more accurate - and much slower per pair - which
is exactly why this reranks a ~15-chunk candidate pool instead of
searching the whole collection with it.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 - small (~80MB), free,
CPU-friendly, MS MARCO-trained. It's the standard first choice for
this in the sentence-transformers ecosystem, worth naming by model
card rather than "a reranker" if this comes up in an interview.
"""
import math
import os

from sentence_transformers import CrossEncoder

RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Lazy singleton: loaded on first call, not at import time, so
# importing this module (e.g. from a test, or a code path where
# ENABLE_RERANK=false) doesn't pay the ~80MB load cost for nothing.
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = CrossEncoder(RERANKER_MODEL_NAME)
    return _model


def rerank(query, chunks, score_key="rerank_score"):
    """
    Scores every chunk against the query with the cross-encoder and
    returns a new list sorted by that score, descending. Each chunk
    dict gets `score_key` added; all its existing fields (document_id,
    filename, the hybrid "_additional.score", etc.) are left as-is -
    this only adds a field and reorders, it doesn't replace anything.

    Raw cross-encoder outputs are unbounded logits, not a 0-1 score.
    They're passed through a sigmoid before storing - sigmoid is
    monotonic so the ranking itself is identical either way, but this
    keeps the stored score on a roughly 0-1 scale so a
    MIN_RERANK_SCORE-style threshold downstream stays interpretable
    as "how confident", the same way MIN_RELEVANCE_SCORE was for the
    hybrid score it's replacing in that role.
    """
    if not chunks:
        return chunks

    model = _get_model()
    pairs = [(query, c["content"]) for c in chunks]
    raw_scores = model.predict(pairs)

    for chunk, raw in zip(chunks, raw_scores):
        chunk[score_key] = 1 / (1 + math.exp(-float(raw)))

    return sorted(chunks, key=lambda c: c[score_key], reverse=True)