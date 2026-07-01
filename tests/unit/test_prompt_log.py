"""Tests for LLM prompt logging."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.llm.prompt_log import log_llm_request, log_llm_response


def test_log_llm_request_and_response(caplog):
    logger = logging.getLogger("test.llm")
    messages = [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": "Turn on the light."},
    ]

    with caplog.at_level(logging.INFO, logger="test.llm"):
        log_llm_request(logger, model="test-model", messages=messages, json_mode=True)
        log_llm_response(logger, model="test-model", content='{"steps": []}')

    assert "LLM request (model=test-model, json_mode=True, messages=2)" in caplog.text
    assert "LLM prompt [1/2] role=system" in caplog.text
    assert "You are an agent." in caplog.text
    assert "LLM prompt [2/2] role=user" in caplog.text
    assert "Turn on the light." in caplog.text
    assert 'LLM response (model=test-model)' in caplog.text
    assert '{"steps": []}' in caplog.text
