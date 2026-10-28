"""Metrics for the CUAD evaluation. A span is a (start, end) character range."""

from typing import Literal

from lensor.vectorstore.base import ChunkHit

Span = tuple[int, int]
Outcome = Literal["tp", "fp", "fn", "tn"]

MATCH_THRESHOLD = 0.5


def span_jaccard(a: Span, b: Span) -> float:
    overlap = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = (a[1] - a[0]) + (b[1] - b[0]) - overlap
    return overlap / union if union > 0 else 0.0


def score_contract(
    pred: list[Span], labels: list[Span], threshold: float = MATCH_THRESHOLD
) -> list[Outcome]:
    """Score one clause type in one contract.

    A prediction that misses existing labels counts as both "fp" and "fn".
    """
    if not pred and not labels:
        return ["tn"]
    if not pred:
        return ["fn"]
    if not labels:
        return ["fp"]
    if any(span_jaccard(p, label) >= threshold for p in pred for label in labels):
        return ["tp"]
    return ["fp", "fn"]


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def recall_at_k(hits: list[ChunkHit], labels: list[Span]) -> float:
    """1.0 when a retrieved chunk overlaps a label span, else 0.0."""
    for hit in hits:
        for start, end in labels:
            if hit.start_char < end and start < hit.end_char:
                return 1.0
    return 0.0
