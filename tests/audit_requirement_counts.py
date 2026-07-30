"""
tests/audit_requirement_counts.py

เปรียบเทียบ:
  1. จำนวน bullet ที่นับได้จาก jd_text ตรงๆ (ทั้ง Required + Preferred)
  2. จำนวน requirements ที่ JD Extractor สกัดได้จริง (จาก extraction_cache.json)

ไม่เรียก API ใดๆ — อ่านจาก cache และ gold dataset เท่านั้น
"""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
GOLD_PATH   = os.path.join(BASE, "gold_dataset_final.json")
CACHE_PATH  = os.path.join(BASE, "extraction_cache.json")
RESULTS_PATH = os.path.join(BASE, "evaluation_results.json")

with open(GOLD_PATH, encoding="utf-8") as f:
    gold = {item["pair_id"]: item for item in json.load(f)}

with open(CACHE_PATH, encoding="utf-8") as f:
    raw_cache = json.load(f)
    cache = {k: v for k, v in raw_cache.items() if not k.startswith("__")}

with open(RESULTS_PATH, encoding="utf-8") as f:
    eval_results = {r["pair_id"]: r for r in json.load(f)["details"]}

def count_bullets(text: str) -> tuple[int, int, int]:
    """
    นับ bullet ในแต่ละหมวดของ JD text
    Returns: (must_bullets, nice_bullets, total_bullets)
    """
    lines = text.splitlines()
    
    # ตรวจ section header
    MUST_HEADERS = re.compile(
        r"required|must.have|qualifications|responsibilities|minimum|essential|skills needed",
        re.IGNORECASE
    )
    NICE_HEADERS = re.compile(
        r"preferred|nice.to.have|bonus|plus|advantage|desired|optional",
        re.IGNORECASE
    )
    BULLET_PATTERN = re.compile(r"^\s*[-•*]\s+\S")
    HEADER_PATTERN = re.compile(r"^\s*([A-Za-z][^:]{3,60}:)\s*$")  # บรรทัดที่เป็น header เช่น "Required Skills:"
    
    current_section = "must"  # default
    must_bullets = 0
    nice_bullets = 0
    
    for line in lines:
        # ตรวจ section header
        if HEADER_PATTERN.match(line):
            if MUST_HEADERS.search(line):
                current_section = "must"
            elif NICE_HEADERS.search(line):
                current_section = "nice"
        
        # นับ bullet
        if BULLET_PATTERN.match(line):
            if current_section == "must":
                must_bullets += 1
            else:
                nice_bullets += 1
    
    return must_bullets, nice_bullets, must_bullets + nice_bullets


print("=" * 100)
print(f"{'Pair ID':<10} | {'Role':<35} | {'Bullets M/N':<12} | {'Extractor M/N':<14} | {'Diff M':<7} | {'Under-pred Must':<15}")
print("=" * 100)

problem_pairs = []
for pair_id in sorted(gold.keys()):
    item = gold[pair_id]
    jd_text = item["jd_text"]

    # นับ bullet จาก jd_text
    must_b, nice_b, total_b = count_bullets(jd_text)

    # ดึงจำนวน requirements จาก cache
    pair_cache = cache.get(pair_id, {})
    if "jd_data" not in pair_cache:
        print(f"{pair_id:<10} | {'(no cache)':<35} | {'N/A':<12} | {'N/A':<14} | {'N/A':<7} | N/A")
        continue

    reqs = pair_cache["jd_data"].get("requirements", [])
    ext_must = sum(1 for r in reqs if r["priority"] == "must_have")
    ext_nice = sum(1 for r in reqs if r["priority"] == "nice_to_have")
    diff_must = ext_must - must_b

    # ดึงผล eval
    eval_r = eval_results.get(pair_id, {})
    gold_must  = eval_r.get("gold_must", "?")
    pred_must  = eval_r.get("pred_py_must", "?")
    delta_must = (pred_must - gold_must) if isinstance(pred_must, int) else "?"

    role = item.get("target_role", "")[:33]
    bullets_str   = f"{must_b}/{nice_b}"
    extractor_str = f"{ext_must}/{ext_nice}"
    diff_str = f"+{diff_must}" if diff_must > 0 else str(diff_must)
    delta_str = f"{delta_must:+d}" if isinstance(delta_must, int) else delta_must

    flag = " ⬅ INFLATE" if diff_must > 0 else ""

    print(f"{pair_id:<10} | {role:<35} | {bullets_str:<12} | {extractor_str:<14} | {diff_str:<7} | {delta_str:<10}{flag}")

    if diff_must > 0:
        problem_pairs.append((pair_id, must_b, ext_must, diff_must))

print("=" * 100)
print(f"\n📌 สรุป: พบ {len(problem_pairs)} คู่ที่ JD Extractor สกัด must_have requirements เกิน bullet จริง:")
for pid, b, e, d in sorted(problem_pairs, key=lambda x: -x[3]):
    print(f"   {pid}: bullet={b} extracted={e} over-count=+{d}")

print("\n📋 Detail requirements สำหรับ pair ที่ under-predict หนัก (pair_04, pair_06, pair_07, pair_09):")
for pid in ["pair_04", "pair_06", "pair_07", "pair_09"]:
    print(f"\n{'─'*80}")
    print(f"  [{pid}] {gold[pid].get('target_role','')}")
    reqs = cache.get(pid, {}).get("jd_data", {}).get("requirements", [])
    for i, r in enumerate(reqs):
        print(f"    [{i}] {r['priority']:<12} | {r['skill']}")
    print(f"\n  --- JD Bullets (ต้นฉบับ) ---")
    for line in gold[pid]["jd_text"].splitlines():
        if re.match(r"^\s*[-•*]\s+\S", line):
            print(f"    {line.strip()}")
