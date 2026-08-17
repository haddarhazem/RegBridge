import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProjectType = Literal["idea", "startup_in_creation", "existing_startup"]
ProjectVisibility = Literal["private", "authenticated", "public"]
MemberRole = Literal["owner", "founder", "admin", "member", "viewer"]
MembershipStatus = Literal["invited", "active", "revoked"]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_type: ProjectType
    raw_description: str = Field(min_length=1)
    display_name: str | None = None
    user_goal: str | None = None
    current_progress: str | None = None
    country_code: str = "FR"
    target_market: str = "France"
    language: str = "fr"
    visibility: ProjectVisibility = "private"


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    raw_description: str | None = Field(default=None, min_length=1)
    user_goal: str | None = None
    current_progress: str | None = None
    country_code: str | None = None
    target_market: str | None = None
    language: str | None = None
    visibility: ProjectVisibility | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    project_type: ProjectType
    display_name: str | None
    visibility: ProjectVisibility
    is_member: bool
    raw_description: str | None = None
    user_goal: str | None = None
    current_progress: str | None = None
    country_code: str | None = None
    target_market: str | None = None
    language: str | None = None
    owner_user_id: uuid.UUID | None = None


class ProjectMemberInvite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    member_role: Literal["founder", "admin", "member", "viewer"] = "member"


class ProjectMemberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_role: Literal["founder", "admin", "member", "viewer"]


class ProjectMemberResponse(BaseModel):
    user_id: uuid.UUID
    first_name: str | None
    last_name: str | None
    member_role: MemberRole
    status: MembershipStatus
    joined_at: datetime | None
