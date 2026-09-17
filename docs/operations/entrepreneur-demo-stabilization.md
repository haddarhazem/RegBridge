# Entrepreneur demo stabilization

Research: **PAUSED**. The local demo provider is **Gemini 3.5 Flash-Lite** after
the bounded operational qualification recorded below. This is a demo-recovery
check, not a benchmark, provider comparison, corpus change or research decision.

## Runtime and synthetic data

The actual application is served by FastAPI at `http://127.0.0.1:8000`.
PostgreSQL, Keycloak, MinIO and ClamAV use the existing Compose services. The
backend is a separate uvicorn process, not a Compose backend/frontend service.
The current local PostgreSQL mapping is 25432; do not replace `.env` to match
historical documentation mentioning 55432.

The dedicated local account is `enersight-demo@regbridge.example`. Its generated
password exists only in the gitignored `.env.demo.local`; open that file locally,
never paste its contents into reports or commit it. The account was registered
through Keycloak and assigned the entrepreneur role through RegBridge onboarding.

`EnerSight Demo` was created through the UI. Its activity, sector, technology,
data, target market and location are confirmed synthetic declarations. Redundant
machine proposals were rejected through the fact-review controls, not silently
promoted. The original EnerSight projects were not changed. The demo copy was
transitioned through the product to `startup_in_creation` for compliance.

`Contrat EnerSight Demo` is an uploaded synthetic UTF-8 TXT, version 1. MinIO
storage, malware scanning and extraction ran normally. Successful contract
analysis returned eight evidence-locked observations through Gemini. Earlier
failed attempts remain visible in immutable analysis history; they are not
deleted or presented as successes.

## Defects reproduced in the running application

* Roadmap POST returned 200 with zero items. The assessment agent returned only
  prose while the assessment service consumed empty `findings`, recommendations
  and missing-information lists. Assessment generation now requests a typed
  structure and verifies **all** its text with the existing verifier. The existing
  assessment DTO and roadmap algorithm are retained. An empty structured
  assessment cannot create another empty roadmap and the UI points back to
  regulatory generation. No requirement is manufactured when evidence is absent.
* Compliance control PATCH returned 500: its response accessed an unloaded
  `definition`. The service now loads the definition and refreshed update timestamp
  before constructing the DTO, including in a fresh request session.
* Startup navigation repeatedly requested the idea-only onboarding endpoint,
  generating hidden 404s. Those requests are now limited to idea projects.
* Empty compliance history triggered a predictable latest-score 404. The frontend
  now uses its already-fetched chronological history to display the latest score.
* Contract analysis selected Mistral directly. It now uses the same configured
  `LLMProvider` selector as the rest of the development runtime; evidence resolution,
  immutable source versions and restricted public observations are unchanged.

Fullscreen failure was **not reproduced** with the current served assets. Real
clicks expanded the drawer from 460px to the full 1440px viewport and to 390px on
mobile. Hide/reopen and expand/reduce did not create another response request.
The old reloader left a child process holding port 8000; that verified child was
stopped and a single non-reloading backend was started. Served JS/CSS hashes were
checked against the working tree.

## Honest demo limitations

Compliance navigation is startup-only (`startup_in_creation` or `existing_startup`).
The backend service currently enforces active project membership and adoption,
not a lifecycle restriction. This work does not change those domain rules.

The shipped RGPD and AI Act baseline catalog versions have **zero control
definitions**. Adopting them therefore cannot demonstrate a meaningful score.
The calculation button now explains the missing-control prerequisite instead of
inviting an empty calculation. The actual scoring demo uses the **already existing
Synthetic Test Framework V1**, clearly a synthetic workflow demonstration, not a
claim that RegBridge has a populated RGPD compliance catalog. One applicable
control in progress with no completion evidence produced a persisted **0%** score
(0/1), which is the honest deterministic result.

The successful regulatory assessment contains sourced general energy-regulation
information and two conditional preparation recommendations. It does **not**
establish an unconditional obligation on the SaaS vendor. Its prose explains
missing coverage for software/privacy requirements. Do not relabel those
recommendations as mandatory obligations or invent evidence URLs. Some Copilot
retrievals contain irrelevant website-interface excerpts; the verified answer
acknowledges insufficient evidence. Retrieval research remains paused.

