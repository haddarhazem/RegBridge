from .contracts import ExperimentRequest, Intent


class DeterministicClassifier:
    """Maps declared fixture intent; it does not assess natural language."""

    mapping = {
        "regulatory": ["regulatory"],
        "regulatory_and_contract": ["regulatory", "contract"],
        "unsupported": [],
    }

    def classify(self, request: ExperimentRequest) -> Intent:
        return Intent(capabilities=list(self.mapping.get(request.declared_intent, [])))

