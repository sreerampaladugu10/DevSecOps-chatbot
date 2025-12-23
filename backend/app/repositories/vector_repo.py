"""
Vector repository for ChromaDB operations.

Provides vector storage and semantic search capabilities using
Azure OpenAI embeddings with ChromaDB as the vector store.
"""

from typing import Optional

import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

from app.core.config import settings as app_settings
from app.core.llm import get_embeddings


class AzureEmbeddingFunction(EmbeddingFunction):
    """
    ChromaDB embedding function using Azure OpenAI.

    Wraps the Azure OpenAI embeddings model to provide embeddings
    in the format expected by ChromaDB.
    """

    def __call__(self, input: Documents) -> Embeddings:
        """
        Generate embeddings for input documents.

        Args:
            input: List of text documents to embed.

        Returns:
            List of embedding vectors.

        Raises:
            ValueError: If embeddings model is not initialized or API fails.
        """
        embeddings = get_embeddings()
        if embeddings is None:
            raise ValueError("Embeddings not initialized - check AZURE_OPENAI_API_KEY in .env")
        try:
            return embeddings.embed_documents(list(input))
        except Exception as e:
            raise ValueError(f"Embedding generation failed: {str(e)}")


class VectorRepository:
    """
    Repository for vector storage and semantic search operations.

    Manages a ChromaDB collection for security policies with
    Azure OpenAI embeddings.

    Attributes:
        client: ChromaDB persistent client instance.
        _collection: Cached reference to the policies collection.
    """

    def __init__(self):
        """Initialize the ChromaDB client with persistent storage."""
        self.client = chromadb.PersistentClient(
            path=app_settings.CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
        self._collection = None

    @property
    def collection(self):
        """
        Get or create the security policies collection.

        Lazily initializes the collection on first access.

        Returns:
            ChromaDB collection for security policies.
        """
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name="security_policies",
                metadata={"description": "Security policies and rules for RAG"},
                embedding_function=AzureEmbeddingFunction()
            )
        return self._collection

    def add_policy(self, policy_id: str, content: str, metadata: Optional[dict] = None) -> None:
        """
        Add a policy to the vector store.

        Args:
            policy_id: Unique identifier for the policy.
            content: Text content to embed and store.
            metadata: Optional metadata dictionary.
        """
        self.collection.add(
            ids=[policy_id],
            documents=[content],
            metadatas=[metadata or {}]
        )

    def add_policies_batch(self, policies: list[dict]) -> None:
        """
        Add multiple policies in a single batch operation.

        Args:
            policies: List of policy dicts with id, content, and optional metadata.
        """
        ids = [p["id"] for p in policies]
        documents = [p["content"] for p in policies]
        metadatas = [p.get("metadata", {}) for p in policies]
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def search(self, query: str, n_results: int = 3) -> list[dict]:
        """
        Search for policies by semantic similarity.

        Args:
            query: Natural language search query.
            n_results: Maximum number of results to return.

        Returns:
            List of matching policies with id, content, metadata, and distance.
        """
        try:
            results = self.collection.query(query_texts=[query], n_results=n_results)
            policies = []
            if results["documents"] and len(results["documents"]) > 0:
                for i, doc in enumerate(results["documents"][0]):
                    policies.append({
                        "id": results["ids"][0][i],
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else None
                    })
            return policies
        except Exception as e:
            raise ValueError(f"Vector search failed: {str(e)}")

    def delete_policy(self, policy_id: str) -> None:
        """
        Delete a policy from the vector store.

        Args:
            policy_id: ID of the policy to delete.
        """
        self.collection.delete(ids=[policy_id])

    def get_all_policies(self) -> list[dict]:
        """
        Retrieve all policies from the vector store.

        Returns:
            List of all stored policies with id and content.
        """
        results = self.collection.get()
        return [
            {"id": results["ids"][i], "content": results["documents"][i]}
            for i in range(len(results["ids"]))
        ]

    def count(self) -> int:
        """
        Count total policies in the vector store.

        Returns:
            Number of policies stored.
        """
        return self.collection.count()


def get_vector_repo() -> VectorRepository:
    """
    Factory function to create a VectorRepository instance.

    Returns:
        New VectorRepository instance.
    """
    return VectorRepository()
