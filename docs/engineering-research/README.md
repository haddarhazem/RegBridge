# Engineering Research

RegBridge uses research-oriented engineering when a meaningful technical
uncertainty exists. The workflow is:

Research Question -> Hypothesis -> Alternatives -> Experimental Protocol ->
Controlled Experiment -> Metrics -> Results -> Interpretation -> Limitations ->
Engineering Decision -> Production implementation

This process is appropriate for decisions such as orchestration architecture,
RAG retrieval, verification, model quality/cost trade-offs, matching, and
evidence strategies. It is not required for trivial file naming, CRUD, REST
routing, or ordinary refactoring.

- [Research agenda](RESEARCH_AGENDA.md)
- [Experiment guide](EXPERIMENT_GUIDE.md)
- [Metrics catalog](METRICS_CATALOG.md)
- [Experiment protocols](experiments/README.md)
- [Result summaries](results/README.md)
- [Research decisions](decisions/README.md)

Experiments are manually and explicitly run initially; production tests remain
mandatory CI. No experiment result, decision, or production architecture is
validly claimed until the relevant run has been performed and its limitations
documented.
