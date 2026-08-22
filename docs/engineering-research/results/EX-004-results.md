# EX-004 results — Adaptive onboarding

## Execution

The frozen benchmark contained 20 synthetic scenarios across `activity`, `sector`, `technology`, `data`, `market`, and `location`. V1 used the existing production deterministic rules without modification after seeing results. No database, vector store, model provider, or network service was used.

## EX-004A historical metrics

| Metric | V0 fixed | V1 adaptive |
|---|---:|---:|
| Scenarios | 20 | 20 |
| Required-context coverage | 100.00% | 88.68% |
| Irrelevant-question rate | 11.67% | 1.16% |
| Average questions | 6.00 | 4.30 |
| Relevant-question density | 0.8833 | 0.9884 |
| Repeated-question rate after resume | 100.00% (9/9) | 0.00% (0/9) |
| Resume cases | 3 | 3 |
| Completion cases | 20 | 10 |
| Average questions in completed cases | 6.00 | 4.30 |

The preserved first-run artifact used the misleading field name `data_minimization_ratio` and reported V1 as 1.0930. The corrected density counts relevant newly selected questions / all newly selected questions; it is 0.8833 for V0 and 0.9884 for the original V1 run on the development set.

## Comparison

V1 reduced the mean number of selected questions by 1.70 per scenario, or 28.33%. The irrelevant-question rate fell by 10.50 percentage points, approximately a 90.06% relative reduction. Resume repeats fell from 9 of 9 confirmed fields selected again in V0 to 0 of 9 in V1.

The original report’s 88.68% V1 coverage included rule misses and did not distinguish already confirmed resume context. After the metric/evaluator audit and the minimal lexical correction, the development-set policy collects all expected domains, while the historical first-run result remains recorded as `PARTIALLY SUPPORTED`.

Representative observations from the frozen per-scenario output:

- ONB-002 and ONB-010 expected both technology and data context, but V1 selected only the four baseline domains.
- ONB-003 and ONB-004 selected technology but not data, despite both domains being expected.
- ONB-018 had four already confirmed domains; V1 selected no questions and repeated none, while V0 repeated all four confirmed domains and asked two irrelevant questions.
- ONB-019 and ONB-020 demonstrate partial resume behavior: V1 skipped confirmed fields and collected the remaining selected context, with no repeats.

## EX-004A result

**PARTIALLY SUPPORTED** for the original development-set run.

H2 is supported: the adaptive strategy eliminates repeated questions after resume. H1 was only partially supported in the original run because of rule misses and the metric/evaluator issue. The follow-up correction is evaluated independently below.

## EX-004B result

On the independent 12-case holdout, V1R achieved 100.00% coverage, 0.00% irrelevant-question rate, 4.67 average questions, 1.0000 relevant-question density, 0/6 resume repetitions, and 12/12 completion cases. V0 measured 100.00%, 13.89%, 6.00, 0.8611, 6/6, and 12/12 respectively. Under the pre-declared priority of coverage over minimization and question count, the corrected adaptive approach is **SUPPORTED** for this small holdout.

## Limitations

- The sample is small (20 synthetic scenarios) and is not customer or legal data.
- Expected relevance is an independent experiment annotation, not a legal determination or an LLM judgment.
- The “collected” coverage convention counts initially confirmed fields; a user confirmation is treated as usable context, not re-verified by this experiment.
- The benchmark exercises six onboarding domains only and does not measure wording, user comprehension, abandonment, or downstream regulatory-answer quality.
- V1 was evaluated as-is. No post-result tuning was performed.
- V0 is a controlled fixed-question baseline, not a claim about a future product questionnaire UX.

## Reproduction

```text
python -m pytest experiments/onboarding/ex004_adaptive_onboarding/tests -q
python -m experiments.onboarding.ex004_adaptive_onboarding.run_ex004
```

Production SCRUM-187 implementation files were not changed during this experiment. The PostgreSQL-backed production validation remains blocked by the local PostgreSQL service being unavailable at `127.0.0.1:55432`; this research result does not remove that validation requirement.