Gemini has returned upstream 429 and 500 responses during this operational pass.
Successful generation is not a reliability or legal-quality qualification.
Verification failures still block output. A 201 conversation response containing
a blocked-answer placeholder is **not** a successful AI answer for acceptance.

## Repeatable real-browser command

From the repository root, with the actual services already running:

```powershell
$env:DEMO_ACCEPTANCE='1'
python -m scripts.demo_acceptance presentation
```

The `presentation` harness logs in normally, uses the stable synthetic project,
loads its existing verified regulatory assessment and completed contract
analysis, generates only a new deterministic roadmap, changes an item and
reloads it, sends one real Copilot question, checks desktop/mobile fullscreen and
hidden completion, updates a real compliance control, calculates/reloads the
score and logs out. It never regenerates the assessment or contract analysis.
No intercepted responses or direct database writes are used. Network records
and screenshots are local ignored artifacts under `artifacts/browser-e2e/demo-*`.

Individual `setup`/`regulatory`, `roadmap`, `copilot`, `contracts` and `compliance`
stages exist for explicit operational diagnosis. `regulatory` and `contracts`
make real provider calls and preserve another result version/attempt. Do not run
them in a loop or mistake them for model qualification. Ordinary regression tests
use synthetic provider boundaries and are separate from this live acceptance.

The `post` stage performs the unaffected tail after a provider failure: it reloads
the already completed real contract analysis, recalculates/reloads compliance and
logs out. It does not make another LLM call and does not replace the required
uninterrupted `all` acceptance.

The historical `all`, `regulatory` and `contracts` stages intentionally create
new immutable provider-backed results and are diagnostic tools, not the reliable
presentation path. Do not use them immediately before a live presentation.

## Predictable backend startup

Use the guarded Windows helper from the repository root:

```powershell
.\scripts\start-demo.ps1
```

It verifies the existing Compose dependencies, refuses an unrelated port-8000
owner, starts one non-reloading Uvicorn process and waits for `/health`. If it
reports an existing confirmed RegBridge Uvicorn process, replace only that
process explicitly:

```powershell
.\scripts\start-demo.ps1 -ReplaceExistingRegBridge
```

Development responses for the landing, auth and Entrepreneur static assets carry
`Cache-Control: no-store`; production cache behavior is unchanged.

## Entrepreneur lifecycle/API matrix

| Frontend operation | Idea endpoint | Startup endpoint | General endpoint | Valid lifecycle(s) |
| --- | --- | --- | --- | --- |
| Create/select/read/update project | Existing `POST /projects/ideas` is not used by this UI | None | `POST/GET/PATCH /projects...` | All; creation payload starts at `idea` |
| Adaptive onboarding | `GET/PATCH /projects/{id}/onboarding` | None | None | `idea` only |
| Initial fact inference | `POST /projects/{id}/facts/infer` | None | None | `idea` only |
| Review confirmed/inferred facts | None | None | `/projects/{id}/facts...` | All, with active membership |
| Lifecycle transition/history | None | None | `/projects/{id}/transition`, `/lifecycle-history` | `idea → startup_in_creation → existing_startup` |
| Regulatory assessments | None | None | `/projects/{id}/assessments...` | All current project lifecycles |
| Launch roadmaps | None | None | `/projects/{id}/roadmaps...` | All current project lifecycles with a verified structured assessment |
| Documents and contract analysis | None | None | `/projects/{id}/documents`, `/documents/...` | All current project lifecycles with object authorization |
| Compliance controls and scoring | None | None | `/projects/{id}/compliance...` | Frontend: startup lifecycles; backend: active authorized membership |
| Startup profile | None | `/projects/{id}/startup-profile...` | None | `startup_in_creation`, `existing_startup` |

The startup UI no longer renders onboarding or inference controls that target
idea-only operations. No new `GET /ideas/...` endpoint was created: the general
project read contract already supplies the project data needed after transition.

## Gemini demo request governor

