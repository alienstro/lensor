import json
from collections.abc import Callable

import httpx2 as httpx
import pytest
from pydantic import BaseModel

from lensor.config import Settings
from lensor.llm.client import LLMError, OpenRouterClient

BASE = "https://openrouter.ai/api/v1"


class Answer(BaseModel):
    value: str


class Recorder:
    """A mock transport. It records each request, so no test reaches the network."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)


def make_client(recorder: Recorder, **settings: object) -> OpenRouterClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(recorder))
    return OpenRouterClient(
        Settings(openrouter_api_key="test-key", **settings),  # type: ignore[arg-type]
        max_retries=0,
        http_client=http,
    )


def json_reply(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "r1",
            "object": "chat.completion",
            "created": 0,
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"value": "ok"}'},
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
                "cost": 0.0001,
            },
        },
    )


async def test_complete_json_sends_provider_prefs() -> None:
    route = Recorder(json_reply)
    result, usage = await make_client(route).complete_json(
        "m", [{"role": "user", "content": "hi"}], Answer
    )
    assert str(route.requests[-1].url) == f"{BASE}/chat/completions"
    body = json.loads(route.requests[-1].content)
    assert body["provider"] == {
        "require_parameters": True,
        "data_collection": "deny",
        "sort": "price",
    }
    assert "reasoning" not in body
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert result == Answer(value="ok")
    assert (usage.prompt_tokens, usage.completion_tokens, usage.cost_usd) == (10, 2, 0.0001)


async def test_complete_json_turns_reasoning_off_when_disabled() -> None:
    route = Recorder(json_reply)
    await make_client(route, llm_extract_reasoning=False).complete_json(
        "m", [{"role": "user", "content": "hi"}], Answer
    )
    body = json.loads(route.requests[-1].content)
    assert body["reasoning"] == {"enabled": False}


async def test_embed_batches_and_order() -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["provider"] == {"data_collection": "deny"}
        texts = body["input"]
        # Return the items in reverse order, as an API may do.
        data = [
            {"object": "embedding", "index": i, "embedding": [float(len(t)), float(i)]}
            for i, t in reversed(list(enumerate(texts)))
        ]
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": data,
                "model": "e",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    route = Recorder(reply)
    texts = ["a" * n for n in range(1, 6)]
    vectors = await make_client(route).embed(texts, batch_size=2)
    assert len(route.requests) == 3
    assert str(route.requests[0].url) == f"{BASE}/embeddings"
    assert [v[0] for v in vectors] == [1.0, 2.0, 3.0, 4.0, 5.0]


async def test_http_error_raises_llm_error() -> None:
    route = Recorder(
        lambda request: httpx.Response(
            429, json={"error": {"message": "rate limited", "code": 429}}
        )
    )
    with pytest.raises(LLMError, match="429"):
        await make_client(route).complete_json("m", [{"role": "user", "content": "hi"}], Answer)


async def test_stream_chat_joins_tool_call_deltas() -> None:
    chunks = [
        {"choices": [{"index": 0, "delta": {"content": "Hel"}}]},
        {"choices": [{"index": 0, "delta": {"content": "lo"}}]},
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "t1",
                                "type": "function",
                                "function": {"name": "search_clauses", "arguments": '{"query":'},
                            }
                        ]
                    },
                }
            ]
        },
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [{"index": 0, "function": {"arguments": ' "renewal"}'}}]
                    },
                }
            ]
        },
        {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}},
    ]
    stream = (
        "".join(
            "data: "
            + json.dumps(
                {"id": "s", "object": "chat.completion.chunk", "created": 0, "model": "m", **c}
            )
            + "\n\n"
            for c in chunks
        )
        + "data: [DONE]\n\n"
    )
    route = Recorder(
        lambda request: httpx.Response(
            200, text=stream, headers={"content-type": "text/event-stream"}
        )
    )
    events = [
        e
        async for e in make_client(route).stream_chat(
            "m", [{"role": "user", "content": "x"}], tools=[]
        )
    ]
    kinds = [type(e).__name__ for e in events]
    assert kinds == ["TextDelta", "TextDelta", "ToolCall", "Usage"]
    call = events[2]
    assert (call.id, call.name, call.arguments) == ("t1", "search_clauses", '{"query": "renewal"}')
