"""Test doubles. No test calls OpenRouter."""

import hashlib
from collections.abc import AsyncIterator, Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from lensor.llm.client import LLMError, LLMEvent, Usage

T = TypeVar("T", bound=BaseModel)

JsonScript = BaseModel | dict | Exception | Callable[[list[dict]], BaseModel | dict]


def fake_vector(text: str, dim: int = 1536) -> list[float]:
    """A fixed vector for a text, so that the same text gives the same vector."""
    digest = hashlib.sha256(text.encode()).digest()
    return [((digest[i % len(digest)] + i) % 251) / 251.0 + 0.001 for i in range(dim)]


class FakeLLMClient:
    """Returns scripted results in order.

    `json_results` items are used one per `complete_json` call. When one item is left, it is
    used again. An item can be a model, a dict, an exception to raise, or a callable that
    takes the messages. `event_scripts` work the same way for `stream_chat`.
    """

    def __init__(
        self,
        json_results: list[JsonScript] | None = None,
        event_scripts: list[list[LLMEvent] | Exception] | None = None,
        dim: int = 1536,
        usage: Usage | None = None,
        embed_error: Exception | None = None,
    ) -> None:
        self.json_results = list(json_results or [])
        self.event_scripts = list(event_scripts or [])
        self.dim = dim
        self.usage = usage or Usage(100, 20, 0.001)
        self.embed_error = embed_error
        self.json_calls: list[dict[str, Any]] = []
        self.chat_calls: list[dict[str, Any]] = []
        self.embed_calls: list[list[str]] = []

    @staticmethod
    def _next(queue: list) -> Any:
        if not queue:
            raise LLMError("FakeLLMClient has no scripted result")
        return queue.pop(0) if len(queue) > 1 else queue[0]

    async def complete_json(
        self, model: str, messages: list[dict], schema: type[T]
    ) -> tuple[T, Usage]:
        self.json_calls.append({"model": model, "messages": messages, "schema": schema})
        item = self._next(self.json_results)
        if isinstance(item, Exception):
            raise item
        if callable(item) and not isinstance(item, BaseModel):
            item = item(messages)
        if isinstance(item, dict):
            item = schema.model_validate(item)
        return schema.model_validate(item.model_dump()), self.usage

    async def stream_chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
        tool_choice: str = "auto",
    ) -> AsyncIterator[LLMEvent]:
        self.chat_calls.append(
            {"model": model, "messages": list(messages), "tools": tools, "tool_choice": tool_choice}
        )
        script = self._next(self.event_scripts)
        if isinstance(script, Exception):
            raise script
        for event in script:
            yield event

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        if self.embed_error is not None:
            raise self.embed_error
        return [fake_vector(t, self.dim) for t in texts]
