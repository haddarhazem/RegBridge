from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ..common.classifier import DeterministicClassifier
from ..common.contracts import AgentExecutionRequest, AgentExecutionResult, ExperimentRequest, OrchestrationResult
from ..common.router import AgentRegistry, DeterministicRouter
from ..common.trace_adapter import TraceAdapter


class WorkflowState(TypedDict, total=False):
    request: ExperimentRequest
    root_id: object
    capabilities: list[str]
    context: object
    results: list[AgentExecutionResult]
    failures: list[str]
    outcome: OrchestrationResult


class LangGraphOrchestrator:
    def __init__(self, *, classifier: DeterministicClassifier, router: DeterministicRouter, context_builder, registry: AgentRegistry, trace: TraceAdapter) -> None:
        self.classifier = classifier
        self.router = router
        self.context_builder = context_builder
        self.registry = registry
        self.trace = trace
        graph = StateGraph(WorkflowState)
        graph.add_node("classify", self._classify)
        graph.add_node("route", self._route)
        graph.add_node("build_context", self._build_context)
        graph.add_node("execute_agents", self._execute_agents)
        graph.add_node("aggregate", self._aggregate)
        graph.add_edge(START, "classify")
        graph.add_edge("classify", "route")
        graph.add_conditional_edges("route", self._after_route, {"build_context": "build_context", "aggregate": "aggregate"})
        graph.add_conditional_edges("build_context", self._after_context, {"execute_agents": "execute_agents", "aggregate": "aggregate"})
        graph.add_edge("execute_agents", "aggregate")
        graph.add_edge("aggregate", END)
        self.graph = graph.compile()

    async def _classify(self, state: WorkflowState):
        intent = self.classifier.classify(state["request"])
        return {"capabilities": intent.capabilities}

    async def _route(self, state: WorkflowState):
        try:
            return {"capabilities": self.router.route(type("IntentState", (), {"capabilities": state["capabilities"]})())}
        except ValueError:
            return {"failures": ["unsupported_capability"]}

    def _after_route(self, state: WorkflowState):
        return "build_context" if state.get("capabilities") and not state.get("failures") else "aggregate"

    async def _build_context(self, state: WorkflowState):
        try:
            return {"context": self.context_builder.build(state["request"])}
        except PermissionError:
            return {"failures": ["authorization_rejected"]}

    def _after_context(self, state: WorkflowState):
        return "execute_agents" if state.get("context") else "aggregate"

    async def _execute_agents(self, state: WorkflowState):
        results, failures = [], list(state.get("failures", []))
        for capability in state["capabilities"]:
            agent = self.registry.resolve(capability)
            child_id = await self.trace.create(request_id=state["request"].request_id, agent_name=agent.agent_name, capability=capability, parent_run_id=state["root_id"])
            execution = AgentExecutionRequest(request_id=state["request"].request_id, parent_run_id=state["root_id"], intent=capability, authorized_context=state["context"], locale=state["request"].locale)
            result = agent.execute(execution)
            results.append(result)
            if result.status == "succeeded":
                await self.trace.succeed(child_id, result)
            else:
                failures.append(f"{capability}:{result.error_code or 'agent_failed'}")
                await self.trace.fail(child_id, result.error_code or "agent_failed", "controlled agent failure")
        return {"results": results, "failures": failures}

    async def _aggregate(self, state: WorkflowState):
        request = state["request"]
        results = state.get("results", [])
        failures = state.get("failures", [])
        if "authorization_rejected" in failures:
            outcome = OrchestrationResult(request_id=request.request_id, status="unauthorized", failures=failures, provenance=["classifier", "router", "context_builder"])
        elif not state.get("capabilities") or "unsupported_capability" in failures:
            outcome = OrchestrationResult(request_id=request.request_id, status="unsupported", failures=failures, provenance=["classifier", "router"])
        else:
            status = "succeeded" if not failures else ("partial" if any(item.status == "succeeded" for item in results) else "failed")
            outcome = OrchestrationResult(request_id=request.request_id, status=status, results=results, failures=failures, provenance=["classifier", "router", "context_builder"] + [item.agent_name for item in results])
        if outcome.status != "unauthorized":
            await self.trace.succeed(state["root_id"], AgentExecutionResult(agent_name="langgraph-orchestrator", capability="orchestration", status="succeeded", structured_payload={"status": outcome.status, "result_count": len(results)}))
        return {"outcome": outcome}

    async def run(self, request: ExperimentRequest) -> OrchestrationResult:
        root_id = await self.trace.create(request_id=request.request_id, agent_name="langgraph-orchestrator", capability="orchestration", parent_run_id=None)
        state = await self.graph.ainvoke({"request": request, "root_id": root_id, "results": [], "failures": []})
        if state["outcome"].status == "unauthorized":
            await self.trace.fail(root_id, "authorization_denied", "Resource access denied")
        return state["outcome"]
