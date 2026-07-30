"""
tests/debug_pair13_diag.py

Diagnostic script สำหรับ pair_13 (Junior/Entry-level Accountant)
วัตถุประสงค์: วินิจฉัยว่าทำไม nice-to-have Py score หายจาก 50 เป็น 0 หลังแก้ prompt fit_analyzer.py
ห้ามแก้โค้ดใดๆ ในสคริปต์นี้ — diagnostic เท่านั้น
"""
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Candidate Keys
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
    import time
    for attempt in range(5):
        key_env = get_current_key()
        try:
            return fn(*args, api_key_env_var=key_env, **kwargs)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                rotate_key()
            elif "503" in err_str or "UNAVAILABLE" in err_str:
                print(f"⚠️ 503 UNAVAILABLE (attempt {attempt+1}/5) — รอ 3 วินาทีก่อนลองใหม่...")
                time.sleep(3)
            else:
                raise e
    raise RuntimeError("Max retries exceeded for call_with_rotation")

MODEL = "gemini-flash-latest"

# โหลด extraction cache
CACHE_PATH = "tests/extraction_cache.json"
extraction_cache = {}
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, encoding="utf-8") as f:
        extraction_cache = json.load(f)

# โหลด gold dataset
with open("tests/gold_dataset_final.json", encoding="utf-8") as f:
    dataset = json.load(f)

item = next(x for x in dataset if x["pair_id"] == "pair_13")
resume_text = item["resume_text"]
jd_text = item["jd_text"]

DIVIDER = "=" * 90

print(f"\n{DIVIDER}")
print(f"  DIAGNOSTIC FOR PAIR_13 (Junior/Entry-level Accountant)")
print(DIVIDER)

# 1) Resume & JD Extractor
from agents.resume_extractor import extract_resume, ResumeData
from agents.jd_extractor import extract_jd, JDData

if "pair_13" in extraction_cache:
    print("📦 โหลด resume_data และ jd_data จาก extraction_cache (pair_13)")
    cache_item = extraction_cache["pair_13"]
    resume_data = ResumeData.model_validate(cache_item["resume_data"])
    jd_data = JDData.model_validate(cache_item["jd_data"])
else:
    print("เรียก LLM สกัด resume_data และ jd_data")
    resume_data = call_with_rotation(extract_resume, resume_text)
    jd_data = call_with_rotation(extract_jd, jd_text)

print("\n─── [A] resume_text ต้นฉบับเต็ม ─────────────────────────────────────────────────")
print(resume_text)

print("\n─── [B] jd_data.requirements ทั้งหมด ───────────────────────────────────────────")
must_reqs = []
nice_reqs = []
for i, req in enumerate(jd_data.requirements):
    tag = f"[{i}] skill={req.skill!r} priority={req.priority} min_years={req.min_years}"
    if req.priority == "must_have":
        must_reqs.append((i, req))
    else:
        nice_reqs.append((i, req))
    print(f"  {tag}")

print(f"\nสรุป Requirements: ทั้งหมด {len(jd_data.requirements)} ตัว (must_have = {len(must_reqs)} ตัว, nice_to_have = {len(nice_reqs)} ตัว)")

print("\n─── [C] Nice-To-Have Requirements รายตัว ────────────────────────────────────────")
for idx, req in nice_reqs:
    print(f"  [index={idx}] skill={req.skill!r} priority={req.priority} min_years={req.min_years}")

# 2) Fit Analyzer (ก่อนเข้า Judge)
from agents.fit_analyzer import analyze_fit
fit_result = call_with_rotation(analyze_fit, resume_data, jd_data)

