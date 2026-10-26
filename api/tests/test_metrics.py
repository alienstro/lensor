import pytest

from lensor.eval.metrics import prf, recall_at_k, score_contract, span_jaccard
from lensor.vectorstore.base import ChunkHit


def test_span_jaccard() -> None:
    assert span_jaccard((0, 10), (5, 15)) == pytest.approx(5 / 15)
    assert span_jaccard((0, 10), (0, 10)) == 1.0
    assert span_jaccard((0, 5), (5, 10)) == 0.0
    assert span_jaccard((3, 3), (3, 3)) == 0.0


def test_score_contract_cases() -> None:
    assert score_contract([(0, 10)], [(0, 9)]) == ["tp"]
    assert score_contract([(0, 10)], []) == ["fp"]
    assert score_contract([], [(0, 10)]) == ["fn"]
    assert score_contract([], []) == ["tn"]
    # A prediction that misses the labels is a false positive and a false negative.
    assert score_contract([(50, 60)], [(0, 10)]) == ["fp", "fn"]
    # One match is enough when there are several spans.
    assert score_contract([(50, 60), (0, 10)], [(0, 10), (90, 99)]) == ["tp"]


def test_prf_zero_safe() -> None:
    assert prf(0, 0, 0) == (0.0, 0.0, 0.0)
    precision, recall, f1 = prf(3, 1, 2)
    assert (precision, recall) == (0.75, 0.6)
    assert f1 == pytest.approx(2 * 0.75 * 0.6 / 1.35)


def test_recall_at_k() -> None:
    hits = [ChunkHit(1, 1, 100, 200, "t", 0.9), ChunkHit(2, 1, 300, 400, "t", 0.8)]
    assert recall_at_k(hits, [(150, 160)]) == 1.0
    assert recall_at_k(hits, [(0, 50)]) == 0.0
    assert recall_at_k(hits, [(200, 300)]) == 0.0
