from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ClaimVerdict = Literal["SUPPORTED", "UNSUPPORTED", "UNVERIFIABLE"]


class ClaimVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: str
    section: str
    claim_text: str
    claim_type: str
    verdict: ClaimVerdict
    reason_code: str
    evidence_refs: list[str]


class BriefVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brief_run_id: uuid.UUID
    verifier_strategy: str
    verifier_version: str
    status: str
    created_at: datetime
    claims: list[ClaimVerificationResponse]


class BriefVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
