# Experiment Guide

An experiment is a controlled investigation, not a production test. Use it
only when there is meaningful technical uncertainty and link it to Jira.

Before running, define the research question, hypothesis, alternatives,
independent and controlled variables, dataset/workload, environment,
configuration, metrics, procedure, and reproduction command. Keep production
code independent of `experiments/`; experiments may reuse production code.

Important runs should record the experiment ID, run ID, Git commit, dataset and
version, provider/model/version, prompt version, configuration, seed, date,
environment, metrics, latency, token usage, and cost where applicable.

Use file-based outputs initially. A minimal result object is:

```json
{
  "experiment_id": "EX-001",
  "run_id": "run-...",
  "git_commit": "...",
  "dataset_version": "...",
  "configuration": {},
  "metrics": {}
}
```

Run outputs belong under `artifacts/experiments/`. Do not add MLflow, Weights &
Biases, DVC, Kubeflow, Ray, Airflow, or a database for experiment runs yet.
Prefer module/script execution such as `python -m experiments...`; notebooks
may be used later for exploration but are not the canonical implementation.
