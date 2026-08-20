# Results - EX-001

## Environment

- Python 3.12.6 on Windows 10.
- LangGraph 1.2.11.
- Experiment: EX-001, RQ-001, SCRUM-183.
- No external network, API key, provider, or LLM was used.
- Raw machine-readable output: `artifacts/experiments/EX-001/runs.json`.

## Scenario Results

| Scenario | Lightweight | LangGraph |
| --- | --- | --- |
| S1 single-agent success | PASS | PASS |
| S2 two-agent success | PASS | PASS |
| S3 partial failure | PASS: partial, success retained, failure identified | PASS: partial, success retained, failure identified |
| S4 unauthorized context | PASS: 0 body loads, 0 fake invocations | PASS: 0 body loads, 0 fake invocations |
| S5 trace hierarchy | PASS: one root and two children | PASS: one root and two children |

The shared suite ran 11 tests: `11 passed`.

## Objective Observations

| Observation | Lightweight | LangGraph |
| --- | ---: | ---: |
| Variant implementation LOC | 47 | 86 |
| Variant-specific source files | 1 | 1 |
| Direct orchestration dependencies | 0 | 1 (`langgraph==1.2.11`, optional research group) |
| Unauthorized resource body loads | 0 | 0 |
| Unauthorized fake-agent invocations | 0 | 0 |
| S2 trace runs | 3 | 3 |
| Trace hierarchy | Correct | Correct |

Both variants return the same Pydantic `OrchestrationResult` contract. S3
retains the successful regulatory result and explicitly records the
controlled contract failure. S4 rejects before the sensitive projection is
loaded. Trace payloads contain only SCRUM-182 allowlisted projections and not
the sentinel forbidden fixture body.

## Runtime Microbenchmark

Warm-up: 10 iterations. Measured iterations: 100. Median and p95 are local
orchestration overhead only, not end-to-end GenAI performance.

| Variant | Median | P95 |
| --- | ---: | ---: |
| Lightweight | 0.7793 ms | 1.2989 ms |
| LangGraph | 9.80315 ms | 11.9147 ms |

Runtime has weight 1 and did not determine the recommendation.

## Weighted Evaluation

Scores are 1 (poor) through 5 (excellent), and are structured engineering
judgment rather than objective scientific truth.

| Criterion | Weight | Lightweight score | Lightweight weighted | LangGraph score | LangGraph weighted | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Authorization control | 5 | 5 | 25 | 5 | 25 | Same explicit policy/context boundary; both loaded 0 forbidden bodies |
| Testability | 5 | 5 | 25 | 4 | 20 | Same deterministic suite; LangGraph adds graph harness |
| Traceability | 5 | 5 | 25 | 4 | 20 | Shared adapter preserved root/child/request correlation; LangGraph requires adaptation |
| Debuggability | 4 | 5 | 20 | 4 | 16 | Direct control flow versus graph-state conventions |
| Partial failure handling | 4 | 5 | 20 | 4 | 16 | Both passed S3; direct aggregation is more localized |
| Extensibility | 4 | 4 | 16 | 5 | 20 | Graph nodes/edges offer more workflow composition |
| Provider independence | 3 | 5 | 15 | 5 | 15 | Neither uses a provider or model |
| Implementation complexity | 3 | 5 | 15 | 3 | 9 | 47 versus 86 variant LOC; graph setup adds ceremony |
| Dependency footprint | 2 | 5 | 10 | 3 | 6 | No direct runtime dependency versus one optional framework dependency |
| Runtime overhead | 1 | 5 | 5 | 3 | 3 | 0.7793 ms versus 9.80315 ms median |
| **Total** | **36** |  | **176 / 180** |  | **150 / 180** |  |

## Error Analysis

No scenario failed. The main observed difference was not correctness but
mechanism: LangGraph required explicit state and conditional-edge adapters to
keep authorization outside framework behavior and map the graph execution to
SCRUM-182 runs. The custom prototype expressed the same boundary directly.

## Qualitative Observations

LangGraph has useful graph composition capability, but a feature existing in a
framework was not awarded value unless it helped the current controlled
workflow. Persistence/checkpointing was deliberately excluded because it
would create a competing state/trace mechanism.

## Unexpected Behavior

LangGraph's installed package brings transitive checkpoint/runtime packages,
although this experiment did not enable persistence or use them. The direct
dependency remains isolated in the optional `research` group.

## Limitations / Threats to Validity

- Fake agents are much simpler than future production agents.
- Only one framework was evaluated.
- The small workflow may favor lightweight code.
- Cyclic/stateful/human-in-the-loop workflows could change the result.
- Runtime excludes LLM and network latency.
- Developer familiarity influences qualitative complexity scores.
- A future framework version may change the conclusions.
- The runner uses the shared SCRUM-182-semantic in-memory adapter for
  deterministic comparison; the repository-backed adapter is provided for
  integration without creating a second trace implementation.

## Conclusion

Both candidates satisfied the controlled scenarios and security assertions.
For the current RegBridge workflow, the evidence supports LIGHTWEIGHT: it
preserves the same explicit authorization and trace guarantees with fewer
concepts, no direct orchestration dependency, lower measured overhead, and
more localized failure handling. This is a research recommendation only; no
production winner was implemented.
