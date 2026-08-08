"""
tests/debug_pair04_09.py

Diagnostic script สำหรับ pair_04 และ pair_09:
- ตรวจสอบ jd_data.requirements และ matches (ก่อน Judge)
- เช็ค matches[i].category vs jd_data.requirements[i].priority (indexing verification)
- ตรวจสอบการทำงานของ Judge Agent (หลัง Judge)
- หาสาเหตุความต่างระหว่าง LLM score (ก่อน Judge) และ Python score (หลัง Judge)
"""

import json
import sys
import os
import time

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Candidate API Keys
CANDIDATE_KEYS = [
    "GOOGLE_API_KEY",
    "GOOGLE_API_KEY_FRIEND1",
    "GOOGLE_API_KEY_FRIEND2",
    "GOOGLE_API_KEY_FRIEND3",
    "GOOGLE_API_KEY_FRIEND4",
    "GOOGLE_API_KEY_FRIEND5",
]

VALID_KEYS = [k for k in CANDIDATE_KEYS if os.getenv(k)]
current_key_idx = 0

def get_current_key() -> str:
    global current_key_idx
    if current_key_idx < len(VALID_KEYS):
        return VALID_KEYS[current_key_idx]
    raise RuntimeError("API Key ทั้งหมดหมดโควต้าแล้ว")

def rotate_key() -> str:
    global current_key_idx
    old_key = get_current_key()
    current_key_idx += 1
    if current_key_idx < len(VALID_KEYS):
        new_key = VALID_KEYS[current_key_idx]
        print(f"⚠️ Key [{old_key}] ชนโควต้า 429 → สลับไปใช้ [{new_key}]")
        return new_key
    raise RuntimeError("API Key ทั้งหมดหมดโควต้าแล้ว")

def call_with_rotation(fn, *args, **kwargs):
    for attempt in range(5):
        key_env = get_current_key()
        try:
            return fn(*args, api_key_env_var=key_env, **kwargs)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                rotate_key()
            elif "503" in err_str or "UNAVAILABLE" in err_str:
                print(f"⚠️ 503 UNAVAILABLE (attempt {attempt+1}/5) — รอ 3 วินาทีก่อนลองใหม่...")
                time.sleep(3)
            else:
                raise e
    raise RuntimeError("Max retries exceeded for call_with_rotation")

MODEL = "gemini-flash-latest"

CACHE_PATH = "tests/extraction_cache.json"
extraction_cache = {}
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, encoding="utf-8") as f:
        raw = json.load(f)
        extraction_cache = {k: v for k, v in raw.items() if not k.startswith("__")}
    print(f"📦 โหลด extraction cache: {list(extraction_cache.keys())}")

with open("tests/gold_dataset_final.json", encoding="utf-8") as f:
    dataset = json.load(f)

DIVIDER = "=" * 90

def get_resume_jd_data(pair_id: str, resume_text: str, jd_text: str):
    from agents.resume_extractor import extract_resume, ResumeData
    from agents.jd_extractor import extract_jd, JDData

    if pair_id in extraction_cache:
        cache = extraction_cache[pair_id]
        print(f"  [CACHE HIT] โหลด resume_data และ jd_data จาก cache สำหรับ {pair_id}")
        resume_data = ResumeData.model_validate(cache["resume_data"])
        jd_data = JDData.model_validate(cache["jd_data"])
    else:
        print(f"  [CACHE MISS] เรียก LLM สกัดข้อมูล {pair_id}")
        resume_data = call_with_rotation(extract_resume, resume_text, model=MODEL)
        jd_data = call_with_rotation(extract_jd, jd_text, model=MODEL)

    return resume_data, jd_data


