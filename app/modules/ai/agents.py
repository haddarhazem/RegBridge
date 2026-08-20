"""Small provider-neutral agent boundary."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.modules.ai.contracts import AgentRequest, AgentResult


class Agent(Protocol):
    name: str
    capabilities: tuple[str, ...]

    async def run(self, request: AgentRequest) -> AgentResult:
        """Run against a validated DTO, never an ORM entity or DB session."""


class AgentRegistry:
    def __init__(self, agents: Iterable[Agent] = ()) -> None:
        self._by_capability: dict[str, Agent] = {}
        for agent in agents:
            self.register(agent)

    def register(self, agent: Agent) -> None:
        for capability in agent.capabilities:
            if capability in self._by_capability:
                raise ValueError(f"Capability already registered: {capability}")
            self._by_capability[capability] = agent

    def resolve(self, capability: str) -> Agent:
        try:
            return self._by_capability[capability]
        except KeyError as exc:
            raise ValueError(f"Unknown capability: {capability}") from exc

