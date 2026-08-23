import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class OpportunityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str
    opportunity_type: str = Field(min_length=1, max_length=60)
    criteria: dict = Field(default_factory=dict)
    visibility: str = Field(default="AUTHENTICATED", pattern="^(AUTHENTICATED|PUBLIC)$")
    status: str = Field(default="DRAFT", pattern="^(DRAFT|PUBLISHED)$")
    application_deadline: datetime | None = None

class OpportunityPatch(BaseModel):
    expected_version_id: uuid.UUID
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    opportunity_type: str | None = Field(default=None, max_length=60)
    criteria: dict | None = None
    visibility: str | None = Field(default=None, pattern="^(AUTHENTICATED|PUBLIC)$")
    application_deadline: datetime | None = None

class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; investor_profile_id: uuid.UUID; current_version_id: uuid.UUID | None; version_number: int
    title: str; description: str; opportunity_type: str; criteria: dict; visibility: str; status: str
    application_deadline: datetime | None; published_at: datetime | None; created_at: datetime; updated_at: datetime

class OpportunityVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; opportunity_id: uuid.UUID; version_number: int; title: str; description: str
    opportunity_type: str; criteria: dict; visibility: str; status: str; application_deadline: datetime | None
    published_at: datetime | None; created_by_user_id: uuid.UUID; created_at: datetime
