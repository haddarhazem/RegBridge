from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


FIELDS = ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "keywords", "limitations")
Status = Literal["SUPPORTED", "NOT_AVAILABLE"]


class FieldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=500)


class StructuredField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    items: list[FieldItem] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_state(self):
        if self.status == "SUPPORTED" and not self.items:
            raise ValueError("SUPPORTED requires at least one item")
        if self.status == "NOT_AVAILABLE" and self.items:
            raise ValueError("NOT_AVAILABLE cannot contain items")
        return self


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_version_id: str = Field(min_length=1, max_length=120)
    locator: dict


class EvidenceItem(FieldItem):
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=5)


class EvidenceField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    items: list[EvidenceItem] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_state(self):
        if self.status == "SUPPORTED" and not self.items:
            raise ValueError("SUPPORTED requires evidence-backed items")
        if self.status == "NOT_AVAILABLE" and self.items:
            raise ValueError("NOT_AVAILABLE cannot contain items")
        return self


class StructuredExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: StructuredField
    technologies: StructuredField
    research_problem: StructuredField
    methodology: StructuredField
    main_results: StructuredField
    explicit_applications: StructuredField
    limitations: StructuredField
    keywords: StructuredField
    regbridge_abstract: str = Field(default="", max_length=1200)


class EvidenceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: EvidenceField
    technologies: EvidenceField
    research_problem: EvidenceField
    methodology: EvidenceField
    main_results: EvidenceField
    explicit_applications: EvidenceField
    limitations: EvidenceField
    keywords: EvidenceField
    regbridge_abstract: str = Field(default="", max_length=1200)


class EvidenceIdItem(FieldItem):
    evidence_ids: list[str] = Field(min_length=1, max_length=5)


class EvidenceIdField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    items: list[EvidenceIdItem] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_state(self):
        if self.status == "SUPPORTED" and not self.items:
            raise ValueError("SUPPORTED requires allowlisted evidence IDs")
        if self.status == "NOT_AVAILABLE" and self.items:
            raise ValueError("NOT_AVAILABLE cannot contain items")
        return self


class EvidenceIdExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: EvidenceIdField
    technologies: EvidenceIdField
    research_problem: EvidenceIdField
    methodology: EvidenceIdField
    main_results: EvidenceIdField
    explicit_applications: EvidenceIdField
    limitations: EvidenceIdField
    keywords: EvidenceIdField
    regbridge_abstract: str = Field(default="", max_length=1200)


class ExtractiveItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_ids: list[str] = Field(min_length=1, max_length=5)


class ExtractiveField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status
    items: list[ExtractiveItem] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_state(self):
        if self.status == "SUPPORTED" and not self.items:
            raise ValueError("SUPPORTED requires source segment IDs")
        if self.status == "NOT_AVAILABLE" and self.items:
            raise ValueError("NOT_AVAILABLE cannot contain source segment IDs")
        return self


class ExtractiveExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: ExtractiveField
    technologies: ExtractiveField
    research_problem: ExtractiveField
    methodology: ExtractiveField
    main_results: ExtractiveField
    explicit_applications: ExtractiveField
    keywords: ExtractiveField
    limitations: ExtractiveField


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["SUPPORTED", "UNSUPPORTED", "UNVERIFIABLE"]
