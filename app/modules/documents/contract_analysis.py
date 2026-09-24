"""Document-first, evidence-validated primitives for contract analysis.

This module deliberately separates deterministic document structure and
evidence checks from semantic interpretation. A section is never created by
searching a clause taxonomy: the immutable uploaded text defines the initial
structure. Semantic providers may classify a detected section later, but their
claims cannot become trusted until their quoted evidence is located in that
same section.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ClauseStatus = Literal["FOUND", "MISSING", "AMBIGUOUS", "CONTRADICTORY", "OTHER", "NOT_APPLICABLE"]
RiskLevel = Literal["low", "medium", "high", "critical", "informational", "unknown"]
VerificationStatus = Literal["VERIFIED", "PARTIALLY_VERIFIED", "UNVERIFIED"]
SourceMethod = Literal["NATIVE", "OCR", "MIXED"]


class ContractEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_version_id: uuid.UUID
    quote: str = Field(min_length=1, max_length=12000)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    locator: str = Field(min_length=1, max_length=300)
    section_id: str = Field(default="legacy-section", min_length=1, max_length=80)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    source_method: SourceMethod = "NATIVE"
    verification_status: VerificationStatus = "VERIFIED"


class ClauseAnalysis(BaseModel):
    """Bounded persisted result for one actual document section or gap."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(default="legacy-section", min_length=1, max_length=80)
    clause_type: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    status: ClauseStatus
    source_text: str = Field(max_length=12000)
    source_location: str | None = Field(default=None, max_length=300)
    evidence: list[ContractEvidence] = Field(default_factory=list, max_length=4)
    verification_status: VerificationStatus = "UNVERIFIED"
    source_method: SourceMethod = "NATIVE"
    plain_language_summary: str = Field(min_length=1, max_length=2500)
    purpose: str = Field(min_length=1, max_length=1200)
    what_the_clause_requires: str | None = Field(default=None, max_length=2000)
    affected_party: str | None = Field(default=None, max_length=80)
    risk_level: RiskLevel = "unknown"
    issues: list[str] = Field(default_factory=list, max_length=8)
    why_it_matters: str | None = Field(default=None, max_length=1800)
    ambiguities: list[str] = Field(default_factory=list, max_length=8)
    missing_elements: list[str] = Field(default_factory=list, max_length=8)
    potential_consequences: list[str] = Field(default_factory=list, max_length=6)
    recommendation: str | None = Field(default=None, max_length=2000)
    suggested_revision: str | None = Field(default=None, max_length=3000)
    related_clauses: list[str] = Field(default_factory=list, max_length=8)
    confidence: float | None = Field(default=None, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list, max_length=5)


class ContractAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_type: str | None = Field(default=None, max_length=100)
    parties: list[str] = Field(default_factory=list, max_length=6)
    party_details: list["ContractParty"] = Field(default_factory=list, max_length=6)
    effective_dates: list[str] = Field(default_factory=list, max_length=6)
    clauses: list[ClauseAnalysis] = Field(default_factory=list, max_length=60)
    overall_risk_level: RiskLevel = "unknown"
    summary: str = Field(min_length=1, max_length=4000)
    recommendations: list[str] = Field(default_factory=list, max_length=20)
    missing_context: list[str] = Field(default_factory=list, max_length=12)
    semantic_status: Literal["completed", "partial"] = "partial"


class ContractExtractionError(ValueError):
    """Raised for an unavailable or unusable extracted contract."""


