"""
tests/inspect_detailed_matches.py

Inspect Fit Analyzer matches (before Judge) and Verified matches (after Judge) for:
pair_09, pair_10, pair_11, pair_06
"""

import json
import sys
import os

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

GOLD_PATH = "tests/gold_dataset_final.json"
CACHE_PATH = "tests/extraction_cache.json"

from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.fit_analyzer import analyze_fit
from agents.judge_agent import judge_matches
from schemas import ResumeData, JDData

with open(GOLD_PATH, encoding="utf-8") as f:
    gold_data = {x["pair_id"]: x for x in json.load(f)}

with open(CACHE_PATH, encoding="utf-8") as f:
    raw_cache = json.load(f)
    cache_data = {k: v for k, v in raw_cache.items() if not k.startswith("__")}

DIVIDER = "=" * 90


def analyze_pair_details(pid: str):
    item = gold_data[pid]
    c = cache_data[pid]
    
    resume_data = ResumeData.model_validate(c["resume_data"])
    jd_data = JDData.model_validate(c["jd_data"])
    resume_text = item["resume_text"]
    
    print(f"\n{DIVIDER}")
    print(f"  DETAILED ANALYSIS FOR {pid} ({item.get('target_role', '')})")
    print(DIVIDER)
    
    # 1. Fit Analyzer
    fit_res = analyze_fit(resume_data, jd_data)
    
    # 2. Judge
    verified_res = judge_matches(fit_res.matches, resume_text)
    
    print(f"\n--- Requirements vs Fit Analyzer (LLM) vs Judge (Py) vs Gold ---")
    
    gold_matches_by_skill = {gm["skill"].lower(): gm["status"] for gm in item.get("gold_matches", [])}
    
    for i, (req, m_before, m_after) in enumerate(zip(jd_data.requirements, fit_res.matches, verified_res)):
        print(f"\n[{i}] Req Skill: {req.skill!r} ({req.priority})")
        print(f"    - Fit Analyzer Status: {m_before.status!r}")
        print(f"    - Fit Analyzer Evidence: {m_before.evidence!r}")
        
        in_resume = False
        if m_before.evidence and m_before.evidence.strip() in resume_text:
            in_resume = True
        print(f"    - Evidence is exact substring in resume: {in_resume}")
        print(f"    - Judge Status: {m_after.status!r}")
        
        # find matching gold
        from agents.skill_normalizer import normalize_skill_name, _normalizer
        _normalizer._lazy_load()
        emb_req = _normalizer.model.encode([req.skill], normalize_embeddings=True)[0]
        
        best_gold_skill = None
        best_sim = -1.0
        for gm in item.get("gold_matches", []):
            emb_gold = _normalizer.model.encode([gm["skill"]], normalize_embeddings=True)[0]
            sim = float(emb_req @ emb_gold)
            if sim > best_sim:
                best_sim = sim
                best_gold_skill = gm
                
        if best_gold_skill and best_sim >= 0.4:
            print(f"    - Gold Match: {best_gold_skill['skill']!r} -> status={best_gold_skill['status']!r} (sim={best_sim:.2f})")
        else:
            print(f"    - Gold Match: None found")


if __name__ == "__main__":
    for pid in ["pair_09", "pair_10", "pair_11", "pair_06"]:
        analyze_pair_details(pid)
