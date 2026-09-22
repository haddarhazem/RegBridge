"""Derived trusted project knowledge graph read model.

PostgreSQL records and facts remain the source of truth. The graph is rebuilt
on demand and contains only confirmed/corrected project knowledge and verified
regulatory assessment state. It is never a regulatory evidence store.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.modules.projects.knowledge_enrichment import normalize_concept_key


class KnowledgeNodeType(StrEnum):
    PROJECT = "PROJECT"
    SECTOR = "SECTOR"
    MARKET = "MARKET"
    GEOGRAPHY = "GEOGRAPHY"
    TECHNOLOGY = "TECHNOLOGY"
    DATA_CATEGORY = "DATA_CATEGORY"
    PROVIDER = "PROVIDER"
    BUSINESS_MODEL = "BUSINESS_MODEL"
    LIFECYCLE_STAGE = "LIFECYCLE_STAGE"
    DOCUMENT = "DOCUMENT"
    REGULATORY_ASSESSMENT = "REGULATORY_ASSESSMENT"
    REGULATORY_DOMAIN = "REGULATORY_DOMAIN"
    EVIDENCE = "EVIDENCE"


class KnowledgeRelation(StrEnum):
    HAS_SECTOR = "HAS_SECTOR"
    TARGETS_MARKET = "TARGETS_MARKET"
    OPERATES_IN = "OPERATES_IN"
    USES_TECHNOLOGY = "USES_TECHNOLOGY"
    PROCESSES_DATA = "PROCESSES_DATA"
    USES_PROVIDER = "USES_PROVIDER"
    HAS_BUSINESS_MODEL = "HAS_BUSINESS_MODEL"
    HAS_STAGE = "HAS_STAGE"
    HAS_DOCUMENT = "HAS_DOCUMENT"
    HAS_REGULATORY_ASSESSMENT = "HAS_REGULATORY_ASSESSMENT"
    AFFECTED_BY = "AFFECTED_BY"
    SUPPORTED_BY = "SUPPORTED_BY"
    DERIVED_FROM = "DERIVED_FROM"


class KnowledgeTrustStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    VERIFIED = "VERIFIED"


class KnowledgeProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(max_length=80)
    source_field: str | None = Field(default=None, max_length=80)
    source_ref: str | None = Field(default=None, max_length=120)


class KnowledgeNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    type: KnowledgeNodeType
    label: str = Field(min_length=1, max_length=500)
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=10)
    trust_status: KnowledgeTrustStatus
    provenance: KnowledgeProvenance


class KnowledgeEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)
    relation: KnowledgeRelation
    trust_status: KnowledgeTrustStatus
    provenance: KnowledgeProvenance


class GraphMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "project-knowledge-graph-v1.2.1"
    node_count: int = Field(ge=0, le=100)
    edge_count: int = Field(ge=0, le=150)
    trusted_only: bool = True


class ProjectKnowledgeGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[KnowledgeNode] = Field(default_factory=list, max_length=100)
    edges: list[KnowledgeEdge] = Field(default_factory=list, max_length=150)
    metadata: GraphMetadata


class GraphContext(BaseModel):
    """Small, safe graph projection for an agent request, never raw facts."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[KnowledgeNode] = Field(default_factory=list, max_length=30)
    edges: list[KnowledgeEdge] = Field(default_factory=list, max_length=50)
    max_depth: int = Field(default=2, ge=1, le=2)


@dataclass(frozen=True)
class GraphFactProjection:
    domain: str
    value: str
    status: str
    origin: str
    id: uuid.UUID | None = None
    provenance: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphDocumentProjection:
    id: uuid.UUID
    title: str
    document_type: str
    classification: str
    visibility: str


@dataclass(frozen=True)
class GraphRegulatoryAssessmentProjection:
    id: uuid.UUID
    version: int
    verification_verdict: str
    domains: tuple[str, ...] = ()
    evidence_organizations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectKnowledgeGraphProjection:
    project_id: uuid.UUID
    display_name: str | None
    project_type: str
    country_code: str | None
    activity: str | None
    sector: str | None
    technology: str | None
    data_context: str | None
    target_market: str | None
    location: str | None
    confirmed_fields: frozenset[str]
    # Startup profile fields are structured, user-controlled project data.  The
    # graph reader is already behind the active-member authorization boundary.
    business_model: str | None = None
    facts: tuple[GraphFactProjection, ...] = ()
    documents: tuple[GraphDocumentProjection, ...] = ()
    regulatory_assessment: GraphRegulatoryAssessmentProjection | None = None


