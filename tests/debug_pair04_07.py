"""
tests/debug_pair04_07.py

Diagnostic script สำหรับ pair_04 (Sales Representative) และ pair_07 (Graphic Designer)
ใช้ Key Auto-Rotation อัตโนมัติเมื่อเจอ 429
"""
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# รายชื่อ Candidate Keys ทั้งหมด
CANDIDATE_KEYS = [
    "GOOGLE_API_KEY",
    "GOOGLE_API_KEY_FRIEND1",
    "GOOGLE_API_KEY_FRIEND2",
    "GOOGLE_API_KEY_FRIEND3",
    "GOOGLE_API_KEY_FRIEND4",
    "GOOGLE_API_KEY_FRIEND5",
]

# กรองเฉพาะ key ที่มีค่าอยู่จริง
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
    print(f"📦 โหลด extraction cache: {list(extraction_cache.keys())}")

# โหลด gold dataset
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
        resume_data = call_with_rotation(extract_resume, resume_text)
        jd_data = call_with_rotation(extract_jd, jd_text)

    return resume_data, jd_data


def run_diagnostic(pair_id: str):
    item = next(x for x in dataset if x["pair_id"] == pair_id)
    resume_text = item["resume_text"]
    jd_text = item["jd_text"]

    print(f"\n{DIVIDER}")
    print(f"  DIAGNOSTIC: {pair_id}")
    print(DIVIDER)

    # ───────────────────────────────────────────────
    # A) resume_text ต้นฉบับเต็ม
    # ───────────────────────────────────────────────
    print("\n─── [A] resume_text ต้นฉบับเต็ม ─────────────────────────────────────────────────")
    print(resume_text)

    # ───────────────────────────────────────────────
    # B) STEP 1+2 — Resume + JD Extractor
    # ───────────────────────────────────────────────
    print(f"\n─── [STEP 1] Resume Extractor ────────────────────────────────────────────────────")
    resume_data, jd_data = get_resume_jd_data(pair_id, resume_text, jd_text)
    print(resume_data.model_dump_json(indent=2, ensure_ascii=False))

    # ───────────────────────────────────────────────
    # C) jd_data.requirements (ครบ + priority)
    # ───────────────────────────────────────────────
    print(f"\n─── [STEP 2] JD Extractor — jd_data.requirements (ครบทุกตัว พร้อม priority) ────")
    print(f"  job_title: {jd_data.job_title!r}")
    print(f"  overall_min_years: {jd_data.overall_min_years}")
    print(f"  requirements ({len(jd_data.requirements)} รายการ):")
    for i, req in enumerate(jd_data.requirements):
        print(f"    [{i}] skill={req.skill!r}  priority={req.priority}  min_years={req.min_years}")

    # ───────────────────────────────────────────────
    # D) STEP 3 — Fit Analyzer → matches ก่อนเข้า Judge
    # ───────────────────────────────────────────────
    print(f"\n─── [STEP 3] Fit Analyzer — matches ก่อนเข้า Judge ─────────────────────────────")
    from agents.fit_analyzer import analyze_fit
    fit_result = call_with_rotation(analyze_fit, resume_data, jd_data)
    print(f"  LLM must_have_score={fit_result.must_have_score}  nice_to_have_score={fit_result.nice_to_have_score}  fit_score={fit_result.fit_score}")
    print(f"  matches ({len(fit_result.matches)} รายการ):")
    for i, m in enumerate(fit_result.matches):
        print(f"    [{i}] skill={m.skill!r}")
        print(f"         status={m.status!r}")
        print(f"         evidence={m.evidence!r}")
        print(f"         years_found={m.years_found}")

    # ───────────────────────────────────────────────
    # E) STEP 4 — Judge Agent raw output (VerifiedMatch)
    # ───────────────────────────────────────────────
    print(f"\n─── [STEP 4] Judge Agent — VerifiedMatch raw output ──────────────────────────────")
    from agents.judge_agent import judge_matches
    corrected_matches = call_with_rotation(judge_matches, fit_result.matches, resume_text)

    print(f"\n─── [STEP 5] verified_matches หลังผ่าน Judge (corrected) ────────────────────────")
    for i, m in enumerate(corrected_matches):
        print(f"    [{i}] skill={m.skill!r}  status={m.status!r}  evidence={m.evidence!r}")

    # ───────────────────────────────────────────────
    # G) STEP 6 — เทียบ before/after สำหรับ match ที่ถูกปัด
    # ───────────────────────────────────────────────
    print(f"\n─── [STEP 6] เปรียบเทียบ before/after Judge สำหรับ match ที่ถูกปัด ─────────────")

    changed_to_missing = []
    unchanged_count = 0
    for i, (before, after) in enumerate(zip(fit_result.matches, corrected_matches)):
        if before.status in ("met", "partial") and after.status == "missing":
            changed_to_missing.append((i, before, after))
        else:
            unchanged_count += 1

    print(f"  สรุป: Judge เปลี่ยนเป็น missing {len(changed_to_missing)} / {len(fit_result.matches)} ตัว  |  ไม่เปลี่ยน {unchanged_count} ตัว")

    for (i, before, after) in changed_to_missing:
        print(f"\n  ── Match [{i}] skill={before.skill!r} (ก่อน={before.status!r} → หลัง='missing') ──")
        print(f"     Evidence ที่ Fit Analyzer อ้าง: {before.evidence!r}")

    # ───────────────────────────────────────────────
    # H) Gold standard
    # ───────────────────────────────────────────────
    print(f"\n─── [STEP 7] Gold Standard ────────────────────────────────────────────────────────")
    print(f"  gold_must_have_score={item['gold_must_have_score']}  "
          f"gold_nice_to_have_score={item['gold_nice_to_have_score']}  "
          f"gold_fit_score={item['gold_fit_score']}")
    print(f"  gold_matches ({len(item['gold_matches'])} รายการ):")
    for gm in item["gold_matches"]:
        print(f"    {gm['skill']}: {gm['status']}")

    return {
        "pair_id": pair_id,
        "total_matches": len(fit_result.matches),
        "total_paded_to_missing": len(changed_to_missing),
    }


# ─── รัน diagnostic ทั้งสอง pair ───
results = []
for pid in ["pair_04", "pair_07"]:
    r = run_diagnostic(pid)
    results.append(r)

print(f"\n{DIVIDER}")
print("  DIAGNOSTIC VERIFICATION SUMMARY")
print(DIVIDER)
for r in results:
    print(f"  {r['pair_id']}: Match ที่ถูกปัดเป็น missing = {r['total_paded_to_missing']} / {r['total_matches']}")
print(DIVIDER)
