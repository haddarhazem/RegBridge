"""Safe, opt-in smoke tests for the configured Mistral boundaries.

These tests deliberately validate availability and response shape only. They
never print provider responses, prompts, document text, credentials, or
authorization material, and they are skipped during ordinary regression.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import NoReturn

import pytest

from app.core.config import get_settings
from app.modules.ai.llm import (
    LLMGenerationError,
    LLMGenerationRequest,
    LLMMessage,
    LLMProviderUnavailableError,
)
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.documents.ocr import get_ocr_provider


pytestmark = [pytest.mark.live_provider, pytest.mark.external]


def _require_opt_in():
    if os.getenv("RUN_LIVE_PROVIDER_TESTS") != "1":
        pytest.skip("RUN_LIVE_PROVIDER_TESTS=1 is required for live provider smoke tests")
    settings = get_settings()
    if settings.mistral_api_key is None:
        pytest.skip("MISTRAL_API_KEY is not configured")
    return settings


def _failure_category(error: BaseException) -> str:
    """Map adapter failures to safe operational categories without messages."""

    status = getattr(error, "http_status", None)
    if status is None:
        cause = getattr(error, "__cause__", None)
        status = getattr(cause, "status_code", None)
    if status in (401, 403):
        return "AUTHENTICATION"
    if status == 429:
        return "RATE_LIMIT"
    if isinstance(status, int) and status >= 500:
        return "PROVIDER_5XX"

    category = str(getattr(error, "category", "")).upper()
    cause_type = str(getattr(error, "cause_type", ""))
    cause_name = type(getattr(error, "__cause__", None)).__name__
    if (
        "TIMEOUT" in category
        or "UNAVAILABLE" in category
        or cause_type in {"ConnectError", "ConnectTimeout", "ReadTimeout", "TimeoutError"}
        or cause_name in {"ConnectError", "ConnectTimeout", "ReadTimeout", "TimeoutError"}
    ):
        return "NETWORK"
    if isinstance(error, (LLMGenerationError,)) or "INVALID" in category or "GENERATION_ERROR" in category:
        return "INVALID_RESPONSE"
    if isinstance(error, LLMProviderUnavailableError):
        return "NETWORK"
    return "INVALID_RESPONSE"


def _fail_safely(error: BaseException) -> NoReturn:
    return pytest.fail(f"LIVE_PROVIDER_{_failure_category(error)}")


@pytest.mark.asyncio
async def test_mistral_generation_returns_minimal_structured_response():
    settings = _require_opt_in()
    if not settings.mistral_model:
        pytest.skip("MISTRAL_MODEL is not configured")
    try:
        provider = get_mistral_provider()
        response = await provider.generate(
            LLMGenerationRequest(
                messages=[
                    LLMMessage(role="system", content="Return only the requested JSON object."),
                    LLMMessage(role="user", content='Return exactly {"status":"ok"}. No other text.'),
                ],
                temperature=0,
                max_tokens=32,
                response_format={"type": "json_object"},
                prompt_version="live-smoke-v1",
                operation="live_provider_smoke",
            )
        )
        payload = json.loads(response.content)
    except Exception as error:
        _fail_safely(error)
    assert isinstance(payload, dict)
    assert payload.get("status") == "ok"
    assert response.execution is not None
    assert response.execution.provider == "mistral"


def _synthetic_scanned_pdf(directory: Path) -> Path:
    image_path = directory / "ocr-smoke.png"
    pdf_path = directory / "ocr-smoke.pdf"
    image = pytest.importorskip("PIL.Image")
    image_draw = pytest.importorskip("PIL.ImageDraw")
    from fpdf import FPDF

    canvas = image.new("RGB", (1600, 900), "white")
    draw = image_draw.Draw(canvas)
    draw.text((100, 400), "RegBridge OCR smoke phrase", fill="black")
    canvas.save(image_path)
    pdf = FPDF(unit="pt", format=(1600, 900))
    pdf.add_page()
    pdf.image(str(image_path), x=0, y=0, w=1600, h=900)
    pdf.output(str(pdf_path))
    return pdf_path


@pytest.mark.asyncio
async def test_mistral_ocr_reads_synthetic_scanned_pdf_and_cleans_local_fixture():
    _require_opt_in()
    with tempfile.TemporaryDirectory(prefix="regbridge-ocr-smoke-") as temporary_directory:
        directory = Path(temporary_directory)
        pdf_path = _synthetic_scanned_pdf(directory)
        try:
            provider = get_ocr_provider()
            result = await provider.extract(pdf_path.read_bytes(), pdf_path.name, "application/pdf")
        except Exception as error:
            _fail_safely(error)
        assert result.pages
        assert result.normalized_text.strip()
        assert re.sub(r"\s+", " ", "RegBridge OCR smoke phrase").casefold() in re.sub(
            r"\s+", " ", result.normalized_text
        ).casefold()
    assert not pdf_path.exists()
    assert not (directory / "ocr-smoke.png").exists()
