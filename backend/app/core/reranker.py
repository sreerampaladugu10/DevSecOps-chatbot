"""
Flash Reranker for improving RAG retrieval quality.

Provides reranking capabilities using LLM-based relevance scoring.
Reranking improves retrieval by scoring query-document relevance
more accurately than embedding similarity alone.
"""

from typing import Optional
from dataclasses import dataclass
import time
import json
import re

from app.core.config import settings
from app.core.llm import get_llm


@dataclass
class RerankResult:
    """Result from reranking operation."""
    id: str
    content: str
    metadata: dict
    original_score: Optional[float]
    rerank_score: float
    original_rank: int
    new_rank: int


@dataclass
class RetrievalMetrics:
    """
    Metrics for evaluating retrieval quality.

    Tracks latency, score distribution, and rank changes
    to help optimize RAG pipeline performance.
    """
    query: str
    total_candidates: int
    reranked_count: int
    latency_ms: float
    embedding_latency_ms: float
    rerank_latency_ms: float
    top_score: float
    score_spread: float
    rank_changes: int
    avg_rerank_score: float

    def to_dict(self) -> dict:
        """Convert metrics to dictionary for API responses."""
        return {
            "query": self.query[:100],
            "total_candidates": self.total_candidates,
            "reranked_count": self.reranked_count,
            "latency_ms": round(self.latency_ms, 2),
            "embedding_latency_ms": round(self.embedding_latency_ms, 2),
            "rerank_latency_ms": round(self.rerank_latency_ms, 2),
            "top_score": round(self.top_score, 4),
            "score_spread": round(self.score_spread, 4),
            "rank_changes": self.rank_changes,
            "avg_rerank_score": round(self.avg_rerank_score, 4),
        }


class FlashReranker:
    """
    Fast reranker using LLM-based relevance scoring.

    Uses Azure OpenAI to score query-document relevance with a
    lightweight prompt. Called "Flash" because it uses a single
    batched LLM call for efficiency.
    """

    RERANK_PROMPT = """Score the relevance of each document to the query.
Return ONLY a JSON array of scores from 0.0 to 1.0, one per document.
Higher scores = more relevant. Be strict - only highly relevant docs get > 0.7.

Query: {query}

Documents:
{documents}

Return format: [0.85, 0.42, 0.91]
Scores only, no explanation."""

    def __init__(self, use_llm_rerank: bool = True):
        self.use_llm_rerank = use_llm_rerank
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm(temperature=0)
        return self._llm

    def _keyword_score(self, query: str, content: str) -> float:
        """Keyword-based relevance scoring as fallback."""
        query_terms = set(query.lower().split())
        content_lower = content.lower()

        if not query_terms:
            return 0.0

        matches = sum(1 for term in query_terms if term in content_lower)
        base_score = matches / len(query_terms)

        if query.lower() in content_lower:
            base_score = min(1.0, base_score + 0.3)

        return base_score

    def _llm_rerank(self, query: str, documents: list[dict]) -> list[float]:
        """Use LLM to score document relevance."""
        if not documents:
            return []

        doc_text = "\n".join(
            f"[{i+1}] {doc['content'][:500]}"
            for i, doc in enumerate(documents)
        )

        prompt = self.RERANK_PROMPT.format(query=query, documents=doc_text)

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()

            if content.startswith("["):
                scores = json.loads(content)
            else:
                match = re.search(r'\[[\d.,\s]+\]', content)
                if match:
                    scores = json.loads(match.group())
                else:
                    return [self._keyword_score(query, d['content']) for d in documents]

            scores = [max(0.0, min(1.0, float(s))) for s in scores]

            while len(scores) < len(documents):
                scores.append(0.5)

            return scores[:len(documents)]

        except Exception:
            return [self._keyword_score(query, d['content']) for d in documents]

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: Optional[int] = None
    ) -> tuple[list[RerankResult], RetrievalMetrics]:
        """
        Rerank documents by relevance to query.

        Args:
            query: Search query.
            documents: List of document dicts with id, content, metadata, distance.
            top_k: Number of top results to return. None = return all.

        Returns:
            Tuple of (reranked results, retrieval metrics).
        """
        start_time = time.time()

        if not documents:
            metrics = RetrievalMetrics(
                query=query, total_candidates=0, reranked_count=0,
                latency_ms=0, embedding_latency_ms=0, rerank_latency_ms=0,
                top_score=0, score_spread=0, rank_changes=0, avg_rerank_score=0,
            )
            return [], metrics

        rerank_start = time.time()
        if self.use_llm_rerank:
            scores = self._llm_rerank(query, documents)
        else:
            scores = [self._keyword_score(query, d['content']) for d in documents]
        rerank_latency = (time.time() - rerank_start) * 1000

        results = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            results.append(RerankResult(
                id=doc['id'],
                content=doc['content'],
                metadata=doc.get('metadata', {}),
                original_score=doc.get('distance'),
                rerank_score=score,
                original_rank=i,
                new_rank=-1
            ))

        results.sort(key=lambda x: x.rerank_score, reverse=True)

        rank_changes = 0
        for i, r in enumerate(results):
            r.new_rank = i
            if r.original_rank != i:
                rank_changes += 1

        if top_k is not None:
            results = results[:top_k]

        total_latency = (time.time() - start_time) * 1000
        scores_list = [r.rerank_score for r in results]

        metrics = RetrievalMetrics(
            query=query,
            total_candidates=len(documents),
            reranked_count=len(results),
            latency_ms=total_latency,
            embedding_latency_ms=total_latency - rerank_latency,
            rerank_latency_ms=rerank_latency,
            top_score=max(scores_list) if scores_list else 0,
            score_spread=(max(scores_list) - min(scores_list)) if len(scores_list) > 1 else 0,
            rank_changes=rank_changes,
            avg_rerank_score=sum(scores_list) / len(scores_list) if scores_list else 0,
        )

        return results, metrics


def get_reranker(use_llm: bool = True) -> FlashReranker:
    """Factory function to get reranker instance."""
    return FlashReranker(use_llm_rerank=use_llm)
