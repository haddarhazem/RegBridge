import json

import pytest
from app.modules.ai.llm import LLMExecutionMetadata, LLMGenerationResponse
from app.modules.ai.llm import LLMGenerationRequest, LLMMessage
from app.modules.ai.providers.mistral import MistralLLMProvider

from app.modules.research.extraction_parser import parse_source, resolve_segment, segment_source
from experiments.research_extraction.ex024_research_extraction.contracts import EvidenceExtraction, EvidenceIdExtraction, ExtractiveExtraction, StructuredExtraction
from experiments.research_extraction.ex024_research_extraction.runner import BENCHMARK, _score, _validate_evidence
from experiments.research_extraction.ex024_research_extraction.runner_r1 import _evidence_stats
from experiments.research_extraction.ex024_research_extraction.runner_r1 import evaluate_candidate
from experiments.research_extraction.ex024_research_extraction.artifact_store import write_completed_run
from experiments.research_extraction.ex024_research_extraction.v4_extractive import build_abstract, resolve_extractive_values
from experiments.research_extraction.ex024_research_extraction.r3c import application_confusion, build_manifest, validate_manifest


def test_benchmark_is_frozen_and_meets_gate():
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    assert benchmark["frozen"] is True
    assert len(benchmark["cases"]) == 15
    assert sum(len(case["gold"]) for case in benchmark["cases"]) == 105


def test_source_locators_are_deterministic_and_exact():
    parsed = parse_source("R209-001", "text/plain", b"first paragraph\nsecond paragraph")
    locator = parsed.locator(1)
    assert parsed.resolve(locator.__dict__) == "second paragraph"
    assert parsed.locator(1) == locator


def test_source_segments_are_allowlisted_and_version_scoped():
    parsed = parse_source("v1", "text/plain", b"alpha\nbeta")
    segments = segment_source(parsed)
    assert [item.segment_id for item in segments] == ["SRC-001", "SRC-002"]
    assert resolve_segment(segments, "SRC-002", "v1").text == "beta"
    with pytest.raises(ValueError):
        resolve_segment(segments, "SRC-002", "v2")


def test_evidence_id_schema_rejects_unknown_shape():
    with pytest.raises(ValueError):
        EvidenceIdExtraction.model_validate({"domains":{"status":"SUPPORTED","items":[{"value":"x","evidence_ids":[]}]} })


def test_evidence_id_stats_separate_reference_validity_from_claim_content():
    parsed = parse_source("v1", "text/plain", b"graphene membrane")
    extraction = EvidenceIdExtraction.model_validate({"domains":{"status":"SUPPORTED","items":[{"value":"not graphene","evidence_ids":["SRC-001"]}]},"technologies":{"status":"NOT_AVAILABLE","items":[]},"research_problem":{"status":"NOT_AVAILABLE","items":[]},"methodology":{"status":"NOT_AVAILABLE","items":[]},"main_results":{"status":"NOT_AVAILABLE","items":[]},"explicit_applications":{"status":"NOT_AVAILABLE","items":[]},"limitations":{"status":"NOT_AVAILABLE","items":[]},"keywords":{"status":"NOT_AVAILABLE","items":[]}})
    valid, invalid, texts, values = _evidence_stats(extraction, segment_source(parsed), "v1")
    assert (valid, invalid) == (1, 0)
    assert texts["domains:not graphene"] == ["graphene membrane"]
    assert values == [{"field": "domains", "value": "not graphene"}]


@pytest.mark.asyncio
async def test_r1_v2_and_v3_use_allowlisted_ids_and_bounded_verifier():
    class StubProvider:
        model = "stub"

        async def generate(self, request):
            not_available = {"status": "NOT_AVAILABLE", "items": []}
            fields = {field: not_available for field in ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "limitations", "keywords")}
            if request.operation.endswith("v2_extraction") or request.operation.endswith("v3_extraction"):
                fields["technologies"] = {"status": "SUPPORTED", "items": [{"value": "graphene membrane", "evidence_ids": ["SRC-001"]}]}
            if request.operation.endswith("v3_verifier"):
                content = json.dumps({"verdict": "SUPPORTED"})
            else:
                content = json.dumps({**fields, "regbridge_abstract": ""})
            return LLMGenerationResponse(content=content, model=self.model, execution=LLMExecutionMetadata(status="success", provider="stub", model=self.model))

    case = {"case_id": "STUB-001", "source_text": "graphene membrane", "gold": {field: (["graphene membrane"] if field == "technologies" else []) for field in ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "limitations")}}
    v2 = await evaluate_candidate(StubProvider(), case, "V2")
    v3 = await evaluate_candidate(StubProvider(), case, "V3")
    assert v2["score"]["evidence_valid"] == 1
    assert v3["verification"]["supported"] == 1


