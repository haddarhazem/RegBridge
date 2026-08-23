import uuid
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class StartupSearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sector: str | None = None
    stage: str | None = None
    geography: str | None = None
    technology: str | None = None
    page: int = Field(default=1, ge=1, le=100000)
    limit: int = Field(default=20, ge=1, le=100)
    sort: Literal["name", "sector", "stage", "geography", "technology"] = "name"

class StartupSearchResult(BaseModel):
    startup_id: uuid.UUID
    display_name: str | None
    sector: str | None
    stage: str | None
    geography: str | None
    technology: str | None
    public_fields: dict = Field(default_factory=dict)
    shared_fields: dict = Field(default_factory=dict)

class StartupSearchResponse(BaseModel):
    items: list[StartupSearchResult]
    page: int
    limit: int
    total_count: int
