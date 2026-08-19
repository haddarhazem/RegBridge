# Experiments

Experiments are controlled engineering investigations. They are not
production tests: tests ask whether an implementation satisfies its contract,
while experiments ask which approach performs better under defined conditions.

Experiments may call real production components, but production code must never
import from this directory. Every experiment must link to a Jira ticket, state a
research question, define its configuration and metrics, and keep its code
simple. Configuration is versioned, and important runs should be reproducible.

Run outputs belong under `artifacts/experiments/` and should use the machine-
readable convention described in
[the research guide](../docs/engineering-research/EXPERIMENT_GUIDE.md).

The first prepared experiment is [EX-001](orchestration/ex001_custom_vs_framework/).
