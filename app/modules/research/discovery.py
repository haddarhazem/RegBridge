from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import AuditLog
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.research.models import (ResearchDiscovery, ResearchDiscoveryVersion, ResearchEvidenceRef,
    ResearchExtractionItem, ResearchExtractionRun, ResearchOutput, ResearchOutputVersion)
from app.modules.research.extraction import FIELDS, build_abstract
from app.modules.research.access_service import ResearchAccessService
from app.modules.sharing.models import InvestorShareGrant

VISIBILITIES = {"PRIVATE", "PUBLIC", "MATCHABLE"}

def _content(fields: dict[str, list[str]], evidence: dict[str, list[dict]], abstract: str) -> dict:
    return {"fields": fields, "evidence": evidence, "abstract": abstract}

class DiscoveryService:
    def __init__(self, session: AsyncSession): self.session = session

    async def _run(self, actor, run_id):
        run = await self.session.scalar(select(ResearchExtractionRun).where(ResearchExtractionRun.id == run_id, ResearchExtractionRun.owner_user_id == actor.user_id))
        if run is None: raise HTTPException(404, "Research extraction not found")
        return run

    async def _owned(self, actor, discovery_id):
        item = await self.session.scalar(select(ResearchDiscovery).where(ResearchDiscovery.id == discovery_id, ResearchDiscovery.owner_user_id == actor.user_id))
        if item is None: raise HTTPException(404, "Research discovery not found")
        return item

    async def _version(self, actor, discovery_id, version_id=None):
        await self._owned(actor, discovery_id)
        query = select(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.discovery_id == discovery_id)
        if version_id: query = query.where(ResearchDiscoveryVersion.id == version_id)
        else: query = query.order_by(ResearchDiscoveryVersion.version_number.desc()).limit(1)
        version = await self.session.scalar(query)
        if version is None: raise HTTPException(404, "Research discovery version not found")
        return version

    async def initialize(self, actor: AuthenticatedPrincipal, run_id: uuid.UUID):
        run = await self._run(actor, run_id)
        if run.status != "GENERATED": raise HTTPException(409, "Extraction is not reviewable")
        existing = await self.session.scalar(select(ResearchDiscovery).where(ResearchDiscovery.research_output_id == run.research_output_id, ResearchDiscovery.owner_user_id == actor.user_id))
        if existing: raise HTTPException(409, "Discovery already initialized")
        items = (await self.session.scalars(select(ResearchExtractionItem).where(ResearchExtractionItem.run_id == run.id).order_by(ResearchExtractionItem.field, ResearchExtractionItem.item_order))).all()
        fields = {field: [] for field in FIELDS}; evidence = {field: [] for field in FIELDS}
        for item in items:
            if item.source_text: fields[item.field].append(item.source_text)
            refs = (await self.session.scalars(select(ResearchEvidenceRef).where(ResearchEvidenceRef.item_id == item.id).order_by(ResearchEvidenceRef.item_order))).all()
            evidence[item.field].extend({"segment_id": ref.segment_id, "locator": ref.locator} for ref in refs)
        discovery = ResearchDiscovery(id=uuid.uuid4(), research_output_id=run.research_output_id, owner_user_id=actor.user_id); self.session.add(discovery); await self.session.flush()
        version = ResearchDiscoveryVersion(id=uuid.uuid4(), discovery_id=discovery.id, version_number=1, extraction_run_id=run.id, research_output_version_id=run.research_output_version_id, document_version_id=run.document_version_id, source_sha256=run.source_sha256, content=_content(fields, evidence, run.regbridge_abstract), visibility={field: "PRIVATE" for field in (*FIELDS, "abstract")}, status="DRAFT")
        self.session.add(version); self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="research_discovery.initialized", resource_type="research_discovery", resource_id=discovery.id, metadata_json={"version_id": str(version.id), "extraction_run_id": str(run.id)})); await self.session.commit(); return version

    async def correct(self, actor, discovery_id, base_version_id, content: dict, visibility: dict | None = None):
        base = await self._version(actor, discovery_id, base_version_id)
        latest = await self._version(actor, discovery_id)
        if latest.id != base.id:
            raise HTTPException(409, "Correction is based on a stale discovery version")
        if base.status == "APPROVED" and not content: raise HTTPException(409, "Correction content is required")
        current_values = content.get("fields", {})
        if set(current_values) - set(FIELDS): raise HTTPException(422, "Unknown discovery field")
        allowed = {field: set(base.content.get("fields", {}).get(field, [])) for field in FIELDS}
        for field, values in current_values.items():
            if any(value not in allowed[field] for value in values): raise HTTPException(422, "Correction must remain source-backed")
        fields = {field: list(current_values.get(field, base.content["fields"].get(field, []))) for field in FIELDS}
        evidence = {field: base.content["evidence"].get(field, []) for field in FIELDS}
        abstract = build_abstract(fields)
        if visibility is None: visibility = {field: "PRIVATE" for field in (*FIELDS, "abstract")}
        if set(visibility) - set((*FIELDS, "abstract")) or any(value not in VISIBILITIES for value in visibility.values()): raise HTTPException(422, "Invalid discovery visibility")
        max_version = await self.session.scalar(select(func.max(ResearchDiscoveryVersion.version_number)).where(ResearchDiscoveryVersion.discovery_id == discovery_id)) or 0
        version = ResearchDiscoveryVersion(id=uuid.uuid4(), discovery_id=discovery_id, version_number=max_version + 1, extraction_run_id=base.extraction_run_id, research_output_version_id=base.research_output_version_id, document_version_id=base.document_version_id, source_sha256=base.source_sha256, content=_content(fields, evidence, abstract), visibility=visibility, status="DRAFT")
        self.session.add(version); self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="research_discovery.corrected", resource_type="research_discovery", resource_id=discovery_id, metadata_json={"version_id": str(version.id), "base_version_id": str(base.id)}))
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(409, "Concurrent discovery correction conflict") from exc
        return version

    async def approve(self, actor, discovery_id, version_id):
        version = await self._version(actor, discovery_id, version_id)
        if version.id != (await self._version(actor, discovery_id)).id:
            raise HTTPException(409, "Only the current discovery version can be approved")
        if version.status == "APPROVED": return version
        version.status = "APPROVED"; version.approved_by_user_id = actor.user_id; version.approved_at = datetime.now(timezone.utc)
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="research_discovery.approved", resource_type="research_discovery", resource_id=discovery_id, metadata_json={"version_id": str(version.id)})); await self.session.commit(); return version

    async def public(self, discovery_id):
        version = await self.session.scalar(select(ResearchDiscoveryVersion).join(ResearchDiscovery).join(ResearchOutput, ResearchOutput.id == ResearchDiscovery.research_output_id).where(ResearchDiscovery.id == discovery_id, ResearchOutput.rights_metadata_status == "COMPLETE", ResearchDiscoveryVersion.status == "APPROVED").order_by(ResearchDiscoveryVersion.version_number.desc()).limit(1))
        if version is None: raise HTTPException(404, "Public research discovery not found")
        return {"discovery_id": discovery_id, "version_id": version.id, "version_number": version.version_number, "fields": {field: values for field, values in version.content["fields"].items() if version.visibility.get(field) == "PUBLIC"}, "abstract": version.content["abstract"] if version.visibility.get("abstract") == "PUBLIC" else None}

    async def matchable(self, actor, discovery_id):
        version = await self._version(actor, discovery_id)
        if version.status != "APPROVED":
            raise HTTPException(404, "Approved research discovery not found")
        return {"discovery_id": discovery_id, "version_id": version.id, "fields": {field: values for field, values in version.content["fields"].items() if version.visibility.get(field) == "MATCHABLE"}}

    async def granted(self, actor, discovery_id, version_id):
        version = await self.session.scalar(select(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.id == version_id, ResearchDiscoveryVersion.discovery_id == discovery_id, ResearchDiscoveryVersion.status == "APPROVED"))
        if version is None or not await ResearchAccessService(self.session).has_scope(actor, discovery_version_id=version.id, scope="DISCOVERY_READ"):
            raise HTTPException(404, "Research discovery version not found")
        fields = {field: values for field, values in version.content.get("fields", {}).items() if version.visibility.get(field) in {"PUBLIC", "MATCHABLE"}}
        grant = await self.session.scalar(select(InvestorShareGrant).where(InvestorShareGrant.recipient_user_id == actor.user_id, InvestorShareGrant.resource_type == "RESEARCH_DISCOVERY_VERSION", InvestorShareGrant.resource_id == version.id, InvestorShareGrant.resource_version_id == version.id, InvestorShareGrant.scope == "DISCOVERY_READ", InvestorShareGrant.status == "ACTIVE"))
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action="RESEARCH_DISCOVERY_ACCESSED", resource_type="research_discovery_version", resource_id=version.id, project_id=grant.project_id if grant else None, metadata_json={"grant_id": str(grant.id) if grant else None, "scope": "DISCOVERY_READ", "result": "allowed"}))
        await self.session.commit()
        return {"discovery_id": discovery_id, "version_id": version.id, "version_number": version.version_number, "fields": fields}
