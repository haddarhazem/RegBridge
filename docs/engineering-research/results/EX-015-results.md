# EX-015 Results

Both candidates were evaluated programmatically against the frozen benchmark.
The raw result is `artifacts/experiments/ex015_investor_sharing_results.json`.
Both preserve default deny, recipient/project/resource/version isolation,
revocation, auditability, and no transitive access in the candidate model.

V0 is selected for production because its exact resource/version scope is
easier to inspect and cannot expand when a product bundle changes. V1's frozen
bundle snapshot avoids the measured evolution hazard, but it still requires
more bundle-specific semantics and makes least privilege less obvious. The
production implementation therefore uses V0 only. Its polymorphic resource
reference is compensated by strict allowlist validation and project ownership
checks.

The benchmark is synthetic and does not replace a security review. A future
investor profile subsystem may add recipient eligibility, but SCRUM-197 uses
the existing authenticated `User` identity and does not invent that subsystem.
