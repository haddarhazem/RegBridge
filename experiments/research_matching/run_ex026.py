from __future__ import annotations
import hashlib, json, math, random
from pathlib import Path
from experiments.research_matching.matcher import sparse, tokens, canonical

ROOT=Path(__file__).parents[2]
FIELDS=("domains","technologies","research_problem","keywords")
TOPICS=[("computer vision manufacturing","machine learning","detecting factory surface defects",["inspection","defect"]),("energy systems","forecasting","predicting electricity demand",["energy","demand"]),("medical health","medical imaging","segmenting lesions in scans",["lesion","segmentation"]),("agriculture","remote sensing","monitoring crop stress",["crop","satellite"]),("urban mobility","optimization","reducing traffic congestion",["traffic","routing"]),("cybersecurity","anomaly detection","detecting network intrusion",["network","intrusion"]),("materials","nanomaterials","designing recyclable battery materials",["battery","recycling"]),("water quality","sensors","detecting drinking water contamination",["water","contamination"]),("education","natural language processing","supporting language learner feedback",["language","feedback"]),("logistics","optimization","forecasting warehouse demand",["warehouse","demand"]),("climate","simulation","estimating urban flood risk",["flood","risk"]),("health","wearables","detecting cardiac anomalies",["cardiac","signals"]),("manufacturing","robotics","planning collaborative robot motion",["robot","motion"]),("agriculture","sensors","optimizing irrigation from soil data",["soil","irrigation"]),("language","natural language processing","translating technical documents",["translation","documents"]),("marine science","computer vision","classifying marine species",["marine","classification"]),("finance","time series","detecting transaction anomalies",["transactions","anomaly"]),("public health","statistics","estimating disease transmission",["disease","transmission"]),("construction","computer vision","monitoring worksite safety equipment",["safety","worksite"]),("astronomy","spectroscopy","identifying exoplanet atmospheres",["exoplanet","atmosphere"])]

def benchmark():
    needs=[{"id":f"FQ{i+1:02}","domains":[d],"technologies":[t],"research_problem":p,"keywords":k} for i,(d,t,p,k) in enumerate(TOPICS)]
    snaps=[]; strong={}; partial={}
    for i,(d,t,p,k) in enumerate(TOPICS[:16]):
        sid=f"FS{i+1:02}"; snaps.append({"id":sid,"domains":[d],"technologies":[t],"research_problem":p.replace("detecting","study of detecting").replace("predicting","study of predicting"),"keywords":k}); strong[f"FQ{i+1:02}"]=[sid]
        if i<8: partial[f"FQ{i+1:02}"]=[f"FS{((i+1)%8)+1:02}"]
    for i in range(18,32):
        sid=f"FS{i+1:02}"; d,t,p,k=TOPICS[i%10]; snaps.append({"id":sid,"domains":["generic research"],"technologies":[t],"research_problem":f"general methods for {t}","keywords":[t.split()[0]]})
    return {"version":"research_matching_recovery_ex026_v1","seed":2601,"needs":needs,"research_snapshots":snaps,"strong_pairs":strong,"partial_pairs":partial,"development_need_ids":["FQ01","FQ02","FQ03","FQ04","FQ05","FQ06","FQ19","FQ20"],"holdout_need_ids":[f"FQ{i:02}" for i in range(7,19)],"zero_relevant_need_ids":["FQ19","FQ20"],"tags":{"FQ01":["SAME_TECH_WRONG_PROBLEM"],"FQ02":["GENERIC_TERM"],"FQ03":["MISSING_FIELDS"],"FQ04":["CROSS_LANGUAGE"],"FQ05":["POLYSEMY"],"FQ19":["NO_MATCH"],"FQ20":["NO_MATCH"]}}

def rank(need, corpus): return sorted(({"id":x["id"],"score":sparse(need,x,corpus)} for x in corpus),key=lambda x:(-x["score"],x["id"]))
def evidence(need, item):
    problem=bool(tokens(need.get("research_problem")) & tokens(item.get("research_problem")))
    domain=bool(tokens(need.get("domains")) & tokens(item.get("domains")))
    tech=bool(tokens(need.get("technologies")) & tokens(item.get("technologies")))
    keyword=bool(tokens(need.get("keywords")) & tokens(item.get("keywords")))
    return problem or (domain and tech), (problem,domain,tech,keyword)