The configured Gemini adapter is a process-wide cached provider. Its request
boundary serializes generation, spaces calls from the **end** of the prior call,
and performs at most three attempts within a 90-second total budget. Retryable
429 and 500/502/503/504 responses use bounded backoff with jitter and honor
`Retry-After`. A daily quota classification fails immediately. A 429 that omits
quota details receives a conservative bounded 30-second cooldown; safe logs
contain only status/code/classification, retry timing and allowlisted quota
identifiers.

The measured pre-hardening sequence was: regulatory generation `HTTP 200`, then
semantic verification `HTTP 429` three times after approximately 3.0 and 6.3
seconds. Gemini returned no `Retry-After` or quota detail, so the exact quota
class remains `UNKNOWN`; the assessment correctly persisted as blocked. This
evidence justified longer response-to-request spacing and the bounded unknown-429
cooldown, but does not justify claiming that a hard or daily quota is solved.

A later blocked assessment does not erase an earlier verified version. The
Roadmap screen transparently selects the newest verified structured assessment,
identifies its version to the user, and keeps blocked attempts in history.

## Demo provider recovery — 2026-09-13

Official Gemini documentation lists `gemini-3.5-flash-lite` as a stable text
model supported by the Developer/Interactions API, including structured output;
the pricing table lists free-tier input and output. A bounded single-attempt
qualification passed in this order:

1. exact plain `OK` response: 10 tokens, 2.87 seconds;
2. tiny structured JSON plus local Pydantic validation: 23 tokens, 2.39 seconds;
3. the production `SemanticVerificationOutput` schema plus exact local Pydantic
   validation: verdict `pass`, 255 tokens, 2.72 seconds.

Because the first candidate passed all gates, `gemini-3.5-flash` was not called.
The local gitignored `.env` now selects `LLM_PROVIDER=gemini` and
`GEMINI_MODEL=gemini-3.5-flash-lite`; support for Gemini 3.8 remains in code.

The final `presentation` browser journey passed. It reused verified assessment
 v3 and the existing completed eight-observation contract analysis, generated
deterministic roadmap v9 with two items and persisted an item-status change,
then completed one Copilot turn with the required question, a visible
2,333-character answer and no
warnings. Closing, navigating and reopening preserved the response; desktop and
mobile fullscreen checks passed. Compliance recomputation persisted the honest
synthetic score of 0/1 (0%), followed by successful logout. The captured business
network had no 4xx/5xx response, failed transport or JavaScript exception.

The Copilot trace records exactly two successful Gemini operations using
`gemini-3.5-flash-lite`: answer generation (888 input, 268 output tokens) and
semantic verification (1,236 input, 322 output tokens). No regulatory assessment
or contract-analysis provider call occurred during the final presentation.

If the provider returns HTTP 429 in a future demo, the UI displays only:
`Le service IA a atteint sa limite temporaire. Réessayez dans quelques instants.`
Internal provider status, quota identifiers and error text remain hidden.

## Personal manual acceptance checklist

1. Open `http://127.0.0.1:8000/auth/login/`; hard-refresh once to load current assets.
2. Choose **Continuer avec votre organisation**. Sign in using the dedicated local
   demo credentials in `.env.demo.local`, then enter the Entrepreneur workspace.
3. Open **EnerSight Demo → Mon projet**. Confirm the six declarations and the
   **Startup en création** lifecycle. Do not change the original EnerSight.
4. Open **Réglementation**. Select the completed assessment version with sources
   and recommendations. Read its applicability and evidence limitations. A new
   generation must display a real result or an honest blocked/unavailable state.
5. Open **Roadmap de lancement → Nouvelle version**. Expect the two actual
   recommendation-derived steps. Reload; open the first step, change **Statut**,
   wait for saving, then reload again. Its status must remain.
6. Open **Copilote** and send **Quelles sont les principales obligations
   réglementaires pour EnerSight, et quelles informations manquent encore ?**
   Close it while loading and navigate to Roadmap. Reopen:
   the same question and its answer/loading/error state must remain.
7. Use the expand button, then reduce, close and reopen. Fullscreen must fill the
   viewport with reachable controls and input. Closing must not cancel; **Arrêter**
   is the explicit cancellation control. A quota/verification error is not success.
8. Open **Documents → Contrat EnerSight Demo**. Confirm version 1 is clean and
   ready. The source is immutable. Additional uploads must use synthetic files.
