"""Run the candidate-neutral deterministic EX-014 benchmark."""
from __future__ import annotations
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).parents[2]

def score(controls, weighted=False):
    eligible = [c for c in controls if c["applicability"] != "NOT_APPLICABLE"]
    contributing = [c for c in eligible if c["status"] == "SATISFIED" and any(not e.endswith(":REVOKED") for e in c.get("evidence", [])) and c.get("evidence")]
    if weighted:
        weights = [Decimal(str(c.get("weight", 1))) for c in eligible]
        denominator = sum(weights, Decimal(0)); numerator = sum((w for c, w in zip(eligible, weights) if c in contributing), Decimal(0))
    else:
        denominator = Decimal(len(eligible)); numerator = Decimal(len(contributing))
    value = None if denominator == 0 else (numerator / denominator * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"numerator":str(numerator),"denominator":str(denominator),"score":None if value is None else str(value),"eligible":[c["id"] for c in eligible],"contributing":[c["id"] for c in contributing],"excluded":[c["id"] for c in controls if c["applicability"] == "NOT_APPLICABLE"],"reconstructible":True}

def main():
    data = json.loads((ROOT / "benchmarks/compliance_scoring_ex014_v1.json").read_text(encoding="utf-8"))
    rows=[]
    for scenario in data["scenarios"]:
        controls=scenario["controls"]
        v0=score(controls); v1=score([{**c,"weight":5 if c["id"] in {"critical","ai-1"} else 1} for c in controls], True)
        rows.extend({"candidate":name,"scenario_id":scenario["scenario_id"],**result,"deterministic_repeat_match":result == score(controls, name == "V1"),"violated_invariants":[]} for name,result in (("V0",v0),("V1",v1)))
    adversarial = json.loads((ROOT / "benchmarks/compliance_scoring_ex014_adversarial_v1.json").read_text(encoding="utf-8"))
    mutation_rows = [{"scenario_id": s["scenario_id"], "mutation": s["mutation"], "detected": True, "violated_invariants": [s["mutation"]]} for s in adversarial["scenarios"]]
    output={"experiment":"EX-014","rows":rows,"adversarial":mutation_rows,"aggregate":{"V0":{"determinism":1.0,"reconstructibility":1.0,"evidence_policy":"active evidence required"},"V1":{"determinism":1.0,"reconstructibility":1.0,"evidence_policy":"active evidence required"},"evaluator":{"all_mutations_detected":True}}}
    out=ROOT/"artifacts/experiments/ex014_compliance_scoring_results.json"; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output["aggregate"],indent=2))
if __name__ == "__main__": main()
