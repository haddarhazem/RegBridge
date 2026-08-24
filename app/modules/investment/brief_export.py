"""Deterministic formatting of an already-approved opportunity brief."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF


RENDERER_VERSION = "scrum207-fpdf2-v1"


def _unicode_font() -> tuple[str, str]:
    candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    )
    for path in candidates:
        if path.exists():
            return "RegBridgeUnicode", str(path)
    raise RuntimeError("A Unicode TrueType font is required for deterministic PDF export")


def _lines(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def render_opportunity_brief_pdf(content: dict, version_number: int) -> bytes:
    """Render only the five persisted content sections; never generate prose."""

    pdf = FPDF(format="A4")
    pdf.set_compression(False)
    font_name, font_path = _unicode_font()
    pdf.add_font(font_name, "", font_path)
    pdf.add_font(font_name, "B", font_path)
    pdf.set_title(f"Investor Opportunity Brief v{version_number}")
    pdf.set_author("RegBridge")
    pdf.set_creation_date(datetime(2000, 1, 1, tzinfo=timezone.utc))
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.set_font(font_name, "B", 16)
    pdf.cell(0, 10, "Investor Opportunity Brief", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font_name, "", 10)
    pdf.cell(0, 7, f"Version {version_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    sections = (
        ("1. Executive Summary", [content["executive_summary"]], False),
        ("2. Why This Startup Fits Your Thesis", content["thesis_fit"], True),
        ("3. Key Investment Highlights", content["investment_highlights"], True),
        ("4. Missing Information", content["missing_information"], True),
        ("5. Disclaimer", [content["disclaimer"]], False),
    )
    for heading, values, bullets in sections:
        pdf.set_font(font_name, "B", 12)
        pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(font_name, "", 10)
        for value in _lines(values):
            if bullets:
                pdf.multi_cell(pdf.epw, 6, f"- {value}", wrapmode="CHAR")
            else:
                pdf.multi_cell(pdf.epw, 6, value, wrapmode="CHAR")
        pdf.ln(4)

    return bytes(pdf.output())
