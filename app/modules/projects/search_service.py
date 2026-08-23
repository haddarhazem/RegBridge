from __future__ import annotations
import uuid
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project
from app.modules.projects.profile_models import StartupProfile, StartupProfileRevision
from app.modules.projects.search_schemas import StartupSearchFilters, StartupSearchResponse, StartupSearchResult
from app.modules.sharing.models import InvestorShareGrant

PUBLIC = "public"

class StartupSearchService:
    """One query-time-authorized startup search path; no Python post-filtering."""
    def __init__(self, session: AsyncSession) -> None: self.session=session

    def _shared_exists(self, actor: AuthenticatedPrincipal):
        return exists(select(1).select_from(StartupProfile).join(StartupProfileRevision, and_(StartupProfileRevision.profile_id == StartupProfile.id, StartupProfileRevision.revision_number == StartupProfile.current_revision)).join(InvestorShareGrant, and_(InvestorShareGrant.project_id == StartupProfile.project_id, InvestorShareGrant.resource_id == StartupProfileRevision.id)).where(StartupProfile.project_id == Project.id, InvestorShareGrant.recipient_user_id == actor.user_id, InvestorShareGrant.resource_type == "STARTUP_PROFILE_REVISION", InvestorShareGrant.status == "ACTIVE", InvestorShareGrant.scope == "READ"))

    def _authorized_query(self, actor: AuthenticatedPrincipal):
        return select(Project).where(Project.project_type.in_(["startup_in_creation", "existing_startup"]), or_(Project.visibility == PUBLIC, self._shared_exists(actor)))

    def _apply_filters(self, query, filters: StartupSearchFilters):
        values={"sector":Project.sector,"stage":Project.current_progress,"geography":Project.location,"technology":Project.technology}
        for name,column in values.items():
            value=getattr(filters,name)
            if value is not None:
                # Project fields are searchable only for public projects. A
                # shared private profile cannot leak its private project row.
                query=query.where(and_(Project.visibility == PUBLIC, func.lower(column) == value.strip().lower()))
        return query

    def _ordering(self, query, filters: StartupSearchFilters):
        columns={"name":Project.display_name,"sector":Project.sector,"stage":Project.current_progress,"geography":Project.location,"technology":Project.technology}
        column=columns[filters.sort]
        public_value=case((Project.visibility == PUBLIC,column),else_=None)
        return query.order_by(public_value.asc().nulls_last(), Project.id.asc())

    async def search(self, actor: AuthenticatedPrincipal, filters: StartupSearchFilters) -> StartupSearchResponse:
        # The authorization predicate is present before filters, count, offset,
        # and limit. A separate bulk projection query avoids per-row grant lookups.
        base=self._apply_filters(self._authorized_query(actor),filters)
        total=int(await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0)
        query=self._ordering(base,filters).offset((filters.page-1)*filters.limit).limit(filters.limit)
        projects=list((await self.session.scalars(query)).all()); ids=[project.id for project in projects]
        revisions={}
        if ids:
            revision_rows=(await self.session.execute(select(StartupProfile.project_id,StartupProfileRevision.snapshot).join(StartupProfileRevision,and_(StartupProfileRevision.profile_id == StartupProfile.id,StartupProfileRevision.revision_number == StartupProfile.current_revision)).where(StartupProfile.project_id.in_(ids)))).all()
            revisions={project_id:snapshot or [] for project_id,snapshot in revision_rows}
        shared_ids=set()
        if ids:
            shared_ids=set((await self.session.scalars(select(InvestorShareGrant.project_id).join(StartupProfile,and_(StartupProfile.project_id == InvestorShareGrant.project_id)).join(StartupProfileRevision,and_(StartupProfileRevision.profile_id == StartupProfile.id,StartupProfileRevision.revision_number == StartupProfile.current_revision,StartupProfileRevision.id == InvestorShareGrant.resource_id)).where(InvestorShareGrant.project_id.in_(ids),InvestorShareGrant.recipient_user_id == actor.user_id,InvestorShareGrant.resource_type == "STARTUP_PROFILE_REVISION",InvestorShareGrant.status == "ACTIVE",InvestorShareGrant.scope == "READ"))).all())
        items=[]
        for project in projects:
            public_project=project.visibility == PUBLIC
            snapshot=revisions.get(project.id,[])
            public_fields={item["field_name"]:item.get("value") for item in snapshot if item.get("visibility") == "PUBLIC" and public_project}
            shared_fields={item["field_name"]:item.get("value") for item in snapshot if item.get("visibility") == "INVESTOR_SHARED" and project.id in shared_ids}
            items.append(StartupSearchResult(startup_id=project.id,display_name=project.display_name if public_project else None,sector=project.sector if public_project else None,stage=project.current_progress if public_project else None,geography=project.location if public_project else None,technology=project.technology if public_project else None,public_fields=public_fields,shared_fields=shared_fields))
        return StartupSearchResponse(items=items,page=filters.page,limit=filters.limit,total_count=total)
