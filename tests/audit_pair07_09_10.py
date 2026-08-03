"""
tests/audit_pair07_09_10.py

ขั้นที่ 1: เทียบ bullet count vs requirements จาก cache
ขั้นที่ 2: ดู matches จาก evaluation_results.json + extraction_cache.json
          เพื่อหาสาเหตุ under-predict — ไม่เรียก LLM ใดๆ
"""
import json, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
GOLD_PATH    = os.path.join(BASE, "gold_dataset_final.json")
CACHE_PATH   = os.path.join(BASE, "extraction_cache.json")

with open(GOLD_PATH, encoding="utf-8") as f:
    gold = {x["pair_id"]: x for x in json.load(f)}

with open(CACHE_PATH, encoding="utf-8") as f:
    raw = json.load(f)
    cache = {k: v for k, v in raw.items() if not k.startswith("__")}

BULLET_RE = re.compile(r"^\s*[-•*]\s+\S")

def get_bullets(text):
    return [l.strip() for l in text.splitlines() if BULLET_RE.match(l)]

# ===============================================================
# ขั้นที่ 1 : bullet count vs requirement count
# ===============================================================
print("=" * 90)
print("ขั้นที่ 1 — Bullet Count vs JD Extractor Requirements (from cache)")
print("=" * 90)

TARGET = ["pair_07", "pair_08", "pair_09", "pair_10"]
for pid in TARGET:
    item  = gold[pid]
    bullets = get_bullets(item["jd_text"])
    reqs  = cache.get(pid, {}).get("jd_data", {}).get("requirements", [])
    must  = [r for r in reqs if r["priority"] == "must_have"]
    nice  = [r for r in reqs if r["priority"] == "nice_to_have"]
    print(f"\n{'─'*80}")
    print(f"[{pid}] {item.get('target_role','')}   "
          f"Gold Must={item['gold_must_have_score']} Py Must=?")
    print(f"  Bullets  : {len(bullets)} รายการ")
    print(f"  Extractor: {len(must)} must_have + {len(nice)} nice_to_have = {len(reqs)} รวม")
    print(f"\n  JD Bullets ต้นฉบับ:")
    for b in bullets:
        print(f"    • {b}")
    print(f"\n  Requirements ที่ extract ได้:")
    for r in reqs:
        print(f"    [{r['priority']:<12}] {r['skill']}")

# ===============================================================
# ขั้นที่ 2 : อ่าน verified_matches จาก evaluation_results.json
# ===============================================================
EVAL_PATH = os.path.join(BASE, "evaluation_results.json")
if not os.path.exists(EVAL_PATH):
    print("\n⚠️ ไม่พบ evaluation_results.json — รัน evaluate_gold.py ก่อน")
else:
    with open(EVAL_PATH, encoding="utf-8") as f:
        eval_data = json.load(f)
    eval_by_id = {r["pair_id"]: r for r in eval_data["details"]}

    print("\n\n" + "=" * 90)
    print("ขั้นที่ 2 — Score Breakdown (Gold vs LLM vs Py) จาก evaluation_results.json")
    print("=" * 90)
    for pid in TARGET:
        r = eval_by_id.get(pid, {})
        item = gold[pid]
        reqs = cache.get(pid, {}).get("jd_data", {}).get("requirements", [])
        must_reqs = [x["skill"] for x in reqs if x["priority"] == "must_have"]
        nice_reqs = [x["skill"] for x in reqs if x["priority"] == "nice_to_have"]
        
        print(f"\n{'─'*80}")
        print(f"[{pid}] {item.get('target_role','')}")
        print(f"  Gold:  Must={r.get('gold_must','?')}  Nice={r.get('gold_nice','?')}  Fit={r.get('gold_fit','?')}")
        print(f"  LLM:   Must={r.get('pred_llm_must','?')}  Nice={r.get('pred_llm_nice','?')}  Fit={r.get('pred_llm_fit','?')}")
        print(f"  Py:    Must={r.get('pred_py_must','?')}  Nice={r.get('pred_py_nice','?')}  Fit={r.get('pred_py_fit','?')}")
        
        must_gap = r.get('gold_must', 0) - r.get('pred_py_must', 0)
        nice_gap = r.get('gold_nice', 0) - r.get('pred_py_nice', 0)
        print(f"  Gap:   Must={-must_gap:+d}  Nice={-nice_gap:+d}")
        
        print(f"\n  Must-Have requirements ที่ JD Extractor สกัดได้ ({len(must_reqs)}):")
        for s in must_reqs:
            print(f"    - {s}")
        
        print(f"\n  Gold matches ที่ควรจะเป็น:")
        for gm in item.get("gold_matches", []):
            print(f"    - [{gm['status']:<7}] {gm['skill']}")

    # ===============================================================
    # ขั้นที่ 3 : สรุป hypothesis
    # ===============================================================
    print("\n\n" + "=" * 90)
    print("สรุป Analysis")
    print("=" * 90)
    
    for pid in TARGET:
        r = eval_by_id.get(pid, {})
        item = gold[pid]
        reqs = cache.get(pid, {}).get("jd_data", {}).get("requirements", [])
        must_reqs = [x["skill"] for x in reqs if x["priority"] == "must_have"]
        bullets = get_bullets(item["jd_text"])
        gold_must_skills = [gm["skill"] for gm in item.get("gold_matches", []) if gm["status"] != "missing"]
        
        must_gap = r.get('gold_must', 0) - r.get('pred_py_must', 0)
        
        print(f"\n[{pid}] Gap Must={must_gap:+d}")
        
        # ตรวจว่า gold skills ถูกครอบคลุมโดย extracted requirements ไหม
        print(f"  Gold expects: {len(gold_must_skills)} skills ที่ควรเป็น met/partial")
        print(f"  Extractor got: {len(must_reqs)} must_have requirements")
        
        # ตรวจ % ที่ Python score ได้ = (ค่า Py) / 100 * len(must_reqs) 
        py_must = r.get('pred_py_must', 0)
        if len(must_reqs) > 0:
            implied_met = py_must / 100 * len(must_reqs)
            print(f"  Implied met count: {implied_met:.1f}/{len(must_reqs)} "
                  f"(Python score {py_must}% × {len(must_reqs)} reqs)")
