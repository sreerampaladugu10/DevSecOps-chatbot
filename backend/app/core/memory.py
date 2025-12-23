"""
Conversation memory management with summarization.

Provides efficient context management for long conversations by:
- Storing conversation history with TTL
- Summarizing older messages to reduce token usage
- Maintaining per-session memory isolation
"""

from typing import Optional
from datetime import datetime
from cachetools import TTLCache
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel

from app.core.llm import get_llm


# Session-based conversation memory with 1-hour TTL
_session_memory: TTLCache = TTLCache(maxsize=1000, ttl=3600)


class ConversationSummary(BaseModel):
    """Summary of conversation history."""
    summary: str
    message_count: int
    last_updated: datetime


class ConversationMemory:
    """
    Manages conversation memory with automatic summarization.

    Stores messages per session and summarizes older messages when
    the context grows too large, reducing token usage while preserving
    important context.

    Attributes:
        max_messages_before_summary: Trigger summarization after this many messages.
        summary_retain_recent: Keep this many recent messages unsummarized.
    """

    max_messages_before_summary: int = 10
    summary_retain_recent: int = 4

    @classmethod
    def get_session_key(cls, username: str, session_id: Optional[str] = None) -> str:
        """Generate unique session key."""
        if session_id:
            return f"{username}:{session_id}"
        return f"{username}:default"

    @classmethod
    def get_messages(
        cls,
        username: str,
        session_id: Optional[str] = None
    ) -> list[dict]:
        """
        Get conversation history for a session.

        Args:
            username: User identifier.
            session_id: Optional session identifier.

        Returns:
            List of message dictionaries with role and content.
        """
        key = cls.get_session_key(username, session_id)
        session = _session_memory.get(key, {})
        return session.get("messages", [])

    @classmethod
    def add_message(
        cls,
        username: str,
        role: str,
        content: str,
        session_id: Optional[str] = None
    ) -> None:
        """
        Add a message to conversation history.

        Args:
            username: User identifier.
            role: Message role (user/assistant).
            content: Message content.
            session_id: Optional session identifier.
        """
        key = cls.get_session_key(username, session_id)
        session = _session_memory.get(key, {"messages": [], "summary": None})
        session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        _session_memory[key] = session

    @classmethod
    def get_context_messages(
        cls,
        username: str,
        session_id: Optional[str] = None,
        include_summary: bool = True
    ) -> list[dict]:
        """
        Get messages formatted for LLM context.

        If a summary exists and include_summary is True, prepends
        the summary as a system message before recent messages.

        Args:
            username: User identifier.
            session_id: Optional session identifier.
            include_summary: Whether to include conversation summary.

        Returns:
            List of messages ready for LLM context.
        """
        key = cls.get_session_key(username, session_id)
        session = _session_memory.get(key, {"messages": [], "summary": None})

        messages = session.get("messages", [])
        summary = session.get("summary")

        context = []

        # Add summary if available
        if include_summary and summary:
            context.append({
                "role": "system",
                "content": f"Previous conversation summary: {summary['summary']}"
            })

        # Add messages (without timestamps for LLM)
        for msg in messages:
            context.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return context

    @classmethod
    async def summarize_if_needed(
        cls,
        username: str,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Summarize older messages if conversation is too long.

        Triggers summarization when message count exceeds threshold,
        replacing older messages with a summary while keeping recent ones.

        Args:
            username: User identifier.
            session_id: Optional session identifier.

        Returns:
            Summary text if summarization occurred, None otherwise.
        """
        key = cls.get_session_key(username, session_id)
        session = _session_memory.get(key, {"messages": [], "summary": None})
        messages = session.get("messages", [])

        if len(messages) < cls.max_messages_before_summary:
            return None

        llm = get_llm()
        if llm is None:
            return None

        # Messages to summarize (older ones)
        to_summarize = messages[:-cls.summary_retain_recent]
        to_keep = messages[-cls.summary_retain_recent:]

        # Build summary prompt
        conversation_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in to_summarize
        ])

        existing_summary = session.get("summary", {}).get("summary", "")
        if existing_summary:
            conversation_text = f"Previous summary: {existing_summary}\n\n{conversation_text}"

        summary_prompt = f"""Summarize the following conversation in 2-3 sentences,
capturing the key topics discussed and any important context:

{conversation_text}

Summary:"""

        response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
        summary_text = response.content

        # Update session with summary and trimmed messages
        session["summary"] = {
            "summary": summary_text,
            "message_count": len(to_summarize),
            "last_updated": datetime.utcnow().isoformat()
        }
        session["messages"] = to_keep
        _session_memory[key] = session

        return summary_text

    @classmethod
    def clear_session(
        cls,
        username: str,
        session_id: Optional[str] = None
    ) -> None:
        """
        Clear conversation history for a session.

        Args:
            username: User identifier.
            session_id: Optional session identifier.
        """
        key = cls.get_session_key(username, session_id)
        if key in _session_memory:
            del _session_memory[key]

    @classmethod
    def get_stats(cls) -> dict:
        """Get memory statistics."""
        return {
            "active_sessions": len(_session_memory),
            "max_sessions": _session_memory.maxsize,
            "ttl_seconds": _session_memory.ttl
        }
