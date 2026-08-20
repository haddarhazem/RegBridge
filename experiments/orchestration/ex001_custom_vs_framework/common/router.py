from __future__ import annotations

from collections.abc import Mapping

from .contracts import Intent


class AgentRegistry:
    def __init__(self, agents: Mapping[str, object]) -> None:
        self._agents = dict(agents)

    def resolve(self, capability: str):
        try:
            return self._agents[capability]
        except KeyError as exc:
            raise ValueError(f"Unknown capability: {capability}") from exc


class DeterministicRouter:
    def route(self, intent: Intent) -> list[str]:
        supported = {"regulatory", "contract"}
        if any(capability not in supported for capability in intent.capabilities):
            raise ValueError("Unsupported capability")
        return list(intent.capabilities)

