import json
import sys
import os
import time
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from agents.resume_extractor import extract_resume
from agents.jd_extractor import extract_jd
from agents.fit_analyzer import analyze_fit
from agents.judge_agent import judge_matches

MODEL = "gemini-flash-latest"

CANDIDATE_KEY_ENVS = [
    "GOOGLE_API_KEY",
    "GOOGLE_API_KEY_FRIEND1",
    "GOOGLE_API_KEY_FRIEND2",
    "GOOGLE_API_KEY_FRIEND3",
    "GOOGLE_API_KEY_FRIEND4",
    "GOOGLE_API_KEY_FRIEND5",
]

valid_keys = [k for k in CANDIDATE_KEY_ENVS if os.getenv(k) and os.getenv(k).strip()]
print(f"[Model: {MODEL}] พบ API key {len(valid_keys)} ตัว: {', '.join(valid_keys)}\n")

key_idx = [0]

def call_with_rotation(fn, *args, **kwargs):
    for _ in range(len(valid_keys)):
        key = valid_keys[key_idx[0]]
        try:
            kwargs["api_key_env_var"] = key
            kwargs["model"] = MODEL
            return fn(*args, **kwargs)
        except Exception as e:
            if any(k in str(e).lower() for k in ("429", "quota", "exhausted")):
                print(f"  ⚠️ Key [{key}] หมดโควต้า 429 → ลอง key ถัดไป", flush=True)
                key_idx[0] = (key_idx[0] + 1) % len(valid_keys)
                time.sleep(2)
            else:
                raise
    raise RuntimeError("ทุก API key หมดโควต้า")

# โหลดเฉพาะ pair_15 จาก gold dataset
with open("tests/gold_dataset_final.json", encoding="utf-8") as f:
    dataset = json.load(f)
item = next(x for x in dataset if x["pair_id"] == "pair_15")

print("=" * 80)
print("  DEBUG PAIR_15 (Senior Software Engineer)")
print("=" * 80)

print("\n=== STEP 1: Resume Extractor ===")
resume_data = call_with_rotation(extract_resume, item["resume_text"])
print(resume_data.model_dump_json(indent=2, ensure_ascii=False))
time.sleep(2)

print("\n=== STEP 2: JD Extractor ===")
jd_data = call_with_rotation(extract_jd, item["jd_text"])
print(jd_data.model_dump_json(indent=2, ensure_ascii=False))
time.sleep(2)

print("\n=== STEP 3: Fit Analyzer (ก่อนเข้า Judge) ===")
fit_result = call_with_rotation(analyze_fit, resume_data, jd_data)
for i, m in enumerate(fit_result.matches):
    print(f"  [{i}] skill={m.skill!r} status={m.status} evidence={m.evidence!r} years={m.years_found}")

print(f"\n  must_have_score={fit_result.must_have_score}")
print(f"  nice_to_have_score={fit_result.nice_to_have_score}")
print(f"  fit_score={fit_result.fit_score}")
time.sleep(2)

print("\n=== STEP 4: Judge Agent (หลังตรวจ evidence) ===")
verified = call_with_rotation(judge_matches, fit_result.matches, item["resume_text"])
for i, m in enumerate(verified):
    print(f"  [{i}] skill={m.skill!r} status={m.status} evidence={m.evidence!r}")

print("\n=== STEP 5: Before/After Judge ===")
changed_count = 0
for before, after in zip(fit_result.matches, verified):
    changed = "⬅ CHANGED" if before.status != after.status else ""
    if before.status != after.status:
        changed_count += 1
    print(f"  {before.skill!r}: {before.status} → {after.status} {changed}")
    if before.status != after.status:
        print(f"     evidence ที่ถูก reject: {before.evidence!r}")
print(f"\n  สรุป: Judge เปลี่ยน {changed_count} / {len(fit_result.matches)} ตัว")

print("\n=== JD Requirements priority ===")
for i, req in enumerate(jd_data.requirements):
    print(f"  [{i}] skill={req.skill!r} priority={req.priority} min_years={req.min_years}")

print("\n=== Gold ที่ควรจะเป็น ===")
for gm in item["gold_matches"]:
    print(f"  {gm['skill']}: ควรเป็น {gm['status']}")

print("\n=== Gold Scores ===")
print(f"  gold_must_have_score={item['gold_must_have_score']}")
print(f"  gold_nice_to_have_score={item['gold_nice_to_have_score']}")
print(f"  gold_fit_score={item['gold_fit_score']}")
