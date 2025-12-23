"""
Utility functions for LLM operations.

Provides:
- Retry logic with exponential backoff
- Input/output guardrails and validation
- Embedding cache for performance
- Rate limiting utilities
"""

import re
import hashlib
from typing import Optional, Callable, Any
from functools import wraps

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from cachetools import TTLCache
from langchain_openai import AzureOpenAIEmbeddings

from app.core.config import settings


# Embedding cache - TTL of 1 hour, max 10000 entries
_embedding_cache: TTLCache = TTLCache(maxsize=10000, ttl=3600)


class ContentGuardrails:
    """
    Guardrails for validating and sanitizing LLM inputs and outputs.

    Checks for:
    - PII (emails, phone numbers, SSNs)
    - Harmful content patterns
    - Prompt injection attempts
    - Output validation
    """

    # Patterns for PII detection
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    PHONE_PATTERN = re.compile(r'\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    CREDIT_CARD_PATTERN = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')

    # Patterns for prompt injection detection
    INJECTION_PATTERNS = [
        re.compile(r'ignore\s+(previous|all|above)\s+instructions', re.IGNORECASE),
        re.compile(r'disregard\s+(previous|all|above)', re.IGNORECASE),
        re.compile(r'you\s+are\s+now\s+', re.IGNORECASE),
        re.compile(r'pretend\s+to\s+be', re.IGNORECASE),
        re.compile(r'act\s+as\s+if\s+you', re.IGNORECASE),
        re.compile(r'jailbreak', re.IGNORECASE),
        re.compile(r'DAN\s+mode', re.IGNORECASE),
    ]

    # Harmful content patterns
    HARMFUL_PATTERNS = [
        re.compile(r'how\s+to\s+(hack|exploit|attack)', re.IGNORECASE),
        re.compile(r'create\s+(malware|virus|ransomware)', re.IGNORECASE),
        re.compile(r'bypass\s+security', re.IGNORECASE),
    ]

    @classmethod
    def detect_pii(cls, text: str) -> dict:
        """
        Detect PII in text.

        Args:
            text: Text to scan for PII.

        Returns:
            Dictionary with detected PII types and counts.
        """
        return {
            "emails": len(cls.EMAIL_PATTERN.findall(text)),
            "phones": len(cls.PHONE_PATTERN.findall(text)),
            "ssns": len(cls.SSN_PATTERN.findall(text)),
            "credit_cards": len(cls.CREDIT_CARD_PATTERN.findall(text)),
        }

    @classmethod
    def has_pii(cls, text: str) -> bool:
        """Check if text contains any PII."""
        pii = cls.detect_pii(text)
        return any(count > 0 for count in pii.values())

    @classmethod
    def redact_pii(cls, text: str) -> str:
        """
        Redact PII from text.

        Args:
            text: Text with potential PII.

        Returns:
            Text with PII redacted.
        """
        text = cls.EMAIL_PATTERN.sub('[EMAIL REDACTED]', text)
        text = cls.PHONE_PATTERN.sub('[PHONE REDACTED]', text)
        text = cls.SSN_PATTERN.sub('[SSN REDACTED]', text)
        text = cls.CREDIT_CARD_PATTERN.sub('[CARD REDACTED]', text)
        return text

    @classmethod
    def detect_prompt_injection(cls, text: str) -> bool:
        """
        Detect potential prompt injection attempts.

        Args:
            text: User input to check.

        Returns:
            True if injection patterns detected.
        """
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(text):
                return True
        return False

    @classmethod
    def detect_harmful_content(cls, text: str) -> bool:
        """
        Detect potentially harmful content requests.

        Args:
            text: Text to check.

        Returns:
            True if harmful patterns detected.
        """
        for pattern in cls.HARMFUL_PATTERNS:
            if pattern.search(text):
                return True
        return False

    @classmethod
    def validate_input(cls, text: str) -> tuple[bool, Optional[str]]:
        """
        Validate user input for safety.

        Args:
            text: User input to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if len(text) > 10000:
            return False, "Message too long (max 10000 characters)"

        if cls.detect_prompt_injection(text):
            return False, "Invalid input detected"

        if cls.detect_harmful_content(text):
            return False, "Request cannot be processed"

        return True, None

    @classmethod
    def sanitize_output(cls, text: str, redact_pii: bool = True) -> str:
        """
        Sanitize LLM output before returning to user.

        Args:
            text: LLM output.
            redact_pii: Whether to redact PII.

        Returns:
            Sanitized text.
        """
        if redact_pii:
            text = cls.redact_pii(text)
        return text


class EmbeddingCache:
    """
    Cache for embedding vectors to reduce API calls.

    Uses content hash as key for efficient lookup.
    """

    @staticmethod
    def _get_cache_key(text: str) -> str:
        """Generate cache key from text content."""
        return hashlib.md5(text.encode()).hexdigest()

    @classmethod
    def get(cls, text: str) -> Optional[list[float]]:
        """
        Get cached embedding for text.

        Args:
            text: Text to lookup.

        Returns:
            Cached embedding vector or None.
        """
        key = cls._get_cache_key(text)
        return _embedding_cache.get(key)

    @classmethod
    def set(cls, text: str, embedding: list[float]) -> None:
        """
        Cache embedding for text.

        Args:
            text: Original text.
            embedding: Embedding vector to cache.
        """
        key = cls._get_cache_key(text)
        _embedding_cache[key] = embedding

    @classmethod
    def get_or_compute(
        cls,
        text: str,
        embeddings: AzureOpenAIEmbeddings
    ) -> list[float]:
        """
        Get cached embedding or compute and cache it.

        Args:
            text: Text to embed.
            embeddings: Embeddings model to use if not cached.

        Returns:
            Embedding vector.
        """
        cached = cls.get(text)
        if cached is not None:
            return cached

        embedding = embeddings.embed_query(text)
        cls.set(text, embedding)
        return embedding

    @classmethod
    def cache_stats(cls) -> dict:
        """Get cache statistics."""
        return {
            "size": len(_embedding_cache),
            "max_size": _embedding_cache.maxsize,
            "ttl": _embedding_cache.ttl,
        }


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 10,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for adding retry logic with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts.
        min_wait: Minimum wait time between retries (seconds).
        max_wait: Maximum wait time between retries (seconds).
        exceptions: Tuple of exception types to retry on.

    Returns:
        Decorated function with retry logic.
    """
    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(exceptions),
            reraise=True
        )
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)
        return wrapper
    return decorator


async def with_retry_async(
    func: Callable,
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 10,
    *args,
    **kwargs
) -> Any:
    """
    Execute async function with retry logic.

    Args:
        func: Async function to execute.
        max_attempts: Maximum retry attempts.
        min_wait: Minimum wait between retries.
        max_wait: Maximum wait between retries.
        *args: Function arguments.
        **kwargs: Function keyword arguments.

    Returns:
        Function result.

    Raises:
        Last exception if all retries fail.
    """
    import asyncio

    last_exception = None
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                wait_time = min(min_wait * (2 ** attempt), max_wait)
                await asyncio.sleep(wait_time)

    raise last_exception
