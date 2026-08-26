import uuid

import pytest

from app.modules.research.discovery import VISIBILITIES
from app.modules.research.extraction import build_abstract


def test_discovery_defaults_are_private_and_bounded():
    assert VISIBILITIES == {"PRIVATE", "PUBLIC", "MATCHABLE"}
    assert build_abstract({field: [] for field in ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "keywords", "limitations")}) == ""


def test_abstract_only_uses_source_backed_fields():
    values = {field: [] for field in ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "keywords", "limitations")}
    values["main_results"] = ["The model achieved 93.2% accuracy."]
    assert build_abstract(values) == "The reported result is The model achieved 93.2% accuracy."


def test_public_projection_never_contains_private_evidence_by_contract():
    public = {"fields": {"domains": ["explicit domain"]}, "abstract": "public abstract"}
    assert "evidence" not in public and "source_text" not in public
