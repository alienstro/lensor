import asyncio
import json

import pytest

from lensor.clauses import CLAUSE_TYPES
from lensor.models import ClauseExtraction, Contract
from lensor.routes import contracts as contracts_route
from lensor.sse import sse_event

pytestmark = pytest.mark.db

TEXT = "SUPPLY AGREEMENT. This Agreement renews automatically for one year. Fraud is not capped."


def test_sse_event_format() -> None:
    assert sse_event({"a": 1}) == 'data: {"a": 1}\n\n'
    assert sse_event({"a": 1}, event="status") == 'event: status\ndata: {"a": 1}\n\n'


async def test_upload_rejects_bad_files(api, monkeypatch) -> None:
    monkeypatch.setattr(contracts_route, "MAX_UPLOAD_BYTES", 100)
    cases = [
        (("deal.docx", b"PK..."), 415),
        (("big.pdf", b"x" * 101), 413),
        (("empty.txt", b""), 400),
    ]
    for (name, data), status in cases:
        response = await api.post("/api/contracts", files={"file": (name, data)})
        assert response.status_code == status, name
        assert response.json()["detail"]


async def test_upload_starts_pipeline(api, session_factory) -> None:
    api.fake_llm.json_results = [
        {
            "clauses": [
                {
                    "clause_type": "Renewal Term",
                    "found": True,
                    "quotes": ["This Agreement renews automatically for one year."],
                    "summary": "Renews each year.",
                    "risk_level": "medium",
                }
            ]
        },
        {"overview": "A supply deal."},
    ]

    response = await api.post("/api/contracts", files={"file": ("acme_supply.txt", TEXT.encode())})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    async with session_factory() as session:
        contract = await session.get(Contract, body["id"])
        assert contract is not None
        assert (contract.title, contract.source, contract.status) == (
            "Acme Supply",
            "upload",
            "ready",
        )


async def seed(session_factory) -> tuple[int, int]:
    async with session_factory() as session:
        risky = Contract(title="Risky", source="cuad", text=TEXT, status="ready", risk_score=60)
        calm = Contract(title="Calm", source="cuad", text="x", status="ready", risk_score=15)
        session.add_all([calm, risky])
        await session.flush()
        for name in CLAUSE_TYPES:
            session.add(
                ClauseExtraction(
                    contract_id=calm.id,
                    clause_type=name,
                    found=False,
                    summary="",
                    model="m",
                    prompt_version=1,
                )
            )
        session.add_all(
            [
                ClauseExtraction(
                    contract_id=risky.id,
                    clause_type="Renewal Term",
                    found=True,
                    quote="This Agreement renews automatically for one year.",
                    start_char=18,
                    end_char=67,
                    summary="Renews.",
                    risk_level="medium",
                    model="m",
                    prompt_version=1,
                ),
                ClauseExtraction(
                    contract_id=risky.id,
                    clause_type="Uncapped Liability",
                    found=True,
                    quote="Fraud is not capped.",
                    start_char=68,
                    end_char=88,
                    summary="No cap.",
                    risk_level="high",
                    model="m",
                    prompt_version=1,
                ),
            ]
        )
        await session.commit()
        return risky.id, calm.id


async def test_list_and_get_contract(api, session_factory) -> None:
    risky_id, _ = await seed(session_factory)

    listing = (await api.get("/api/contracts")).json()

    assert [c["title"] for c in listing] == ["Risky", "Calm"]
    first = listing[0]
    assert (first["risk_score"], first["risk_level"]) == (60, "high")
    assert [r["clause_type"] for r in first["reasons"]] == [
        "Uncapped Liability",
        "Cap on Liability",
        "Renewal Term",
    ]
    assert "text" not in first

    detail = (await api.get(f"/api/contracts/{risky_id}")).json()
    assert detail["text"] == TEXT
    assert [c["clause_type"] for c in detail["clauses"]] == list(CLAUSE_TYPES)
    renewal = detail["clauses"][1]
    assert renewal == {
        "clause_type": "Renewal Term",
        "found": True,
        "quotes": ["This Agreement renews automatically for one year."],
        "spans": [[18, 67]],
        "summary": "Renews.",
        "risk_level": "medium",
    }
    assert detail["clauses"][0]["found"] is False
    assert (await api.get("/api/contracts/999999")).status_code == 404


async def test_status_stream_ends_on_ready(api, session_factory, monkeypatch) -> None:
    monkeypatch.setattr(contracts_route, "STATUS_POLL_SECONDS", 0.01)
    async with session_factory() as session:
        contract = Contract(title="T", source="upload", text="", status="extracting")
        session.add(contract)
        await session.commit()
        contract_id = contract.id

    async def finish() -> None:
        await asyncio.sleep(0.1)
        async with session_factory() as session:
            row = await session.get(Contract, contract_id)
            assert row is not None
            row.status = "ready"
            await session.commit()

    task = asyncio.create_task(finish())
    response = await api.get(f"/api/contracts/{contract_id}/status")
    await task

    assert response.headers["content-type"].startswith("text/event-stream")
    events = [
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [e["status"] for e in events] == ["extracting", "ready"]
