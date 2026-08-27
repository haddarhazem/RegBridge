# SCRUM-213 release-security report

The deterministic coverage matrix covers projects, documents, sharing/grants,
contracts, compliance, and research, including ownership, active membership,
visibility, exact recipient/resource/scope/version matching, revocation,
unauthenticated access, and IDOR attempts.

EX-027 covers direct user, indirect RAG, document, tool output, role
impersonation, cross-user, visibility override, grant escalation,
policy-exfiltration, multilingual, multi-turn, and benign-control cases.

Findings:

- Critical vulnerabilities: 0.
- High findings: 0.
- Successful unauthorized object/tool/RAG actions: 0.
- Backend private or cross-user disclosure: 0.
- Visibility and grant bypasses: 0.
- Medium robustness findings: model prohibited-action attempts and
  model-reported sentinel signals; deterministic backend checks prevented
  execution.

Release status: no unresolved critical security vulnerability; release blocker:
NO. RD-023 selected no mitigation because neither P0 nor P1 satisfied the
pre-registered utility gates. No prompt-level production change is made.
Existing deterministic backend authorization is retained. Model-level
prompt-injection-following remains a medium robustness finding. No additional
research is required for SCRUM-213.
