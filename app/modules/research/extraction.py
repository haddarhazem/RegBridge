"""Production evidence-locked research extraction (SCRUM-209)."""
from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.llm import LLMGenerationRequest, LLMMessage
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.audit import AuditLog
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.research.extraction_parser import parse_source, segment_source, resolve_segment
from app.modules.research.models import ResearchEvidenceRef, ResearchExtractionItem, ResearchExtractionRun, ResearchOutputVersion

FIELDS = ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "keywords", "limitations")


class ExtractiveItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_ids: list[str] = Field(min_length=1, max_length=5)


class ExtractiveField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["SUPPORTED", "NOT_AVAILABLE"]
    items: list[ExtractiveItem] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_state(self):
        if not self.valid():
            raise ValueError("SUPPORTED requires evidence and NOT_AVAILABLE cannot contain evidence")
        return self

    def valid(self) -> bool:
        return (self.status == "SUPPORTED" and bool(self.items)) or (self.status == "NOT_AVAILABLE" and not self.items)


class ExtractiveExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domains: ExtractiveField; technologies: ExtractiveField; research_problem: ExtractiveField; methodology: ExtractiveField
    main_results: ExtractiveField; explicit_applications: ExtractiveField; keywords: ExtractiveField; limitations: ExtractiveField


def extraction_schema() -> dict:
    schema = ExtractiveExtraction.model_json_schema()
    schema["additionalProperties"] = False
    return schema


def build_abstract(values: dict[str, list[str]]) -> str:
    clauses = []
    if values["research_problem"]: clauses.append(f"This research addresses {values['research_problem'][0]}")
    if values["technologies"] or values["methodology"]: clauses.append(f"It reports {'; '.join((values['technologies'][:1] + values['methodology'][:1]))}")
    if values["main_results"]: clauses.append(f"The reported result is {values['main_results'][0]}")
    if values["explicit_applications"]: clauses.append(f"The source states the application {values['explicit_applications'][0]}")
    return ". ".join(clauses) + ("." if clauses else "")


def resolve_selection(extraction: ExtractiveExtraction, segments, version_id: str):
    values = {field: [] for field in FIELDS}; references = {field: [] for field in FIELDS}
    for field in FIELDS:
        selected = getattr(extraction, field)
        if not selected.valid(): raise ValueError("INVALID_EXTRACTION_STATE")
        for item in selected.items:
            for evidence_id in dict.fromkeys(item.evidence_ids):
                segment = resolve_segment(segments, evidence_id, version_id)
                values[field].append(segment.text); references[field].append(segment)
    return values, references


async def _read_source(storage, key: str) -> bytes:
    chunks = []
    async for chunk in storage.stream(key): chunks.append(chunk)
    return b"".join(chunks)


class ResearchExtractionService:
    def __init__(self, session: AsyncSession, storage, provider=None):
        self.session, self.storage, self.provider = session, storage, provider or get_mistral_provider()

    async def _version(self, actor, output_id, version_id):
        row = await self.session.execute(select(ResearchOutputVersion, DocumentVersion).join(DocumentVersion, DocumentVersion.id == ResearchOutputVersion.document_version_id).join(Document, Document.id == DocumentVersion.document_id).where(ResearchOutputVersion.id == version_id, ResearchOutputVersion.research_output_id == output_id, Document.owner_user_id == actor.user_id, Document.deleted_at.is_(None)))
        result = row.first()
        if result is None: raise HTTPException(status_code=404, detail="Research output version not found")
        return result

    async def create(self, actor: AuthenticatedPrincipal, output_id: uuid.UUID, version_id: uuid.UUID):
        version, document = await self._version(actor, output_id, version_id)
        if document.malware_scan_status != "clean": raise HTTPException(status_code=422, detail="Research source is not usable")
        content = await _read_source(self.storage, document.storage_key)
        digest = hashlib.sha256(content).hexdigest()
        if digest != version.content_hash or digest != document.sha256: raise HTTPException(status_code=409, detail="Research source integrity check failed")
        parsed = parse_source(str(version.id), document.mime_type, content); segments = segment_source(parsed)
        prompt = "Select explicit research fields. Return only the supplied JSON schema. Select source segment IDs only; never generate factual values.\n" + "\n".join(f"{s.segment_id}: {s.text}" for s in segments)
        try:
            response = await self.provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content=prompt)], temperature=0, max_tokens=1200, response_format=extraction_schema(), prompt_version="scrum209-v1", operation="research_extraction"))
            extraction = ExtractiveExtraction.model_validate(json.loads(response.content)); values, refs = resolve_selection(extraction, segments, str(version.id))
        except Exception as exc:
            self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="research_extraction.failed", resource_type="research_output_version", resource_id=version.id, metadata_json={"category": getattr(exc, "category", "provider_or_validation_error")})); await self.session.commit()
            raise HTTPException(status_code=502, detail="Research extraction provider failed") from exc
        run = ResearchExtractionRun(id=uuid.uuid4(), owner_user_id=actor.user_id, research_output_id=output_id, research_output_version_id=version.id, document_version_id=document.id, source_sha256=digest, strategy="extractive_evidence_locked", strategy_version="v1", provider="mistral", model=response.model, prompt_version="scrum209-v1", schema_version="extractive-v1", segmenter_version="paragraph-v1", status="GENERATED", regbridge_abstract=build_abstract(values), completed_at=datetime.now(timezone.utc))
        self.session.add(run); await self.session.flush()
        for field in FIELDS:
            current = getattr(extraction, field)
            if current.status == "NOT_AVAILABLE":
                self.session.add(ResearchExtractionItem(id=uuid.uuid4(), run_id=run.id, field=field, status=current.status, source_text=None, item_order=0)); continue
            for order, (value, selected) in enumerate(zip(values[field], refs[field])):
                item = ResearchExtractionItem(id=uuid.uuid4(), run_id=run.id, field=field, status="SUPPORTED", source_text=value, item_order=order); self.session.add(item); await self.session.flush()
                self.session.add(ResearchEvidenceRef(id=uuid.uuid4(), item_id=item.id, research_output_version_id=version.id, document_version_id=document.id, segment_id=selected.segment_id, locator=selected.locator.__dict__, item_order=order))
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="research_extraction.completed", resource_type="research_extraction_run", resource_id=run.id, metadata_json={"research_output_id": str(output_id), "version_id": str(version.id), "strategy": run.strategy})); await self.session.commit(); return run
