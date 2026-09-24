"""Small provider-neutral OCR adapter backed by the installed Mistral SDK."""

from __future__ import annotations

from typing import Any, Protocol

from mistralai.client import Mistral
from mistralai.client.models import File, FileChunk

from app.core.config import Settings, get_settings
from app.core.observability import dependency_result, elapsed_ms, emit_event
from app.modules.documents.extraction import ExtractionError, ExtractionResult, normalize_text
import time


class OcrProvider(Protocol):
    async def extract(self, document_bytes: bytes, filename: str, mime_type: str) -> ExtractionResult: ...


class OcrFailure(ExtractionError):
    pass


class MistralOcrProvider:
    def __init__(self, *, api_key, model: str, client: Any | None = None, timeout_ms: int | None = None) -> None:
        key = api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else api_key
        if not key:
            raise OcrFailure("OCR_PROVIDER_UNAVAILABLE", "Mistral OCR is not configured")
        self.model = model
        self.timeout_ms = timeout_ms
        self._client = client or Mistral(api_key=key)

    async def extract(self, document_bytes: bytes, filename: str, mime_type: str) -> ExtractionResult:
        started = time.perf_counter()
        uploaded_id: str | None = None
        result: ExtractionResult | None = None
        try:
            uploaded = await self._client.files.upload_async(
                file=File(fileName=filename, content=document_bytes, content_type=mime_type),
                purpose="ocr",
                visibility="user",
                timeout_ms=self.timeout_ms,
            )
            uploaded_id = str(uploaded.id)
            response = await self._client.ocr.process_async(
                model=self.model,
                document=FileChunk(file_id=uploaded_id),
                include_image_base64=False,
                include_blocks=False,
                timeout_ms=self.timeout_ms,
            )
            pages = [normalize_text(str(getattr(page, "markdown", "") or "")) for page in getattr(response, "pages", [])]
            text = "\n\n".join(f"PAGE {index}\n{page}" for index, page in enumerate(pages, 1) if page).strip()
            if not text:
                raise OcrFailure("OCR_INVALID_RESPONSE", "Mistral OCR returned no usable text")
            result = ExtractionResult(
                text,
                tuple(pages),
                "mistral_ocr",
                "mistral-ocr-v2",
                "mistral",
                str(getattr(response, "model", self.model)),
                page_methods=tuple("OCR" for _ in pages),
            )
            return result
        except OcrFailure:
            raise
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            category = "OCR_TIMEOUT" if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.casefold() else "OCR_PROVIDER_UNAVAILABLE"
            if status_code == 429 or isinstance(status_code, int) and status_code >= 500:
                category = "OCR_PROVIDER_UNAVAILABLE"
            raise OcrFailure(category) from exc
        finally:
            if uploaded_id is not None:
                try:
                    await self._client.files.delete_async(file_id=uploaded_id, timeout_ms=self.timeout_ms)
                except Exception as cleanup_error:
                    emit_event("document.ocr.cleanup_failed", component="document_extraction", error_category=type(cleanup_error).__name__)
                    if result is None:
                        # The original processing error remains the meaningful failure.
                        pass
            dependency_result(dependency="mistral", operation="document_ocr", status="ok" if result else "error", duration_ms=elapsed_ms(started), error_category=None if result else "OCR_FAILED")


def get_ocr_provider() -> OcrProvider:
    settings: Settings = get_settings()
    return MistralOcrProvider(api_key=settings.mistral_api_key, model=settings.mistral_ocr_model)
