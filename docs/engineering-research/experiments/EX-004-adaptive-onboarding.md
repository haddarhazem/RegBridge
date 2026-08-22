# EX-004 — Adaptive onboarding evaluation

## Research question

Does the deterministic adaptive onboarding strategy reduce unnecessary questions compared with a fixed six-domain questionnaire while preserving the relevant regulatory context?

## Frozen protocol

This is a small, research-only comparison for SCRUM-187. The benchmark and the hypotheses were frozen before executing V1. The experiment does not call PostgreSQL, Qdrant, Mistral, or any network service.

- V0: ask `activity`, `sector`, `technology`, `data`, `market`, and `location` for every scenario. On resumed scenarios, already confirmed fields are still counted as asked so repeat burden is measured.
- V1: call the existing deterministic production `next_questions` rules exactly as implemented at experiment start.
- No V2, LLM, coaching, business-advice, or production-rule variant was evaluated.

The frozen scenario set is `benchmarks/adaptive_onboarding_v1.json`, containing 20 synthetic non-private cases and a complete independent expected-relevance matrix over the six domains. Three cases contain initial confirmed fields to evaluate resume behavior.

## Metrics

- Required-context coverage: relevant domains collected / relevant domains expected. A domain initially confirmed before the comparison counts as collected; this avoids penalizing resume cases for context already present.
- Irrelevant-question rate: irrelevant selected questions / all selected questions.
- Average questions: selected questions per scenario.
- Data-minimization ratio: relevant domains collected / selected questions. This is a relevance-density indicator; on resumed cases it can exceed 1 because confirmed context is counted as collected but is not a newly selected question.
- Repeated-question rate: confirmed domains selected again / initially confirmed domains.
- Completion efficiency: scenarios with all expected relevant domains collected and their average selected questions.

## Frozen hypotheses

- H1: V1 lowers average questions and irrelevant-question rate while maintaining equivalent or near-equivalent context coverage.
- H2: V1 avoids repeats after resume.

The runner is `experiments/onboarding/ex004_adaptive_onboarding/run_ex004.py`. Its output is an ignored local artifact under `artifacts/experiments/EX-004/`.

## EX-004A follow-up audit and correction

The original development-set execution is preserved as historical evidence and remains `PARTIALLY SUPPORTED`. Its original field named `data_minimization_ratio` was misleading: it used relevant context collected (including initially confirmed fields) as the numerator while using newly selected questions as the denominator. That is why V1 could report 1.0930. The corrected metric is `relevant_question_density`: relevant newly selected questions / all newly selected questions, which is bounded to 0..1.

The corrected values computed from the preserved 20-case development set are:

- V0: 0.8833
- original V1 rule set, after metric correction: 0.9884

The original V1 misses were separated into actual rule misses and resume accounting. The actual rule misses were:

| Scenario | Expected domain | Skipped domain | Cause | Classification |
|---|---|---|---|---|
| ONB-002 | technology, data | technology, data | e-commerce and commerce wording was not recognized | A |
| ONB-003 | data | data | SaaS wording did not trigger data context | A |
| ONB-004 | data | data | AI wording did not trigger data context | A |
| ONB-007 | technology, data | technology, data | marketplace wording was not recognized | A |
| ONB-008 | technology, data | data | education/formation wording did not trigger data context | A |
| ONB-009 | technology | technology | sensor wording was not recognized | A |
| ONB-010 | technology, data | technology, data | connected/IoT wording was not recognized | A |
| ONB-011 | technology | technology | transport/logistics wording was not recognized | A |
| ONB-012 | technology | technology | energy wording was not recognized | A |

ONB-018, ONB-019, and ONB-020 also appeared as misses if only newly selected fields were compared. Those are resume-state accounting problems, not rule misses: their initially confirmed fields were already collected. They are classified C/D and are excluded from the corrected coverage calculation.

The smallest correction was deterministic lexical normalization with explicit domain terms for those observed contexts. No generic `plateforme` data trigger was added because an existing production regression test intentionally treats a generic web reservation platform as not automatically data-relevant. No LLM, classifier, framework, or scoring model was introduced.

## EX-004B independent holdout

The 12-case holdout is `benchmarks/adaptive_onboarding_holdout_v1.json`. Expected relevance was defined before running the revised policy and the original development benchmark was not changed.

| Metric | V0 fixed | V1R corrected adaptive |
|---|---:|---:|
| Required-context coverage | 100.00% | 100.00% |
| Irrelevant-question rate | 13.89% | 0.00% |
| Average questions | 6.00 | 4.67 |
| Relevant-question density | 0.8611 | 1.0000 |
| Resume repetition | 100.00% (6/6) | 0.00% (0/6) |
| Completion cases | 12/12 | 12/12 |

The holdout contained no missed relevant domains for V1R. Under the declared priority `coverage > data minimization > question-count reduction`, the corrected adaptive approach is supported on this small holdout. This is not a universal UX claim.
