# EX-019 Results

The frozen 12-scenario core benchmark and 10-scenario adversarial suite were
executed by `experiments/event_registration_consistency/run_ex019.py`.
All ten evaluator mutations were detected.

Both candidates achieved zero duplicate-active participation and complete
state, authorization, cancellation, concurrency, and audit correctness in the
abstract evaluator. V0 required two synchronization rules and two writes for
a transition (current state plus audit). V1 required five synchronization rules
and three writes because immutable actions must also maintain a deterministic
current projection.

V0 is selected because the required invariants do not justify append-only
participation actions for this minimal module. Audit rows preserve meaningful
transitions without introducing a generic event-sourcing framework.

The benchmark is synthetic and does not measure attendance, recommendations,
social behavior, or marketplace scale.
