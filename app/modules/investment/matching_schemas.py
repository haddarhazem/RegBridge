import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class MatchingCreate(BaseModel):
    startup_project_id: uuid.UUID
    investor_thesis_version_id: uuid.UUID | None = None


class MatchingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    investor_user_id: uuid.UUID
    investor_thesis_version_id: uuid.UUID
    startup_project_id: uuid.UUID
    startup_snapshot_revision_id: uuid.UUID | None
    investor_snapshot: dict
    startup_snapshot: dict
    matching_method: str
    matching_method_version: str
    score: Decimal | None
    score_formula: str
    dimensions: dict
    report: dict
    explanation_mode: str
    llm_provider: str | None
    llm_model: str | None
    prompt_version: str | None
    created_at: datetime


class MatchingListItem(BaseModel):
    """Safe owner-list projection; snapshots remain available only via detail."""

    id: uuid.UUID
    startup_project_id: uuid.UUID
    startup_display_name: str | None
    investor_thesis_version_id: uuid.UUID
    investor_thesis_version_number: int | None
    created_at: datetime
    result_summary: dict
    dimensions: dict
    unknown_dimensions: list[str]
    status: str
