# RegBridge Entrepreneur Full Recovery Report

Validation completed locally on 2026-09-12. This is operational recovery, not
Gemini qualification. No benchmark, Jira update, commit or push was performed.

## 1. Root-Cause Matrix

| Symptom | Root cause | Layer | Fix | Regression | Status |
| --- | --- | --- | --- | --- | --- |
| Undefined `.map()` | Regulatory view destructured `versions`, while state supplied `assessments` | Frontend contract | Explicit property mapping | Populated assessment JS test; real browser navigation | Fixed |
| Mon projet fails | Original exception not reproduced on current tree; no evidence of the same cause | Frontend/API | Current response shape and long data rendering verified | JS rendering, real browser and context audit | Pass now; historical attribution unproven |
| Roadmap fails | Original exception not reproduced; malformed non-null roadmap was not rejected at boundary | API client | Validate required id/items; preserve legitimate null empty state | Null/malformed/populated tests; browser | Pass |
| Old messages in fresh chat | Automatic latest persisted thread selection confused history with active state | Copilot UI | Lazy new thread, explicit Historique/Nouvelle conversation | Real persisted history, refresh and relogin | Fixed |
| Arrêter ineffective | Cancellation did not reliably own/clear the full preparation/response lifecycle | Copilot UI | AbortController across preparation and generation; object/controller stale-result guards | Stop before thread, late reply, send again, close, navigation, project switch, logout | Pass |
| Stuck spinner | Component display style overrode HTML hidden; synchronous retrieval also blocked the event loop | CSS/backend | Scoped hidden rule, flexible drawer layout, bounded request/body reads, worker-thread sync retrieval | Browser idle/finished states; retrieval thread test | Fixed |
| Context unverifiable | Name/type-only presentation | Frontend | Deterministic confirmed-field count and expandable values | Six-field browser fixture; actual DB/API/ContextBuilder audit | Fixed |
| Gemini Copilot unavailable | Full generation returned HTTP 200 but incomplete at 900-token cap; conversation creation also hit async ORM/projection defects | Provider/config/API | Bounded configurable caps; local 4000/4000; explicit ConversationResponse projection | Fail-closed adapter tests; real DB route; direct and real browser Gemini success | Pass |

No wholesale normalization, authentication bypass, provider failover, retrieval
strategy change, or semantic-verifier weakening was introduced.

## 2. Runtime

| Service | Result | Current endpoint |
| --- | --- | --- |
| PostgreSQL | PASS | 127.0.0.1:25432 |
| Keycloak | PASS | 127.0.0.1:18080 |
| Backend/database health | PASS, HTTP 200 | http://127.0.0.1:8000/health |
| Frontend/static | PASS, HTTP 200 | http://127.0.0.1:8000/entrepreneur/ |
| MinIO | PASS, HTTP 200 | 127.0.0.1:19000; console 19001 |
| ClamAV | Running; document upload accepted | 3310 |
| Qdrant | PASS, read-only | Existing configured cloud collection |
| Gemini | PASS, real calls | Existing configured provider |

Effective provider: **gemini**. Model: **gemini-3.8-flash**.
The API was restarted to refresh cached settings. Existing local services were
used; PostgreSQL/Keycloak data were not recreated.

Applied migration: `runtime_context_bounds`, matching repository heads.
CI's stale `self_service_auth` comparison now compares actual versus repository
heads, preserving failure on an unapplied revision. Local comparison passed;
GitHub Actions itself was not run.

Qdrant starting/ending/final count: **47,881 / 47,881 / 47,881**.
No Qdrant writes were performed. Count equality alone is not a complete corpus
content checksum.

## 3. Frontend Recovery

Fatal reproduced property: `versions` in `views.regulatory`, supplied through
`assessments` in application state. This was a frontend assumption bug, not
proof that every historical page error had the same source.

Dashboard, Mon projet, Roadmap, Documents, Réglementation, Contrats and Équipe &
accès: **PASS**. Compliance's existing real-browser journey also passed.
Uncaught JavaScript errors in the successful recovery/browser journeys: **0**.

Bootstrap contract review:

| API family | Expected shape | Handling |
| --- | --- | --- |
| Current user | Authenticated user object | Existing OIDC/current-user mechanism |
| GET /projects | Array of project summaries | Array remains required |
| GET /projects/:id | Project object | Required authorized object |
| GET /projects/:id/onboarding | Onboarding object | Confirmed dimensions preserved |
| GET /projects/:id/facts | Array | Required collection |
| GET /projects/:id/assessments/latest | Assessment or legitimate empty response | Existing optional handling |
| GET /projects/:id/assessments | Array | Correctly passed as assessments to view |
| GET /projects/:id/roadmaps/latest | Roadmap object or null | Null is empty state; malformed non-null is error |
| GET /projects/:id/documents | Array | Version/analysis collections loaded through existing endpoints |
| GET /projects/:id/members | Array | Existing object authorization |
| Compliance frameworks/controls/history | Arrays; latest score optional | Existing startup-only workflow |
| GET /conversations | Array | Requested only for explicit history |
| POST /conversations | ConversationResponse object | Explicit safe projection; no async lazy assignment |
| POST /conversations/:id/responses | Persisted user/assistant turn | HTTP 201 used directly, no unbounded follow-up fetch |

Non-404 failures are no longer silently converted into optional empty state.
The final sanitized browser inventory recorded GET project/fact/document/member/
assessment collections as HTTP 200 arrays; onboarding/project objects as HTTP 200;
latest roadmap and latest assessment as HTTP 200 null; conversation creation and
turn responses as HTTP 201 objects. It is retained locally in
`artifacts/browser-e2e/recovery-bootstrap-contracts.json` without response values,
credentials or query strings. Compliance and auth coverage come from their
separate existing journeys, not this inventory.
Safe French errors distinguish validation, authorization, missing resource,
conflict, rate limit, timeout, cancellation and service/network failure.
API body parsing remains inside its timeout window.

Screenshots inspected at 1440x900 and 390x844 show usable input/history controls,
no idle spinner and no horizontal page overflow. This is not an exhaustive
responsive/accessibility certification.

## 4. EnerSight Context

The local database contains **two separate projects named EnerSight**. One has
only activity confirmed; it was not silently merged or filled. The complete
project has:

| Field | Confirmed | Length | DB to API to ContextBuilder |
| --- | --- | --- | --- |
| Activity | YES | 157 | PASS |
| Sector | YES | 21 | PASS |
| Technology | YES | 444 | PASS |
| Data | YES | 572 | PASS |
| Market | YES | 6 | PASS |
| Location | YES | 21 | PASS |

All six confirmed: **YES**, for the complete record.
Data remains within the current 2,000-character contract.
ContextBuilder: **PASS**. Context visible/verifiable in UI: **YES**.

The real record was audited read-only without printing its values. Browser/AI
tests used a separate synthetic EnerSight-like project, not the real owner's
login or private documents. The 572-character rendering has an independent JS
regression; browser context-count coverage uses the synthetic six-field fixture.

## 5. Conversation Lifecycle

Historical messages preserved: **YES**.
Fresh active thread: **PASS**.
Old message automatically injected: **NO**.
Project switching: **PASS**.
Logout transient-state cleanup: **PASS**.
Cross-project and cross-user isolation: **PASS** in targeted authorization,
conversation/context and browser regressions.

Opening the drawer is idle and does not create or select a persisted thread.
First send creates the thread. Explicit history restores only the selected
authorized project conversation. Closing a completed drawer retains its active
in-session exchange; a reload/relogin starts fresh. New conversation and project
changes reset transient state without deleting history.

## 6. Copilot Cancellation

Arrêter: **PASS**.
Browser request aborted: **YES**.
Loading cleared/input restored: **YES / YES**.
Late response ignored: **YES**.
Send after cancellation: **PASS**.
Server cancellation: **NO guarantee**.
Upstream Gemini cancellation: **NOT SUPPORTED by the current flow**.

The dedicated race tests hold the AI HTTP boundary to deterministically test
late results. They do not claim to interrupt a real Gemini computation.
An already-started server operation can still finish and persist a valid answer
in its original thread. The UI abandons that active thread and ignores its late
result. No fabricated assistant cancellation/failure message is persisted.

## 7. AI Pipeline

Provider/model: **gemini / gemini-3.8-flash**.
ContextBuilder, SCRUM-183 orchestrator, RegulatoryAgent: **PASS**.
Selected capability: **regulatory**.
BGE-M3: **PASS**, **1,024 dimensions**.
Qdrant: **PASS**, **top_k=5**, **5 evidence chunks**.
Generation: **PASS**.
SemanticVerifier: **PASS**.
AgentRun correlation/persistence: **PASS**.
Real browser Copilot response: **HTTP 201**, exact answer persisted.

The successful browser turn's generation took approximately **5.592 s**, verifier
**6.049 s**. Input tokens: **42,054**; output tokens: **1,458**.
Cost: **not available**. These stage times are not end-to-end browser latency.

The separate successful direct pipeline took **17.595 s** after initialization.
Generation used 1,037 output tokens: the former 900-token setting was insufficient
for that completed response. Both new settings remain bounded (maximum 4000),
defaults remain 900, and only the local Gemini recovery configuration uses 4000.
Incomplete/empty output remains rejected. There is no silent alternate provider.

