"""Conservative candidate extraction for the derived project knowledge graph.

This module deliberately recognises only explicit, user-provided structured
lists.  It never treats a candidate as confirmed knowledge and never calls an
LLM.  Narrative free text remains available for a future opt-in extractor,
after a separately reviewed privacy decision.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


KnowledgeCandidateDomain = Literal["technology", "data"]
KnowledgeCandidateType = Literal["TECHNOLOGY", "DATA_CATEGORY"]
KnowledgeCandidateRelation = Literal["USES_TECHNOLOGY", "PROCESSES_DATA"]

ConversationCandidateDomain = Literal["technology", "data", "market", "provider"]
ConversationCandidateType = Literal["TECHNOLOGY", "DATA_CATEGORY", "MARKET", "PROVIDER"]
ConversationCandidateRelation = Literal["USES_TECHNOLOGY", "PROCESSES_DATA", "TARGETS_MARKET", "USES_PROVIDER"]


class KnowledgeConcept(BaseModel):
    """A normalized, bounded concept; it carries no claim of truth by itself."""

    model_config = ConfigDict(extra="forbid")

    concept_type: KnowledgeCandidateType
    canonical_label: str = Field(min_length=1, max_length=120)
    normalized_key: str = Field(min_length=1, max_length=140)
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=5)


class KnowledgeCandidate(BaseModel):
    """A proposed project fact that must be explicitly confirmed by a user."""

    model_config = ConfigDict(extra="forbid")

    concept: KnowledgeConcept
    domain: KnowledgeCandidateDomain
    source_field: KnowledgeCandidateDomain
    source_locator: str = Field(min_length=1, max_length=80)
    proposed_relation: KnowledgeCandidateRelation
    extraction_method: Literal["structured_delimited_v1"]

    def as_project_fact_payload(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "value": self.concept.canonical_label,
            "origin": "inferred",
            "status": "pending_confirmation",
            "provenance": {
                "source_field": self.source_field,
                "source_locator": self.source_locator,
                "excerpt": self.concept.canonical_label,
                "rule": "knowledge-graph-structured-list-v1",
                "extraction_method": self.extraction_method,
            },
            "uncertainty": "medium",
        }


class ConversationKnowledgeCandidate(BaseModel):
    """A safe, pending-only project fact proposal from one user message.

    This deliberately contains no model reasoning and no assistant content.
    It is a small contract between deterministic conversation parsing and the
    existing ``project_facts`` lifecycle.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID
    project_id: uuid.UUID
    concept_type: ConversationCandidateType
    relation_type: ConversationCandidateRelation
    value: str = Field(min_length=1, max_length=120)
    normalized_value: str = Field(min_length=1, max_length=140)
    domain: ConversationCandidateDomain
    source: Literal["COPILOT_CONVERSATION"] = "COPILOT_CONVERSATION"
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    source_excerpt: str = Field(min_length=1, max_length=300)
    status: Literal["PENDING"] = "PENDING"
    operation: Literal["ADD", "REMOVE"] = "ADD"
    extraction_method: Literal["conversation_deterministic_v1"] = "conversation_deterministic_v1"

    def as_project_fact_payload(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "value": self.value,
            "origin": "inferred",
            "status": "pending_confirmation",
            "provenance": {
                "source_field": "copilot_message",
                "source_locator": f"conversation:{self.conversation_id}:message:{self.message_id}",
                "excerpt": self.source_excerpt,
                "rule": "conversation-knowledge-deterministic-v1",
                "extraction_method": self.extraction_method,
                "source": self.source,
                "conversation_id": str(self.conversation_id),
                "message_id": str(self.message_id),
                "operation": self.operation,
            },
            "uncertainty": "medium",
        }


def normalize_concept_key(value: str) -> str:
    """Conservative identity normalization, intentionally without fuzzy matching."""
    normalized = unicodedata.normalize("NFKD", value.strip().casefold())
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return normalized[:140]


class ProjectKnowledgeCandidateExtractor:
    """Extract candidates from only explicitly delimited technology/data lists.

    A phrase such as ``we are considering sensors and predictive analytics`` is
    not a structured list and intentionally produces no candidate.  A user can
    still declare or correct it through the ordinary project workflow.
    """

    _FIELDS: dict[str, tuple[KnowledgeCandidateType, KnowledgeCandidateRelation]] = {
        "technology": ("TECHNOLOGY", "USES_TECHNOLOGY"),
        "data": ("DATA_CATEGORY", "PROCESSES_DATA"),
    }

    @staticmethod
    def _items(value: str | None) -> list[str]:
        if not value or len(value) > 2_000:
            return []
        # A comma, semicolon, bullet, or line break is an explicit user
        # structure.  Conjunctions and natural sentences are deliberately not
        # guessed at.
        if not re.search(r"[,;\n\u2022]", value):
            return []
        raw_items = re.split(r"\s*(?:[,;\n\u2022])\s*", value)
        if not 2 <= len(raw_items) <= 12:
            return []
        values: list[str] = []
        for item in raw_items:
            cleaned = re.sub(r"\s+", " ", item).strip(" -\t")
            if not cleaned or len(cleaned) > 120 or re.search(r"[.!?]", cleaned):
                return []
            values.append(cleaned)
        return values

    def extract(self, *, technology: str | None, data_context: str | None) -> list[KnowledgeCandidate]:
        inputs = {"technology": technology, "data": data_context}
        candidates: list[KnowledgeCandidate] = []
        seen: set[tuple[str, str]] = set()
        for field, value in inputs.items():
            concept_type, relation = self._FIELDS[field]
            for label in self._items(value):
                key = normalize_concept_key(label)
                identity = (field, key)
                if not key or identity in seen:
                    continue
                seen.add(identity)
                candidates.append(KnowledgeCandidate(
                    concept=KnowledgeConcept(concept_type=concept_type, canonical_label=label, normalized_key=key),
                    domain=field,
                    source_field=field,
                    source_locator=f"project.{field}",
                    proposed_relation=relation,
                    extraction_method="structured_delimited_v1",
                ))
        return candidates


