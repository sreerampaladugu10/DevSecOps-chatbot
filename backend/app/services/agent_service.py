"""
Agent service for orchestrating multi-agent chat interactions.

This module provides the service layer between the API and the agent system,
handling message processing, response formatting, tracing, and input validation.
"""

import json
from typing import Optional, AsyncGenerator

from langsmith import traceable

from app.agents.supervisor import run_agent, run_agent_stream
from app.models.schemas import ChatRequest, ChatResponse, ToolCall
from app.core.utils import ContentGuardrails


class AgentService:
    """
    Service class for processing chat messages through the multi-agent system.

    This class acts as an intermediary between the API layer and the
    LangGraph-based agent system, handling request transformation and
    response formatting.
    """

    @staticmethod
    @traceable(name="AgentService.process_message", tags=["api", "chat"])
    def process_message(request: ChatRequest, username: Optional[str] = None) -> ChatResponse:
        """
        Process a chat message through the multi-agent supervisor.

        Transforms the incoming request into the format expected by the agent
        system, invokes the supervisor graph, and formats the response.
        Validates input using guardrails before processing.

        Args:
            request: The incoming chat request with message and history.
            username: Optional username of the authenticated user for tracking.

        Returns:
            ChatResponse containing:
            - response: The AI-generated response text
            - tool_calls: List of tools invoked during processing
            - trace_url: LangSmith trace URL for debugging
            - token_usage: Token consumption and cost breakdown

        Raises:
            ValueError: If input validation fails (prompt injection, harmful content).
        """
        # Validate input with guardrails
        is_valid, error_message = ContentGuardrails.validate_input(request.message)
        if not is_valid:
            raise ValueError(error_message)

        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]

        result = run_agent(request.message, history, username=username)

        tool_calls = [
            ToolCall(tool_name=tc["tool_name"], arguments=tc["arguments"])
            for tc in result.get("tool_calls", [])
        ]

        return ChatResponse(
            response=result["response"],
            tool_calls=tool_calls,
            trace_url=result.get("trace_url"),
            token_usage=result.get("token_usage")
        )

    @staticmethod
    async def process_message_stream(
        request: ChatRequest,
        username: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Process a chat message with streaming response.

        Validates input, streams tokens as they are generated, and emits
        events for tool calls and final metadata.

        Args:
            request: The incoming chat request with message and history.
            username: Optional username of the authenticated user.

        Yields:
            Server-Sent Event dictionaries with types:
            - token: Individual tokens as generated
            - tool_call: When a tool is invoked
            - metadata: Final token usage and trace URL
            - done: Stream complete signal
            - error: If validation or processing fails
        """
        # Validate input with guardrails
        is_valid, error_message = ContentGuardrails.validate_input(request.message)
        if not is_valid:
            yield {
                "event": "error",
                "data": json.dumps({"error": error_message})
            }
            return

        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]

        try:
            async for event in run_agent_stream(
                request.message,
                history,
                username=username
            ):
                yield event

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