Earlier incomplete full-turn failures are retained as negative evidence; a
successful minimal request alone did not prove the full pipeline.
The browser verifier reported three supported aggregate claims and zero
structural issues. This is not exhaustive clause-level legal validation.

## 8. User-Visible Copilot Answer

Exact persisted answer also checked against the browser DOM:

Sur la base exclusive des éléments réglementaires fournis (qui portent sur les tableaux de sanctions prononcées par la CNIL en 2023 et 2025) :

### Informations réglementaires générales issues des sources disponibles
Les délibérations de la CNIL rappellent plusieurs obligations et principes clés dont le non-respect a conduit à des sanctions :
* **Données personnelles :**
  * Obligation de traiter les données de manière licite, respect d'une base légale (notamment art. 6-1 et art. 7 du RGPD pour la preuve du consentement, ou règles de prospection commerciale par voie électronique).
  * Principe de minimisation des données et limitation des finalités (ne pas détourner l'usage des données).
  * Obligation de transparence et d'information des personnes concernées.
  * Respect des droits des personnes : droit d'accès, droit d'opposition, droit à l'effacement et retrait du consentement.
  * Respect de durées de conservation limitées des données.
  * Encadrement juridique des relations contractuelles entre responsable de traitement et sous-traitant (notamment l'interdiction de sous-traiter sans autorisation).
  * Tenue d'un registre des activités de traitement.
  * Réalisation d'une analyse d'impact (AIPD) le cas échéant.
  * Rôle et désignation du délégué à la protection des données (DPO), lorsqu'applicable.
  * Coopération obligatoire avec l'autorité de contrôle (la CNIL).
* **Sécurité des données et de la plateforme :**
  * Obligation de sécurité des données (sanction des défauts de sécurité).
  * Gestion des incidents : obligation de documenter les violations de données, de les notifier à l'autorité de contrôle et de les communiquer aux personnes concernées.
  * Gestion des cookies et traceurs (exigence de recueil du consentement et d'information).
* **Intelligence artificielle :**
  * Les sources disponibles sont **insuffisantes** pour identifier des obligations réglementaires spécifiques applicables à l'intelligence artificielle (ex. règlement européen sur l'IA / AI Act). Les extraits mentionnent uniquement des logiciels spécialisés dans le cadre de sanctions CNIL (ex. reconnaissance faciale, aide au recrutement) sans détailler de cadre réglementaire IA dédié.

---

### Implications pour le projet EnerSight
* **Données traitées (coordonnées professionnelles, factures énergétiques, compteurs) :** EnerSight doit veiller à définir des finalités explicites, s'assurer d'une base légale adéquate, informer clairement les utilisateurs et limiter les données collectées au strict nécessaire (minimisation), tout en encadrant leurs durées de conservation.
* **Sécurité de la plateforme SaaS :** EnerSight doit mettre en œuvre des mesures de sécurité adaptées pour éviter les défauts de sécurité, tenir un registre des traitements, prévoir des procédures de documentation/notification en cas de violation de données et formaliser les contrats de sous-traitance le cas échéant.
* **Composante IA :** Les sources fournies ne permettent pas de préciser les obligations spécifiques liées au développement ou à l'intégration de l'IA pour EnerSight.

---

*Avertissement : RegBridge fournit des informations réglementaires générales et ne remplace pas un avocat, un conseil en propriété industrielle, un expert-comptable ou une autorité compétente. Ce service ne constitue pas une certification officielle.*

User-visible sources: **CNIL** (one organization; duplicates removed).
Technical point IDs, chunk indexes and scores are retained internally, not in
the public sources. No public source URL was added: the existing contract is
organization-only.

Personalization: **PERSONALIZED** to the synthetic authorized EnerSight data.
Single-answer evidence inspection identified:

- Fabricated citations: **0**.
- Unsupported critical claims: **0 identified against retrieved excerpts**, subject to the applicability caveat below.
- Contradictions: **0 identified**.
- Invented EnerSight facts: **0 identified**.
- Private leakage: **0 observed**.

Qualification caveat: the incident notification/communication bullet does not
state applicability thresholds. The retrieved material is CNIL sanctions tables,
not a comprehensive applicability analysis. This caveat and the limited AI-law
coverage must not be hidden by the verifier's PASS. These are single-answer
inspection results, not benchmark metrics or human legal approval.

## 9. Browser Acceptance

Login, Entrepreneur navigation, Mon projet, Roadmap, fresh Copilot thread,
generation, cancellation and logout/relogin: **PASS**.
Uncaught JavaScript errors: **0** in successful acceptance runs.

- Six dedicated non-live recovery/race cases passed.
- One real live Gemini browser turn passed, with exact persistence and sources.
- Three additional existing browser journeys passed: critical journey/persistence,
  cross-user denial and compliance.
- One existing document upload/version/reload browser journey passed. Its name
  mentions extraction, but its assertions do **not** prove worker completion.

The non-live cancellation fixtures never call a model. Synthetic accounts and
projects created by the browser harness remain local; original user history was
not deleted. The direct live fixture cleans only its own synthetic records.

## 10. Regression

| Check | Result |
| --- | --- |
| Focused frontend/projects/context/Copilot/provider/verifier/auth suite | **93 passed** |
| Executable Node frontend contracts | **3 passed** |
| Full regression | **363 passed, 21 skipped** |
| Real named EnerSight read-only projection audit | **1 passed** |
| Live provider plain and structured connectivity | **1 passed (2 requests)** |
| Direct live Copilot | **1 passed** |
| Dedicated non-live browser recovery | **6 passed** |
| Real live browser Copilot | **1 passed** |
| Existing critical journey, cross-user denial, compliance | **3 passed** |
| Existing document upload/version/reload | **1 passed** |
| Python compilation, JS syntax | **PASS** |
| Production app import and no app-to-experiments import | **PASS** |
| Secret scan | **PASS**: no private configured credential match; public development default matches reviewed |
| git diff --check | **PASS** |

The extra five skips are the newly added explicitly opt-in browser race cases.
One final regression attempt encountered eight Windows shared-temp permission
errors (355 passed/16 skipped); the isolated-temp rerun above passed. No tests
were disabled to obtain the passing result. One targeted invocation used a
nonexistent historical test filename; it ran no tests and was corrected before
the passing 93-test run. Initial browser fixture failures were corrected, not
counted as successful runs.

Commands actually executed across the recovery include:

```powershell
docker compose up -d minio minio-init clamav
docker compose ps --format '{{.Service}} {{.State}} {{.Ports}}'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --reload --reload-dir app
python -m alembic current
python -m alembic heads
python -m pytest tests/test_entrepreneur_recovery_live.py -q
python -m pytest tests/test_entrepreneur_live_copilot.py -q
python -m pytest tests/test_entrepreneur_context_audit.py -q -s -p no:cacheprovider --tb=short
python -m pytest tests/e2e/browser/test_copilot_recovery.py -k 'not live_browser' -q -p no:cacheprovider --tb=short
node --test tests/frontend-recovery.test.cjs
python -m pytest -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider --basetemp $recoveryTemp --tb=short
python -m compileall -q app
node --check frontend/entrepreneur/app.js
node --check frontend/entrepreneur/api.js
node --check frontend/entrepreneur/views.js
node --check frontend/auth/auth-runtime.js
git diff --check
```

Live commands used explicit `ENTREPRENEUR_LIVE=1`; the context audit used
`ENTREPRENEUR_CONTEXT_AUDIT=1`; browser commands used a disposable generated
password and local base URL. `$recoveryTemp` was a new unique directory under the
Windows temporary directory, not an existing directory selected for deletion.
Read-only HTTP/collection checks and in-memory known-secret/import audits were
also executed. Exact rerunnable opt-in instructions are in
`docs/runbooks/automated-validation.md`.

## 11. Remaining Issues

- No currently reproduced runtime blocker in the tested Entrepreneur journey.
- Original Mon projet/Roadmap historical stack traces were not recovered; current
  passing behavior does not establish their exact historical cause.
- Upstream/server cancellation is not guaranteed.
- Retrieval returned five largely overlapping CNIL sanctions excerpts, offering
  narrow legal coverage and no sufficient AI Act evidence. Corpus/vector/query
  strategy was intentionally not changed.
- Single-answer PASS does not qualify Gemini; output applicability nuance,
  cost, latency and safety still require the deferred qualification gate.
- The second incomplete EnerSight project remains distinct and unchanged.
- Document extraction worker completion and exhaustive viewport/keyboard testing
  were not proven by this recovery's document/UI checks.
- CI logic was checked locally; no remote CI run was triggered.

## 12. Final Verdict

Entrepreneur application recovered: **YES for the tested recovery scope**.
Manual Gemini Copilot usable: **YES**.
Ready for developer manual review: **YES**.
Ready to resume Gemini qualification benchmark: **YES, as a separate authorized task**.
Ready to commit: **YES for recovery changes after review; no commit performed**.
Ready to move to Researcher frontend: **NO until developer review and the deferred Gemini qualification decision**.

Gemini is **not declared production-qualified** by this report.
