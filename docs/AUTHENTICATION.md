# Authentication

## Purpose

RegBridge delegates authentication to an external, provider-neutral OIDC/OAuth2 identity provider. The API acts as a resource server and validates bearer JWT access tokens; it does not store passwords or issue tokens.

## Flow

```text
Bearer access token → JWT validation → user_identities → users → user_roles/roles → AuthenticatedPrincipal → protected route
```

## Configuration

Required for protected authentication: `OIDC_ISSUER` and `OIDC_AUDIENCE`.

Optional: `OIDC_DISCOVERY_URL` and `OIDC_ALGORITHMS` (default `RS256`). The issuer discovery document supplies `jwks_uri`. No production provider is hardcoded.

## Identity mapping

The configured issuer and validated token `sub` map to `user_identities.provider` and `user_identities.provider_subject`, which resolve to one `users` row. The V2.1 uniqueness constraint protects against duplicate external identities.

Unknown valid identities are rejected with 403. No automatic first-login provisioning or signup workflow is currently approved.

## Roles

RegBridge global roles come from PostgreSQL through `user_roles` and `roles`. Arbitrary role claims in an external token do not grant RegBridge roles. Project roles remain separate and belong to SCRUM-179.

## Protected API

`GET /health` is public. `GET /me` requires `Authorization: Bearer <access_token>` and returns the business user ID, email, and database-controlled global roles.

Authentication failures return 401 with `WWW-Authenticate: Bearer`; valid but unprovisioned or unavailable accounts return 403.

## Security rules

- no passwords or refresh tokens are stored;
- bearer tokens and complete JWTs are never logged;
- signature, issuer, audience, expiration, subject, and allowed algorithm are validated;
- external token roles are not trusted as RegBridge authorization data.

## Local/test authentication

Tests generate ephemeral RSA keys and patch signing-key retrieval. They validate JWT behavior without contacting a public identity provider. No authentication bypass is enabled.
