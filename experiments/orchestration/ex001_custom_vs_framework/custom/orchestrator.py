from __future__ import annotations

from ..common.classifier import DeterministicClassifier
from ..common.contracts import AgentExecutionRequest, AgentExecutionResult, ExperimentRequest, OrchestrationResult
from ..common.router import AgentRegistry, DeterministicRouter
from ..common.trace_adapter import TraceAdapter


class LightweightOrchestrator:
    def __init__(self, *, classifier: DeterministicClassifier, router: DeterministicRouter, context_builder, registry: AgentRegistry, trace: TraceAdapter) -> None:
        self.classifier = classifier
        self.router = router
        self.context_builder = context_builder
        self.registry = registry
        self.trace = trace

    async def run(self, request: ExperimentRequest) -> OrchestrationResult:
        root_id = await self.trace.create(request_id=request.request_id, agent_name="lightweight-orchestrator", capability="orchestration", parent_run_id=None)
        try:
            intent = self.classifier.classify(request)
            if not intent.capabilities:
                result = OrchestrationResult(request_id=request.request_id, status="unsupported", provenance=["classifier", "router"])
                await self.trace.succeed(root_id, AgentExecutionResult(agent_name="lightweight-orchestrator", capability="orchestration", status="succeeded", structured_payload={"status": result.status}))
                return result
            capabilities = self.router.route(intent)
            context = self.context_builder.build(request)
        except PermissionError as exc:
            result = OrchestrationResult(request_id=request.request_id, status="unauthorized", failures=["authorization_rejected"], provenance=["classifier", "router", "context_builder"])
            await self.trace.fail(root_id, "authorization_denied", str(exc))
            return result
        except ValueError:
            result = OrchestrationResult(request_id=request.request_id, status="unsupported", failures=["unsupported_capability"], provenance=["classifier", "router"])
            await self.trace.succeed(root_id, AgentExecutionResult(agent_name="lightweight-orchestrator", capability="orchestration", status="succeeded", structured_payload={"status": result.status}))
            return result

        results: list[AgentExecutionResult] = []
        failures: list[str] = []
        for capability in capabilities:
            agent = self.registry.resolve(capability)
            child_id = await self.trace.create(request_id=request.request_id, agent_name=agent.agent_name, capability=capability, parent_run_id=root_id)
            execution = AgentExecutionRequest(request_id=request.request_id, parent_run_id=root_id, intent=capability, authorized_context=context, locale=request.locale)
            result = agent.execute(execution)
            results.append(result)
            if result.status == "succeeded":
                await self.trace.succeed(child_id, result)
            else:
                failures.append(f"{capability}:{result.error_code or 'agent_failed'}")
                await self.trace.fail(child_id, result.error_code or "agent_failed", "controlled agent failure")
        status = "succeeded" if not failures else ("partial" if results and any(item.status == "succeeded" for item in results) else "failed")
        aggregate = OrchestrationResult(request_id=request.request_id, status=status, results=results, failures=failures, provenance=["classifier", "router", "context_builder"] + [item.agent_name for item in results])
        await self.trace.succeed(root_id, AgentExecutionResult(agent_name="lightweight-orchestrator", capability="orchestration", status="succeeded", structured_payload={"status": status, "result_count": len(results)}))
        return aggregate
