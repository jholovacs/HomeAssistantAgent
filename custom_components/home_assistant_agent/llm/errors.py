"""Ollama client errors."""


class OllamaRequestError(Exception):
    """Base error for Ollama HTTP failures."""


class OllamaTimeoutError(OllamaRequestError):
    """Raised when an Ollama request exceeds the configured timeout."""
