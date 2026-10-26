import json

import pytest

from lensor.agent.loop import run_agent
from lensor.agent.tools import ToolContext
from lensor.llm.client import LLMError, TextDelta, ToolCall, Usage
from lensor.models import ClauseExtraction, Contract
from lensor.routes import chat as chat_route
from lensor.vectorstore.pgvector_store import PgVectorStore
from tests.fakes import FakeLLMClient

QUESTION = [{"role": "user", "content": "Which contracts renew by themselves?"}]


async def collect(llm: FakeLLMClient, session_factory, max_tool_calls: int = 8) -> list[dict]:
    ctx = ToolContext(session_factory, PgVectorStore(session_factory), llm)
    return [e async for e in run_agent(QUESTION, ctx, llm, "m", max_tool_calls=max_tool_calls)]


@pytest.mark.db
async def test_agent_runs_tool_then_answers(session_factory) -> None:
    async with session_factory() as session:
        contract = Contract(title="Deal", source="cuad", text="x" * 50, status="ready")
        session.add(contract)
        await session.flush()
        session.add(
            ClauseExtraction(
                contract_id=contract.id,
                clause_type="Renewal Term",
                found=True,
                quote="x" * 10,
                start_char=0,
                end_char=10,
                summary="s",
                risk_level="low",
                model="m",
                prompt_version=1,
            )
        )
        await session.commit()
        cid = contract.id
    call = ToolCall("t1", "get_contract_summary", f'{{"contract_id": {cid}}}')
    llm = FakeLLMClient(
        event_scripts=[
            [call, Usage(1, 1, None)],
            [TextDelta("Deal renews "), TextDelta(f"[c:{cid}:0-10].")],
        ]
    )

    events = await collect(llm, session_factory)

    assert [e["type"] for e in events] == [
        "tool_call",
        "tool_result",
        "token",
        "token",
        "citations",
        "done",
    ]
    assert events[0]["name"] == "get_contract_summary"
    assert events[0]["args"] == {"contract_id": cid}
    assert events[1] == {
        "type": "tool_result",
        "id": "t1",
        "name": "get_contract_summary",
        "ok": True,
    }
    assert events[4]["items"][0]["verified"] is True
    second = llm.chat_calls[1]["messages"]
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"][0]["id"] == "t1"
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "t1"


@pytest.mark.db
async def test_agent_stops_at_tool_limit(session_factory) -> None:
    call = ToolCall("t", "get_contract_summary", '{"contract_id": 1}')
    llm = FakeLLMClient(event_scripts=[[call]])

    events = await collect(llm, session_factory, max_tool_calls=3)

    assert [e["type"] for e in events].count("tool_call") == 3
    assert events[-1]["type"] == "done"
    assert llm.chat_calls[-1]["tool_choice"] == "none"
    assert all(c["tool_choice"] == "auto" for c in llm.chat_calls[:-1])


@pytest.mark.db
async def test_agent_llm_error_event(session_factory) -> None:
    llm = FakeLLMClient(event_scripts=[LLMError("OpenRouter error 429: rate limited")])

    events = await collect(llm, session_factory)

    assert events == [{"type": "error", "message": "OpenRouter error 429: rate limited"}]


@pytest.mark.db
async def test_agent_bad_tool_arguments_do_not_crash(session_factory) -> None:
    llm = FakeLLMClient(
        event_scripts=[[ToolCall("t1", "compare_clauses", "{not json")], [TextDelta("Sorry.")]]
    )

    events = await collect(llm, session_factory)

    assert events[1] == {"type": "tool_result", "id": "t1", "name": "compare_clauses", "ok": False}
    assert events[-1]["type"] == "done"


@pytest.mark.db
async def test_chat_route_streams_sse(api) -> None:
    api.fake_llm.event_scripts = [[TextDelta("No contract has that.")]]

    response = await api.post("/api/chat", json={"messages": QUESTION})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert [e["type"] for e in events] == ["token", "citations", "done"]
    bad = await api.post("/api/chat", json={"messages": [{"role": "system", "content": "x"}]})
    assert bad.status_code == 422


@pytest.mark.db
async def test_chat_rate_limit(api, monkeypatch) -> None:
    monkeypatch.setattr(chat_route, "RATE_LIMIT", "2/minute")
    chat_route.limiter.reset()
    api.fake_llm.event_scripts = [[TextDelta("ok")]]

    codes = [
        (await api.post("/api/chat", json={"messages": QUESTION})).status_code for _ in range(3)
    ]

    chat_route.limiter.reset()
    assert codes == [200, 200, 429]


@pytest.mark.db
async def test_agent_marks_offsets_not_from_tools_unverified(session_factory) -> None:
    async with session_factory() as session:
        contract = Contract(title="Deal", source="cuad", text="x" * 50, status="ready")
        session.add(contract)
        await session.commit()
        cid = contract.id
    llm = FakeLLMClient(event_scripts=[[TextDelta(f"It renews [c:{cid}:0-10].")]])

    events = await collect(llm, session_factory)

    citations = next(e for e in events if e["type"] == "citations")["items"]
    assert citations[0]["verified"] is False
