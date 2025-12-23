"""
Token-aware context management for LLM conversations.

Provides intelligent context window management by:
- Tracking token usage per message
- Compressing context via summarization when approaching limits
- Preserving recent context while summarizing older messages
- Supporting different strategies (sliding window, summarize, hybrid)

GPT-4o context window: 128K tokens
Recommended operating range: Keep context under 80K for best performance
"""

from typing import Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
import tiktoken

from app.core.config import settings
from app.core.llm import get_llm


# Token limits for different models
MODEL_LIMITS = {
    "gpt-4o": {"context": 128000, "target": 80000, "reserve_output": 4096},
    "gpt-4o-mini": {"context": 128000, "target": 80000, "reserve_output": 4096},
    "gpt-4": {"context": 8192, "target": 6000, "reserve_output": 2000},
    "gpt-4-turbo": {"context": 128000, "target": 80000, "reserve_output": 4096},
}

# Default encoding for token counting
try:
    ENCODING = tiktoken.encoding_for_model("gpt-4o")
except Exception:
    ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class Message:
    """A conversation message with token metadata."""
    role: str
    content: str
    token_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    is_summary: bool = False

    def __post_init__(self):
        if self.token_count == 0:
            self.token_count = count_tokens(self.content)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ContextState:
    """Current state of the context window."""
    messages: list[Message] = field(default_factory=list)
    summary: Optional[str] = None
    summary_token_count: int = 0
    total_tokens: int = 0
    summarized_message_count: int = 0

    def to_dict(self) -> dict:
        return {
            "message_count": len(self.messages),
            "total_tokens": self.total_tokens,
            "has_summary": self.summary is not None,
            "summary_tokens": self.summary_token_count,
            "summarized_messages": self.summarized_message_count,
        }


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    try:
        return len(ENCODING.encode(text))
    except Exception:
        # Fallback: rough estimate of 4 chars per token
        return len(text) // 4


def get_model_limits(model_name: Optional[str] = None) -> dict:
    """Get token limits for the current model."""
    name = (model_name or settings.AZURE_OPENAI_DEPLOYMENT_NAME).lower()
    return MODEL_LIMITS.get(name, MODEL_LIMITS["gpt-4o"])


class ContextManager:
    """
    Manages conversation context with token-aware compression.

    Strategies:
    - sliding_window: Drop oldest messages when limit reached
    - summarize: Summarize older messages, keep recent ones
    - hybrid: Summarize first, then slide if still over limit
    """

    SUMMARY_PROMPT = """Summarize this conversation concisely, preserving:
1. Key topics discussed and decisions made
2. Important facts, numbers, or specifics mentioned
3. Any pending questions or action items
4. Tool calls made and their results (briefly)

Keep the summary under 500 tokens. Be factual and specific.

Conversation:
{conversation}

Summary:"""

    def __init__(
        self,
        strategy: Literal["sliding_window", "summarize", "hybrid"] = "hybrid",
        target_tokens: Optional[int] = None,
        keep_recent: int = 6,
        model_name: Optional[str] = None
    ):
        """
        Initialize context manager.

        Args:
            strategy: How to handle context overflow
            target_tokens: Target token count (default: model's target)
            keep_recent: Number of recent messages to always keep
            model_name: Model name for token limits
        """
        self.strategy = strategy
        self.limits = get_model_limits(model_name)
        self.target_tokens = target_tokens or self.limits["target"]
        self.keep_recent = keep_recent
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0)
        return self._llm

    def create_state(self) -> ContextState:
        """Create new empty context state."""
        return ContextState()

    def add_message(
        self,
        state: ContextState,
        role: str,
        content: str
    ) -> ContextState:
        """
        Add a message to the context state.

        Args:
            state: Current context state
            role: Message role (user/assistant/system)
            content: Message content

        Returns:
            Updated context state
        """
        msg = Message(role=role, content=content)
        state.messages.append(msg)
        state.total_tokens += msg.token_count
        return state

    def get_context_tokens(self, state: ContextState) -> int:
        """Calculate total tokens including summary."""
        total = state.summary_token_count if state.summary else 0
        total += sum(m.token_count for m in state.messages)
        return total

    def needs_compression(self, state: ContextState) -> bool:
        """Check if context needs compression."""
        return self.get_context_tokens(state) > self.target_tokens

    def _sliding_window(self, state: ContextState) -> ContextState:
        """Apply sliding window - drop oldest messages."""
        while (self.get_context_tokens(state) > self.target_tokens
               and len(state.messages) > self.keep_recent):
            removed = state.messages.pop(0)
            state.total_tokens -= removed.token_count
        return state

    async def _summarize_older(self, state: ContextState) -> ContextState:
        """Summarize older messages, keep recent ones."""
        if len(state.messages) <= self.keep_recent:
            return state

        # Split messages
        to_summarize = state.messages[:-self.keep_recent]
        to_keep = state.messages[-self.keep_recent:]

        # Build conversation text for summary
        conv_parts = []
        if state.summary:
            conv_parts.append(f"Previous context: {state.summary}")

        for msg in to_summarize:
            prefix = "User" if msg.role == "user" else "Assistant"
            conv_parts.append(f"{prefix}: {msg.content[:1000]}")

        conversation = "\n\n".join(conv_parts)
        prompt = self.SUMMARY_PROMPT.format(conversation=conversation)

        try:
            response = await self.llm.ainvoke(prompt)
            summary_text = response.content

            state.summary = summary_text
            state.summary_token_count = count_tokens(summary_text)
            state.summarized_message_count += len(to_summarize)
            state.messages = to_keep
            state.total_tokens = sum(m.token_count for m in to_keep)

        except Exception:
            # Fallback to sliding window if summarization fails
            state = self._sliding_window(state)

        return state

    async def compress(self, state: ContextState) -> ContextState:
        """
        Compress context using configured strategy.

        Args:
            state: Current context state

        Returns:
            Compressed context state
        """
        if not self.needs_compression(state):
            return state

        if self.strategy == "sliding_window":
            return self._sliding_window(state)

        elif self.strategy == "summarize":
            return await self._summarize_older(state)

        else:  # hybrid
            # First try summarization
            state = await self._summarize_older(state)
            # If still over limit, apply sliding window
            if self.needs_compression(state):
                state = self._sliding_window(state)
            return state

    def build_messages(
        self,
        state: ContextState,
        system_prompt: Optional[str] = None
    ) -> list[dict]:
        """
        Build message list for LLM, including summary if present.

        Args:
            state: Current context state
            system_prompt: Optional system prompt to prepend

        Returns:
            List of message dicts ready for LLM
        """
        messages = []

        # System prompt first
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add summary as system context if present
        if state.summary:
            summary_msg = f"""[Previous conversation summary - {state.summarized_message_count} messages]:
{state.summary}

[Recent conversation continues below]"""
            messages.append({"role": "system", "content": summary_msg})

        # Add actual messages
        for msg in state.messages:
            messages.append(msg.to_dict())

        return messages

    def get_stats(self, state: ContextState) -> dict:
        """Get context statistics."""
        limits = self.limits
        current_tokens = self.get_context_tokens(state)

        return {
            "current_tokens": current_tokens,
            "target_tokens": self.target_tokens,
            "max_tokens": limits["context"],
            "utilization_pct": round(current_tokens / self.target_tokens * 100, 1),
            "message_count": len(state.messages),
            "has_summary": state.summary is not None,
            "summarized_messages": state.summarized_message_count,
            "strategy": self.strategy,
            "needs_compression": self.needs_compression(state),
        }


