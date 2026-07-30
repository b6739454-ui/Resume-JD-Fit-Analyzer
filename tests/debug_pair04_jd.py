"""
tests/debug_pair04_jd.py

Debug JD Extractor ของ pair_04 หลังแก้ prompt (1-bullet = 1-requirement)
- ใช้ resume_data จาก extraction_cache.json (ไม่เรียก API ซ้ำ)
- เรียก JD Extractor ใหม่ด้วย prompt ที่แก้แล้ว
- เทียบ requirements ที่ได้ กับ bullet ต้นฉบับ
"""
import json, os, sys, time
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from agents.jd_extractor import extract_jd
from agents.fit_analyzer import analyze_fit
from agents.judge_agent import judge_matches
from schemas import ResumeData, JDData

MODEL = "gemini-flash-latest"
CANDIDATE_KEY_ENVS = [
    "GOOGLE_API_KEY", "GOOGLE_API_KEY_FRIEND1", "GOOGLE_API_KEY_FRIEND2",
    "GOOGLE_API_KEY_FRIEND3", "GOOGLE_API_KEY_FRIEND4", "GOOGLE_API_KEY_FRIEND5",
]
valid_keys = [k for k in CANDIDATE_KEY_ENVS if os.getenv(k) and os.getenv(k).strip()]
print(f"[Model: {MODEL}] keys: {len(valid_keys)} ตัว\n")
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
                print(f"  ⚠️ Key [{key}] 429 → ลอง key ถัดไป", flush=True)
                key_idx[0] = (key_idx[0] + 1) % len(valid_keys)
                time.sleep(2)
            else:
                raise
    raise RuntimeError("ทุก key หมดโควต้า")

# โหลดข้อมูล
CACHE_PATH = "tests/extraction_cache.json"
GOLD_PATH  = "tests/gold_dataset_final.json"

with open(GOLD_PATH, encoding="utf-8") as f:
    dataset = json.load(f)
item = next(x for x in dataset if x["pair_id"] == "pair_04")

with open(CACHE_PATH, encoding="utf-8") as f:
    raw = json.load(f)
    cache = {k: v for k, v in raw.items() if not k.startswith("__")}

pair_cache = cache.get("pair_04", {})

print("=" * 80)
print("  DEBUG PAIR_04 — JD Extractor (หลังแก้ prompt)")
print("=" * 80)

# โหลด resume_data จาก cache
resume_data = ResumeData.model_validate(pair_cache["resume_data"])
print(f"✅ โหลด resume_data จาก cache (ไม่เรียก API)\n")

# แสดง JD bullets ต้นฉบับ
print("=== JD Bullets ต้นฉบับ ===")
import re
for line in item["jd_text"].splitlines():
    if re.match(r"^\s*[-•*]\s+\S", line):
        print(f"  {line.strip()}")

# เรียก JD Extractor ใหม่ (prompt ใหม่)
print("\n=== JD Extractor (prompt ใหม่) ===")
jd_data = call_with_rotation(extract_jd, item["jd_text"])
print(f"  จำนวน requirements: {len(jd_data.requirements)}")
for i, r in enumerate(jd_data.requirements):
    print(f"  [{i}] {r.priority:<12} | {r.skill}")
time.sleep(2)

# นับ bullet จริงเพื่อเปรียบเทียบ
bullet_count = sum(1 for line in item["jd_text"].splitlines() if re.match(r"^\s*[-•*]\s+\S", line))
print(f"\n📊 Bullet count จริง: {bullet_count}")
print(f"📊 Requirements ที่สกัดได้: {len(jd_data.requirements)}")
print(f"📊 Must-Have: {sum(1 for r in jd_data.requirements if r.priority == 'must_have')}")
print(f"📊 Nice-To-Have: {sum(1 for r in jd_data.requirements if r.priority == 'nice_to_have')}")

# รัน Fit + Judge ด้วย jd_data ใหม่
print("\n=== Fit Analyzer (jd_data ใหม่) ===")
fit_result = call_with_rotation(analyze_fit, resume_data, jd_data)
for i, m in enumerate(fit_result.matches):
    print(f"  [{i}] {m.status:<8} | {m.skill} | ev={m.evidence!r:.60s}")
print(f"\n  must_have_score={fit_result.must_have_score}, nice_to_have_score={fit_result.nice_to_have_score}, fit_score={fit_result.fit_score}")
time.sleep(2)

print("\n=== Judge Agent ===")
verified = call_with_rotation(judge_matches, fit_result.matches, item["resume_text"])
changed = sum(1 for b, a in zip(fit_result.matches, verified) if b.status != a.status)
for i, (b, a) in enumerate(zip(fit_result.matches, verified)):
    flag = " ⬅ CHANGED" if b.status != a.status else ""
    print(f"  [{i}] {b.status}→{a.status} | {b.skill}{flag}")
print(f"\n  Judge เปลี่ยน {changed}/{len(verified)} ตัว")

# คำนวณ score ด้วย Python
def py_score(matches, reqs):
    mw, nw = [], []
    for m, r in zip(matches, reqs):
        w = 1.0 if m.status == "met" else (0.5 if m.status == "partial" else 0.0)
        (mw if r.priority == "must_have" else nw).append(w)
    must = int(sum(mw)/len(mw)*100) if mw else 0
    nice = int(sum(nw)/len(nw)*100) if nw else 0
    fit = int(0.7*must + 0.3*nice) if (mw and nw) else (must or nice)
    return must, nice, fit

must, nice, fit = py_score(verified, jd_data.requirements)
print(f"\n📊 Final Python Score: Must={must}, Nice={nice}, Fit={fit}")
print(f"📊 Gold Score:         Must={item['gold_must_have_score']}, Nice={item['gold_nice_to_have_score']}, Fit={item['gold_fit_score']}")

print("\n=== Gold ที่ควรจะเป็น ===")
for gm in item["gold_matches"]:
    print(f"  {gm['skill']}: {gm['status']}")
