# Authentication

## Architecture

RegBridge uses a provider-neutral OIDC/OAuth2 architecture:

```text
Browser public client
  -> Authorization Code + PKCE (oidc-client-ts 3.5.0, Apache-2.0)
  -> configured identity provider
  -> bearer access token
  -> FastAPI JWT validation
  -> user_identities(provider, provider_subject)
  -> users + database-controlled roles
```

The browser is a public client and has no client secret. FastAPI remains a stateless OAuth2 resource server: it does not store passwords, issue access tokens, or create a browser cookie session.

## Backend configuration

Required for JWT validation:

- `OIDC_ISSUER`
- `OIDC_AUDIENCE`

Optional validator settings:

- `OIDC_DISCOVERY_URL`
- `OIDC_ALGORITHMS` (default `RS256`)

Required for the browser Authorization Code + PKCE flow:

- `OIDC_CLIENT_ID`: public SPA client identifier;
- `OIDC_REDIRECT_URI`: exact callback URI, locally `http://127.0.0.1:8000/auth/callback/`;
- `OIDC_SCOPE`: normally `openid profile email`.

Optional browser settings:

- `OIDC_POST_LOGOUT_REDIRECT_URI`;
- `OIDC_AUTHORIZATION_AUDIENCE` when the provider requires an `audience` authorization parameter;
- `OIDC_RESOURCE` when the provider uses the OAuth resource indicator parameter.

`GET /auth/config` exposes only this public browser configuration. It never returns a secret.

## Local Keycloak development provider

Keycloak is bundled only as a reproducible local development/test identity provider. Production authentication remains provider-neutral and uses the same standard discovery, JWT, issuer, audience, and JWKS settings.

1. Set development-only bootstrap credentials in the current shell. Do not put a real or reused password in the repository:

   ```powershell
   $env:KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME="regbridge-dev-admin"
   $env:KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD="<synthetic-development-only-password>"
   ```

2. Start PostgreSQL and Keycloak with the existing Compose stack:

   ```powershell
   docker compose up -d postgres keycloak
   ```

3. Configure the RegBridge process with the public local values below (there is no OIDC client secret):

   ```dotenv
   OIDC_ISSUER=http://127.0.0.1:18080/realms/regbridge
   OIDC_AUDIENCE=regbridge-api
   OIDC_CLIENT_ID=regbridge-frontend
   OIDC_REDIRECT_URI=http://127.0.0.1:8000/auth/callback/
   OIDC_POST_LOGOUT_REDIRECT_URI=http://127.0.0.1:8000/auth/login/
   OIDC_SCOPE=openid profile email
   OIDC_ALGORITHMS=RS256
   ```

4. Apply migrations and start the combined FastAPI/static-frontend server:

   ```powershell
   alembic upgrade head
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

5. Open `http://127.0.0.1:8000/auth/register/`. The RegBridge registration action redirects to Keycloak; select **Register** there to create a synthetic local identity. Keycloak owns identity and credentials, while RegBridge assigns `entrepreneur`, `investor`, and `researcher` through its role-onboarding page.

The versioned import at `infra/keycloak/regbridge-realm.json` creates realm `regbridge` and public client `regbridge-frontend`. It enables Authorization Code Flow, requires PKCE S256, disables implicit and password/direct grants, uses exact localhost redirect/origin/logout URIs, emits the explicit `regbridge-api` access-token audience, and contains no users, passwords, or RegBridge business roles. Re-import into a clean Keycloak data store when validating changes to the realm file; an existing realm is not overwritten at startup.

Local endpoints:

- frontend and API: `http://127.0.0.1:8000`;
- issuer: `http://127.0.0.1:18080/realms/regbridge`;
- discovery: `http://127.0.0.1:18080/realms/regbridge/.well-known/openid-configuration`;
- callback: `http://127.0.0.1:8000/auth/callback/`;
- post-logout destination: `http://127.0.0.1:8000/auth/login/`.

For a real local E2E, create four synthetic identities through provider registration, then verify entrepreneur, investor, researcher, and combined multi-role onboarding. Logout and use a fresh browser context for the returning-login check. Never copy access tokens into RegBridge or browser developer tools, and never record test passwords or tokens in test output.

Troubleshooting:

