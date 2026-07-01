"""LLM client errors."""


class LLMRequestError(Exception):
    """Base error for LLM HTTP failures."""


class LLMTimeoutError(LLMRequestError):
    """Raised when an LLM request exceeds the configured timeout."""


# Backward-compatible aliases (removed in a future release).
OllamaRequestError = LLMRequestError
OllamaTimeoutError = LLMTimeoutError