class ContractSection(BaseModel):
    """A document-defined region retained before semantic classification."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(min_length=1, max_length=80)
    heading: str | None = Field(default=None, max_length=240)
    raw_text: str = Field(min_length=1, max_length=16000)
    normalized_text: str = Field(min_length=1, max_length=16000)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    source_method: SourceMethod = "NATIVE"


class ContractParty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    role: str | None = Field(default=None, max_length=80)
    source_section_id: str = Field(min_length=1, max_length=80)
    source_quote: str = Field(min_length=1, max_length=800)
    page_number: int = Field(ge=1)


@dataclass(frozen=True)
class EvidenceClaim:
    section_id: str
    quote: str


def normalize_for_match(value: str) -> str:
    folded = "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(char)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", folded).split())


def _page_for_offset(source: str, offset: int) -> int:
    pages = list(re.finditer(r"(?m)^PAGE\s+(\d+)\s*$", source))
    page = 1
    for match in pages:
        if match.start() > offset:
            break
        page = int(match.group(1))
    return page


def _is_heading(value: str) -> bool:
    stripped = value.strip()
    if not stripped or len(stripped) > 180 or len(stripped.split()) > 14:
        return False
    if re.match(r"^(?:article|clause)\s+\d+(?:\s*[-.:].*)?$", stripped, flags=re.IGNORECASE):
        return True
    if re.match(r"^\d+(?:\.\d+)*[.)]\s+\S+", stripped):
        return True
    letters = "".join(character for character in stripped if character.isalpha())
    return bool(letters) and letters == letters.upper() and len(letters) >= 3


def segment_contract_text(text: str, *, source_method: SourceMethod = "NATIVE") -> list[ContractSection]:
    """Detect actual headings first, with a bounded paragraph fallback."""

    source = text.strip()
    if not source:
        raise ContractExtractionError("Document version has no extracted text")
    lines = source.splitlines(keepends=True)
    starts: list[tuple[int, str | None]] = []
    offset = 0
    for line in lines:
        clean = line.strip()
        if _is_heading(clean):
            starts.append((offset, clean))
        offset += len(line)
    sections: list[ContractSection] = []
    if starts:
        if starts[0][0] > 0 and source[: starts[0][0]].strip():
            starts.insert(0, (0, None))
        for index, (start, heading) in enumerate(starts):
            end = starts[index + 1][0] if index + 1 < len(starts) else len(source)
            raw = source[start:end].strip()
            if raw:
                actual_start = source.find(raw, start, end)
                actual_end = actual_start + len(raw)
                sections.append(
                    ContractSection(
                        section_id=f"section-{len(sections) + 1}",
                        heading=heading,
                        raw_text=raw,
                        normalized_text=normalize_for_match(raw),
                        page_start=_page_for_offset(source, actual_start),
                        page_end=_page_for_offset(source, max(actual_start, actual_end - 1)),
                        start_offset=actual_start,
                        end_offset=actual_end,
                        source_method=source_method,
                    )
                )
    else:
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n+", source) if item.strip()]
        cursor = 0
        for paragraph in paragraphs:
            start = source.find(paragraph, cursor)
            cursor = start + len(paragraph)
            sections.append(
                ContractSection(
                    section_id=f"section-{len(sections) + 1}",
                    heading=None,
                    raw_text=paragraph,
                    normalized_text=normalize_for_match(paragraph),
                    page_start=_page_for_offset(source, start),
                    page_end=_page_for_offset(source, start + len(paragraph) - 1),
                    start_offset=start,
                    end_offset=start + len(paragraph),
                    source_method=source_method,
                )
            )
    return sections[:60]


def verify_evidence_claim(
    *, section: ContractSection, claim: EvidenceClaim, document_version_id: uuid.UUID
) -> ContractEvidence | None:
    """Resolve a claim only inside its named section.

    Exact matching is preferred. A conservative word-sequence fallback accepts
    whitespace or punctuation differences only; it never searches another
    section and requires at least four meaningful tokens.
    """

    if claim.section_id != section.section_id or not claim.quote.strip():
        return None
    quote = claim.quote.strip()
    relative_start = section.raw_text.find(quote)
    if relative_start < 0:
        tokens = re.findall(r"[A-Za-z0-9À-ÖØ-öø-ÿ]+", quote)
        if len(tokens) < 4:
            return None
        expression = r"(?<!\w)" + r"\W+".join(re.escape(token) for token in tokens) + r"(?!\w)"
        match = re.search(expression, section.raw_text, flags=re.IGNORECASE | re.UNICODE)
        if match is None:
            return None
        relative_start, relative_end = match.span()
        quote = section.raw_text[relative_start:relative_end]
    else:
        relative_end = relative_start + len(quote)
    start = section.start_offset + relative_start
    end = section.start_offset + relative_end
    return ContractEvidence(
        document_version_id=document_version_id,
        quote=quote,
        start_char=start,
        end_char=end,
        locator=f"{section.heading or section.section_id} - pages {section.page_start}-{section.page_end}, characters {start}-{end}",
        section_id=section.section_id,
        page_start=section.page_start,
        page_end=section.page_end,
        source_method=section.source_method,
        verification_status="VERIFIED",
    )


def extract_parties(sections: list[ContractSection]) -> list[str]:
    """Extract bounded legal-name/role pairs from the opening sections only."""

    preamble = "\n".join(section.raw_text for section in sections[:2])[:4000]
    matches = re.finditer(
        r"\b([A-Z][A-Za-z0-9& .'-]{1,90}?\s+(?:SAS|SARL|SA|SASU|EURL|LTD|INC))\b(?:\s*,?\s*(?:ci-apr[eè]s|hereinafter)\s+(?:le|la)?\s*([A-Za-zÀ-ÖØ-öø-ÿ -]{3,40}))?",
        preamble,
        flags=re.IGNORECASE,
    )
    values: list[str] = []
    for match in matches:
        name = re.sub(r"^(?:entre|et)\s+", "", " ".join(match.group(1).split()), flags=re.IGNORECASE)
        role = " ".join((match.group(2) or "").split(".")[0].split())
        rendered = f"{name} - {role}" if role else name
        if rendered not in values:
            values.append(rendered)
    return values[:6]


def extract_party_details(sections: list[ContractSection]) -> list[ContractParty]:
    """Extract legal-name/role pairs and retain their preamble source text."""

    values: list[ContractParty] = []
    for section in sections[:2]:
        for match in re.finditer(r"\b([A-Z][A-Za-z0-9& .'-]{1,90}?\s+(?:SAS|SARL|SA|SASU|EURL|LTD|INC))\b(?:\s*,?\s*(?:ci-apr\S*|hereinafter)\s+(?:le|la)?\s*([A-Za-z -]{3,40}))?", section.raw_text[:4000], flags=re.IGNORECASE):
            name = re.sub(r"^(?:entre|et)\s+", "", " ".join(match.group(1).split()), flags=re.IGNORECASE)
            role = " ".join((match.group(2) or "").split(".")[0].split()) or None
            if any(item.name.casefold() == name.casefold() for item in values):
                continue
            values.append(ContractParty(name=name, role=role, source_section_id=section.section_id, source_quote=match.group(0).strip(), page_number=section.page_start))
    return values[:6]


def extract_parties(sections: list[ContractSection]) -> list[str]:
    return [f"{item.name} - {item.role}" if item.role else item.name for item in extract_party_details(sections)]


class ContractAnalyzer:
    """Structural fallback when external semantic analysis is not enabled.

    It does not decide that a section is ambiguous, contradictory, or risky.
    It preserves the detected document structure and verified source spans, and
    marks output partial so it cannot masquerade as semantic analysis.
    """

    def __init__(self, provider=None) -> None:
        self.provider = provider

    def analyze(
        self, *, text: str, document_version_id: uuid.UUID, source_method: SourceMethod = "NATIVE"
    ) -> ContractAnalysisOutput:
        sections = segment_contract_text(text, source_method=source_method)
        clauses = [
            ClauseAnalysis(
                section_id=section.section_id,
                clause_type="other",
                title=section.heading or f"Section {index}",
                status="OTHER",
                source_text=section.raw_text,
                source_location=f"Pages {section.page_start}-{section.page_end}",
                evidence=[
                    ContractEvidence(
                        document_version_id=document_version_id,
                        quote=section.raw_text,
                        start_char=section.start_offset,
                        end_char=section.end_offset,
                        locator=f"{section.heading or section.section_id} - pages {section.page_start}-{section.page_end}, characters {section.start_offset}-{section.end_offset}",
                        section_id=section.section_id,
                        page_start=section.page_start,
                        page_end=section.page_end,
                        source_method=section.source_method,
                    )
                ],
                verification_status="VERIFIED",
                source_method=section.source_method,
                plain_language_summary="Section structurelle detectee; une analyse semantique autorisee est requise pour qualifier les risques.",
                purpose="Conserve la structure et le texte exact du document avant interpretation semantique.",
                risk_level="informational",
                limitations=["Analyse semantique externe non activee; aucun risque n'est deduit de cette seule structure."],
            )
            for index, section in enumerate(sections, 1)
        ]
        return ContractAnalysisOutput(
            parties=extract_parties(sections),
            party_details=extract_party_details(sections),
            clauses=clauses,
            overall_risk_level="unknown",
            summary="Structure du document extraite et verifiee. L'analyse semantique necessite un fournisseur explicitement autorise.",
            missing_context=["Analyse semantique non effectuee: le traitement externe des contrats n'est pas active."],
            semantic_status="partial",
        )

    async def extract(self, *, text: str, document_version_id: uuid.UUID):
        return self.analyze(text=text, document_version_id=document_version_id), None


# Historical compatibility name. It is intentionally structural only.
ContractExtractor = ContractAnalyzer
