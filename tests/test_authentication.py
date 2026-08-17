import uuid
from unittest.mock import AsyncMock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings
from app.main import app
from app.modules.identity.auth import OIDCValidator
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal


@pytest.fixture
def signing_keys() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def make_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://regbridge:regbridge@localhost:5432/regbridge",
        oidc_issuer="https://issuer.example.test/",
        oidc_audience="https://api.example.test/",
    )


def make_token(private_key: rsa.RSAPrivateKey, **overrides: object) -> str:
    claims: dict[str, object] = {
        "iss": "https://issuer.example.test/",
        "aud": "https://api.example.test/",
        "sub": "subject-123",
        "exp": 4102444800,
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


@pytest.mark.asyncio
async def test_me_without_token_returns_401() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_me_returns_business_identity_and_multiple_database_roles() -> None:
    principal = AuthenticatedPrincipal(
        user_id=uuid.uuid4(),
        email="user@example.test",
        roles=("entrepreneur", "researcher"),
        provider="https://issuer.example.test/",
    )
    app.dependency_overrides[get_authenticated_principal] = lambda: principal
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/me", headers={"Authorization": "Bearer test-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["roles"] == ["entrepreneur", "researcher"]
    assert "provider" not in response.json()


@pytest.mark.asyncio
async def test_validator_accepts_signed_token_and_validates_standard_claims(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    private_key, public_key = signing_keys
    validator = OIDCValidator(make_settings())
    validator._get_signing_key = AsyncMock(return_value=public_key)  # type: ignore[method-assign]

    claims = await validator.validate(make_token(private_key))

    assert claims["sub"] == "subject-123"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://wrong.example.test/"},
        {"aud": "https://wrong.example.test/"},
        {"exp": 1},
    ],
)
async def test_validator_rejects_wrong_issuer_audience_or_expiration(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey], overrides: dict[str, object]
) -> None:
    private_key, public_key = signing_keys
    validator = OIDCValidator(make_settings())
    validator._get_signing_key = AsyncMock(return_value=public_key)  # type: ignore[method-assign]

    with pytest.raises(ValueError):
        await validator.validate(make_token(private_key, **overrides))


@pytest.mark.asyncio
async def test_validator_rejects_invalid_signature(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey],
) -> None:
    _, public_key = signing_keys
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    validator = OIDCValidator(make_settings())
    validator._get_signing_key = AsyncMock(return_value=public_key)  # type: ignore[method-assign]

    with pytest.raises(ValueError):
        await validator.validate(make_token(other_private_key))
