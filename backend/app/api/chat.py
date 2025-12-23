"""
Chat API endpoints for conversational AI interactions.

Provides both synchronous and streaming endpoints for processing user messages
through the multi-agent system with tool calling capabilities.
"""

import json
import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatRequest, ChatResponse
from app.models.database import User
from app.services.agent_service import AgentService
from app.core.security import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
) -> ChatResponse:
    """
    Process a chat message through the multi-agent system (synchronous).

    This endpoint receives user messages and routes them to specialized
    agents (scan, policy, ticket) based on intent. Returns the AI response
    along with any tool calls made and token usage statistics.

    Args:
        request: Chat request containing the message and conversation history.
        current_user: Authenticated user from JWT token.

    Returns:
        ChatResponse with AI response, tool calls, token usage, and trace URL.

    Raises:
        HTTPException: 401 if not authenticated, 500 if processing fails.
    """
    try:
        return AgentService.process_message(request, current_user.username)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
) -> EventSourceResponse:
    """
    Process a chat message with streaming response (Server-Sent Events).

    Streams tokens as they are generated for better UX. Also streams
    tool call notifications and final metadata.

    Event types:
    - token: Individual tokens as they're generated
    - tool_call: When a tool is invoked
    - metadata: Final token usage and trace URL
    - done: Stream complete signal

    Args:
        request: Chat request containing the message and conversation history.
        current_user: Authenticated user from JWT token.

    Returns:
        EventSourceResponse with streamed events.
    """
    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            async for event in AgentService.process_message_stream(
                request,
                current_user.username
            ):
                yield event
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())
