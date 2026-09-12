# Entrepreneur demo stabilization

Research: **PAUSED**. Gemini: **functional development provider**. Qualification:
**DEFERRED**. No benchmark, provider comparison, corpus change or new research
decision is part of this work.

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
python -m scripts.demo_acceptance all
```

The harness logs in normally, uses the stable synthetic project, loads its actual
assessment, generates a new roadmap, changes an item and reloads it, sends one
real Copilot question, checks desktop/mobile fullscreen and hidden completion,
loads the actual uploaded contract analysis, updates a real compliance control,
calculates/reloads the score and logs out. No intercepted responses or direct
database writes are used. Network records and screenshots are local ignored
artifacts under `artifacts/browser-e2e/demo-*`.

Individual `setup`/`regulatory`, `roadmap`, `copilot`, `contracts` and `compliance`
stages exist for explicit operational diagnosis. `regulatory` and `contracts`
make real provider calls and preserve another result version/attempt. Do not run
them in a loop or mistake them for model qualification. Ordinary regression tests
use synthetic provider boundaries and are separate from this live acceptance.

The `post` stage performs the unaffected tail after a provider failure: it reloads
the already completed real contract analysis, recalculates/reloads compliance and
logs out. It does not make another LLM call and does not replace the required
uninterrupted `all` acceptance.

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
6. Open **Copilote** and send **Quelles obligations réglementaires principales
   concernent ce projet ? Précisez les informations manquantes et les limites des
   sources disponibles.** Close it while loading and navigate to Roadmap. Reopen:
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
