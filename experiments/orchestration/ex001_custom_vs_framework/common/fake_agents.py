from __future__ import annotations

from collections import Counter

from .contracts import AgentExecutionRequest, AgentExecutionResult


class FakeAgent:
    capability = ""
    agent_name = ""

    def __init__(self, failures: set[str] | None = None) -> None:
        self.failures = failures or set()
        self.invocations = Counter()
        self.received_contexts: list[AgentExecutionRequest] = []

    def execute(self, request: AgentExecutionRequest) -> AgentExecutionResult:
        self.invocations[self.capability] += 1
        self.received_contexts.append(request)
        if self.capability in self.failures:
            return AgentExecutionResult(
                agent_name=self.agent_name,
                capability=self.capability,
                status="failed",
                error_code="controlled_failure",
                warnings=["deterministic fixture failure"],
            )
        return AgentExecutionResult(
            agent_name=self.agent_name,
            capability=self.capability,
            status="succeeded",
            findings=[f"{self.capability} finding for {request.authorized_context.project_name}"],
            sources=[str(request.authorized_context.resource_id)],
            structured_payload={"capability": self.capability, "fixture": "controlled"},
        )


class RegulatoryFakeAgent(FakeAgent):
    capability = "regulatory"
    agent_name = "regulatory-fake"


class ContractFakeAgent(FakeAgent):
    capability = "contract"
    agent_name = "contract-fake"

