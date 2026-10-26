import logging

from lensor.clauses import CLAUSE_TYPES
from lensor.extract.extractor import VerifiedClause, extract_clauses
from lensor.extract.risk import risk_level_for, risk_reasons, risk_score
from lensor.vectorstore.base import ChunkHit
from tests.fakes import FakeLLMClient

TEXT = (
    "SUPPLY AGREEMENT. This Agreement renews automatically for one year. "
    "This Agreement is governed by the laws of Delaware."
)


def clause(name: str, found: bool = True, quotes: list[str] | None = None, risk="medium") -> dict:
    return {
        "clause_type": name,
        "found": found,
        "quotes": quotes or [],
        "summary": f"About {name}.",
        "risk_level": risk if found else None,
    }


async def test_extract_drops_unverified_quotes(caplog) -> None:
    llm = FakeLLMClient(
        json_results=[
            {
                "clauses": [
                    clause(
                        "Renewal Term",
                        quotes=[
                            "This Agreement renews automatically for one year.",
                            "The Supplier may renew at its sole option.",
                        ],
                    ),
                    clause("Governing Law", quotes=["The laws of Texas govern."]),
                ]
            }
        ]
    )

    with caplog.at_level(logging.WARNING):
        clauses, usage = await extract_clauses(TEXT, llm, "m")

    by_type = {c.clause_type: c for c in clauses}
    renewal = by_type["Renewal Term"]
    assert renewal.found is True
    assert renewal.quotes == ["This Agreement renews automatically for one year."]
    assert renewal.spans == [(18, 67)]
    law = by_type["Governing Law"]
    assert (law.found, law.quotes, law.spans, law.risk_level, law.summary) == (
        False,
        [],
        [],
        None,
        "",
    )
    assert "dropped" in caplog.text.lower()
    assert usage.prompt_tokens == 100


async def test_extract_normalizes_clause_types() -> None:
    llm = FakeLLMClient(
        json_results=[
            {
                "clauses": [
                    clause("Price Restrictions", quotes=["SUPPLY AGREEMENT."]),
                    clause("governing law", quotes=["governed by the laws of Delaware"]),
                    clause("Governing Law", quotes=["SUPPLY AGREEMENT."]),
                    clause("Non-Compete", found=False),
                ]
            }
        ]
    )

    clauses, _ = await extract_clauses(TEXT, llm, "m")

    assert [c.clause_type for c in clauses] == list(CLAUSE_TYPES)
    law = clauses[CLAUSE_TYPES.index("Governing Law")]
    assert law.quotes == ["governed by the laws of Delaware"]
    assert all(not c.found for c in clauses if c.clause_type != "Governing Law")


async def test_extract_retrieval_mode_sends_chunks_not_full_text() -> None:
    queries: list[str] = []

    async def retrieve(query: str) -> list[ChunkHit]:
        queries.append(query)
        return [ChunkHit(1, 1, 18, 67, TEXT[18:67], 0.9)]

    llm = FakeLLMClient(json_results=[{"clauses": [clause("Renewal Term", quotes=[TEXT[18:67]])]}])

    clauses, _ = await extract_clauses(TEXT, llm, "m", mode="retrieval", retrieve=retrieve)

    assert len(queries) == len(CLAUSE_TYPES)
    prompt = "\n".join(m["content"] for m in llm.json_calls[0]["messages"])
    assert "governed by the laws of Delaware" not in prompt
    assert clauses[CLAUSE_TYPES.index("Renewal Term")].spans == [(18, 67)]


def found(*names: str) -> list[VerifiedClause]:
    return [
        VerifiedClause(name, name in names, [(0, 1)] if name in names else [], [], "", None)
        for name in CLAUSE_TYPES
    ]


def test_risk_score() -> None:
    clauses = found("Uncapped Liability", "Renewal Term", "Cap on Liability")

    reasons = risk_reasons(clauses)

    assert risk_score(clauses) == 45
    assert risk_level_for(45) == "medium"
    assert [(r.clause_type, r.points) for r in reasons] == [
        ("Uncapped Liability", 30),
        ("Renewal Term", 15),
    ]


def test_risk_score_bounds() -> None:
    worst = found(
        "Uncapped Liability",
        "Renewal Term",
        "Non-Compete",
        "Change of Control",
        "Termination for Convenience",
    )
    assert risk_score(worst) == 100
    assert risk_level_for(100) == "high"
    assert risk_level_for(60) == "high"
    assert risk_level_for(59) == "medium"
    assert risk_level_for(29) == "low"
    assert risk_score(found("Cap on Liability")) == 0
