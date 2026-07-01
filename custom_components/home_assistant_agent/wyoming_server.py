"""Embedded Wyoming intent handle server."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from wyoming.handle import Handled, NotHandled
from wyoming.info import Attribution, Describe, HandleModel, HandleProgram, Info
from wyoming.intent import Recognize
from wyoming.ping import Ping, Pong
from wyoming.server import AsyncEventHandler, AsyncTcpServer

if TYPE_CHECKING:
    from .agent.loop import AgentLoop

_LOGGER = logging.getLogger(__name__)


class AgentWyomingHandler(AsyncEventHandler):
    """Wyoming handler that routes recognize events to the agent loop."""

    def __init__(
        self,
        reader,
        writer,
        agent_loop: AgentLoop,
        *,
        name: str = "Home Assistant Agent",
    ) -> None:
        super().__init__(reader, writer)
        self._agent_loop = agent_loop
        self._name = name

    async def handle_event(self, event) -> bool:
        if Describe.is_type(event.type):
            info = Info(
                handle=[
                    HandleProgram(
                        name=self._name,
                        description="Autonomous Home Assistant agent",
                        attribution=Attribution(
                            name="Home Assistant Agent",
                            url="https://github.com/jholovacs/HomeAssistantAgent",
                        ),
                        installed=True,
                        version="0.1.0",
                        models=[
                            HandleModel(
                                name="default",
                                languages=["en"],
                                attribution=Attribution(
                                    name="Home Assistant Agent",
                                    url="https://github.com/jholovacs/HomeAssistantAgent",
                                ),
                                installed=True,
                                description=None,
                                version="0.1.0",
                            )
                        ],
                        supports_handled_streaming=False,
                        supports_home_control=True,
                    )
                ],
            )
            await self.write_event(info.event())
            return True

        if Ping.is_type(event.type):
            ping = Ping.from_event(event)
            await self.write_event(Pong(text=ping.text).event())
            return True

        if Recognize.is_type(event.type):
            recognize = Recognize.from_event(event)
            text = recognize.text or ""
            if not text.strip():
                await self.write_event(NotHandled(text="No input received.").event())
                return True

            try:
                result = await self._agent_loop.run_conversation(text)
                response = result.response_text or "Done."
                await self.write_event(Handled(text=response).event())
            except Exception as err:
                _LOGGER.exception("Wyoming handle failed: %s", err)
                await self.write_event(
                    NotHandled(text="Sorry, I could not process that.").event()
                )
            return True

        return True


class WyomingServer:
    """Manages the embedded Wyoming TCP server lifecycle."""

    def __init__(
        self,
        agent_loop: AgentLoop,
        port: int,
        *,
        host: str = "0.0.0.0",
    ) -> None:
        self._agent_loop = agent_loop
        self._host = host
        self._port = port
        self._server = AsyncTcpServer(host, port)
        self._started = False

    @property
    def uri(self) -> str:
        return f"tcp://{self._host}:{self._port}"

    async def start(self) -> None:
        """Start the Wyoming server."""
        if self._started:
            return

        def handler_factory(reader, writer):
            return AgentWyomingHandler(reader, writer, self._agent_loop)

        await self._server.start(handler_factory)
        self._started = True
        _LOGGER.info("Wyoming server listening on %s", self.uri)

    async def stop(self) -> None:
        """Stop the Wyoming server."""
        if not self._started:
            return

        await self._server.stop()
        self._started = False
        _LOGGER.info("Wyoming server stopped")
