import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProfileVisibility(str, Enum):
    PUBLIC = "PUBLIC"
    INVESTOR_SHARED = "INVESTOR_SHARED"
    PRIVATE = "PRIVATE"


StartupProfileFieldName = Literal[
    "website",
    "fundraising_target",
    "investor_summary",
    "internal_notes",
    "employee_range",
    "business_model",
    "traction_summary",
    "contact_email",
]


class StartupProfileFieldUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: StartupProfileFieldName
    value: str | int | float | bool | None = Field(default=None)
    visibility: ProfileVisibility


class StartupProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[StartupProfileFieldUpdate] = Field(min_length=1, max_length=32)


class StartupProfileFieldResponse(BaseModel):
    field_name: str
    section: str
    value: str | int | float | bool | None
    visibility: ProfileVisibility


class StartupProfileResponse(BaseModel):
    project_id: uuid.UUID
    project_type: Literal["startup_in_creation", "existing_startup"]
    revision: int
    fields: list[StartupProfileFieldResponse]


class PublicStartupProfileResponse(BaseModel):
    fields: dict[str, str | int | float | bool | None]


class StartupProfileRevisionResponse(BaseModel):
    revision: int
    snapshot: list[dict]
    changed_by_user_id: uuid.UUID
    created_at: datetime