_DOMAIN_MAPPING: dict[str, tuple[KnowledgeNodeType, KnowledgeRelation, str]] = {
    "sector": (KnowledgeNodeType.SECTOR, KnowledgeRelation.HAS_SECTOR, "sector"),
    "technology": (KnowledgeNodeType.TECHNOLOGY, KnowledgeRelation.USES_TECHNOLOGY, "technology"),
    "data": (KnowledgeNodeType.DATA_CATEGORY, KnowledgeRelation.PROCESSES_DATA, "data"),
    "provider": (KnowledgeNodeType.PROVIDER, KnowledgeRelation.USES_PROVIDER, "provider"),
    "market": (KnowledgeNodeType.MARKET, KnowledgeRelation.TARGETS_MARKET, "market"),
    "location": (KnowledgeNodeType.GEOGRAPHY, KnowledgeRelation.OPERATES_IN, "location"),
    "business_model": (KnowledgeNodeType.BUSINESS_MODEL, KnowledgeRelation.HAS_BUSINESS_MODEL, "business_model"),
}


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part).strip().casefold() for part in parts)
    return f"{prefix}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", " ", value).strip()
    return compact or None


def _graph_label(value: str, *, limit: int = 120) -> tuple[str, bool]:
    """Keep legacy prose readable without making it dominate a graph."""
    if len(value) <= limit:
        return value, False
    return value[: limit - 1].rstrip() + "…", True


_LIFECYCLE_LABELS = {
    "idea": "Projet idée",
    "startup_in_creation": "Startup en création",
    "existing_startup": "Startup existante",
}


def _canonical_items(value: str | None) -> tuple[list[str], bool]:
    """Return safe canonical atoms, or one bounded narrative fallback.

    The onboarding technology and data fields are free text.  We never infer
    concepts from prose, but an explicitly-delimited list or a compact scalar
    remains a useful canonical atomic value.  Longer prose remains visible as
    a fallback only while no confirmed fact represents that category.
    """
    cleaned = _clean(value)
    if cleaned is None:
        return [], False
    listed = _explicit_items(cleaned)
    if listed:
        return listed, False
    words = re.findall(r"[\wÀ-ÿ'-]+", cleaned)
    is_narrative = len(cleaned) > 120 or len(words) > 7 or bool(re.search(r"[.!?\n]", cleaned))
    return ([cleaned], is_narrative)


_SOURCE_PRIORITY = {
    "project_field": 2,
    "startup_profile_field": 2,
    "project_fact": 4,
    "project_record": 3,
    "document_metadata": 3,
    "verified_regulatory_assessment": 5,
}


def _explicit_items(value: str | None) -> list[str]:
    """Use direct atomic values only where user syntax made a list explicit."""
    cleaned = _clean(value)
    if not cleaned or not re.search(r"[,;\n\u2022]", cleaned):
        return []
    values = [re.sub(r"\s+", " ", item).strip(" -\t") for item in re.split(r"\s*(?:[,;\n\u2022])\s*", cleaned)]
    if not 2 <= len(values) <= 12 or any(not item or len(item) > 120 or re.search(r"[.!?]", item) for item in values):
        return []
    return values


