from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from lensor.agent.loop import run_agent
from lensor.agent.tools import ToolContext
from lensor.config import get_settings
from lensor.deps import LLMDep, SessionFactoryDep, SettingsDep, StoreDep
from lensor.sse import SSE_HEADERS, sse_event

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
RATE_LIMIT = get_settings().chat_rate_limit


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)

    @field_validator("messages")
    @classmethod
    def _last_is_user(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        if messages[-1].role != "user":
            raise ValueError("The last message must come from the user.")
        return messages


@router.post("/api/chat")
@limiter.limit(lambda: RATE_LIMIT)
async def chat(
    request: Request,
    body: ChatRequest,
    session_factory: SessionFactoryDep,
    llm: LLMDep,
    store: StoreDep,
    settings: SettingsDep,
) -> StreamingResponse:
    ctx = ToolContext(session_factory, store, llm)
    messages = [m.model_dump() for m in body.messages]

    async def events() -> AsyncIterator[str]:
        async for event in run_agent(
            messages, ctx, llm, settings.llm_model_agent, settings.agent_max_tool_calls
        ):
            yield sse_event(event)

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)
