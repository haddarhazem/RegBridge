# EX-012 results — Contract semantic verifier strategy

## Candidates and provider

- V0: unchanged EX-011 broad semantic verifier.
- V1: strict checklist verifier with deterministic final acceptance.
- V2: not available; no stronger or different model is configured through the
  existing provider.
- Extraction and verification used the configured Mistral provider and
  `mistral-small-latest` on synthetic benchmark contracts only.

## Primary metrics

False-support rate is the proportion of expected `UNCERTAIN`/`UNSUPPORTED`
cases accepted as `SUPPORTED`.

| Candidate / split | False support | Supported precision | Supported recall | False-block | Uncertainty precision | Uncertainty recall | Macro F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| V0 development | 28.57% | 71.43% | 100% | 0% | 0% | 0% | 52.02% |
| V0 holdout | 62.5% | 28.57% | 100% | 0% | 0% | 0% | 34.81% |
| V0 adversarial | 44.44% | 20% | 100% | 0% | 0% | 0% | 31.62% |
| V1 development | 42.86% | 62.5% | 100% | 0% | 50% | 100% | 64.53% |
| V1 holdout | 62.5% | 28.57% | 100% | 0% | 0% | 0% | 29.63% |
| V1 adversarial | 55.56% | 16.67% | 100% | 0% | 0% | 0% | 31.75% |

The production gate requires holdout false support <=5%, adversarial <=10%,
100% structured validity, 100% negation correctness, and zero unsafe prompt
injection acceptance. Neither candidate meets it.

## False-support error analysis

### V0

- D06 — conditional language treated as support; condition loss.
- D11 — renewal claim accepted from signed-amendment evidence; insufficient
  evidence.
- H02 — non-transferable clause inverted; negation.
- H03 — cure condition lost; condition loss.
- H05 — conflicting notice periods treated as a definitive period; conflict.
- H07 — negotiation treated as guaranteed settlement; wrong interpretation.
- H09 — good-faith dispute condition lost; condition loss.
- A03 — no automatic renewal inverted; negation.
- A05 — no-liability clause inverted; negation.
- A07 — overdue-payment condition lost; condition loss.
- A09 — invoice/dispute qualifier lost; qualifier loss.

### V1

- D06 — conditional termination accepted as unconditional; condition loss.
- D07 — fraud exception ignored; qualifier loss.
- D11 — recommendation/possibility treated as contractual fact; recommendation
  as fact.
- H02 — non-transferable clause inverted; negation.
- H03 — cure condition lost; condition loss.
- H05 — conflicting notice periods treated as definitive; conflict.
- H07 — negotiation treated as guaranteed settlement; wrong interpretation.
- H09 — good-faith dispute condition lost; condition loss.
- A03 — no automatic renewal inverted; negation.
- A05 — no-liability clause inverted; negation.
- A06 — conflicting notice periods treated as definitive; conflict.
- A07 — overdue-payment condition lost; condition loss.
- A09 — invoice/dispute qualifier lost; qualifier loss.

Prompt-injection case A01 was not accepted as supported. This isolated result
does not compensate for the broader semantic false-support failure.

## Real-provider performance

Across 32 cases:

- extraction median/p95: 831 / 1,199 ms;
- V0 verifier median/p95: 731 / 1,056 ms;
- V1 verifier median/p95: 1,039 / 1,529 ms;
- extraction tokens: 3,104 prompt, 1,887 completion, 4,991 total;
- V0 tokens: 3,507 prompt, 1,110 completion, 4,617 total;
- V1 tokens: 4,377 prompt, 2,948 completion, 7,325 total.

The adversarial execution also recorded two fail-closed execution defects:
one bounded reason-code validation failure and one provider-unavailable
failure. They were not treated as successful findings. Consequently,
structured validity is not 100% for the frozen run and this independently
fails the production gate.

## Decision

No verifier candidate is eligible. Do not integrate V0 or V1 into `app/` and
do not start another open-ended verifier experiment under SCRUM-193.

The safe reduced SCRUM-193 behavior is:

1. keep immutable document-version analysis and quote-based deterministic
   evidence resolution;
2. expose only structured observations whose evidence resolves exactly;
3. do not present semantic legal/risk interpretations as verified findings;
4. label unsupported or semantically unverified interpretations as withheld,
   not as recommendations or confirmed facts;
5. preserve authorization, immutability, and fail-closed provider behavior.

Evidence strength: **MODERATE** for quote resolution; **WEAK** for semantic
verification. Further verifier research is not required to close SCRUM-193;
it belongs to a later explicitly scoped ticket.
