"""AWS Bedrock Claude Haiku LLM provider.

Provides the chat-oriented LLM used by the RAG-enhanced chat endpoint.
Uses ChatBedrockConverse which supports inference profiles (global/us prefixed model IDs).
"""

from __future__ import annotations

from langchain_aws import ChatBedrockConverse

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)

_bedrock_llm: ChatBedrockConverse | None = None


def get_bedrock_llm(cfg: AgentConfig | None = None) -> ChatBedrockConverse:
    """Return the singleton Bedrock Claude Haiku chat model.

    Uses ``global.anthropic.claude-haiku-4-5-20251001-v1:0`` by default
    (configurable via ``AIOPS_BEDROCK_LLM_MODEL``).
    """
    global _bedrock_llm

    if _bedrock_llm is not None:
        return _bedrock_llm

    cfg = cfg or get_config()

    logger.info(
        "initializing_bedrock_llm",
        model=cfg.bedrock_llm_model,
        region=cfg.aws_region,
    )

    _bedrock_llm = ChatBedrockConverse(
        model=cfg.bedrock_llm_model,
        region_name=cfg.aws_region,
        temperature=cfg.bedrock_temperature,
        max_tokens=cfg.bedrock_max_tokens,
    )

    return _bedrock_llm


def reset_bedrock_llm() -> None:
    """Reset the singleton (useful in tests)."""
    global _bedrock_llm
    _bedrock_llm = None
