# EX-020 results

| Candidate | Scenarios | Passed | Unauthorized disclosure |
|---|---:|---:|---:|
| V0 | 24 | 24 | 0 |
| V1 | 24 | 24 | 0 |

Both candidates pass the deterministic safety protocol. V0 has a coarse
acceptance scope and can expand unintentionally when new channels are added.
V1 adds contact-consent records and validation, but provides explicit channel
scope, immutable snapshots, and independent revocation.

## Decision

V1 is selected. The incremental data and rule complexity is justified by the
stronger protection against sibling-channel disclosure and stale-consent
expansion. Project/resource authorization remains separate from contact
consent. No LLM or hybrid mechanism is justified.