print("\n─── [D] Fit Analyzer Matches (ก่อนเข้า Judge) ──────────────────────────────────")
print(f"  LLM must_have_score={fit_result.must_have_score}  nice_to_have_score={fit_result.nice_to_have_score}  fit_score={fit_result.fit_score}")
print("\n  [เฉพาะ Nice-To-Have Matches ก่อนเข้า Judge]:")
for idx, req in nice_reqs:
    m = fit_result.matches[idx] if idx < len(fit_result.matches) else None
    if m:
        print(f"    [index={idx}] skill={m.skill!r} status={m.status!r} evidence={m.evidence!r} years={m.years_found}")
    else:
        print(f"    [index={idx}] ไม่พบ match")

print("\n  [ Must-Have Matches ก่อนเข้า Judge สำหรับเปรียบเทียบ]:")
for idx, req in must_reqs:
    m = fit_result.matches[idx] if idx < len(fit_result.matches) else None
    if m:
        print(f"    [index={idx}] skill={m.skill!r} status={m.status!r} evidence={m.evidence!r}")

# 3) Judge Agent
from agents.judge_agent import judge_matches

print("\n─── [E] Judge Agent Verified Matches (หลังตรวจ evidence) ─────────────────────────")
corrected_matches = call_with_rotation(judge_matches, fit_result.matches, resume_text)

print("\n  [เฉพาะ Nice-To-Have Matches หลังเข้า Judge]:")
for idx, req in nice_reqs:
    m = corrected_matches[idx] if idx < len(corrected_matches) else None
    if m:
        print(f"    [index={idx}] skill={m.skill!r} status={m.status!r} evidence={m.evidence!r}")

# 4) ตรวจสอบ match Nice-To-Have ที่ถูกปัด หรือเปลี่ยนสถานะ
print("\n─── [F] วิเคราะห์ Nice-To-Have match ที่เปลี่ยนสถานะหลัง Judge ────────────────────")
resume_lower = resume_text.lower()
for idx, req in nice_reqs:
    before = fit_result.matches[idx]
    after = corrected_matches[idx]
    print(f"\n  ── [index={idx}] skill={req.skill!r} (ก่อน Judge={before.status!r} → หลัง Judge={after.status!r}) ──")
    print(f"     Evidence ที่ Fit Analyzer อ้าง: {before.evidence!r}")

    if before.evidence:
        ev_clean = before.evidence.strip().lower()
        idx_found = resume_lower.find(ev_clean[:60])
        if idx_found >= 0:
            snippet = resume_text[max(0, idx_found-20):idx_found+100]
            print(f"     [ค้นใน resume] ✅ พบข้อความจริงที่ตำแหน่ง {idx_found}: ...{snippet!r}...")
        else:
            print(f"     [ค้นใน resume] ❌ ไม่พบข้อความ 60 ตัวแรก: {ev_clean[:60]!r}")
    else:
        print(f"     [ค้นใน resume] ⚠️  evidence เป็น null / ไม่มีข้อความ")

# 5) คำนวณคะแนน Python ใหม่ของ Nice-To-Have
from agents.fit_analyzer import _compute_scores_python
must_score, nice_score, fit_score = _compute_scores_python(corrected_matches, jd_data.requirements)

print("\n─── [G] คะแนนคำนวณใหม่โดย Python ───────────────────────────────────────────────")
print(f"  Must-Have Score (Py): {must_score}")
print(f"  Nice-To-Have Score (Py): {nice_score}")
print(f"  Fit Score (Py): {fit_score}")

print("\n─── [H] เปรียบเทียบกับรอบก่อนหน้า (ก่อนแก้ prompt) ──────────────────────────────")
print("  รอบก่อนหน้า (Before Prompt Fix):")
print("    pred_py_must: 100")
print("    pred_py_nice: 50   (มี 1 ใน 2 nice-to-have match ที่ได้ status='partial' หรือ 'met')")
print("    pred_py_fit:  85")
print("\n  รอบปัจจุบัน (After Prompt Fix):")
print(f"    pred_py_must: {must_score}")
print(f"    pred_py_nice: {nice_score}")
print(f"    pred_py_fit:  {fit_score}")

print(f"\n{DIVIDER}")
