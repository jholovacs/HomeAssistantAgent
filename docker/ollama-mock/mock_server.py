"""Minimal Ollama API mock for integration tests."""

from __future__ import annotations

import json
from aiohttp import web

MODEL_NAME = "test-model"
TEST_ENTITY = "input_boolean.agent_test_switch"

EMPTY_PLAN = {
    "reasoning": "No action required.",
    "steps": [],
    "notify_user": False,
    "response_text": "Everything looks fine.",
    "summary_for_memory": "No changes needed.",
}

TURN_ON_PLAN = {
    "reasoning": "User requested the test switch be turned on.",
    "steps": [
        {
            "service": "input_boolean.turn_on",
            "target": {"entity_id": TEST_ENTITY},
            "data": {},
            "expected": {"entity_id": TEST_ENTITY, "state": "on"},
        }
    ],
    "notify_user": True,
    "response_text": "Turning on the agent test switch.",
    "summary_for_memory": "Turned on agent test switch.",
}


def _plan_for_messages(messages: list[dict]) -> dict:
    """Return a deterministic plan based on the last user message."""
    user_text = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            user_text = message.get("content", "").lower()
            break

    if "turn on" in user_text and "switch" in user_text:
        return TURN_ON_PLAN
    if "turn on" in user_text and "agent" in user_text:
        return TURN_ON_PLAN
    if TEST_ENTITY in user_text:
        return TURN_ON_PLAN
    return EMPTY_PLAN


async def handle_tags(_request: web.Request) -> web.Response:
    return web.json_response({"models": [{"name": MODEL_NAME}]})


async def handle_chat(request: web.Request) -> web.Response:
    body = await request.json()
    messages = body.get("messages", [])
    plan = _plan_for_messages(messages)
    content = json.dumps(plan)
    return web.json_response({"message": {"role": "assistant", "content": content}})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/api/tags", handle_tags)
    app.router.add_post("/api/chat", handle_chat)
    return app


def main() -> None:
    web.run_app(create_app(), host="0.0.0.0", port=11434)


if __name__ == "__main__":
    main()
