"""Deterministic native document extraction and OCR fallback contracts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.config import get_settings


class ExtractionError(Exception):
    def __init__(self, category: str, message: str = "Document extraction failed") -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class ExtractionResult:
    normalized_text: str
    pages: tuple[str, ...]
    method: str
    extractor_version: str
    provider: str | None = None
    model: str | None = None
    page_methods: tuple[str, ...] = ()
    ocr_required_pages: tuple[int, ...] = ()

    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(self.normalized_text.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    """Normalize transport artefacts without rewriting meaningful document text."""
    value = value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    return value.strip()


def page_text(pages: list[str] | tuple[str, ...]) -> str:
    normalized_pages = [normalize_text(page) for page in pages]
    return "\n\n".join(f"PAGE {index}\n{page}" for index, page in enumerate(normalized_pages, 1) if page).strip()


def pdf_ocr_required_pages(pages: list[str] | tuple[str, ...], *, min_pdf_chars: int) -> tuple[int, ...]:
    """Return only clearly unusable pages; images alone are not enough.

    The threshold is deliberately lower than the whole-document threshold so a
    short but legible page is retained natively. An entirely unreadable PDF is
    still represented by ``OCR_REQUIRED`` in ``extract_native``.
    """

    per_page_minimum = max(8, min_pdf_chars // 4)
    return tuple(
        index for index, page in enumerate(pages, 1)
        if len(re.sub(r"\s+", "", normalize_text(page))) < per_page_minimum
    )


def extraction_status(version) -> str:
    metadata = version.extraction_metadata or {}
    extraction = metadata.get("extraction") if isinstance(metadata, dict) else None
    status = extraction.get("status") if isinstance(extraction, dict) else None
    if status in {"pending", "processing", "ready", "failed"}:
        return status
    # Versions created before the worker existed already have a valid extraction.
    return "ready" if bool(version.extracted_text) else "pending"


def extract_native(path: Path, extension: str, *, min_pdf_chars: int | None = None) -> ExtractionResult:
    if extension == ".txt":
        try:
            text = normalize_text(path.read_bytes().decode("utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise ExtractionError("NATIVE_EXTRACTION_FAILED", "TXT is not valid UTF-8") from exc
        if not text:
            raise ExtractionError("EMPTY_EXTRACTION", "TXT contains no usable text")
        return ExtractionResult(text, (text,), "native", "native-text-v1", page_methods=("NATIVE",))

    if extension == ".docx":
        text = _extract_docx(path)
        if not text:
            raise ExtractionError("OCR_REQUIRED", "DOCX has no sufficient native text")
        return ExtractionResult(text, (text,), "native", "native-docx-v1", page_methods=("NATIVE",))

    if extension == ".pdf":
        try:
            pages = [normalize_text(page.extract_text() or "") for page in PdfReader(str(path)).pages]
        except Exception as exc:
            raise ExtractionError("NATIVE_EXTRACTION_FAILED", "PDF text extraction failed") from exc
        text = page_text(pages)
        threshold = min_pdf_chars if min_pdf_chars is not None else get_settings().document_native_text_min_chars
        if len(re.sub(r"\s+", "", text)) >= threshold:
            required = pdf_ocr_required_pages(pages, min_pdf_chars=threshold)
            return ExtractionResult(
                text,
                tuple(pages),
                "native",
                "native-pdf-v2",
                page_methods=tuple("OCR_REQUIRED" if index in required else "NATIVE" for index in range(1, len(pages) + 1)),
                ocr_required_pages=required,
            )
        raise ExtractionError("OCR_REQUIRED", "PDF has no sufficient native text")

    raise ExtractionError("UNSUPPORTED_FORMAT", "Unsupported document format")


def _extract_docx(path: Path) -> str:
    try:
        document = DocxDocument(str(path))
        parts: list[str] = []
        for child in document.element.body.iterchildren():
            if child.tag.endswith("}p"):
                value = "".join(node.text or "" for node in child.iter() if node.tag.endswith("}t"))
                if value.strip():
                    parts.append(value)
            elif child.tag.endswith("}tbl"):
                for row in child.iterchildren():
                    cells = []
                    for cell in row.iterchildren():
                        cell_text = " ".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
                        cells.append(normalize_text(cell_text))
                    if any(cells):
                        parts.append("\t".join(cells))
        return normalize_text("\n".join(parts))
    except Exception as exc:
        raise ExtractionError("NATIVE_EXTRACTION_FAILED", "DOCX text extraction failed") from exc
