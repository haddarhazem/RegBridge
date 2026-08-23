import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ContactPointCreate(BaseModel):
    channel: str = Field(pattern="^(EMAIL|WEBSITE)$")
    value: str = Field(min_length=1)
    project_id: uuid.UUID | None = None

class ContactPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; owner_user_id: uuid.UUID; project_id: uuid.UUID | None; channel: str; active: bool; created_at: datetime

class ContactRequestCreate(BaseModel):
    target_type: str = Field(pattern="^(project|investor_profile)$")
    target_id: uuid.UUID
    source_project_id: uuid.UUID | None = None
    message: str | None = None

class ContactRequestResponse(BaseModel):
    id: uuid.UUID; requester_user_id: uuid.UUID; recipient_user_id: uuid.UUID; source_project_id: uuid.UUID | None
    target_type: str; target_id: uuid.UUID; message: str | None; status: str; responded_at: datetime | None; created_at: datetime; updated_at: datetime

class ContactAccept(BaseModel):
    contact_point_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

class ConsentResponse(BaseModel):
    id: uuid.UUID; request_id: uuid.UUID; contact_point_id: uuid.UUID; channel: str; status: str; granted_at: datetime; revoked_at: datetime | None

class ContactDisclosure(BaseModel):
    request_id: uuid.UUID; contacts: list[dict]
