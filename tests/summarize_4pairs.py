"""
tests/summarize_4pairs.py

Print concise summary for pair_09, pair_10, pair_11, pair_06
"""

import json
import os
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

GOLD_PATH = "tests/gold_dataset_final.json"
CACHE_PATH = "tests/extraction_cache.json"
PROG_PATH = "tests/evaluation_progress.json"

with open(GOLD_PATH, encoding="utf-8") as f:
    gold_data = {x["pair_id"]: x for x in json.load(f)}

with open(CACHE_PATH, encoding="utf-8") as f:
    raw_cache = json.load(f)
    cache_data = {k: v for k, v in raw_cache.items() if not k.startswith("__")}

with open(PROG_PATH, encoding="utf-8") as f:
    prog_data = json.load(f)
    results_by_id = {r["pair_id"]: r for r in prog_data.get("results", [])}

DIVIDER = "=" * 80


def summarize_pair(pid: str):
    item = gold_data[pid]
    c = cache_data[pid]
    r = results_by_id.get(pid, {})
    
    print(f"\n{DIVIDER}")
    print(f"  [{pid}] Role: {item.get('target_role', '')}")
    print(DIVIDER)
    print(f"  Scores: Gold Must={item.get('gold_must_have_score')} Nice={item.get('gold_nice_to_have_score')} Fit={item.get('gold_fit_score')}")
    print(f"          LLM  Must={r.get('pred_llm_must')} Nice={r.get('pred_llm_nice')} Fit={r.get('pred_llm_fit')}")
    print(f"          Py   Must={r.get('pred_py_must')} Nice={r.get('pred_py_nice')} Fit={r.get('pred_py_fit')}")
    
    reqs = c["jd_data"]["requirements"]
    print(f"\n  [JD Requirements Extracted ({len(reqs)})]:")
    for i, req in enumerate(reqs):
        print(f"    [{i}] [{req['priority']:<12}] {req['skill']}")
        
    print(f"\n  [Gold Matches ({len(item.get('gold_matches', []))})]:")
    for gm in item.get("gold_matches", []):
        print(f"    - [{gm['status']:<7}] {gm['skill']}")

if __name__ == "__main__":
    for pid in ["pair_09", "pair_10", "pair_11", "pair_06"]:
        summarize_pair(pid)
