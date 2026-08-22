# EX-012 — Contract semantic verifier strategy

EX-012 is the final verifier-selection experiment for SCRUM-193 / RQ-011.
V2 structured extraction and quote-based deterministic evidence resolution
were fixed inputs. The experiment compared the unchanged EX-011 verifier
(V0) with a strict checklist verifier using the same configured Mistral model
(V1). No different/stronger model was configured through the existing
provider, so V2 was unavailable.

The frozen benchmark is synthetic and contains 12 development, 10 holdout,
and 10 adversarial cases. It includes direct support, uncertainty, negation,
conditions, qualifier loss, conflicts, recommendation/risk as fact,
unrelated evidence, fabricated claims, exceptions, cross-sentence language,
and prompt injection.

V1 receives only bounded claim/type/category/evidence/version fields. Contract
evidence is untrusted data and cannot issue instructions. Final acceptance is
derived from the checklist fields rather than from free-form model prose.

The real-provider execution used `mistral-small-latest`. A provider schema
wrapper parsing defect was corrected and the frozen run was repeated. No
private contracts, credentials, or complete prompts are stored.

EX-012 is a stopping experiment. Since no candidate passes the production
gate, no further verifier prompt/model tuning is authorized under SCRUM-193.
