from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.compliance.models import ComplianceControlDefinition, ComplianceEvidence, ComplianceFrameworkVersion, ComplianceScoreCalculation, ControlEvidenceLink, ProjectComplianceControl, ProjectFrameworkAdoption
from app.modules.compliance.scoring import EVIDENCE_POLICY_VERSION, METHOD_KEY, METHOD_VERSION, ROUNDING_POLICY, ScoringControl, calculate
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember

class ComplianceScoreService:
    def __init__(self, session: AsyncSession) -> None: self.session = session

    async def _authorize(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, edit: bool = False) -> None:
        project = await self.session.scalar(select(Project).where(Project.id == project_id))
        member = await self.session.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == actor.user_id, ProjectMember.status == "active"))
        if project is None or member is None or (edit and member.member_role not in {"owner", "founder", "admin"}):
            raise HTTPException(status_code=403 if edit else 404, detail="Project compliance score access denied")

    async def _controls(self, project_id: uuid.UUID, framework_version_id: uuid.UUID | None) -> list[ScoringControl]:
        query = select(ProjectComplianceControl).join(ProjectFrameworkAdoption, ProjectFrameworkAdoption.framework_version_id == ProjectComplianceControl.framework_version_id).where(ProjectComplianceControl.project_id == project_id, ProjectFrameworkAdoption.project_id == project_id, ProjectFrameworkAdoption.status == "active")
        if framework_version_id is not None: query = query.where(ProjectComplianceControl.framework_version_id == framework_version_id)
        controls = list((await self.session.scalars(query.order_by(ProjectComplianceControl.created_at, ProjectComplianceControl.id))).all())
        if not controls:
            return []
        definition_ids = {control.control_definition_id for control in controls}
        definitions = {item.id: item for item in (await self.session.scalars(select(ComplianceControlDefinition).where(ComplianceControlDefinition.id.in_(definition_ids)))).all()}
        control_ids = [control.id for control in controls]
        evidence_rows = list((await self.session.execute(select(ControlEvidenceLink.project_control_id, ComplianceEvidence).join(ComplianceEvidence, ComplianceEvidence.id == ControlEvidenceLink.evidence_id).where(ControlEvidenceLink.project_control_id.in_(control_ids), ComplianceEvidence.project_id == project_id).order_by(ComplianceEvidence.created_at, ComplianceEvidence.id))).all())
        evidence_by_control: dict[uuid.UUID, list[ComplianceEvidence]] = {}
        for control_id, evidence in evidence_rows:
            evidence_by_control.setdefault(control_id, []).append(evidence)
        result=[]
        for control in controls:
            definition = definitions[control.control_definition_id]
            evidence = evidence_by_control.get(control.id, [])
            result.append(ScoringControl(id=str(control.id), definition_id=str(control.control_definition_id), framework_version_id=str(control.framework_version_id), stable_key=definition.stable_key, title=definition.title, status=control.status, applicability=control.applicability, evidence=tuple({"id": str(e.id), "status": e.status} for e in evidence)))
        return result

    async def calculate_current(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, framework_version_id: uuid.UUID | None = None, method_version: str = METHOD_VERSION) -> ComplianceScoreCalculation:
        # A repeatable-read snapshot keeps controls and evidence from mixing
        # states when a concurrent revoke commits during this calculation.
        if not self.session.in_transaction():
            await self.session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        await self._authorize(actor, project_id, edit=True)
        if method_version != METHOD_VERSION: raise HTTPException(status_code=400, detail="Unknown compliance scoring method version")
        if framework_version_id is not None:
            version = await self.session.get(ComplianceFrameworkVersion, framework_version_id)
            adopted = await self.session.scalar(select(ProjectFrameworkAdoption.id).where(ProjectFrameworkAdoption.project_id == project_id, ProjectFrameworkAdoption.framework_version_id == framework_version_id, ProjectFrameworkAdoption.status == "active"))
            if version is None: raise HTTPException(status_code=404, detail="Framework version not found")
            if adopted is None: raise HTTPException(status_code=409, detail="Framework version is not actively adopted by this project")
        controls = await self._controls(project_id, framework_version_id)
        result = calculate(controls)
        snapshot = {"project_control_ids": [c.id for c in controls], "controls": [{"id":c.id,"definition_id":c.definition_id,"framework_version_id":c.framework_version_id,"status":c.status,"applicability":c.applicability,"evidence":[dict(e) for e in c.evidence]} for c in controls]}
        calculation = ComplianceScoreCalculation(project_id=project_id, framework_version_id=framework_version_id, method_key=METHOD_KEY, method_version=METHOD_VERSION, evidence_policy_version=EVIDENCE_POLICY_VERSION, rounding_policy=ROUNDING_POLICY, calculated_at=datetime.now(timezone.utc), numerator=result["numerator"], denominator=result["denominator"], score=result["score"], evidence_coverage=result["evidence_coverage"], input_snapshot=snapshot, explanation=result)
        self.session.add(calculation)
        await self.session.flush()
        await self.session.commit()
        return calculation

    async def latest(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, framework_version_id: uuid.UUID | None = None) -> ComplianceScoreCalculation:
        await self._authorize(actor, project_id)
        query=select(ComplianceScoreCalculation).where(ComplianceScoreCalculation.project_id == project_id)
        if framework_version_id is None: query=query.where(ComplianceScoreCalculation.framework_version_id.is_(None))
        else: query=query.where(ComplianceScoreCalculation.framework_version_id == framework_version_id)
        item=await self.session.scalar(query.order_by(ComplianceScoreCalculation.calculated_at.desc(), ComplianceScoreCalculation.id.desc()).limit(1))
        if item is None: raise HTTPException(status_code=404, detail="No compliance score calculation exists")
        return item

    async def history(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, framework_version_id: uuid.UUID | None = None) -> list[ComplianceScoreCalculation]:
        await self._authorize(actor, project_id)
        query=select(ComplianceScoreCalculation).where(ComplianceScoreCalculation.project_id == project_id)
        if framework_version_id is None: query=query.where(ComplianceScoreCalculation.framework_version_id.is_(None))
        else: query=query.where(ComplianceScoreCalculation.framework_version_id == framework_version_id)
        return list((await self.session.scalars(query.order_by(ComplianceScoreCalculation.calculated_at))).all())

    async def get(self, actor: AuthenticatedPrincipal, project_id: uuid.UUID, score_id: uuid.UUID) -> ComplianceScoreCalculation:
        await self._authorize(actor, project_id)
        item = await self.session.scalar(select(ComplianceScoreCalculation).where(ComplianceScoreCalculation.id == score_id, ComplianceScoreCalculation.project_id == project_id))
        if item is None:
            raise HTTPException(status_code=404, detail="Compliance score calculation not found")
        return item
