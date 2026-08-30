import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthenticatedPrincipal(BaseModel):
    """Validated application identity; never exposes the raw bearer token."""

    model_config = ConfigDict(frozen=True)

    user_id: uuid.UUID
    email: str
    roles: tuple[str, ...]
    provider: str


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    roles: tuple[str, ...]
    needs_role_onboarding: bool


class RoleOptionResponse(BaseModel):
    code: str
    label: str
    description: str


class RoleSelectionRequest(BaseModel):
    roles: list[str] = Field(min_length=1, max_length=3)

    @field_validator("roles")
    @classmethod
    def require_unique_roles(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("roles must not contain duplicates")
        return value


class PublicOIDCConfigResponse(BaseModel):
    authority: str
    client_id: str
    redirect_uri: str
    post_logout_redirect_uri: str | None
    scope: str
    authorization_extra_params: dict[str, str]