class ConversationKnowledgeCandidateExtractor:
    """Extract only explicit, present-tense declarations from user content.

    It intentionally recognises a very small grammar instead of guessing from
    general prose.  This is generic (it has no product or provider vocabulary),
    provider-free, and fails closed for questions, plans and hypotheticals.
    """

    _DECLARATION_PATTERNS: tuple[tuple[re.Pattern[str], ConversationCandidateDomain, ConversationCandidateType, ConversationCandidateRelation], ...] = (
        (re.compile(r"^\s*(?:we|nous)\s+(?:(?:have|avons)\s+)?(?:chosen|chose|choisi)\s+(?P<value>\w[\w ._+/-]{0,110}?)\s+(?:for\s+(?:hosting|infrastructure)|comme\s+(?:fournisseur|hebergeur)(?:\s+(?:cloud|d['\u2019]hebergement))?|pour\s+(?:l['\u2019]?)?hebergement)\s*[.!]?\s*$", re.IGNORECASE), "provider", "PROVIDER", "USES_PROVIDER"),
        (re.compile(r"^\s*(?:we|nous)\s+(?:use|utilisons)\s+(?P<value>\w[\w ._+/-]{0,110}?)\s*[.!]?\s*$", re.IGNORECASE), "technology", "TECHNOLOGY", "USES_TECHNOLOGY"),
        (re.compile(r"^\s*(?:we|nous)\s+(?:process|traitons)\s+(?:(?:the|des|de|les)\s+)?(?P<value>(?:health|personal|customer|patient|medical|donn[\u00e9e]es?)[\w ._'\u2019/-]{0,100})\s*[.!]?\s*$", re.IGNORECASE), "data", "DATA_CATEGORY", "PROCESSES_DATA"),
        (re.compile(r"^\s*(?:we|nous)\s+(?:are\s+now\s+)?(?:targeting|ciblons\s+(?:d[\u00e9e]sormais\s+)?)\s+(?P<value>\w[\w ._+/-]{0,110}?)\s*[.!]?\s*$", re.IGNORECASE), "market", "MARKET", "TARGETS_MARKET"),
    )
    _REMOVAL = re.compile(r"^\s*(?:we|nous)\s+(?:no\s+longer\s+use|n['\u2019]utilisons\s+plus)\s+(?P<value>\w[\w ._+/-]{0,110}?)\s*[.!]?\s*$", re.IGNORECASE)
    _UNSAFE_PREFIX = re.compile(r"^\s*(?:what\s+if|should\s+we|could\s+we|maybe\b|imagine\b|explain\b|si\b|devrions[- ]nous|pourrions[- ]nous|peut[- ]etre|imaginons\b|explique(?:z)?\b)", re.IGNORECASE)

    @staticmethod
    def _value(match: re.Match[str]) -> str | None:
        value = re.sub(r"\s+", " ", match.group("value")).strip(" .,!?:;")
        if not value or len(value) > 120 or "?" in value:
            return None
        return value

    def extract(
        self,
        *,
        project_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        content: str,
    ) -> list[ConversationKnowledgeCandidate]:
        if not content or len(content) > 2_000 or "?" in content or self._UNSAFE_PREFIX.search(content):
            return []
        removal = self._REMOVAL.match(content)
        if removal:
            value = self._value(removal)
            if value is None:
                return []
            # A removal is intentionally never represented as a new positive
            # fact.  It remains pending until an editor confirms the change.
            return [self._candidate(project_id, conversation_id, message_id, value, "technology", "TECHNOLOGY", "USES_TECHNOLOGY", "REMOVE", content)]
        for pattern, domain, concept_type, relation in self._DECLARATION_PATTERNS:
            match = pattern.match(content)
            if match:
                value = self._value(match)
                if value is not None:
                    return [self._candidate(project_id, conversation_id, message_id, value, domain, concept_type, relation, "ADD", content)]
        return []

    @staticmethod
    def _candidate(
        project_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        value: str,
        domain: ConversationCandidateDomain,
        concept_type: ConversationCandidateType,
        relation: ConversationCandidateRelation,
        operation: Literal["ADD", "REMOVE"],
        content: str,
    ) -> ConversationKnowledgeCandidate:
        return ConversationKnowledgeCandidate(
            candidate_id=uuid.uuid4(), project_id=project_id, concept_type=concept_type,
            relation_type=relation, value=value, normalized_value=normalize_concept_key(value),
            domain=domain, conversation_id=conversation_id, message_id=message_id,
            source_excerpt=content.strip()[:300], operation=operation,
        )
