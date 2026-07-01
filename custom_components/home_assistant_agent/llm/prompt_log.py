"""Logging helpers for LLM prompt/response tracing."""

from __future__ import annotations

import logging
from typing import Any


def log_llm_request(
    logger: logging.Logger,
    *,
    model: str,
    messages: list[dict[str, str]],
    json_mode: bool = False,
) -> None:
    """Log outbound LLM prompts."""
    logger.info(
        "LLM request (model=%s, json_mode=%s, messages=%d)",
        model,
        json_mode,
        len(messages),
    )
    for index, message in enumerate(messages, start=1):
        role = message.get("role", "unknown")
        content = message.get("content", "")
        logger.info("LLM prompt [%d/%d] role=%s:\n%s", index, len(messages), role, content)


def log_llm_response(
    logger: logging.Logger,
    *,
    model: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log inbound LLM response text."""
    suffix = ""
    if metadata:
        suffix = f" ({', '.join(f'{key}={value}' for key, value in metadata.items())})"
    logger.info("LLM response (model=%s)%s:\n%s", model, suffix, content)
