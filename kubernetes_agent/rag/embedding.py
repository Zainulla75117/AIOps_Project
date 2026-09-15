"""AWS Bedrock Titan embedding model singleton.

Provides a consistent embedding model instance for both document
ingestion and query-time retrieval to ensure vector space compatibility.
"""

from __future__ import annotations

from langchain_aws import BedrockEmbeddings

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)

_embedding_model: BedrockEmbeddings | None = None


def get_embedding_model(cfg: AgentConfig | None = None) -> BedrockEmbeddings:
    """Return the singleton Bedrock Titan embedding model.

    Uses ``amazon.titan-embed-text-v2:0`` by default (configurable via
    ``AIOPS_BEDROCK_EMBEDDING_MODEL``).
    """
    global _embedding_model

    if _embedding_model is not None:
        return _embedding_model

    cfg = cfg or get_config()

    logger.info(
        "initializing_bedrock_embeddings",
        model=cfg.bedrock_embedding_model,
        region=cfg.aws_region,
    )

    _embedding_model = BedrockEmbeddings(
        model_id=cfg.bedrock_embedding_model,
        region_name=cfg.aws_region,
    )

    return _embedding_model


def reset_embedding_model() -> None:
    """Reset the singleton (useful in tests)."""
    global _embedding_model
    _embedding_model = None
