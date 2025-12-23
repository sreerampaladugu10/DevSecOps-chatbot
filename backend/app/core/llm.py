"""
LLM and embeddings initialization.

Provides singleton instances of Azure OpenAI chat and embedding models
for use throughout the application with retry logic and caching.
"""

from typing import Optional

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

from app.core.config import settings
from app.core.utils import EmbeddingCache

_llm: Optional[AzureChatOpenAI] = None
_embeddings: Optional[AzureOpenAIEmbeddings] = None


def get_llm() -> Optional[AzureChatOpenAI]:
    """
    Get or create the Azure OpenAI chat model singleton.

    Lazily initializes the chat model on first call using
    Azure OpenAI configuration from settings. Includes built-in
    retry logic for transient API errors.

    Returns:
        AzureChatOpenAI instance, or None if API key not configured.
    """
    global _llm
    if _llm is None:
        if not settings.AZURE_OPENAI_API_KEY:
            return None
        _llm = AzureChatOpenAI(
            openai_api_version=settings.OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            temperature=0.7,
            max_tokens=4096,
            max_retries=3,
            timeout=60,
            request_timeout=60
        )
    return _llm


def get_embeddings() -> Optional[AzureOpenAIEmbeddings]:
    """
    Get or create the Azure OpenAI embeddings model singleton.

    Lazily initializes the embeddings model on first call using
    Azure OpenAI configuration from settings. Includes retry logic.

    Returns:
        AzureOpenAIEmbeddings instance, or None if API key not configured.
    """
    global _embeddings
    if _embeddings is None:
        if not settings.AZURE_OPENAI_API_KEY:
            return None
        _embeddings = AzureOpenAIEmbeddings(
            openai_api_version=settings.OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_deployment=settings.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT_NAME,
            max_retries=3,
        )
    return _embeddings


def get_cached_embedding(text: str) -> list[float]:
    """
    Get embedding for text with caching.

    Uses the embedding cache to avoid redundant API calls for
    previously embedded text.

    Args:
        text: Text to embed.

    Returns:
        Embedding vector as list of floats.

    Raises:
        ValueError: If embeddings model not configured.
    """
    embeddings = get_embeddings()
    if embeddings is None:
        raise ValueError("Embeddings model not configured")
    return EmbeddingCache.get_or_compute(text, embeddings)
