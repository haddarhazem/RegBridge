# Frontend and User Journeys

## Frontend architecture

The current UI is framework-free static HTML, CSS, and JavaScript served by FastAPI from `frontend/`. There is no required Node build step for runtime. JavaScript calls the API directly and relies on shared browser-side auth/session helpers.

Major areas:

| Path | Experience |
| --- | --- |
| `frontend/index.html`, `main.js`, `motion.js`, `styles.css` | Public landing page and motion narrative |
| `frontend/auth/` | Login, registration entry, callback, onboarding, workspace selection |
| `frontend/entrepreneur/` | Entrepreneur/startup authenticated workspace |
| `frontend/investor/` | Investor authenticated workspace |

The researcher domain has backend functionality but not a complete equivalent browser workspace.

## Authentication journey

```text
Landing CTA
  -> /auth/login/ or /auth/register/
  -> configured OIDC provider
  -> /auth/callback/
  -> current-user refresh
  -> role onboarding when required
  -> one workspace directly, or workspace chooser
```

Rules:

- One account can hold several business roles.
- Do not put a role selector on the login form.
- Do not create fake social-provider buttons.
- Preserve and validate same-origin `returnTo`; reject open redirects.
- An authenticated user should not remain on the login page.
- Tokens remain in `sessionStorage`; protected data must disappear on logout.

## Landing page

The landing page uses a dark monochrome visual system, persistent technical background, sticky narrative sections, panel morphing, and scroll-linked transitions. Content must remain exclusive and readable:

- one heading per scene;
- one panel content layer at a time;
- one role description at a time;
- floating signals must not cover primary copy;
- reduced-motion mode must retain all information.

Visual refinements should not change backend/API contracts.

## Entrepreneur workspace

The entrepreneur application is project-centered. Current navigation includes:

- overview/dashboard;
- project profile and knowledge graph;
- launch roadmap;
- regulatory view;
- documents;
- contracts;
- compliance for eligible startup-stage projects;
- access/collaboration;
- profile;
- project-aware Copilot.

Important files include `frontend/entrepreneur/app.js`, `api.js`, `store.js`, `views.js`, `knowledge-graph.js`, and `entrepreneur.css`.

The active project controls queries and Copilot context, but the browser-provided project ID is never sufficient authorization; the API rechecks access.

## Investor workspace

Current investor navigation includes:

- dashboard;
- thesis/profile;
- startup discovery;
- matches;
- briefs;
- opportunities;
- events;
- connections/contact requests;
- profile.

Views use investor read APIs and visibility-aware backend services. Never reveal a startup/project solely because its ID appears in the browser.

## Documents and contracts journey

```text
Upload supported file
  -> version created
  -> scan and content validation
  -> extraction job
  -> ready/failed/quarantined state
  -> exact version selected
  -> contract analysis launched
  -> partial/completed result rendered
```

The UI must show real processing state, retry only supported failures, and avoid presenting partial semantic analysis as final. A new upload creates a new immutable version.

## Copilot UI behavior

- Show the active authorized project context.
- Keep one in-flight request per interaction unless the API supports more.
- Stop/cancel controls must actually abort the browser request and restore UI state.
- Do not leave an indefinite loader after a failed/aborted request.
- Render evidence/provenance and insufficiency states distinctly.
- Never expose provider prompts, tokens, credentials, or raw internal traces.

## Shared design system

The product uses a Carbon/Paper monochrome language, technical borders, Space Grotesk where configured, clear focus states, compact labels, and responsive panels. Reuse existing tokens and classes before adding new declarations.

For all changes verify:

- no overlapping copy;
- no horizontal overflow;
- readable 1366x768 and common mobile/tablet sizes;
- keyboard navigation and visible focus;
- labels and accessible names;
- reduced motion;
- loading/error/empty/partial/success states;
- safe French user-facing copy.

## Frontend testing

The repository uses Python source/contract tests for frontend behavior, Node-based JavaScript tests/syntax checks, and Playwright for real browser acceptance when its environment is available. Do not introduce a second frontend framework or E2E framework just for one feature.

## Current change caution

Frontend files may contain active V1.3 visual work. Always inspect `git status` and diffs before editing shared landing, auth, entrepreneur, or investor CSS/JavaScript. Preserve unrelated user changes and avoid broad mechanical rewrites.

