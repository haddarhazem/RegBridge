import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ThesisFields(BaseModel):
    sectors: list[str] | None = None
    stages: list[str] | None = None
    geographies: list[str] | None = None
    technologies: list[str] | None = None
    ticket_min: Decimal | None = Field(default=None, ge=0)
    ticket_max: Decimal | None = Field(default=None, ge=0)
    ticket_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @model_validator(mode="after")
    def valid_range(self) -> "ThesisFields":
        if self.ticket_min is not None and self.ticket_max is not None and self.ticket_min > self.ticket_max:
            raise ValueError("ticket_min must be less than or equal to ticket_max")
        return self

class ThesisCreate(ThesisFields): pass

class ThesisPatch(ThesisFields):
    expected_version_id: uuid.UUID

class ThesisVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    investor_profile_id: uuid.UUID
    version_number: int
    sectors: list[str] | None
    stages: list[str] | None
    geographies: list[str] | None
    technologies: list[str] | None
    ticket_min: Decimal | None
    ticket_max: Decimal | None
    ticket_currency: str | None
    source: str
    created_by_user_id: uuid.UUID
    created_at: datetime

class InvestorProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    current_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    current_version: ThesisVersionResponse | None