def test_completed_research_run_cannot_be_overwritten(tmp_path):
    target = tmp_path / "run.json"
    write_completed_run(target, {"run_id": "r1"})
    with pytest.raises(FileExistsError):
        write_completed_run(target, {"run_id": "r1", "changed": True})


def test_r3_holdout_is_frozen_and_balanced():
    benchmark = json.loads((BENCHMARK.parent / "research_extraction_ex024_r3_holdout_v1.json").read_text(encoding="utf-8"))
    assert benchmark["frozen"] is True and len(benchmark["cases"]) == 16
    assert sum(len(case["gold"]) for case in benchmark["cases"]) == 128
    for field in ("domains", "technologies", "research_problem", "methodology", "main_results", "explicit_applications", "keywords", "limitations"):
        assert sum(bool(case["gold"][field]) for case in benchmark["cases"]) == 8


def test_r3_gold_manifest_and_application_matrix_are_deterministic():
    benchmark = json.loads((BENCHMARK.parent / "research_extraction_ex024_r3_holdout_v1.json").read_text(encoding="utf-8"))
    manifest = build_manifest(benchmark)
    validate_manifest(manifest, benchmark)
    assert len(manifest["items"]) == 64
    rows = [{"predicted":{"explicit_applications": case["gold"]["explicit_applications"]}} for case in benchmark["cases"]]
    assert application_confusion(rows, benchmark["cases"]) == {"TP":8,"TN":8,"FP":0,"FN":0}


def test_r3_comparator_application_audit_uses_case_level_presence():
    benchmark = json.loads((BENCHMARK.parent / "research_extraction_ex024_r3_holdout_v1.json").read_text(encoding="utf-8"))
    result = json.loads((BENCHMARK.parent.parent / "artifacts/experiments/ex024/r3/20260825T153011Z/results.json").read_text(encoding="utf-8"))
    assert application_confusion(result["rows"]["V2"], benchmark["cases"]) == {"TP": 8, "TN": 8, "FP": 0, "FN": 0}
    assert application_confusion(result["rows"]["V3"], benchmark["cases"]) == {"TP": 3, "TN": 8, "FP": 0, "FN": 5}


def test_r3c_field_audit_counts_wrong_field_evidence_as_false_positive():
    from experiments.research_extraction.ex024_research_extraction.runner_r3c import _matrix

    benchmark = json.loads((BENCHMARK.parent / "research_extraction_ex024_r3_holdout_v1.json").read_text(encoding="utf-8"))
    manifest = build_manifest(benchmark)
    rows = []
    for case in benchmark["cases"]:
        rows.append({"selected_ids": {
            "methodology": ["SRC-002", "SRC-004"] if case["gold"]["methodology"] else [],
            "technologies": ["SRC-002"] if case["gold"]["technologies"] else [],
        }})
    matrix = _matrix(rows, benchmark["cases"], manifest)
    assert matrix["methodology"]["FP"] == 8 and matrix["methodology"]["TP"] == 8


def test_v4_exact_copy_and_deterministic_abstract():
    parsed = parse_source("v1", "text/plain", b"The sensor reached 93.2% accuracy.\nThe stated application is water monitoring.")
    extraction = ExtractiveExtraction.model_validate({"domains":{"status":"NOT_AVAILABLE","items":[]},"technologies":{"status":"NOT_AVAILABLE","items":[]},"research_problem":{"status":"NOT_AVAILABLE","items":[]},"methodology":{"status":"NOT_AVAILABLE","items":[]},"main_results":{"status":"SUPPORTED","items":[{"evidence_ids":["SRC-001"]}]},"explicit_applications":{"status":"SUPPORTED","items":[{"evidence_ids":["SRC-002"]}]},"keywords":{"status":"NOT_AVAILABLE","items":[]},"limitations":{"status":"NOT_AVAILABLE","items":[]}})
    values, ids, invalid = resolve_extractive_values(extraction, segment_source(parsed), "v1")
    assert invalid == 0 and values["main_results"] == ["The sensor reached 93.2% accuracy."]
    assert ids["explicit_applications"] == ["SRC-002"]
    assert "93.2%" in build_abstract(values)


