"""Explicit provider-neutral orchestration for the current RegBridge V1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.modules.ai.agents import Agent, AgentRegistry
from app.modules.ai.context import AuthorizedContextBuilder, ContextAuthorizationError
from app.modules.ai.contracts import (
    AgentRequest,
    AgentResult,
    IntentDecision,
    OrchestrationRequest,
    OrchestrationResult,
)
from app.modules.ai.schemas import AgentRunRequestTrace, AgentRunResponseTrace, TraceResourceRef, TraceSourceRef
from app.modules.ai.services import AgentRunService


class IntentClassifier(Protocol):
    async def classify(self, request: OrchestrationRequest) -> IntentDecision: ...


class DeterministicIntentClassifier:
    """Replaceable baseline; semantic model classification is future work."""

    _ALIASES = {
        "regulatory_and_contract": ["regulatory", "contract"],
        "regulatory": ["regulatory"],
        "contract": ["contract"],
    }

    async def classify(self, request: OrchestrationRequest) -> IntentDecision:
        hints = [request.intent_hint] if isinstance(request.intent_hint, str) else request.intent_hint
        capabilities: list[str] = []
        for hint in hints:
            for capability in self._ALIASES.get(hint.strip().lower(), []):
                if capability not in capabilities:
                    capabilities.append(capability)
        return IntentDecision(capabilities=capabilities)


class RoutingError(ValueError):
    pass


@dataclass(frozen=True)
class AgentSelection:
    capability: str
    agent: Agent


class Router:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    def route(self, decision: IntentDecision) -> list[AgentSelection]:
        selected: list[AgentSelection] = []
        seen: set[str] = set()
        for capability in decision.capabilities:
            if capability in seen:
                continue
            try:
                agent = self.registry.resolve(capability)
            except ValueError as exc:
                raise RoutingError(str(exc)) from exc
            selected.append(AgentSelection(capability=capability, agent=agent))
            seen.add(capability)
        return selected


class Aggregator:
    def aggregate(
        self,
        request: OrchestrationRequest,
        capabilities: list[str],
        results: list[AgentResult],
        failures: list[AgentResult],
    ) -> OrchestrationResult:
        if not capabilities:
            status = "unsupported"
        elif failures and results:
            status = "partial"
        elif failures:
            status = "failed"
        else:
            status = "succeeded"
        provenance = [
            f"{item.agent_name}:{item.capability}:{item.status}:{item.run_id}"
            for item in [*results, *failures]
        ]
        return OrchestrationResult(
            request_id=request.request_id,
            status=status,
            selected_capabilities=capabilities,
            results=results,
            failures=failures,
            provenance=provenance,
        )


class AgentContractError(RuntimeError):
    pass


class Orchestrator:
    """Sequential root/child execution using the SCRUM-182 trace service."""

    def __init__(
        self,
        *,
        classifier: IntentClassifier,
        router: Router,
        context_builder: AuthorizedContextBuilder,
        agent_run_service: AgentRunService,
        aggregator: Aggregator | None = None,
    ) -> None:
        self.classifier = classifier
        self.router = router
        self.context_builder = context_builder
        self.agent_run_service = agent_run_service
        self.aggregator = aggregator or Aggregator()

    @staticmethod
    def _trace_request(capability: str, request: OrchestrationRequest) -> AgentRunRequestTrace:
        refs = []
        if request.subject_type and request.subject_id:
            refs.append(TraceResourceRef(resource_type=request.subject_type, resource_id=request.subject_id))
        return AgentRunRequestTrace(intent=capability, locale=request.locale, context_refs=refs)

    async def _create_run(self, request: OrchestrationRequest, *, agent_name: str, capability: str, parent_run_id=None):
        run = await self.agent_run_service.create_run(
            request_id=request.request_id,
            parent_run_id=parent_run_id,
            user_id=request.principal.user_id if request.principal else None,
            agent_name=agent_name,
            capability=capability,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            request_payload=self._trace_request(capability, request),
        )
        await self.agent_run_service.start_run(run.id)
        return run.id

    async def run(self, request: OrchestrationRequest) -> OrchestrationResult:
        root_id = await self._create_run(request, agent_name="orchestrator", capability="orchestration")
        try:
            decision = await self.classifier.classify(request)
            try:
                selections = self.router.route(decision)
            except RoutingError:
                outcome = OrchestrationResult(request_id=request.request_id, status="unsupported", warnings=["No registered agent supports the requested intent"])
                await self.agent_run_service.succeed_run(root_id, self._root_trace(outcome))
                return outcome

            capabilities = [selection.capability for selection in selections]
            if not selections:
                outcome = OrchestrationResult(request_id=request.request_id, status="unsupported", warnings=["Intent is not supported"])
                await self.agent_run_service.succeed_run(root_id, self._root_trace(outcome))
                return outcome

            try:
                context = await self.context_builder.build(request, capabilities)
            except ContextAuthorizationError:
                outcome = OrchestrationResult(request_id=request.request_id, status="unauthorized", selected_capabilities=capabilities, warnings=["Context authorization denied"])
                await self.agent_run_service.fail_run(root_id, error_code="authorization_denied", error_message="Project context access denied")
                return outcome

            successes: list[AgentResult] = []
            failures: list[AgentResult] = []
            for selection in selections:
                agent = selection.agent
                capability = selection.capability
                child_id = await self._create_run(request, agent_name=agent.name, capability=capability, parent_run_id=root_id)
                agent_request = AgentRequest(
                    request_id=request.request_id,
                    parent_run_id=child_id,
                    question=request.question,
                    capability=capability,
                    locale=request.locale,
                    subject_type=context.subject_type,
                    subject_id=context.subject_id,
                    authorized_context=context,
                )
                try:
                    raw_result = await agent.run(agent_request)
                    if not isinstance(raw_result, AgentResult):
                        raise AgentContractError("Agent must return AgentResult")
                    result = raw_result.model_copy(update={"run_id": child_id})
                    if result.status == "succeeded":
                        successes.append(result)
                        await self.agent_run_service.succeed_run(child_id, self._agent_trace(result))
                    else:
                        failures.append(result)
                        await self.agent_run_service.fail_run(child_id, error_code=result.error_code or "agent_failed", error_message="Structured agent failure")
                except Exception:
                    failure = AgentResult(
                        agent_name=agent.name,
                        capability=capability,
                        status="failed",
                        run_id=child_id,
                        error_code="agent_execution_failed",
                        warnings=["Agent execution failed"],
                    )
                    failures.append(failure)
                    await self.agent_run_service.fail_run(child_id, error_code=failure.error_code or "agent_execution_failed", error_message="Agent execution failed")

            outcome = self.aggregator.aggregate(request, capabilities, successes, failures)
            await self.agent_run_service.succeed_run(root_id, self._root_trace(outcome))
            return outcome
        except Exception:
            try:
                await self.agent_run_service.fail_run(root_id, error_code="orchestration_failed", error_message="Orchestration failed")
            except ValueError:
                pass
            raise

    @staticmethod
    def _root_trace(result: OrchestrationResult) -> AgentRunResponseTrace:
        return AgentRunResponseTrace(summary="orchestration completed", result={"status": result.status, "result_count": len(result.results), "failure_count": len(result.failures)})

    @staticmethod
    def _agent_trace(result: AgentResult) -> AgentRunResponseTrace:
        source_refs = [
            TraceSourceRef(source_id=str(item.get("point_id", "")), chunk_id=str(item.get("point_id", "")))
            for item in result.evidence
            if item.get("point_id")
        ]
        return AgentRunResponseTrace(
            summary=f"{result.agent_name} completed",
            result={"status": result.status, "capability": result.capability, **result.structured_payload},
            source_refs=source_refs,
        )