class SessionContextManager:
    """
    Session-based context manager with persistence.

    Manages context per user session with automatic compression.
    """

    _sessions: dict[str, ContextState] = {}
    _managers: dict[str, ContextManager] = {}

    @classmethod
    def get_session_key(cls, username: str, session_id: Optional[str] = None) -> str:
        return f"{username}:{session_id or 'default'}"

    @classmethod
    def get_or_create(
        cls,
        username: str,
        session_id: Optional[str] = None,
        strategy: str = "hybrid"
    ) -> tuple[ContextManager, ContextState]:
        """Get or create context manager and state for session."""
        key = cls.get_session_key(username, session_id)

        if key not in cls._managers:
            cls._managers[key] = ContextManager(strategy=strategy)

        if key not in cls._sessions:
            cls._sessions[key] = cls._managers[key].create_state()

        return cls._managers[key], cls._sessions[key]

    @classmethod
    async def add_exchange(
        cls,
        username: str,
        user_message: str,
        assistant_response: str,
        session_id: Optional[str] = None
    ) -> dict:
        """
        Add a user-assistant exchange and compress if needed.

        Returns context stats after the operation.
        """
        manager, state = cls.get_or_create(username, session_id)

        manager.add_message(state, "user", user_message)
        manager.add_message(state, "assistant", assistant_response)

        # Compress if needed
        if manager.needs_compression(state):
            state = await manager.compress(state)
            key = cls.get_session_key(username, session_id)
            cls._sessions[key] = state

        return manager.get_stats(state)

    @classmethod
    def get_messages(
        cls,
        username: str,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> list[dict]:
        """Get messages for LLM including summary."""
        manager, state = cls.get_or_create(username, session_id)
        return manager.build_messages(state, system_prompt)

    @classmethod
    def clear_session(cls, username: str, session_id: Optional[str] = None):
        """Clear a session's context."""
        key = cls.get_session_key(username, session_id)
        cls._sessions.pop(key, None)
        cls._managers.pop(key, None)

    @classmethod
    def get_stats(cls, username: str, session_id: Optional[str] = None) -> dict:
        """Get stats for a session."""
        manager, state = cls.get_or_create(username, session_id)
        return manager.get_stats(state)
