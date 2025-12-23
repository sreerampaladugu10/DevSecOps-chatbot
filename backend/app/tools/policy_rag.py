"""
Policy RAG tool for semantic search over security policies.

Uses Flash Reranking to improve retrieval quality by re-scoring
candidates based on query relevance.
"""

from langchain_core.tools import tool
from app.repositories.policy_repo import PolicyRepository
from app.core.db import SessionLocal


@tool
def retrieve_policy(query: str, use_reranking: bool = True) -> dict:
    """
    Search security policies using semantic similarity with Flash Reranking.

    Retrieves relevant compliance policies from the vector store and reranks
    them for improved accuracy. Returns policies with relevance scores and
    retrieval quality metrics.

    Args:
        query: Natural language search query (e.g., "password requirements", "data encryption policy")
        use_reranking: Whether to apply Flash Reranking for better relevance (default: True)

    Returns:
        Dictionary with:
        - policies: List of matching policies with rerank scores
        - metrics: Retrieval quality metrics (latency, score distribution, rank changes)
    """
    db = SessionLocal()
    try:
        repo = PolicyRepository(db)
        search_result = repo.search(
            query,
            n_results=3,
            use_reranking=use_reranking,
            n_candidates=10
        )

        return {
            "policies": search_result["results"],
            "metrics": search_result["metrics"].to_dict(),
            "query": query,
            "reranking_enabled": use_reranking
        }
    except Exception as e:
        return {
            "error": f"Policy search failed: {str(e)}",
            "query": query,
            "policies": [],
            "metrics": None
        }
    finally:
        db.close()


@tool
def retrieve_policy_fast(query: str) -> list[dict]:
    """
    Fast policy search without reranking. Use when speed is critical.

    Retrieves policies using embedding similarity only (no LLM reranking).
    Faster but may be less accurate for complex queries.

    Args:
        query: Natural language search query

    Returns:
        List of matching policies sorted by embedding similarity.
    """
    db = SessionLocal()
    try:
        repo = PolicyRepository(db)
        search_result = repo.search(
            query,
            n_results=3,
            use_reranking=False
        )
        return search_result["results"]
    except Exception as e:
        return [{"error": f"Policy search failed: {str(e)}", "query": query}]
    finally:
        db.close()
