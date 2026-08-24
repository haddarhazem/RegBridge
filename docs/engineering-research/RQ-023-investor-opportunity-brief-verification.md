# RQ-023 — Investor Opportunity Brief factuality verification strategy

Question: Which verification strategy detects unsupported factual claims in an
Investor Opportunity Brief while avoiding false blocks of faithful paraphrases?

Candidates: V0 deterministic rules over structured evidence; V1 semantic/model
verification; V2 deterministic-first with semantic fallback.

The benchmark is frozen in
`benchmarks/investor_opportunity_brief_ex023_v1.json`. Production verification
must use the exact persisted SCRUM-204 generation bundle and matching result.
