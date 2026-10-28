"""OpenRouter client for chat, structured output, and embeddings."""

import copy
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import httpx2
import openai
from pydantic import BaseModel, ValidationError

from lensor.config import Settings

T = TypeVar("T", bound=BaseModel)

# OpenRouter routing: only providers that support every parameter and do not keep the data.
# Of those, use the cheapest provider. Some providers charge 2 to 4 times the list price.
CHAT_PROVIDER = {"require_parameters": True, "data_collection": "deny", "sort": "price"}
# Hidden reasoning can be 10 times longer than the answer. Settings can turn it off.
NO_REASONING = {"enabled": False}
EMBED_PROVIDER = {"data_collection": "deny"}


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None


LLMEvent = TextDelta | ToolCall | Usage


class LLMError(Exception):
    """An LLM or embeddings call failed. The message is safe to show to the user."""


class LLMClient(Protocol):
    async def complete_json(
        self, model: str, messages: list[dict], schema: type[T]
    ) -> tuple[T, Usage]: ...

    def stream_chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
        tool_choice: str = "auto",
    ) -> AsyncIterator[LLMEvent]: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Make a Pydantic JSON schema valid for strict structured output.

    Strict mode needs `additionalProperties: false` and every property in `required`.
    """
    schema = copy.deepcopy(model.model_json_schema())

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            node.pop("default", None)
            node.pop("title", None)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return schema


def _usage(raw: Any) -> Usage:
    if raw is None:
        return Usage(0, 0, None)
    extra = getattr(raw, "model_extra", None) or {}
    cost = extra.get("cost")
    return Usage(
        prompt_tokens=raw.prompt_tokens or 0,
        completion_tokens=raw.completion_tokens or 0,
        cost_usd=float(cost) if cost is not None else None,
    )


def _error_message(exc: openai.OpenAIError) -> str:
    if isinstance(exc, openai.APIStatusError):
        return f"OpenRouter error {exc.status_code}: {exc.message}"
    return f"OpenRouter request failed: {exc}"


class OpenRouterClient:
    def __init__(
        self,
        settings: Settings,
        max_retries: int = 2,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = openai.AsyncOpenAI(
            api_key=settings.openrouter_api_key or "missing-key",
            base_url=settings.openrouter_base_url,
            max_retries=max_retries,
            http_client=http_client,
        )

    def _json_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"provider": CHAT_PROVIDER, "usage": {"include": True}}
        if not self._settings.llm_extract_reasoning:
            body["reasoning"] = NO_REASONING
        return body

    async def complete_json(
        self, model: str, messages: list[dict], schema: type[T]
    ) -> tuple[T, Usage]:
        try:
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=model,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "strict": True,
                        "schema": strict_schema(schema),
                    },
                },
                extra_body=self._json_body(),
            )
        except openai.OpenAIError as exc:
            raise LLMError(_error_message(exc)) from exc
        if not response.choices:
            raise LLMError("OpenRouter returned no choices")
        content = response.choices[0].message.content or ""
        try:
            result = schema.model_validate_json(content)
        except ValidationError as exc:
            raise LLMError(
                f"The model returned JSON that does not match the schema: {exc}"
            ) from exc
        return result, _usage(response.usage)

    async def stream_chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
        tool_choice: str = "auto",
    ) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, Any] = {}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        # Collect the tool-call fragments by index. Send each call when the stream ends.
        calls: dict[int, dict[str, str]] = {}
        usage: Usage | None = None
        try:
            stream = await self._client.chat.completions.create(  # type: ignore[call-overload]
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                extra_body={"provider": CHAT_PROVIDER, "usage": {"include": True}},
                **kwargs,
            )
            async for chunk in stream:
                if chunk.usage is not None:
                    usage = _usage(chunk.usage)
                for choice in chunk.choices:
                    delta = choice.delta
                    if delta.content:
                        yield TextDelta(delta.content)
                    for part in delta.tool_calls or []:
                        call = calls.setdefault(part.index, {"id": "", "name": "", "arguments": ""})
                        if part.id:
                            call["id"] = part.id
                        if part.function and part.function.name:
                            call["name"] = part.function.name
                        if part.function and part.function.arguments:
                            call["arguments"] += part.function.arguments
        except openai.OpenAIError as exc:
            raise LLMError(_error_message(exc)) from exc
        for index in sorted(calls):
            call = calls[index]
            yield ToolCall(id=call["id"], name=call["name"], arguments=call["arguments"])
        if usage is not None:
            yield usage

    async def embed(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            try:
                response = await self._client.embeddings.create(
                    model=self._settings.embed_model,
                    input=batch,
                    extra_body={"provider": EMBED_PROVIDER},
                )
            except openai.OpenAIError as exc:
                raise LLMError(_error_message(exc)) from exc
            items = sorted(response.data, key=lambda item: item.index)
            if len(items) != len(batch):
                raise LLMError("OpenRouter returned the wrong number of embeddings")
            vectors.extend(item.embedding for item in items)
        return vectors


def parse_arguments(raw: str) -> dict[str, Any]:
    """Parse tool-call arguments. Bad JSON gives an empty dict."""
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
