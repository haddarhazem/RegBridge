from __future__ import annotations
import math, re, uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember, StartupResearchNeed, StartupResearchNeedVersion, ResearchMatchRun, ResearchMatchResult
from app.modules.research.models import ResearchDiscoveryVersion

FIELDS=("domains","technologies","research_problem","keywords")
def _tokens(value):
    text=" ".join(map(str,value)) if isinstance(value,list) else str(value or "")
    return {x for x in re.findall(r"[\w-]+",text.casefold()) if len(x)>1}
def _canonical(item): return " ".join(f"{f}: {' '.join(map(str,item.get(f,[])))}" for f in FIELDS)
def _score(need, item, corpus):
    q=_tokens(_canonical(need)); docs=[_tokens(_canonical(x)) for x in corpus]; doc=_tokens(_canonical(item)); avg=sum(map(len,docs))/max(1,len(docs)); total=0.0
    for term in q:
        if term not in doc: continue
        df=sum(term in d for d in docs); idf=math.log(1+(len(docs)-df+0.5)/(df+0.5)); tf=1
        total += idf*(tf*2.2)/(tf+1.2*(0.25+0.75*len(doc)/max(1,avg)))
    return total
def _evidence(need,item):
    checks=(("domains","DOMAIN_LEXICAL_ALIGNMENT"),("technologies","TECHNOLOGY_LEXICAL_ALIGNMENT"),("research_problem","PROBLEM_LEXICAL_ALIGNMENT"),("keywords","KEYWORD_LEXICAL_ALIGNMENT"))
    reasons=[]; start=[]; research=[]
    for field,code in checks:
        if _tokens(need.get(field)) & _tokens(item.get(field)):
            reasons.append(code); start.append(field); research.append(field)
    eligible=bool(_tokens(need.get("research_problem"))&_tokens(item.get("research_problem"))) or (bool(_tokens(need.get("domains"))&_tokens(item.get("domains"))) and bool(_tokens(need.get("technologies"))&_tokens(item.get("technologies"))))
    return eligible,reasons,start,research
def _uncertainties(need,item):
    codes=[]
    labels={"domains":"DOMAIN", "technologies":"TECHNOLOGY", "research_problem":"RESEARCH_PROBLEM", "keywords":"KEYWORDS"}
    for side, values in (("STARTUP", need), ("RESEARCH", item)):
        for field in FIELDS:
            if not _tokens(values.get(field)):
                codes.append(f"MISSING_{side}_{labels[field]}")
    return codes
class ResearchMatchingService:
    def __init__(self,session:AsyncSession): self.session=session
    async def _project(self,actor,pid):
        row=await self.session.scalar(select(Project).join(ProjectMember,ProjectMember.project_id==Project.id).where(Project.id==pid,ProjectMember.user_id==actor.user_id,ProjectMember.status=="active"))
        if row is None: raise HTTPException(404,"Project not found")
        return row
    async def create_need(self,actor,pid,data):
        await self._project(actor,pid); need=StartupResearchNeed(project_id=pid); self.session.add(need); await self.session.flush(); v=StartupResearchNeedVersion(need_id=need.id,version_number=1,**data.model_dump()); self.session.add(v); await self.session.commit(); return need,v
    async def version_need(self,actor,pid,nid,data):
        await self._project(actor,pid); need=await self.session.scalar(select(StartupResearchNeed).where(StartupResearchNeed.id==nid,StartupResearchNeed.project_id==pid));
        if need is None: raise HTTPException(404,"Research need not found")
        n=(await self.session.scalar(select(func.max(StartupResearchNeedVersion.version_number)).where(StartupResearchNeedVersion.need_id==nid)) or 0)+1; v=StartupResearchNeedVersion(need_id=nid,version_number=n,**data.model_dump()); self.session.add(v); await self.session.commit(); return need,v
    async def run(self,actor,pid,nid,version_id=None,top_k=5):
        await self._project(actor,pid); need=await self.session.scalar(select(StartupResearchNeed).where(StartupResearchNeed.id==nid,StartupResearchNeed.project_id==pid));
        if need is None: raise HTTPException(404,"Research need not found")
        q=select(StartupResearchNeedVersion).where(StartupResearchNeedVersion.need_id==nid); q=q.where(StartupResearchNeedVersion.id==version_id) if version_id else q.order_by(StartupResearchNeedVersion.version_number.desc()).limit(1); nv=await self.session.scalar(q)
        if nv is None: raise HTTPException(404,"Need version not found")
        rows=(await self.session.scalars(select(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.status=="APPROVED"))).all(); eligible=[]
        need_data={f:getattr(nv,f) for f in FIELDS}
        for row in rows:
            fields={f:row.content.get("fields",{}).get(f,[]) for f in FIELDS if row.visibility.get(f)=="MATCHABLE"}; ok,reasons,srefs,rrefs=_evidence(need_data,fields)
            if ok: eligible.append((row,fields))
        corpus=[fields for _,fields in eligible]
        eligible=[(row,_score(need_data,fields,corpus)) for row,fields in eligible]
        eligible.sort(key=lambda x:(-x[1],str(x[0].id))); run=ResearchMatchRun(project_id=pid,need_version_id=nv.id,top_k=top_k,status="COMPLETED"); self.session.add(run); await self.session.flush()
        for i,(row,score) in enumerate(eligible[:top_k],1):
            fields={f:row.content.get("fields",{}).get(f,[]) for f in FIELDS if row.visibility.get(f)=="MATCHABLE"}; _,reasons,srefs,rrefs=_evidence(need_data,fields); self.session.add(ResearchMatchResult(run_id=run.id,research_discovery_version_id=row.id,rank=i,ranking_score=score,reason_codes=reasons,startup_field_refs=srefs,research_field_refs=rrefs,uncertainty_codes=_uncertainties(need_data,fields)))
        await self.session.commit(); return run
    async def get_run(self,actor,pid,rid):
        await self._project(actor,pid); run=await self.session.scalar(select(ResearchMatchRun).where(ResearchMatchRun.id==rid,ResearchMatchRun.project_id==pid));
        if run is None: raise HTTPException(404,"Match run not found")
        run.results=list((await self.session.scalars(select(ResearchMatchResult).where(ResearchMatchResult.run_id==rid).order_by(ResearchMatchResult.rank))).all()); return run
