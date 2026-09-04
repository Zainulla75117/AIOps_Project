"""Gemini LLM Provider.

Handles interactions with the Google GenAI API for log analysis,
root cause analysis, and recommendation generation.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.utils.logging import get_logger
from kubernetes_agent.utils.retry import retry_async

logger = get_logger(__name__)


class GeminiProvider:
    """Wrapper around the Google GenAI SDK.

    Provides high-level methods for common agentic LLM tasks, specifically
    structured JSON output generation.
    """

    def __init__(self, cfg: AgentConfig | None = None) -> None:
        self._cfg = cfg or get_config()
        # The genai client uses GEMINI_API_KEY from environment by default,
        # but we pass it explicitly from config for safety.
        if not self._cfg.gemini_api_key or self._cfg.gemini_api_key == "test-key-not-real":
            logger.warning("gemini_api_key_missing_or_dummy")
            self._client = None
        else:
            self._client = genai.Client(api_key=self._cfg.gemini_api_key)

        self._model = self._cfg.gemini_model
        
        # We define common config for all LLM calls
        self._default_config = types.GenerateContentConfig(
            temperature=self._cfg.gemini_temperature,
            max_output_tokens=self._cfg.gemini_max_tokens,
            response_mime_type="application/json",
        )

    def is_available(self) -> bool:
        """Return True if the provider is configured and ready."""
        return self._client is not None

    @retry_async(max_attempts=3, base_delay=2.0)
    async def analyze(
        self,
        system_instruction: str,
        prompt: str,
        schema: Optional[type[BaseModel]] = None,
    ) -> dict[str, Any] | BaseModel:
        """Call Gemini to analyze a prompt and return structured JSON.

        Args:
            system_instruction: Instructions for the model's persona/behavior.
            prompt: The specific task and data to analyze.
            schema: Optional Pydantic model class defining the exact JSON schema
                    the model must adhere to.

        Returns:
            If a schema is provided, returns an instance of that schema.
            Otherwise, returns a parsed JSON dictionary.
        """
        if not self._client:
            raise RuntimeError("GeminiProvider is not configured with a valid API key.")

        # Create a specific config for this call, overriding defaults if necessary
        call_config = types.GenerateContentConfig(
            temperature=self._cfg.gemini_temperature,
            max_output_tokens=self._cfg.gemini_max_tokens,
            response_mime_type="application/json",
            system_instruction=system_instruction,
        )

        if schema:
            call_config.response_schema = schema

        logger.debug(
            "gemini_request_started",
            model=self._model,
            prompt_length=len(prompt),
        )

        # Async generation
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=call_config,
        )
        
        if not response.text:
            raise ValueError("Empty response received from Gemini.")

        logger.debug("gemini_request_completed")

        # Parse the JSON response
        try:
            parsed_json = json.loads(response.text)
            
            if schema:
                # Validate and instantiate the Pydantic model
                return schema.model_validate(parsed_json)
                
            return parsed_json
        except json.JSONDecodeError as exc:
            logger.error("gemini_json_parse_failed", response_text=response.text, error=str(exc))
            raise ValueError(f"Failed to parse LLM response as JSON: {exc}")
