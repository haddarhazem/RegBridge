import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ResourceType = Literal["STARTUP_PROFILE_REVISION", "COMPLIANCE_SCORE_CALCULATION", "DOCUMENT_VERSION"]

class ShareGrantCreate(BaseModel):
    recipient_user_id: uuid.UUID
    resource_type: ResourceType
    resource_id: uuid.UUID
    resource_version_id: uuid.UUID | None = None
    scope: Literal["READ"] = "READ"

class ShareGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    recipient_user_id: uuid.UUID
    resource_type: ResourceType
    resource_id: uuid.UUID
    resource_version_id: uuid.UUID | None
    scope: Literal["READ"]
    status: Literal["ACTIVE", "REVOKED"]
    granted_by_user_id: uuid.UUID
    granted_at: datetime
    revoked_by_user_id: uuid.UUID | None
    revoked_at: datetime | None

class SharedResourceResponse(BaseModel):
    grant_id: uuid.UUID
    project_id: uuid.UUID
    resource_type: ResourceType
    resource_id: uuid.UUID
    resource_version_id: uuid.UUID | None
    scope: Literal["READ"]
    access_source: Literal["EXPLICIT_GRANT"] = "EXPLICIT_GRANT"
    payload: dict

class RevokeShareRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
