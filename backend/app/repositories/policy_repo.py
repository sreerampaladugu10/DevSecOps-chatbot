"""
Policy repository for managing security policies.

Provides data access layer for security policies, combining SQLite
storage with ChromaDB vector search for RAG capabilities.
Includes Flash Reranking for improved retrieval quality.
"""

from typing import Optional
import time

from sqlalchemy.orm import Session

from app.models.database import Policy
from app.models.schemas import PolicyCreate
from app.repositories.vector_repo import get_vector_repo
from app.core.reranker import get_reranker, RetrievalMetrics


class PolicyRepository:
    """
    Repository for security policy CRUD operations with vector search.

    Manages policies in both SQLite (structured data) and ChromaDB
    (vector embeddings for semantic search).

    Attributes:
        db: SQLAlchemy database session.
        vector_repo: ChromaDB vector repository instance.
    """

    def __init__(self, db: Session):
        """
        Initialize the policy repository.

        Args:
            db: SQLAlchemy database session for SQL operations.
        """
        self.db = db
        self.vector_repo = get_vector_repo()

    def create(self, policy: PolicyCreate) -> Policy:
        """
        Create a new security policy.

        Saves the policy to both SQLite and ChromaDB with embeddings.

        Args:
            policy: Policy data to create.

        Returns:
            Created Policy database model.
        """
        db_policy = Policy(
            id=policy.id,
            title=policy.title,
            content=policy.content,
            category=policy.category,
            severity=policy.severity
        )
        self.db.add(db_policy)
        self.db.commit()
        self.db.refresh(db_policy)

        self.vector_repo.add_policy(
            policy_id=policy.id,
            content=f"{policy.title}\n{policy.content}",
            metadata={
                "title": policy.title,
                "category": policy.category or "",
                "severity": policy.severity or ""
            }
        )
        return db_policy

    def get_by_id(self, policy_id: str) -> Optional[Policy]:
        """
        Retrieve a policy by its ID.

        Args:
            policy_id: Unique policy identifier.

        Returns:
            Policy if found, None otherwise.
        """
        return self.db.query(Policy).filter(Policy.id == policy_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Policy]:
        """
        Retrieve all policies with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of Policy models.
        """
        return self.db.query(Policy).offset(skip).limit(limit).all()

    def delete(self, policy_id: str) -> bool:
        """
        Delete a policy by ID.

        Removes from both SQLite and ChromaDB.

        Args:
            policy_id: ID of policy to delete.

        Returns:
            True if deleted, False if not found.
        """
        policy = self.db.query(Policy).filter(Policy.id == policy_id).first()
        if not policy:
            return False
        self.db.delete(policy)
        self.db.commit()
        self.vector_repo.delete_policy(policy_id)
        return True

    def search(
        self,
        query: str,
        n_results: int = 3,
        use_reranking: bool = True,
        n_candidates: int = 10
    ) -> dict:
        """
        Search policies using semantic similarity with optional reranking.

        Performs vector search in ChromaDB, optionally reranks results
        using Flash Reranker, and enriches with full policy data.

        Args:
            query: Natural language search query.
            n_results: Number of final results to return.
            use_reranking: Whether to apply Flash Reranking.
            n_candidates: Number of candidates to fetch for reranking.

        Returns:
            Dictionary with:
            - results: List of policy dictionaries with scores
            - metrics: RetrievalMetrics for quality tracking
        """
        embedding_start = time.time()

        # Fetch more candidates if reranking
        fetch_count = n_candidates if use_reranking else n_results
        vector_results = self.vector_repo.search(query, fetch_count)
        embedding_latency = (time.time() - embedding_start) * 1000

        # Enrich with full policy data
        candidates = []
        for vr in vector_results:
            policy = self.get_by_id(vr["id"])
            if policy:
                candidates.append({
                    "id": policy.id,
                    "title": policy.title,
                    "content": policy.content,
                    "category": policy.category,
                    "severity": policy.severity,
                    "distance": vr.get("distance")
                })

        if use_reranking and candidates:
            reranker = get_reranker(use_llm=True)
            reranked, metrics = reranker.rerank(query, candidates, top_k=n_results)

            # Update embedding latency in metrics
            metrics.embedding_latency_ms = embedding_latency
            metrics.latency_ms = embedding_latency + metrics.rerank_latency_ms

            results = [
                {
                    "id": r.id,
                    "title": r.metadata.get("title", r.id),
                    "content": r.content,
                    "category": r.metadata.get("category"),
                    "severity": r.metadata.get("severity"),
                    "distance": r.original_score,
                    "rerank_score": r.rerank_score,
                    "rank_change": r.original_rank - r.new_rank
                }
                for r in reranked
            ]
        else:
            # No reranking - return as-is
            results = candidates[:n_results]
            metrics = RetrievalMetrics(
                query=query,
                total_candidates=len(candidates),
                reranked_count=len(results),
                latency_ms=embedding_latency,
                embedding_latency_ms=embedding_latency,
                rerank_latency_ms=0,
                top_score=results[0]["distance"] if results else 0,
                score_spread=0,
                rank_changes=0,
                avg_rerank_score=0,
            )

        return {"results": results, "metrics": metrics}

    def count(self) -> int:
        """
        Count total number of policies.

        Returns:
            Total policy count.
        """
        return self.db.query(Policy).count()

    def bulk_create(self, policies: list[dict]) -> int:
        """
        Create multiple policies in batch.

        Skips policies that already exist by ID.

        Args:
            policies: List of policy dictionaries to create.

        Returns:
            Number of policies successfully created.
        """
        created = 0
        for p in policies:
            if self.get_by_id(p["id"]):
                continue
            policy = PolicyCreate(
                id=p["id"],
                title=p.get("title", p["id"]),
                content=p["content"],
                category=p.get("metadata", {}).get("category"),
                severity=p.get("metadata", {}).get("severity")
            )
            self.create(policy)
            created += 1
        return created
