# EX-018 Results

The frozen 12-scenario benchmark and 8-scenario adversarial mutation suite
were executed by `experiments/investment_opportunity_lifecycle/run_ex018.py`.
All eight evaluator mutations were detected.

V0 preserved simple current reads, closure filtering, authorization, and
period validation in the abstract evaluator, but it failed the historical
snapshot and stale-concurrency invariants and required five synchronization
rules with duplicated current/history state.

V1 passed historical reproducibility, current-state, closure, active-list,
authorization, period, concurrency, snapshot, and stable-identity invariants.
It required two synchronization rules and no duplicated current/history data.

Limitations: the benchmark is synthetic and does not measure marketplace
demand, investor suitability, financial execution, or scale beyond query
sanity. It evaluates lifecycle correctness only.