- **issuer mismatch:** `OIDC_ISSUER` must exactly equal the access token `iss`, including host and realm path;
- **audience mismatch:** keep backend audience validation enabled and verify the token audience contains `regbridge-api` through the imported audience mapper;
- **redirect mismatch:** use `127.0.0.1`, port `8000`, and the trailing slash exactly as imported;
- **CORS/web origin:** serve RegBridge from the exact `http://127.0.0.1:8000` origin; do not substitute `localhost` without updating the development realm deliberately;
- **expired token:** the local access-token lifetime is five minutes; an expired token must return 401 and the browser must authenticate again according to the current client behavior;
- **realm changes not visible:** realm import runs only when the realm does not already exist; remove only the disposable local Keycloak state or update the realm through an explicit development procedure.

## External provider setup

Configure any external OIDC provider using the same provider-neutral contract:

1. Register a **public SPA** client; do not generate or configure a browser client secret.
2. Enable Authorization Code Flow and require PKCE with the `S256` challenge method.
3. Register the exact redirect URI from `OIDC_REDIRECT_URI`.
4. Register the exact post-logout URI from `OIDC_POST_LOGOUT_REDIRECT_URI` when RP-initiated logout is supported.
5. Allow the frontend origin, locally `http://127.0.0.1:8000`.
6. Register the API resource/audience used by `OIDC_AUDIENCE` and configure the provider to issue signed JWT access tokens for it.
7. Allow `openid profile email`; the access token used for first provisioning must include `sub` and `email` in addition to standard `iss`, `aud`, and `exp` claims.
8. Ensure the discovery document exposes `jwks_uri`; expose `end_session_endpoint` if provider logout is required.
9. Put only the public identifiers and local provider URL in `.env`. Never commit provider test passwords, tokens, or secrets.
10. Start PostgreSQL and RegBridge with `docker compose up -d postgres`, `alembic upgrade head`, and `python -m uvicorn app.main:app --reload`, then open `/auth/register/`.

Login and account creation use the same standards-based provider redirect unless the configured provider itself presents a distinct signup experience.

## First-login provisioning

`GET /me` validates the bearer JWT before any database mutation. A new trusted `(issuer, sub)` creates one minimal `users` row and one `user_identities` row. Existing identities reuse the same user. The database uniqueness constraint and read-after-conflict handling make simultaneous first requests idempotent.

The stable identity is `(provider, provider_subject)`, never email. A signed provider email is required only because the current authoritative `users.email` column is non-null. RegBridge never links an existing account by matching email and does not overwrite user profile fields on returning login.

## Roles

The migration seeds the authoritative global role catalog:

- `entrepreneur`
- `investor`
- `researcher`
- `research_center`
- `admin`

Only `entrepreneur`, `investor`, and `researcher` are self-service. `admin`, `research_center`, project membership roles, and arbitrary strings are denied. External token role claims are never trusted.

Authenticated APIs:

- `GET /me`
- `GET /me/roles/options`
- `PUT /me/roles`

Role updates replace only the caller's self-service roles, preserve externally managed privileged roles, are idempotent, and write an audit event when the set changes.

## Frontend routes

- `/auth/login/`
- `/auth/register/`
- `/auth/callback/`
- `/onboarding/roles/`
- `/workspace/`

The OIDC library stores its transient state and tokens in `sessionStorage`; no token is placed in `localStorage` or exposed through a manual injection API. Successful XSS could still steal browser-accessible bearer tokens, so the frontend avoids unsafe HTML injection, never logs tokens, and relies on short provider-managed token lifetimes. A deployment-level Content Security Policy should be enabled by the reverse proxy once its complete asset and API origins are known.

## Logout limitation

Logout clears local OIDC/user/workspace state and uses the provider's RP-initiated logout endpoint when discovery advertises one. Without that capability, RegBridge can clear only local state. Already-issued stateless access tokens remain valid until expiry unless the provider separately supports and applies revocation or introspection.

## Security invariants

- bearer tokens, authorization codes, refresh tokens, ID tokens, complete claims, passwords, and authorization headers are never logged;
- signature, issuer, audience, expiration, subject, and allowed algorithm are validated before provisioning;
- database roles, memberships, grants, and object authorization remain the backend security boundary;
- knowing a resource identifier or selecting a frontend workspace does not grant authorization;
- redirect targets are restricted to local application paths.

## Tests

Automated tests use ephemeral RSA keys and test-only PostgreSQL rows. They do not contact a public identity provider and do not bypass JWT signature validation in production. A real first-login/relogin browser E2E requires the manual provider setup above and must not be reported as passing until it has run.
