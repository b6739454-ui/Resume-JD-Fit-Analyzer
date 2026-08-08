"""
tests/audit_mismatch_patterns.py

Diagnostic script สำหรับวิเคราะห์ pattern ความแตกต่างเฉพาะคู่:
- pair_09: ตรวจสอบ skill ที่ตกจาก met เป็น missing/partial
- pair_10: ตรวจสอบ nice-to-have skills ที่ Py=0 (Gold=16)
- pair_11: ตรวจสอบ nice-to-have evidence ที่ถูก Judge ปัด (LLM=100, Py=66)
- pair_06: ตรวจสอบ must-have skills (Gold=75, Py=50)
"""

import json
import sys
import os

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GOLD_PATH = "tests/gold_dataset_final.json"
EVAL_PATH = "tests/evaluation_results.json"
CACHE_PATH = "tests/extraction_cache.json"
PROG_PATH = "tests/evaluation_progress.json"

with open(GOLD_PATH, encoding="utf-8") as f:
    gold_data = {x["pair_id"]: x for x in json.load(f)}

with open(EVAL_PATH, encoding="utf-8") as f:
    eval_results = json.load(f)

with open(CACHE_PATH, encoding="utf-8") as f:
    raw_cache = json.load(f)
    cache_data = {k: v for k, v in raw_cache.items() if not k.startswith("__")}

prog_results = {}
if os.path.exists(PROG_PATH):
    with open(PROG_PATH, encoding="utf-8") as f:
        pdata = json.load(f)
        for res in pdata.get("results", []):
            prog_results[res["pair_id"]] = res

DIVIDER = "=" * 90


def audit_pair_09():
    print(f"\n{DIVIDER}")
    print("  AUDIT PAIR_09 (Construction Project Manager)")
    print(DIVIDER)
    
    item = gold_data["pair_09"]
    reqs = cache_data["pair_09"]["jd_data"]["requirements"]
    
    print("\n--- [1] JD Requirements & Priorities ---")
    for i, r in enumerate(reqs):
        print(f"  [{i}] skill={r['skill']!r:<40} priority={r['priority']}")

    print("\n--- [2] Gold Matches vs Actual Resume Text ---")
    for gm in item.get("gold_matches", []):
        print(f"  Gold Skill: {gm['skill']!r:<35} Gold Status: {gm['status']}")

    print("\n--- [3] Resume Text Snippets ---")
    print(item["resume_text"])


def audit_pair_10():
    print(f"\n{DIVIDER}")
    print("  AUDIT PAIR_10 (Nice-to-Have Score Py=0 vs Gold=16)")
    print(DIVIDER)
    
    item = gold_data["pair_10"]
    reqs = cache_data["pair_10"]["jd_data"]["requirements"]
    
    print("\n--- [1] JD Requirements & Priorities ---")
    for i, r in enumerate(reqs):
        print(f"  [{i}] skill={r['skill']!r:<40} priority={r['priority']}")

    print("\n--- [2] Gold Matches ---")
    for gm in item.get("gold_matches", []):
        print(f"  Gold Skill: {gm['skill']!r:<35} Gold Status: {gm['status']}")

    print("\n--- [3] Resume Text Snippets ---")
    print(item["resume_text"])


def audit_pair_11():
    print(f"\n{DIVIDER}")
    print("  AUDIT PAIR_11 (Nice-to-Have LLM=100 vs Py=66)")
    print(DIVIDER)
    
    item = gold_data["pair_11"]
    reqs = cache_data["pair_11"]["jd_data"]["requirements"]
    
    print("\n--- [1] JD Requirements & Priorities ---")
    for i, r in enumerate(reqs):
        print(f"  [{i}] skill={r['skill']!r:<40} priority={r['priority']}")

    print("\n--- [2] Gold Matches ---")
    for gm in item.get("gold_matches", []):
        print(f"  Gold Skill: {gm['skill']!r:<35} Gold Status: {gm['status']}")

    print("\n--- [3] Resume Text Snippets ---")
    print(item["resume_text"])


def audit_pair_06():
    print(f"\n{DIVIDER}")
    print("  AUDIT PAIR_06 (Must-Have Gold=75 vs Py=50)")
    print(DIVIDER)
    
    item = gold_data["pair_06"]
    reqs = cache_data["pair_06"]["jd_data"]["requirements"]
    
    print("\n--- [1] JD Requirements & Priorities ---")
    for i, r in enumerate(reqs):
        print(f"  [{i}] skill={r['skill']!r:<40} priority={r['priority']}")

    print("\n--- [2] Gold Matches ---")
    for gm in item.get("gold_matches", []):
        print(f"  Gold Skill: {gm['skill']!r:<35} Gold Status: {gm['status']}")

    print("\n--- [3] Resume Text Snippets ---")
    print(item["resume_text"])


if __name__ == "__main__":
    audit_pair_09()
    audit_pair_10()
    audit_pair_11()
    audit_pair_06()
