from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import AuditLog
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember
from app.modules.compliance.models import ComplianceControlDefinition, ComplianceEvidence, ComplianceFramework, ComplianceFrameworkVersion, ControlEvidenceLink, ProjectComplianceControl, ProjectFrameworkAdoption
from app.modules.compliance.schemas import AdoptionCreate, ControlStatePatch, EvidenceCreate, EvidenceRevoke


class ComplianceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _project_member(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, *, edit: bool = False) -> Project:
        project = await self.session.scalar(select(Project).where(Project.id == project_id))
        membership = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
        if project is None or membership is None or (edit and membership.member_role not in {"owner", "founder", "admin"}):
            raise HTTPException(status_code=404 if not edit else 403, detail="Project compliance access denied")
        return project

    def _audit(self, actor: AuthenticatedPrincipal, action: str, project_id: uuid.UUID, resource_id: uuid.UUID, resource_type: str, metadata: dict) -> None:
        self.session.add(AuditLog(actor_user_id=actor.user_id, actor_type="user", action=action, resource_type=resource_type, resource_id=resource_id, project_id=project_id, metadata_json=metadata))

    async def frameworks(self) -> list[ComplianceFramework]:
        frameworks = list((await self.session.scalars(select(ComplianceFramework).order_by(ComplianceFramework.stable_key))).all())
        for framework in frameworks:
            setattr(framework, "versions", list((await self.session.scalars(select(ComplianceFrameworkVersion).where(ComplianceFrameworkVersion.framework_id == framework.id).order_by(ComplianceFrameworkVersion.created_at))).all()))
        return frameworks

    async def adopt(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, data: AdoptionCreate) -> ProjectFrameworkAdoption:
        await self._project_member(actor, project_id, edit=True)
        version = await self.session.scalar(select(ComplianceFrameworkVersion).where(ComplianceFrameworkVersion.id == data.framework_version_id, ComplianceFrameworkVersion.status == "active"))
        if version is None:
            raise HTTPException(status_code=404, detail="Active framework version not found")
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            existing = await self.session.scalar(select(ProjectFrameworkAdoption).where(ProjectFrameworkAdoption.project_id == project_id, ProjectFrameworkAdoption.framework_version_id == version.id))
            if existing is not None and existing.status == "active":
                return existing
            active_same = await self.session.scalars(select(ProjectFrameworkAdoption).join(ComplianceFrameworkVersion, ComplianceFrameworkVersion.id == ProjectFrameworkAdoption.framework_version_id).where(ProjectFrameworkAdoption.project_id == project_id, ComplianceFrameworkVersion.framework_id == version.framework_id, ProjectFrameworkAdoption.status == "active"))
            now = datetime.now(timezone.utc)
            for old in active_same:
                old.status = "superseded"
                old.superseded_at = now
            adoption = ProjectFrameworkAdoption(project_id=project_id, framework_version_id=version.id, adopted_by_user_id=actor.user_id, adopted_at=now)
            self.session.add(adoption)
            await self.session.flush()
            definitions = list((await self.session.scalars(select(ComplianceControlDefinition).where(ComplianceControlDefinition.framework_version_id == version.id).order_by(ComplianceControlDefinition.display_order, ComplianceControlDefinition.id))).all())
            for definition in definitions:
                self.session.add(ProjectComplianceControl(project_id=project_id, framework_version_id=version.id, control_definition_id=definition.id, created_by_user_id=actor.user_id))
            self._audit(actor, "compliance.framework_adopted", project_id, adoption.id, "project_framework_adoption", {"framework_version_id": str(version.id)})
        return adoption

    async def controls(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID) -> list[ProjectComplianceControl]:
        await self._project_member(actor, project_id)
        controls = list((await self.session.scalars(select(ProjectComplianceControl).where(ProjectComplianceControl.project_id == project_id).order_by(ProjectComplianceControl.created_at, ProjectComplianceControl.id))).all())
        for control in controls:
            setattr(control, "definition", await self.session.get(ComplianceControlDefinition, control.control_definition_id))
        return controls

    async def update_control(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, control_id: uuid.UUID, data: ControlStatePatch) -> ProjectComplianceControl:
        await self._project_member(actor, project_id, edit=True)
        control = await self.session.scalar(select(ProjectComplianceControl).where(ProjectComplianceControl.id == control_id, ProjectComplianceControl.project_id == project_id))
        if control is None:
            raise HTTPException(status_code=404, detail="Compliance control not found")
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(control, key, value)
            self._audit(actor, "compliance.control_updated", project_id, control.id, "project_compliance_control", {"fields": sorted(data.model_dump(exclude_unset=True))})
        return control

    async def attach_evidence(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, data: EvidenceCreate) -> ComplianceEvidence:
        await self._project_member(actor, project_id, edit=True)
        control = await self.session.scalar(select(ProjectComplianceControl).where(ProjectComplianceControl.id == data.control_id, ProjectComplianceControl.project_id == project_id))
        if control is None:
            raise HTTPException(status_code=404, detail="Compliance control not found")
        if data.document_version_id is not None:
            document_version = await self.session.scalar(select(DocumentVersion).join(Document, Document.id == DocumentVersion.document_id).where(DocumentVersion.id == data.document_version_id, Document.project_id == project_id, Document.deleted_at.is_(None), DocumentVersion.malware_scan_status == "clean"))
            if document_version is None:
                raise HTTPException(status_code=404, detail="Document evidence not found")
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            evidence = ComplianceEvidence(project_id=project_id, document_version_id=data.document_version_id, declaration_type=data.declaration_type, declaration_value=data.declaration_value, declaration_note=data.declaration_note, created_by_user_id=actor.user_id)
            self.session.add(evidence)
            await self.session.flush()
            self.session.add(ControlEvidenceLink(project_control_id=control.id, evidence_id=evidence.id, attached_by_user_id=actor.user_id))
            self._audit(actor, "compliance.evidence_attached", project_id, evidence.id, "compliance_evidence", {"control_id": str(control.id)})
        return evidence

    async def revoke_evidence(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, evidence_id: uuid.UUID, data: EvidenceRevoke) -> ComplianceEvidence:
        await self._project_member(actor, project_id, edit=True)
        evidence = await self.session.scalar(select(ComplianceEvidence).where(ComplianceEvidence.id == evidence_id, ComplianceEvidence.project_id == project_id))
        if evidence is None:
            raise HTTPException(status_code=404, detail="Compliance evidence not found")
        if self.session.in_transaction():
            await self.session.commit()
        async with self.session.begin():
            if evidence.status == "ACTIVE":
                evidence.status = "REVOKED"
                evidence.revoked_at = datetime.now(timezone.utc)
                evidence.revoked_by_user_id = actor.user_id
                evidence.revocation_reason = data.reason
                self._audit(actor, "compliance.evidence_revoked", project_id, evidence.id, "compliance_evidence", {})
        return evidence

    async def evidence_for_control(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, control_id: uuid.UUID) -> list[ComplianceEvidence]:
        await self._project_member(actor, project_id)
        control = await self.session.scalar(select(ProjectComplianceControl).where(ProjectComplianceControl.id == control_id, ProjectComplianceControl.project_id == project_id))
        if control is None:
            raise HTTPException(status_code=404, detail="Compliance control not found")
        return list((await self.session.scalars(select(ComplianceEvidence).join(ControlEvidenceLink, ControlEvidenceLink.evidence_id == ComplianceEvidence.id).where(ControlEvidenceLink.project_control_id == control_id, ComplianceEvidence.project_id == project_id).order_by(ComplianceEvidence.created_at, ComplianceEvidence.id))).all())