class ProjectKnowledgeGraphBuilder:
    """Map only trusted stored project data into a deterministic graph."""

    def build(self, projection: ProjectKnowledgeGraphProjection) -> ProjectKnowledgeGraph:
        nodes: dict[str, KnowledgeNode] = {}
        edges: dict[str, KnowledgeEdge] = {}
        project_id = f"project:{projection.project_id}"
        self._node(nodes, KnowledgeNode(
            id=project_id,
            type=KnowledgeNodeType.PROJECT,
            label=_clean(projection.display_name) or "Projet",
            properties={"project_type": projection.project_type, "country_code": projection.country_code},
            trust_status=KnowledgeTrustStatus.CONFIRMED,
            provenance=KnowledgeProvenance(source_type="project_record", source_ref=str(projection.project_id)),
        ))
        stage_id = self._value_node(nodes, projection.project_id, KnowledgeNodeType.LIFECYCLE_STAGE, projection.project_type, "project_record", "project_type", "project_type")
        if stage_id:
            self._edge(edges, project_id, stage_id, KnowledgeRelation.HAS_STAGE, KnowledgeTrustStatus.CONFIRMED, "project_record", "project_type", "project_type")

        trusted_facts = [fact for fact in projection.facts if fact.status in {"confirmed", "corrected"}]
        # Facts are explicit user confirmations.  They suppress only a broad
        # technology/data narrative from the same category; canonical atomic
        # values stay available and collapse through stable normalized IDs.
        atomic_fact_domains = {fact.domain for fact in trusted_facts if fact.domain in _DOMAIN_MAPPING}
        direct_values = {
            "sector": projection.sector,
            "technology": projection.technology,
            "data": projection.data_context,
            "market": projection.target_market,
            "location": projection.location,
            "business_model": projection.business_model,
        }
        for domain, value in direct_values.items():
            if domain != "business_model" and domain not in projection.confirmed_fields:
                continue
            # Only technology/data are free-text onboarding fields where an
            # explicit delimiter represents several concepts.  A comma inside
            # a structured location (for example "Paris, France") remains one
            # geographic value; source-field semantics always win over text.
            if domain in {"technology", "data"}:
                atomic_values, is_narrative = _canonical_items(value)
            else:
                cleaned = _clean(value)
                atomic_values, is_narrative = ([cleaned], False) if cleaned else ([], False)
            if not atomic_values:
                continue
            # Only the free-text fields can be represented as narrative
            # fallbacks.  Other fields are structured by their source-field
            # meaning, never classified from their text.
            if domain in {"technology", "data"} and is_narrative and domain in atomic_fact_domains:
                continue
            source_type = "startup_profile_field" if domain == "business_model" else "project_field"
            self._add_project_values(
                nodes,
                edges,
                projection.project_id,
                project_id,
                domain,
                atomic_values,
                source_type,
                domain,
                domain,
                narrative_fallback=domain in {"technology", "data"} and is_narrative,
            )
        for fact in trusted_facts:
            self._add_project_value(
                nodes, edges, projection.project_id, project_id, fact.domain, fact.value,
                "project_fact", str(fact.id) if fact.id else fact.domain,
                str(fact.provenance.get("source_field") or fact.domain),
            )
        for document in projection.documents:
            label = _clean(document.title)
            if not label:
                continue
            document_id = self._value_node(
                nodes, projection.project_id, KnowledgeNodeType.DOCUMENT, label,
                "document_metadata", str(document.id), "title",
                {"document_type": document.document_type, "classification": document.classification, "visibility": document.visibility},
            )
            if document_id:
                self._edge(edges, project_id, document_id, KnowledgeRelation.HAS_DOCUMENT, KnowledgeTrustStatus.CONFIRMED, "document_metadata", str(document.id), "title")
        if projection.regulatory_assessment is not None:
            self._add_verified_regulatory_state(nodes, edges, project_id, projection.project_id, projection.regulatory_assessment)
        ordered_nodes = sorted(nodes.values(), key=lambda item: (item.type.value, item.label.casefold(), item.id))
        ordered_edges = sorted(edges.values(), key=lambda item: (item.relation.value, item.source, item.target, item.id))
        return ProjectKnowledgeGraph(nodes=ordered_nodes, edges=ordered_edges, metadata=GraphMetadata(node_count=len(ordered_nodes), edge_count=len(ordered_edges)))

    def _add_project_value(self, nodes: dict[str, KnowledgeNode], edges: dict[str, KnowledgeEdge], project_uuid: uuid.UUID, project_id: str, domain: str, value: str | None, source_type: str, source_ref: str, source_field: str) -> None:
        """Add a fact value, which is always an explicit atomic assertion."""
        label = _clean(value)
        if label is None:
            return
        self._add_project_values(
            nodes, edges, project_uuid, project_id, domain, [label], source_type,
            source_ref, source_field, narrative_fallback=False,
        )

    def _add_project_values(self, nodes: dict[str, KnowledgeNode], edges: dict[str, KnowledgeEdge], project_uuid: uuid.UUID, project_id: str, domain: str, values: list[str], source_type: str, source_ref: str, source_field: str, *, narrative_fallback: bool) -> None:
        mapped = _DOMAIN_MAPPING.get(domain)
        if mapped is None:
            return
        node_type, relation, _ = mapped
        for atomic_label in values:
            node_id = self._value_node(
                nodes,
                project_uuid,
                node_type,
                atomic_label,
                source_type,
                source_ref,
                source_field,
                {"knowledge_kind": "narrative_fallback" if narrative_fallback else "atomic"},
            )
            if node_id:
                self._edge(edges, project_id, node_id, relation, KnowledgeTrustStatus.CONFIRMED, source_type, source_ref, source_field)

    def _add_verified_regulatory_state(self, nodes: dict[str, KnowledgeNode], edges: dict[str, KnowledgeEdge], project_id: str, project_uuid: uuid.UUID, assessment: GraphRegulatoryAssessmentProjection) -> None:
        assessment_id = self._value_node(
            nodes, project_uuid, KnowledgeNodeType.REGULATORY_ASSESSMENT,
            f"Evaluation reglementaire v{assessment.version}", "verified_regulatory_assessment", str(assessment.id), "verification_verdict",
            {"version": assessment.version, "verification_verdict": assessment.verification_verdict},
            trust_status=KnowledgeTrustStatus.VERIFIED,
        )
        if not assessment_id:
            return
        self._edge(edges, project_id, assessment_id, KnowledgeRelation.HAS_REGULATORY_ASSESSMENT, KnowledgeTrustStatus.VERIFIED, "verified_regulatory_assessment", str(assessment.id), "verification_verdict")
        for domain in assessment.domains:
            label = _clean(domain)
            if not label:
                continue
            domain_id = self._value_node(nodes, project_uuid, KnowledgeNodeType.REGULATORY_DOMAIN, label, "verified_regulatory_assessment", str(assessment.id), "regulatory_domains", trust_status=KnowledgeTrustStatus.VERIFIED)
            if domain_id:
                self._edge(edges, project_id, domain_id, KnowledgeRelation.AFFECTED_BY, KnowledgeTrustStatus.VERIFIED, "verified_regulatory_assessment", str(assessment.id), "regulatory_domains")
        for organization in assessment.evidence_organizations:
            label = _clean(organization)
            if not label:
                continue
            evidence_id = self._value_node(nodes, project_uuid, KnowledgeNodeType.EVIDENCE, label, "verified_regulatory_assessment", str(assessment.id), "source_provenance", trust_status=KnowledgeTrustStatus.VERIFIED)
            if evidence_id:
                self._edge(edges, assessment_id, evidence_id, KnowledgeRelation.SUPPORTED_BY, KnowledgeTrustStatus.VERIFIED, "verified_regulatory_assessment", str(assessment.id), "source_provenance")

    @staticmethod
    def _node(nodes: dict[str, KnowledgeNode], node: KnowledgeNode) -> None:
        existing = nodes.get(node.id)
        if existing is None or _SOURCE_PRIORITY.get(node.provenance.source_type, 0) > _SOURCE_PRIORITY.get(existing.provenance.source_type, 0):
            nodes[node.id] = node

    def _value_node(self, nodes: dict[str, KnowledgeNode], project_id: uuid.UUID, node_type: KnowledgeNodeType, label: str | None, source_type: str, source_ref: str, source_field: str, properties: dict[str, str | int | float | bool | None] | None = None, trust_status: KnowledgeTrustStatus = KnowledgeTrustStatus.CONFIRMED) -> str | None:
        cleaned = _clean(label)
        if cleaned is None:
            return None
        normalized_key = normalize_concept_key(cleaned)
        if not normalized_key:
            return None
        display_label, truncated = _graph_label(
            _LIFECYCLE_LABELS.get(cleaned, cleaned)
            if node_type == KnowledgeNodeType.LIFECYCLE_STAGE
            else cleaned
        )
        node_id = _stable_id("node", project_id, node_type.value, normalized_key)
        node_properties = dict(properties or {})
        if node_type != KnowledgeNodeType.DOCUMENT:
            node_properties["normalized_key"] = normalized_key
        if node_type == KnowledgeNodeType.LIFECYCLE_STAGE:
            # Keep the immutable stored enum accessible in the API without
            # making it the user-facing node label.
            node_properties["canonical_value"] = cleaned
        if truncated:
            node_properties["display_value_truncated"] = True
        self._node(nodes, KnowledgeNode(
            id=node_id, type=node_type, label=display_label, properties=node_properties,
            trust_status=trust_status,
            provenance=KnowledgeProvenance(source_type=source_type, source_field=source_field, source_ref=source_ref),
        ))
        return node_id

    @staticmethod
    def _edge(edges: dict[str, KnowledgeEdge], source: str, target: str, relation: KnowledgeRelation, trust_status: KnowledgeTrustStatus, source_type: str, source_ref: str, source_field: str) -> None:
        edge_id = _stable_id("edge", source, relation.value, target)
        edge = KnowledgeEdge(
            id=edge_id, source=source, target=target, relation=relation,
            trust_status=trust_status,
            provenance=KnowledgeProvenance(source_type=source_type, source_field=source_field, source_ref=source_ref),
        )
        existing = edges.get(edge_id)
        if existing is None or _SOURCE_PRIORITY.get(source_type, 0) > _SOURCE_PRIORITY.get(existing.provenance.source_type, 0):
            edges[edge_id] = edge


