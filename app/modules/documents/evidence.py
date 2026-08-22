"""Deterministic evidence resolution against immutable document text."""

from __future__ import annotations


class EvidenceResolutionError(ValueError):
    """Raised when a quote cannot be safely mapped to one source span."""


class EvidenceResolver:
    @staticmethod
    def resolve(document_text: str, quote: str) -> tuple[int, int]:
        if not quote:
            raise EvidenceResolutionError("Evidence quote is empty")
        positions: list[int] = []
        cursor = 0
        while True:
            position = document_text.find(quote, cursor)
            if position < 0:
                break
            positions.append(position)
            cursor = position + 1
        if not positions:
            raise EvidenceResolutionError("Evidence quote was not found in the immutable source")
        if len(positions) > 1:
            raise EvidenceResolutionError("Evidence quote is ambiguous in the immutable source")
        start = positions[0]
        end = start + len(quote)
        if document_text[start:end] != quote:
            raise EvidenceResolutionError("Evidence span invariant failed")
        return start, end
