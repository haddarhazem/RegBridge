# SCRUM-213 security coverage matrix

This matrix maps the deterministic authorization tests already present in the
repository to the SCRUM-213 acceptance surface. Prompt-injection tests are
separate from this object-access matrix; model text never grants authority.

| Domain | Actor / relationship | Visibility or grant | Operation | Expected result | Test reference |
| --- | --- | --- | --- | --- | --- |
| Projects | owner or active member | private project | read/edit according to role | allowed | `tests/test_authorization.py`, `tests/test_scrum187_persistence.py` |
| Projects | unrelated, invited, revoked, anonymous | private project / guessed ID | read or mutate | denied | `tests/test_security_regressions.py`, `tests/test_scrum187_persistence.py` |
| Documents | owner | exact clean version | read/download | allowed | `tests/test_documents.py`, `tests/test_scrum208_research.py` |
| Documents | granted recipient | exact version and active grant | read | allowed | `tests/test_scrum197_sharing.py`, `tests/test_scrum212_access.py` |
| Documents | ungranted, revoked, anonymous, guessed/sibling version | private or shared | read/download | denied | `tests/test_documents.py`, `tests/test_scrum197_sharing.py`, `tests/test_scrum208_research.py` |
| Sharing | project manager | exact recipient/resource/scope/version | create/revoke | allowed | `tests/test_scrum197_sharing.py` |
| Sharing | recipient or unrelated user | different recipient/resource/scope/version | access/escalate/revoke | denied | `tests/test_scrum197_sharing.py`, `tests/test_scrum212_access.py` |
| Contracts | project owner/member | authorized project document | analyze/read | allowed | `tests/test_scrum193_contract_analysis.py` |
| Contracts | cross-project/ungranted/guessed actor | private source | analyze/read | denied, no source leak | `tests/test_scrum193_contract_analysis.py` |
| Compliance | active project member | own startup/project | controls/evidence/score | allowed | `tests/test_scrum194_compliance.py`, `tests/test_scrum195_scoring.py` |
| Compliance | other project/anonymous/guessed actor | private evidence | read/mutate | denied | `tests/test_scrum194_compliance.py`, `tests/test_scrum195_scoring.py` |
| Research | owner | private output/version | read/manage | allowed | `tests/test_scrum208_research.py` |
| Research | recipient | exact `DISCOVERY_READ` or `FULL_DOCUMENT_READ` grant | exact version access | allowed only for that scope/version | `tests/test_scrum212_access.py` |
| Research | cross-researcher/startup, pending, revoked, DRAFT/private | no matching grant | discovery/document access | denied | `tests/test_scrum210_discovery.py`, `tests/test_scrum211_matching.py`, `tests/test_scrum212_access.py` |
| AI boundary | any model output | any claimed role or instruction | authorize object/tool/RAG action | never authoritative | `tests/test_scrum213_security.py`, `tests/test_ai_orchestration.py` |

The matrix intentionally uses relationship- and resource-based authorization;
it does not introduce a global role shortcut.
