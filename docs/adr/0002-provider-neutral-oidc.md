# ADR-0002: Use provider-neutral OIDC authentication

Status: Accepted

## Context

RegBridge needs external authentication, while SCRUM-178 requires the provider to remain configurable. Vendor lock-in is unnecessary at this stage.

## Decision

RegBridge acts as an OIDC/OAuth2 resource server. It validates signed bearer access tokens using configured issuer, audience, discovery, and JWKS settings. Business roles remain in RegBridge PostgreSQL, and no specific provider is hardcoded.

## Consequences

Positive: the provider can change, credentials remain delegated, and the application role model remains independent.

Trade-offs: discovery and provider configuration must be maintained, provider-specific features may require adapters, and opaque tokens would require a separate introspection decision.