def run_pair_diagnostic(pair_id: str):
    item = next(x for x in dataset if x["pair_id"] == pair_id)
    resume_text = item["resume_text"]
    jd_text = item["jd_text"]

    print(f"\n{DIVIDER}")
    print(f"  DIAGNOSTIC: {pair_id} ({item.get('target_role', '')})")
    print(DIVIDER)

    # 1. JD Requirements
    resume_data, jd_data = get_resume_jd_data(pair_id, resume_text, jd_text)
    
    print(f"\n--- [1] jd_data.requirements ที่สกัดได้ทั้งหมด ({len(jd_data.requirements)} รายการ) ---")
    for i, req in enumerate(jd_data.requirements):
        print(f"  [{i}] skill={req.skill!r:<35} priority={req.priority:<15} min_years={req.min_years}")

    # 2. Fit Analyzer (Before Judge)
    print(f"\n--- [2] Fit Analyzer — matches ก่อนเข้า Judge ---")
    from agents.fit_analyzer import analyze_fit
    fit_result = call_with_rotation(analyze_fit, resume_data, jd_data, model=MODEL)
    
    print(f"  LLM/FitAnalyzer Score (ก่อน Judge): Must={fit_result.must_have_score}  Nice={fit_result.nice_to_have_score}  Fit={fit_result.fit_score}")
    print(f"  matches ({len(fit_result.matches)} รายการ):")
    for i, m in enumerate(fit_result.matches):
        print(f"  [{i}] skill={m.skill!r:<30} status={m.status!r:<10} category={m.category!r:<12} req_idx={m.requirement_index}")
        print(f"       evidence={m.evidence!r}")

    # 3. Category vs Priority Indexing Check
    print(f"\n--- [3] ตรวจสอบ Indexing: matches[i].category vs jd_data.requirements[i].priority ---")
    category_mismatches = []
    for i, (m, req) in enumerate(zip(fit_result.matches, jd_data.requirements)):
        match_ok = (m.category == req.priority)
        status_symbol = "✅" if match_ok else "❌ MISMATCH"
        print(f"  [{i}] match.category={m.category!r:<12} vs req.priority={req.priority!r:<12} -> {status_symbol}")
        if not match_ok:
            category_mismatches.append((i, m.category, req.priority))

    if category_mismatches:
        print(f"  🚨 พบ Category/Indexing Bug {len(category_mismatches)} ตัว!")
    else:
        print(f"  ✅ Category และ Priority ตรงกันเป๊ะทุกตัว (ไม่มี Indexing Bug)")

    # 4. Judge Agent
    print(f"\n--- [4] Judge Agent — หลังผ่านการตรวจสอบ (Verified Matches) ---")
    from agents.judge_agent import judge_matches
    verified_matches = call_with_rotation(judge_matches, fit_result.matches, resume_text, model=MODEL)
    
    from evaluate_gold import calculate_scores_python
    py_must, py_nice, py_fit = calculate_scores_python(verified_matches, jd_data.requirements)
    
    print(f"  Python Score (หลัง Judge): Must={py_must}  Nice={py_nice}  Fit={py_fit}")
    print(f"  ความแตกต่างคะแนน Must: LLM Score ({fit_result.must_have_score}) vs Python Score ({py_must}) = ต่างกัน {fit_result.must_have_score - py_must} แต้ม")

    # 5. วิเคราะห์สาเหตุความต่างคะแนน
    print(f"\n--- [5] รายละเอียดการเปลี่ยนสถานะโดย Judge Agent ---")
    rejected_matches = []
    for i, (before, after) in enumerate(zip(fit_result.matches, verified_matches)):
        if before.status != after.status:
            rejected_matches.append((i, before, after))
            print(f"  [{i}] skill={before.skill!r}")
            print(f"       ก่อน Judge: status={before.status!r}, evidence={before.evidence!r}")
            print(f"       หลัง Judge: status={after.status!r}, evidence={after.evidence!r}")
            
            # ตรวจสอบว่า evidence มีอยู่ใน resume_text หรือไม่
            in_resume = False
            if before.evidence and before.evidence.strip() in resume_text:
                in_resume = True
            print(f"       Evidence มีใน resume_text จริงหรือไม่: {in_resume}")

    # 6. แสดง resume_text สำหรับเทียบ
    print(f"\n--- [6] resume_text ต้นฉบับ ---")
    print(resume_text)

    # 7. Gold Reference
    print(f"\n--- [7] Gold Dataset Reference ---")
    print(f"  Gold Must={item['gold_must_have_score']}  Nice={item['gold_nice_to_have_score']}  Fit={item['gold_fit_score']}")
    print(f"  Gold Matches:")
    for gm in item.get("gold_matches", []):
        print(f"    - [{gm['status']:<7}] {gm['skill']}")

    return {
        "pair_id": pair_id,
        "category_mismatches": len(category_mismatches),
        "llm_must": fit_result.must_have_score,
        "py_must": py_must,
        "diff_must": fit_result.must_have_score - py_must,
        "rejected_count": len(rejected_matches),
    }

if __name__ == "__main__":
    summary = []
    for pid in ["pair_04", "pair_09"]:
        res = run_pair_diagnostic(pid)
        summary.append(res)

    print(f"\n{DIVIDER}")
    print("  สรุปภาพรวม DIAGNOSTIC SUMMARY FOR PAIR_04 & PAIR_09")
    print(DIVIDER)
    for s in summary:
        print(f"  [{s['pair_id']}] LLM Must={s['llm_must']} | Py Must={s['py_must']} | Diff={s['diff_must']} | Index Mismatch={s['category_mismatches']} | Judge Rejected={s['rejected_count']}")