class GraphContextProvider:
    """Deterministically select one bounded, trusted, question-relevant subgraph."""

    max_nodes = 24
    max_edges = 32
    max_depth = 2

    _QUESTION_TYPES = {
        KnowledgeNodeType.DATA_CATEGORY: ("donnee", "rgpd", "privacy", "personnelle"),
        KnowledgeNodeType.TECHNOLOGY: ("ia", "intelligence artificielle", "technologie", "cloud", "saas"),
        KnowledgeNodeType.PROVIDER: ("fournisseur", "provider", "hebergement", "hébergement", "hosting", "cloud", "infrastructure"),
        KnowledgeNodeType.SECTOR: ("secteur", "marche", "client"),
        KnowledgeNodeType.MARKET: ("marche", "client", "cible", "financement"),
        KnowledgeNodeType.GEOGRAPHY: ("pays", "france", "europe", "localisation", "geographique", "opere"),
        KnowledgeNodeType.BUSINESS_MODEL: ("modele economique", "business model"),
        KnowledgeNodeType.REGULATORY_ASSESSMENT: ("reglement", "obligation", "conformite", "evaluation"),
        KnowledgeNodeType.REGULATORY_DOMAIN: ("reglement", "obligation", "conformite", "evaluation"),
        KnowledgeNodeType.EVIDENCE: ("reglement", "obligation", "source", "preuve", "conformite"),
    }

    def select(self, graph: ProjectKnowledgeGraph, question: str) -> GraphContext:
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFKD", question.casefold())
            if not unicodedata.combining(character)
        )
        normalized = re.sub(r"\s+", " ", normalized)
        requested_types = {node_type for node_type, terms in self._QUESTION_TYPES.items() if any(term in normalized for term in terms)}
        node_by_id = {node.id: node for node in graph.nodes}
        selected_ids = {node.id for node in graph.nodes if node.type == KnowledgeNodeType.PROJECT}
        selected_edges: list[KnowledgeEdge] = []
        frontier = set(selected_ids)
        for depth in range(1, self.max_depth + 1):
            next_frontier: set[str] = set()
            for edge in graph.edges:
                if edge.source not in frontier or edge.target in selected_ids:
                    continue
                target = node_by_id.get(edge.target)
                if target is None or (depth == 1 and requested_types and target.type not in requested_types):
                    continue
                if len(selected_ids) >= self.max_nodes or len(selected_edges) >= self.max_edges:
                    break
                selected_ids.add(target.id)
                selected_edges.append(edge)
                next_frontier.add(target.id)
            frontier = next_frontier
            if not frontier:
                break
        nodes = [node for node in graph.nodes if node.id in selected_ids][: self.max_nodes]
        node_ids = {node.id for node in nodes}
        edges = [edge for edge in selected_edges if edge.source in node_ids and edge.target in node_ids][: self.max_edges]
        return GraphContext(nodes=nodes, edges=edges, max_depth=self.max_depth)


class ProjectKnowledgeGraphRepository(Protocol):
    async def has_active_membership(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...
    async def load_knowledge_graph_projection(self, project_id: uuid.UUID) -> ProjectKnowledgeGraphProjection | None: ...


class ProjectKnowledgeGraphAccessDenied(Exception):
    """Deliberately indistinguishable denied and absent graph access."""


class ProjectKnowledgeGraphService:
    def __init__(self, repository: ProjectKnowledgeGraphRepository, builder: ProjectKnowledgeGraphBuilder | None = None) -> None:
        self.repository = repository
        self.builder = builder or ProjectKnowledgeGraphBuilder()

    async def get_trusted_graph(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectKnowledgeGraph:
        if not await self.repository.has_active_membership(project_id, user_id):
            raise ProjectKnowledgeGraphAccessDenied("Project knowledge graph not found")
        projection = await self.repository.load_knowledge_graph_projection(project_id)
        if projection is None:
            raise ProjectKnowledgeGraphAccessDenied("Project knowledge graph not found")
        return self.builder.build(projection)
