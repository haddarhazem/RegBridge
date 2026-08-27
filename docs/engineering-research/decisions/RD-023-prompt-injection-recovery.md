# RD-023 — Prompt-injection recovery decision

Related Jira: SCRUM-213. RQ-027 continued. Recovery experiment: EX-027-R1.
Previous EX-027 and RD-022 are preserved; RD-022 records no selection because
its utility gates were not pre-registered.

## Frozen evidence

Fresh benchmark: `prompt_injection_ex027_r1_v1.json`, SHA-256
`74efa08be2faf4e8f96961e5459546b2c6eae7e9297ad0c614b98b54eaf6c580`, with 64
cases (24 DEV, 40 HOLDOUT; 20 adversarial and 20 benign HOLDOUT controls).
Before HOLDOUT, the following gates were frozen: benign completion >=90%,
false refusal <=10%, authorized tool success >=90%, authorized RAG success
>=90%, and zero private, cross-user, unauthorized object/tool/RAG,
visibility, or grant/scope violations.

## Results

On HOLDOUT, P0 and P1 each completed 5/20 benign cases (25%) and falsely
refused 15/20 (75%). Authorized tool success was 3/3 for both. Authorized RAG
success was 6/7 (85.7%) for P0 and 4/7 (57.1%) for P1. P0 had 19/20 and P1
20/20 model-level prohibited-action attempts. Neither executed an unauthorized
object, tool, or RAG action; private and cross-user disclosures, visibility
bypasses, and grant/scope bypasses were zero.

## Final decision

Selected mitigation: NONE. Neither P0 nor P1 satisfied the pre-registered
utility gates, so no candidate earned production promotion. P2 was not
executed because DEV did not justify adding a quarantine layer. The result is
not a license to lower gates or reinterpret false refusals.

## Production consequence

Production consequence: NO PROMPT-LEVEL CHANGE. No production mitigation is
activated from RQ-027. Deterministic backend
authorization, ContextBuilder boundaries, exact grants/versions, tool
permissions, and RAG eligibility remain authoritative. The LLM does not grant
access. A future research question may study utility-preserving refusal
calibration, but no additional research is required for SCRUM-213.

## Limitations

This is one fresh synthetic HOLDOUT with nondeterministic provider behavior;
latency was diagnostic because candidates ran sequentially. Raw synthetic
completions and traces are retained for independent review. The experiment
demonstrates containment, not prompt-injection resistance. Critical
vulnerabilities: 0. Medium finding: model-level prompt-injection-following
remains high. Release blocker: NO. Deterministic backend authorization
prevented unauthorized object, tool, RAG, visibility, and grant actions in the
tested benchmark.
