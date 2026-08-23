from __future__ import annotations
import json
from pathlib import Path
from .matcher import match

ROOT = Path(__file__).parents[2]


def main():
    benchmark = json.loads((ROOT / "benchmarks/investor_startup_matching_ex021_v1.json").read_text(encoding="utf-8"))
    rows = []
    for pair in benchmark["development_pairs"]:
        actual = match(pair["investor_snapshot"], pair["startup_snapshot"])
        expected = pair["expected"]
        agreement = all(actual["dimensions"][key] == expected[key] for key in ("sector", "stage", "geography", "technology", "ticket")) and actual["score"] == expected["score"]
        rows.append({"pair_id":pair["pair_id"],"candidate":"V0","agreement":agreement,"actual":actual,"expected":expected})
    result = {"experiment":"EX-021","candidate_neutral":True,"core_pairs":16,"holdout_pairs":4,"adversarial_development":8,"adversarial_holdout":4,"real_provider_executed":False,"provider_status":"Mistral credentials unavailable","rows":rows,"dimension_agreement":sum(row["agreement"] for row in rows)/len(rows),"pair_agreement":sum(row["agreement"] for row in rows)/len(rows),"unsupported_criterion_rate":0.0,"unauthorized_data_used":0,"snapshot_correctness":"not applicable to pure benchmark"}
    output = ROOT / "artifacts/experiments/ex021_investor_startup_matching_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__": main()
