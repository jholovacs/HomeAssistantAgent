"""Tests for plan parsing."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "custom_components"))

from home_assistant_agent.agent.planner import Planner
from home_assistant_agent.llm.ollama import OllamaClient


@pytest.fixture
def planner():
    llm = OllamaClient("http://localhost:11434", "test")
    return Planner(llm, {})


def test_parse_valid_plan(planner):
    content = json.dumps(
        {
            "reasoning": "Turn on kitchen light",
            "steps": [
                {
                    "service": "light.turn_on",
                    "target": {"entity_id": "light.kitchen"},
                    "data": {},
                    "expected": {"entity_id": "light.kitchen", "state": "on"},
                }
            ],
            "notify_user": True,
            "response_text": "Turning on the kitchen light.",
            "summary_for_memory": "Turned on kitchen light.",
        }
    )
    plan = planner._parse_plan(content)
    assert plan.reasoning == "Turn on kitchen light"
    assert len(plan.steps) == 1
    assert plan.steps[0].service == "light.turn_on"
    assert plan.notify_user is True


def test_parse_blocks_disallowed_service(planner):
    content = json.dumps(
        {
            "reasoning": "Restart",
            "steps": [{"service": "homeassistant.restart", "target": {}, "data": {}}],
            "notify_user": False,
            "response_text": "",
            "summary_for_memory": "",
        }
    )
    plan = planner._parse_plan(content)
    assert plan.steps == []


def test_parse_allows_extra_domains_in_admin_mode():
    llm = OllamaClient("http://localhost:11434", "test")
    admin_planner = Planner(llm, {"admin_mode": True})
    content = json.dumps(
        {
            "reasoning": "Open garage",
            "steps": [{"service": "cover.open_cover", "target": {"entity_id": "cover.garage"}, "data": {}}],
            "notify_user": False,
            "response_text": "",
            "summary_for_memory": "",
        }
    )
    plan = admin_planner._parse_plan(content)
    assert len(plan.steps) == 1
    assert plan.steps[0].service == "cover.open_cover"


def test_parse_blocks_non_allowlisted_domain_without_admin_mode(planner):
    content = json.dumps(
        {
            "reasoning": "Reload config",
            "steps": [{"service": "reload.reload", "target": {}, "data": {}}],
            "notify_user": False,
            "response_text": "",
            "summary_for_memory": "",
        }
    )
    plan = planner._parse_plan(content)
    assert plan.steps == []


def test_parse_invalid_json(planner):
    plan = planner._parse_plan("not json at all")
    assert plan.steps == []
    assert "parse" in plan.reasoning.lower() or "Failed" in plan.reasoning


@pytest.mark.asyncio
async def test_plan_background_calls_llm(planner):
    planner._llm.chat = AsyncMock(
        return_value=json.dumps(
            {
                "reasoning": "No action needed",
                "steps": [],
                "notify_user": False,
                "response_text": "All good.",
                "summary_for_memory": "No changes.",
            }
        )
    )
    plan = await planner.plan_background(
        mission="Keep home efficient",
        preferences="",
        memory="",
        current_time="2026-07-01 12:00 UTC",
        diff="",
        snapshot="",
        automations="",
        scenes="",
        scripts="",
    )
    assert plan.reasoning == "No action needed"
    planner._llm.chat.assert_awaited_once()
