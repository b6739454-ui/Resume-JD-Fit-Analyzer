"""
tests/inspect_pairs.py

Detailed inspector for pair_06, pair_09, pair_10, pair_11:
Prints exact requirements, gold_matches, pred_matches (LLM & Verified Py), evidence, and match status.
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
EVAL_PATH = "tests/evaluation_results.json"
PROG_PATH = "tests/evaluation_progress.json"
CACHE_PATH = "tests/extraction_cache.json"

with open(GOLD_PATH, encoding="utf-8") as f:
    gold_data = {x["pair_id"]: x for x in json.load(f)}

with open(CACHE_PATH, encoding="utf-8") as f:
    raw_cache = json.load(f)
    cache_data = {k: v for k, v in raw_cache.items() if not k.startswith("__")}

prog_data = {}
if os.path.exists(PROG_PATH):
    with open(PROG_PATH, encoding="utf-8") as f:
        p = json.load(f)
        for r in p.get("results", []):
            prog_data[r["pair_id"]] = r

DIVIDER = "=" * 90


def inspect(pid: str):
    print(f"\n{DIVIDER}")
    print(f"  INSPECT PAIR: {pid}")
    print(DIVIDER)
    
    g = gold_data[pid]
    c = cache_data.get(pid, {})
    p = prog_data.get(pid, {})
    
    reqs = c.get("jd_data", {}).get("requirements", [])
    print(f"\n--- [1] JD Requirements ({len(reqs)}) ---")
    for i, r in enumerate(reqs):
        print(f"  [{i}] skill={r['skill']!r:<40} priority={r['priority']}")
        
    print(f"\n--- [2] Gold Scores vs Predicted Scores ---")
    print(f"  Gold: Must={g.get('gold_must_have_score')}  Nice={g.get('gold_nice_to_have_score')}  Fit={g.get('gold_fit_score')}")
    print(f"  Prog: Must={p.get('pred_py_must')} (LLM:{p.get('pred_llm_must')})  Nice={p.get('pred_py_nice')} (LLM:{p.get('pred_llm_nice')})  Fit={p.get('pred_py_fit')} (LLM:{p.get('pred_llm_fit')})")

    print(f"\n--- [3] Gold Matches ({len(g.get('gold_matches', []))}) ---")
    for gm in g.get("gold_matches", []):
        print(f"  Gold Skill: {gm['skill']!r:<35} Status: {gm['status']}")

    print(f"\n--- [4] Resume Text (First 1500 chars) ---")
    print(g["resume_text"][:1500])


if __name__ == "__main__":
    for pid in ["pair_09", "pair_10", "pair_11", "pair_06"]:
        inspect(pid)
