# SCRUM-214 Requirements-to-Test Matrix

SCRUM-214 is the current-release requirements-driven test pass. It reuses the
completed feature tests and does not introduce a research experiment. SCRUM-196
is intentionally excluded: `FUTURE_PERSPECTIVE / POST-MVP / OUT_OF_CURRENT_RELEASE_SCOPE`.

## Scope and levels

The repository has a backend/API E2E boundary. Tests that use `httpx` against
the FastAPI application are contract/API E2E; service tests remain unit or
integration tests and are not counted as actor E2E by themselves. PostgreSQL
is the repository test database and all fixtures use generated UUIDs/emails.

| Ticket / requirement | Production component | Test level and evidence | Status | CI critical |
|---|---|---|---|---|
| SCRUM-176/177/178/179/180/181 | identity, projects, documents, audit, conversations | `test_authentication.py`, `test_authorization.py`, `test_documents.py`, `test_audit.py`, `test_ai_trace_contracts.py` | COVERED | Yes |
| SCRUM-182/183 | conversations, orchestrator, trace contracts | `test_ai_orchestration.py`, `test_ai_services.py`, `test_scrum182_evidence.py`, `test_scrum183_trace_integration.py` | COVERED | Yes |
| SCRUM-184/185/186 | regulatory QA, verification, observability | `test_scrum184_agent.py`, `test_scrum184_retrieval.py`, `test_scrum185_verification.py`, `test_scrum186_observability.py` | COVERED | Yes |
| SCRUM-187/188 | onboarding, facts and trusted context | `test_scrum187_onboarding.py`, `test_scrum187_persistence.py`, `test_scrum188_facts.py`, `test_scrum188_persistence.py` | COVERED | Yes |
| SCRUM-189/190/191/192 | assessments, roadmaps, lifecycle, startup profile | `test_scrum189_assessment.py`, `test_scrum190_roadmap.py`, `test_scrum191_lifecycle.py`, `test_scrum192_profile.py` | COVERED | Yes |
| SCRUM-193/194/195 | contract safety, compliance, deterministic score | `test_scrum193_contract_analysis.py`, `test_scrum194_compliance.py`, `test_scrum195_scoring.py` | COVERED | Yes |
| SCRUM-197/198/199/200 | grants, investor thesis, startup search, opportunities | `test_scrum197_sharing.py`, `test_scrum198_investment.py`, `test_scrum199_search.py`, `test_scrum200_investment_opportunities.py` | COVERED | Yes |
| SCRUM-201/202 | events and consent-gated contact | `test_scrum201_events.py`, `test_scrum202_contact_requests.py` | COVERED | Yes |
| SCRUM-203/204/205/206/207 | matching, briefs, verification, versioning and sharing | `test_scrum203_matching.py`, `test_scrum203_matching_verification.py`, `test_scrum204_brief_generation.py`, `test_scrum205_verification.py`, `test_scrum206_brief_versions.py`, `test_scrum207_export_sharing.py` | COVERED | Yes |
| SCRUM-208/209/210 | research deposits, extraction and approval | `test_scrum208_research.py`, `test_scrum209_extraction.py`, `test_scrum210_discovery.py`, `test_scrum210_postgres_api_e2e.py` | COVERED | Yes |
| SCRUM-211/212 | research matching, scope-independent access and revocation | `test_scrum211_matching.py`, `test_scrum212_access.py` | COVERED | Yes |
| SCRUM-213 | deterministic authorization and prompt-injection regressions | `test_scrum213_security.py`, `test_security_regressions.py` | COVERED | Yes |
| Visitor actor journey | health, anonymous regulatory QA, source serialization, minimized anonymous trace | `test_health.py`, `test_scrum184_agent.py`, `test_ai_trace_contracts.py` | COVERED | Yes |
| Entrepreneur actor journey | authenticated idea project, onboarding resume, facts, assessment, roadmap, lifecycle | `test_scrum187_persistence.py`, `test_scrum188_persistence.py`, `test_scrum189_assessment.py`, `test_scrum190_roadmap.py`, `test_scrum191_lifecycle.py` | COVERED | Yes |
| Startup actor journey | existing-startup profile visibility, document/contract/compliance and sharing | `test_scrum192_profile.py`, `test_documents.py`, `test_scrum193_contract_analysis.py`, `test_scrum194_compliance.py`, `test_scrum197_sharing.py` | COVERED | Yes |
| Investor actor journey | thesis, search, opportunity, event/contact, matching and brief lifecycle | `test_scrum198_investment.py` through `test_scrum207_export_sharing.py` | COVERED | Yes |
| Researcher actor journey | profile, deposit/version, extraction, approval, matching and access | `test_scrum208_research.py` through `test_scrum212_access.py` | COVERED | Yes |

## Deterministic and negative coverage

The suite asserts project-fact trust/precedence, onboarding selection,
visibility projections, grant scopes, compliance score, matching, brief
verification, research uncertainty and access-state transitions. Negative
cases cover pending facts, revoked evidence, private-field leakage, scope
broadenings, UNKNOWN/MISMATCH confusion, draft research, IDOR and stale or
future version access.

## External boundaries and fixtures

CI uses an ephemeral PostgreSQL service and runs `alembic upgrade head` before
tests. Object-storage behavior is exercised with deterministic adapters and
generated document content. Live Mistral and Qdrant checks are optional and
never required by CI; no credentials or production data are used. No external
contract or research paper was required to complete the deterministic suite.

## CI failure propagation

`.github/workflows/ci.yml` runs the full suite, an explicit release-critical
suite, and the security regression suite. Each uses pytest's exit status, so a
failure exits the workflow non-zero. The critical command is intentionally
limited to deterministic/local tests and does not require provider or Qdrant
credentials.

## SCRUM-196

`FUTURE_PERSPECTIVE / POST-MVP / OUT_OF_CURRENT_RELEASE_SCOPE`.

Current-release test obligation: NONE. Current-release release blocker: NO.
`RQ-014` is deferred with the future feature. No polling, monitoring,
change-impact or notification behavior is claimed or tested here.