def graded(b,qid,sid): return 2 if sid in b["strong_pairs"].get(qid,[]) else 1 if sid in b["partial_pairs"].get(qid,[]) else 0
def metrics(b, rankings, ids):
    rows=[]
    for qid in ids:
        rel={x["id"] for x in b["research_snapshots"] if graded(b,qid,x["id"])}; strong={x for x in b["strong_pairs"].get(qid,[])}; top=rankings[qid][:5]; got=[x["id"] for x in top]; gains=[2 if x in strong else 1 if x in rel else 0 for x in got]; r=len(rel)
        ideal=sorted([2]*len(strong)+[1]*(len(rel-strong)),reverse=True)[:5]; dcg=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(gains)); idcg=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(ideal)); first=next((i+1 for i,x in enumerate(got) if x in strong),None)
        rows.append({"p1":float(bool(got and got[0] in rel)),"p3":sum(x in rel for x in got[:3])/3,"p5":sum(x in rel for x in got)/5,"recall":sum(x in rel for x in got)/r if r else 1.0,"hit5":float(bool(set(got)&rel)),"rprecision":sum(x in rel for x in got[:r])/r if r else 1.0,"map":sum((sum(x in rel for x in got[:i])/i) for i,x in enumerate(got,1) if x in rel)/r if r else 0.0,"mrr":1/first if first else 0.0,"ndcg":dcg/idcg if idcg else 1.0,"zero":not rel,"abstained":not got})
    pos=[x for x in rows if not x["zero"]]
    return {k:sum(x[k] for x in pos)/len(pos) for k in ("p1","p3","p5","recall","hit5","rprecision","map","mrr","ndcg")}|{"zero":sum(x["zero"] for x in rows),"correct_abstentions":sum(x["zero"] and x["abstained"] for x in rows),"false_matches":sum(x["zero"] and not x["abstained"] for x in rows),"abstention":sum(x["zero"] and x["abstained"] for x in rows)/sum(x["zero"] for x in rows) if any(x["zero"] for x in rows) else 1.0,"false_abstention":sum(not x["zero"] and x["abstained"] for x in rows)/len(pos) if pos else 0.0,"case_rows":rows}
def choose_threshold(b, rankings):
    values=sorted({0.0}|{row["score"] for q in b["development_need_ids"] for row in rankings[q][:1]})
    candidates=[]
    for t in values:
        filtered={q:[x for x in rows if x["score"]>t] for q,rows in rankings.items()}
        m=metrics(b,filtered,b["development_need_ids"])
        candidates.append((m["abstention"]>=.75,m["recall"],m["rprecision"],m["ndcg"],-m["false_abstention"],-t,t,m))
    return max(candidates)[-2], max(candidates)[-1], candidates
def main():
    b=benchmark(); (ROOT/"artifacts/experiments").mkdir(parents=True,exist_ok=True); raw=json.dumps(b,sort_keys=True).encode(); (ROOT/"artifacts/experiments/ex026_recovery_benchmark.json").write_bytes(raw)
    needs={x["id"]:x for x in b["needs"]}; corpus=b["research_snapshots"]; s0={q:rank(n,corpus) for q,n in needs.items()}; s1={q:[x for x in rows if evidence(needs[q],next(y for y in corpus if y["id"]==x["id"]))[0]] for q,rows in s0.items()}
    dev=metrics(b,s1,b["development_need_ids"]); threshold,threshold_metrics,threshold_grid=choose_threshold(b,s0)
    s2={q:[x for x in rows if x["score"]>threshold] for q,rows in s0.items()}; s3={q:[x for x in rows if x["id"] in {y["id"] for y in s1[q]} and x["score"]>threshold] for q,rows in s0.items()}
    result={"experiment":"EX-026","benchmark_sha256":hashlib.sha256(raw).hexdigest(),"candidates":{k:metrics(b,v,b["holdout_need_ids"]) for k,v in {"S0":s0,"S1":s1,"S2":s2,"S3":s3}.items()},"dev_s1":dev,"threshold":threshold,"threshold_selection":"DEV only; priority zero-match abstention, recall, R-Precision, nDCG, false abstention","threshold_dev_metrics":threshold_metrics,"threshold_grid":[{"threshold":x[6],"abstention":x[7]["abstention"],"recall":x[7]["recall"],"rprecision":x[7]["rprecision"]} for x in threshold_grid],"safety":{"private_full_text":0,"private_fields":0,"draft":0,"revoked":0,"invented_applications":0,"invented_capabilities":0},"frozen":True}
    (ROOT/"artifacts/experiments/ex026_recovery_results.json").write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps({k:{x:y for x,y in v.items() if x!="case_rows"} for k,v in result["candidates"].items()},indent=2))
if __name__=="__main__": main()
