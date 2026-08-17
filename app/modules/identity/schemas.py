import uuid

from pydantic import BaseModel, ConfigDict


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
