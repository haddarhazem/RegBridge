# EX-026 — Sparse matching recovery

RQ-026 tests whether the V1 sparse matcher can satisfy precision and no-match
requirements using a deterministic field-evidence gate and DEV-calibrated
abstention, without another model.

The fresh frozen recovery benchmark contains 20 needs and 32 approved-like
snapshots. It uses 8 DEV needs and 12 HOLDOUT needs, with two HOLDOUT
zero-match cases. The privacy boundary remains CORE fields only and excludes
private, draft and non-matchable content.

Candidates were S0 original sparse, S1 field-aware evidence gate, S2 DEV score
abstention and S3 gate plus abstention. S3 is the selected research candidate;
no new embedding, LLM or retrieval family was introduced.
