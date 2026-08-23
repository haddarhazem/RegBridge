import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

def lower(value: str) -> str: return value.lower()

class EventCreate(BaseModel):
    event_type: str = Field(default="event", max_length=40)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    location_type: str = "online"
    location_details: dict = Field(default_factory=dict)
    starts_at: datetime
    ends_at: datetime
    registration_url: str | None = None
    status: str = "draft"
    @field_validator("event_type", "location_type", "status", mode="before")
    @classmethod
    def normalize(cls, value: str) -> str: return lower(value)
    @model_validator(mode="after")
    def valid(self):
        if self.starts_at >= self.ends_at: raise ValueError("starts_at must be before ends_at")
        if self.event_type not in {"event", "hackathon"}: raise ValueError("event_type must be event or hackathon")
        if self.location_type not in {"online", "onsite", "hybrid"}: raise ValueError("invalid location_type")
        if self.status not in {"draft", "active"}: raise ValueError("status must be draft or active")
        return self

class EventPatch(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    location_type: str | None = None
    location_details: dict | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    registration_url: str | None = None
    expected_updated_at: datetime | None = None
    @field_validator("location_type", mode="before")
    @classmethod
    def normalize_location(cls, value): return lower(value) if value is not None else value

class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; organizer_user_id: uuid.UUID
    event_type: str; title: str; description: str | None; location_type: str; location_details: dict
    starts_at: datetime; ends_at: datetime; registration_url: str | None; status: str; created_at: datetime; updated_at: datetime

class EventRegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID; event_id: uuid.UUID; user_id: uuid.UUID; status: str; registered_at: datetime

class ParticipationResponse(BaseModel):
    event_id: uuid.UUID; user_id: uuid.UUID; status: str | None; active: bool
