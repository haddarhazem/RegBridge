import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProjectType = Literal["idea", "startup_in_creation", "existing_startup"]
ProjectVisibility = Literal["private", "authenticated", "public"]
MemberRole = Literal["owner", "founder", "admin", "member", "viewer"]
MembershipStatus = Literal["invited", "active", "revoked"]
OnboardingField = Literal["activity", "sector", "technology", "data", "market", "location"]
OnboardingStatus = Literal["in_progress", "complete"]
FactDomain = Literal["activity", "sector", "technology", "data", "market", "location"]
FactOrigin = Literal["inferred", "user_declared"]
FactStatus = Literal["pending_confirmation", "confirmed", "corrected", "deleted"]
FactUncertainty = Literal["high", "medium", "low"]


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


class IdeaProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=255)


class IdeaOnboardingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity: str | None = Field(default=None, max_length=500)
    sector: str | None = Field(default=None, max_length=160)
    technology: str | None = Field(default=None, max_length=500)
    data: str | None = Field(default=None, max_length=500)
    target_market: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    confirm: list[OnboardingField] = Field(default_factory=list, max_length=6)


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


class ProjectLifecycleTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: ProjectType


class ProjectLifecycleHistoryResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    from_type: ProjectType
    to_type: ProjectType
    created_at: datetime


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
    activity: str | None = None
    sector: str | None = None
    technology: str | None = None
    data: str | None = None
    location: str | None = None
    onboarding_status: OnboardingStatus | None = None
    confirmed_fields: list[str] = Field(default_factory=list)


class OnboardingQuestion(BaseModel):
    field: OnboardingField
    question: str


class IdeaOnboardingResponse(BaseModel):
    project_id: uuid.UUID
    status: OnboardingStatus
    confirmed_fields: list[OnboardingField]
    next_questions: list[OnboardingQuestion]


class ProjectFactProvenanceResponse(BaseModel):
    source_field: str
    excerpt: str
    rule: str | None = None
    correction: str | None = None


class ProjectFactResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    domain: FactDomain
    value: str
    origin: FactOrigin
    status: FactStatus
    provenance: ProjectFactProvenanceResponse
    uncertainty: FactUncertainty


class ProjectFactCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=500)


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