9. Open **Contrats** and inspect the completed analysis (failed historical attempts
   remain visible). Expect eight verbatim excerpts with categories and offsets,
   not risk ratings, signing advice or a legal certification. To generate again,
   select the exact version and click **Lancer l’analyse**; allow provider recovery
   if quota/unavailability is reported.
10. Open **Conformité**, choose **Synthetic Test Framework · V1**, activate it if
    necessary. Do not present this as a populated RGPD compliance framework.
11. Set the synthetic control to **En cours / Applicable**, save, then **Recalculer
    le score**. Expect **0%**, denominator 1, and its explanation. Reload and select
    the same framework: the immutable latest score remains.
12. Open browser console/network while doing these actions; report any uncaught
    exception or failing business request. Finally click **Se déconnecter**.

No commit, push or Jira update is part of this stabilization task.

## Final attempt status — 2026-09-12

The uninterrupted `all` journey is **NOT PASSED**. It generated roadmap v4 with
two items and verified status persistence, then the real Copilot generation
received an upstream Gemini HTTP 429. The browser received that failure as 429;
no fake response or deterministic success placeholder was substituted.

The follow-up `post` pass completed without another provider call: the browser
reloaded the real Gemini contract analysis (eight exact observations), saved a
compliance control, calculated and reloaded the persisted 0% score, and logged
out. It recorded zero uncaught JavaScript errors, failed transports, 4xx or 5xx.

Independent actual runs had already completed assessment generation and
verification, Copilot generation and verification with hidden completion,
contract extraction/analysis, and compliance update/calculation/persistence.
Those are not a substitute for the failed uninterrupted final acceptance.

Static validation: Python compilation, Entrepreneur app/views JavaScript syntax,
configured-secret comparison against changed sources/diff, and staged/unstaged
`git diff --check` passed. New focused regression cases were added but not run.
Focused/full regression remain **NOT RUN**, following the explicit requirement
to run them only after the final real-browser acceptance succeeds.

**Ready to commit: NO.** Required next steps: restore sufficient Gemini quota or
availability, rerun the real sequential acceptance, then execute focused and full
regression. Do not remove the verifier or change provider to manufacture a pass.

## Final runtime-hardening attempt — 2026-09-12

The backend now runs through `scripts/start-demo.ps1` as one non-reloading
Uvicorn process. The four Entrepreneur assets served by that process were
byte-for-byte identical to the working tree and carried development-only
`Cache-Control: no-store` headers.

The local-only browser stages passed after hardening:

- roadmap v7 was created through the real UI from verified structured assessment
  v3, with two persisted items and a persisted status change;
- the startup UI exposed zero idea-only onboarding/inference actions;
- the existing clean document and completed eight-observation contract analysis
  loaded normally;
- compliance control update and score calculation/reload persisted through the
  UI;
- logout completed;
- these passes recorded zero non-2xx business responses, failed transports or
  JavaScript exceptions.

The explicitly authorized uninterrupted Gemini run did not pass. Regulatory
retrieval returned five Qdrant results, but Gemini returned HTTP 429 on all three
generation attempts. The adapter waited approximately 30 seconds between each
attempt and failed closed after its bounded 90-second budget. The responses had
no provider error code/status, `Retry-After`, quota metric, quota ID, location or
model detail, so the safe classification remains `UNKNOWN`; it must not be
reported as a proven daily or request-rate quota. Assessment v5 was consequently
persisted as `failed/block` with no obligations, recommendations or sources.

Because the uninterrupted browser journey failed before Copilot, contracts and
compliance, the post-success regression gate was not opened. Focused/full tests,
compilation, standalone JS syntax, import-boundary scan, secret scan and
`git diff --check` remain intentionally not run for this final attempt.

A single authorized retry after the local date changed produced the same result:
assessment v6 failed closed after three HTTP 429 responses. The responses were
approximately 45 and 31 seconds apart once response-to-request spacing and the
unknown-quota cooldown were combined. They still contained no safe quota or
retry metadata. This rules out a short in-process request burst as the sufficient
cause, but does not provide enough evidence to distinguish a hard account quota,
model-specific quota or provider capacity limit. No further Gemini calls were
made.
