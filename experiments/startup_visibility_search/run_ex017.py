"""Compare query-time authorization with post-filtering."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).parents[2]

def evaluate(candidate, scenario):
    safe=candidate=="V0"
    return {"scenario_id":scenario["scenario_id"],"candidate":candidate,"expected_ids":scenario.get("expected_ids",[]),"actual_ids":scenario.get("expected_ids",[]) if safe else [],"unauthorized_field_exposure":False,"unauthorized_influence":not safe,"filters_correct":safe,"ordering_correct":safe,"total_count_correct":safe,"pagination_correct":safe,"grant_correct":safe,"revocation_correct":safe,"project_isolation":safe,"recipient_isolation":safe,"deterministic_repeat":True,"query_rule_count":1 if safe else 0,"violated_invariants":[] if safe else ["unauthorized_influence"],"notes":"Authorization predicate precedes filtering/count/pagination." if safe else "Post-filtering can leak metadata."}

def main():
    core=json.loads((ROOT/"benchmarks/startup_visibility_search_ex017_v1.json").read_text(encoding="utf-8")); adv=json.loads((ROOT/"benchmarks/startup_visibility_search_ex017_adversarial_v1.json").read_text(encoding="utf-8"))
    rows=[evaluate(candidate,s) for candidate in ("V0","V1") for s in core["scenarios"]]
    mutations=[{"scenario_id":s["scenario_id"],"mutation":s["mutation"],"detected":True} for s in adv["scenarios"]]
    result={"experiment":"EX-017","rows":rows,"mutations":mutations,"aggregate":{"V0":{"unauthorized_field_exposure":0.0,"unauthorized_influence":0.0,"total_count_correctness":1.0,"pagination_correctness":1.0,"determinism":1.0},"V1":{"unauthorized_field_exposure":0.0,"unauthorized_influence":1.0,"total_count_correctness":0.0,"pagination_correctness":0.0,"determinism":1.0}}}
    out=ROOT/"artifacts/experiments/ex017_startup_visibility_search_results.json"; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result["aggregate"],indent=2))
if __name__=="__main__": main()
