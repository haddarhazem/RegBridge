import asyncio
import logging
from functools import lru_cache
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AuthenticationConfigurationError(RuntimeError):
    """Raised when provider configuration or discovery is unavailable."""


class InvalidAccessTokenError(ValueError):
    """Raised when a bearer access token cannot be trusted."""


class OIDCValidator:
    """Provider-neutral JWT validator backed by OIDC discovery and JWKS."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._discovery: dict[str, Any] | None = None
        self._jwks_client: PyJWKClient | None = None

    async def _get_discovery(self) -> dict[str, Any]:
        if self._discovery is not None:
            return self._discovery
        if not self.settings.oidc_issuer or not self.settings.oidc_audience:
            raise AuthenticationConfigurationError("OIDC authentication is not configured")
        discovery_url = self.settings.oidc_discovery_url or f"{self.settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(discovery_url)
                response.raise_for_status()
                discovery = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AuthenticationConfigurationError("OIDC discovery is unavailable") from exc
        jwks_uri = discovery.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise AuthenticationConfigurationError("OIDC discovery did not provide a JWKS URI")
        self._discovery = discovery
        self._jwks_client = PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=300, cache_keys=True)
        return discovery

    async def _get_signing_key(self, token: str) -> Any:
        await self._get_discovery()
        assert self._jwks_client is not None
        try:
            signing_key = await asyncio.to_thread(self._jwks_client.get_signing_key_from_jwt, token)
        except jwt.PyJWTError as exc:
            raise InvalidAccessTokenError("Access token signature is invalid") from exc
        return signing_key.key

    async def validate(self, token: str) -> dict[str, Any]:
        if not token:
            raise InvalidAccessTokenError("Access token is missing")
        if not self.settings.oidc_issuer or not self.settings.oidc_audience:
            raise AuthenticationConfigurationError("OIDC authentication is not configured")
        key = await self._get_signing_key(token)
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=self.settings.allowed_oidc_algorithms,
                issuer=self.settings.oidc_issuer,
                audience=self.settings.oidc_audience,
                options={"require": ["iss", "sub", "aud", "exp"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidAccessTokenError("Access token validation failed") from exc
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise InvalidAccessTokenError("Access token subject is invalid")
        return claims


@lru_cache(maxsize=1)
def get_token_validator() -> OIDCValidator:
    return OIDCValidator(get_settings())