@pytest.mark.asyncio
async def test_v4_schema_serializes_and_mistral_adapter_accepts_it_without_factual_value():
    from experiments.research_extraction.ex024_research_extraction.runner import _schema

    schema = _schema(ExtractiveExtraction)
    assert '"value"' not in json.dumps(schema)

    class Message:
        content = json.dumps({"domains":{"status":"NOT_AVAILABLE","items":[]},"technologies":{"status":"NOT_AVAILABLE","items":[]},"research_problem":{"status":"NOT_AVAILABLE","items":[]},"methodology":{"status":"SUPPORTED","items":[{"evidence_ids":["SRC-002"]}]},"main_results":{"status":"SUPPORTED","items":[{"evidence_ids":["SRC-001"]}]},"explicit_applications":{"status":"NOT_AVAILABLE","items":[]},"keywords":{"status":"NOT_AVAILABLE","items":[]},"limitations":{"status":"NOT_AVAILABLE","items":[]}})
    class Choice:
        message = Message()
        finish_reason = "stop"
    class Response:
        choices = [Choice()]
        usage = None
        model = "stub"
    class Chat:
        async def complete_async(self, **kwargs):
            assert kwargs["response_format"] == schema
            return Response()
    class Client:
        chat = Chat()
    provider = MistralLLMProvider(api_key="test-only", model="stub", client=Client())
    response = await provider.generate(LLMGenerationRequest(messages=[LLMMessage(role="user", content="select IDs")], response_format=schema))
    assert "value" not in response.content


def test_source_parsers_reject_empty_text():
    with pytest.raises(ValueError, match="SOURCE_TEXT_UNAVAILABLE"):
        parse_source("x", "text/plain", b"")


def test_v1_state_schema_rejects_contradictions():
    with pytest.raises(ValueError):
        StructuredExtraction.model_validate({"domains":{"status":"SUPPORTED","items":[]},"technologies":{"status":"NOT_AVAILABLE","items":[{"value":"x"}]},"research_problem":{"status":"NOT_AVAILABLE","items":[]},"methodology":{"status":"NOT_AVAILABLE","items":[]},"main_results":{"status":"NOT_AVAILABLE","items":[]},"explicit_applications":{"status":"NOT_AVAILABLE","items":[]},"limitations":{"status":"NOT_AVAILABLE","items":[]},"keywords":{"status":"NOT_AVAILABLE","items":[]}})


def test_evidence_wrong_version_is_rejected():
    parsed = parse_source("R209-001", "text/plain", b"graphene membrane")
    model = EvidenceExtraction.model_validate({"domains":{"status":"SUPPORTED","items":[{"value":"x","evidence_refs":[{"source_version_id":"R209-002","locator":{"locator_type":"paragraph","paragraph":0,"start_char":0,"end_char":16}}]}]},"technologies":{"status":"NOT_AVAILABLE","items":[]},"research_problem":{"status":"NOT_AVAILABLE","items":[]},"methodology":{"status":"NOT_AVAILABLE","items":[]},"main_results":{"status":"NOT_AVAILABLE","items":[]},"explicit_applications":{"status":"NOT_AVAILABLE","items":[]},"limitations":{"status":"NOT_AVAILABLE","items":[]},"keywords":{"status":"NOT_AVAILABLE","items":[]}})
    assert _validate_evidence(model, parsed, "R209-001") == (0, 1)


def test_scoring_counts_false_pass_and_false_block():
    case = {"gold":{"domains":["energy"],"technologies":[],"research_problem":[],"methodology":[],"main_results":[],"explicit_applications":[],"limitations":[]}}
    score = _score(case, {"domains":["energy", "machine learning"], "technologies":[], "research_problem":[], "methodology":[], "main_results":[], "explicit_applications":[], "limitations":[]})
    assert score["true_positive"] == 1 and score["unsupported"] == 1 and score["missed"] == 0
