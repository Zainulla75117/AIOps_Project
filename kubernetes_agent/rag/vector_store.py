"""ChromaDB vector store wrapper.

Manages the persistent ChromaDB collection used for RAG document
retrieval.  Uses cosine similarity and the Bedrock Titan embedding
model for vector compatibility.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.rag.embedding import get_embedding_model
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)

_vector_store: Chroma | None = None


def get_vector_store(cfg: AgentConfig | None = None) -> Chroma:
    """Return the singleton ChromaDB-backed LangChain vector store.

    Persistence directory defaults to ``db/chroma_db`` relative to the
    project root.  Distance metric is **cosine similarity**.
    """
    global _vector_store

    if _vector_store is not None:
        return _vector_store

    cfg = cfg or get_config()

    # Resolve persistence path relative to project root
    project_root = Path(__file__).resolve().parent.parent.parent
    persist_dir = project_root / cfg.chroma_persist_dir
    persist_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "initializing_chroma_vector_store",
        persist_dir=str(persist_dir),
        collection=cfg.chroma_collection_name,
    )

    embedding_model = get_embedding_model(cfg)

    _vector_store = Chroma(
        collection_name=cfg.chroma_collection_name,
        embedding_function=embedding_model,
        persist_directory=str(persist_dir),
        collection_metadata={"hnsw:space": "cosine"},
    )

    return _vector_store


def add_documents(docs: list[Document], cfg: AgentConfig | None = None) -> list[str]:
    """Add pre-chunked documents to the vector store.

    Returns the list of IDs assigned by ChromaDB.
    """
    store = get_vector_store(cfg)
    ids = store.add_documents(docs)
    logger.info("documents_added_to_vector_store", count=len(ids))
    return ids


def similarity_search(
    query: str,
    k: int | None = None,
    cfg: AgentConfig | None = None,
) -> list[Document]:
    """Retrieve the top-k most relevant document chunks for a query."""
    cfg = cfg or get_config()
    k = k or cfg.rag_top_k
    store = get_vector_store(cfg)
    results = store.similarity_search(query, k=k)
    logger.debug("similarity_search_completed", query_len=len(query), results=len(results))
    return results


def similarity_search_with_scores(
    query: str,
    k: int | None = None,
    score_threshold: float | None = None,
    cfg: AgentConfig | None = None,
) -> list[tuple[Document, float]]:
    """Retrieve relevant chunks with similarity scores, filtered by threshold.

    Only returns documents whose similarity score meets the threshold.
    For cosine similarity in ChromaDB, lower distance = more similar.
    A distance of 0 is a perfect match, 2 is completely dissimilar.
    We convert to a relevance score: relevance = 1 - (distance / 2).

    Returns:
        List of (Document, relevance_score) tuples, sorted by relevance.
    """
    cfg = cfg or get_config()
    k = k or cfg.rag_top_k
    threshold = score_threshold if score_threshold is not None else cfg.rag_relevance_threshold
    store = get_vector_store(cfg)

    # ChromaDB returns (doc, distance) where distance is cosine distance [0, 2]
    results_with_scores = store.similarity_search_with_score(query, k=k)

    # Convert distance to relevance score and filter
    filtered = []
    for doc, distance in results_with_scores:
        relevance = 1.0 - (distance / 2.0)  # Convert cosine distance to [0, 1] relevance
        if relevance >= threshold:
            filtered.append((doc, relevance))

    logger.debug(
        "scored_search_completed",
        query_len=len(query),
        total_results=len(results_with_scores),
        above_threshold=len(filtered),
        threshold=threshold,
    )
    return filtered


def delete_by_source(source_name: str, cfg: AgentConfig | None = None) -> int:
    """Delete all chunks belonging to a given source document.

    Returns the number of chunks deleted.
    """
    store = get_vector_store(cfg)

    # Query ChromaDB's underlying collection to find IDs by metadata
    collection = store._collection
    results = collection.get(where={"source": source_name})

    if not results["ids"]:
        return 0

    ids_to_delete = results["ids"]
    collection.delete(ids=ids_to_delete)
    logger.info("documents_deleted_from_vector_store", source=source_name, count=len(ids_to_delete))
    return len(ids_to_delete)


def list_sources(cfg: AgentConfig | None = None) -> list[dict[str, Any]]:
    """List all unique source documents in the vector store.

    Returns a list of dicts with ``source`` and ``chunk_count`` keys.
    """
    store = get_vector_store(cfg)
    collection = store._collection

    # Get all metadata
    all_data = collection.get(include=["metadatas"])

    if not all_data["metadatas"]:
        return []

    # Aggregate by source
    source_counts: dict[str, int] = {}
    for meta in all_data["metadatas"]:
        src = meta.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    return [
        {"source": src, "chunk_count": count}
        for src, count in sorted(source_counts.items())
    ]


def get_chunk_previews(
    source_name: str,
    cfg: AgentConfig | None = None,
) -> list[dict[str, Any]]:
    """Get chunk previews for a given source document."""
    store = get_vector_store(cfg)
    collection = store._collection

    results = collection.get(
        where={"source": source_name},
        include=["documents", "metadatas"],
    )

    chunks = []
    for i, (doc, meta) in enumerate(
        zip(results["documents"] or [], results["metadatas"] or [])
    ):
        chunks.append({
            "index": i,
            "content": doc[:500] if doc else "",  # Preview first 500 chars
            "metadata": meta or {},
            "length": len(doc) if doc else 0,
        })

    return chunks


def reset_vector_store() -> None:
    """Reset the singleton (useful in tests)."""
    global _vector_store
    _vector_store = None
