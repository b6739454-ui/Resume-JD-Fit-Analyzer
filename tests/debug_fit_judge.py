"""
tests/debug_fit_judge.py

Debug Fit Analyzer + Judge Agent สำหรับ pair ใดๆ
โดยโหลด resume_data + jd_data จาก extraction_cache (ไม่เรียก Extractor ซ้ำ)
และ print:
  - evidence เต็มจาก Fit Analyzer ทุก skill
  - reason เต็มจาก Judge Agent ทุก skill
  - quote ตรงๆ จาก resume_text เพื่อ cross-check

Usage:
  py tests/debug_fit_judge.py pair_07
  py tests/debug_fit_judge.py pair_09
  py tests/debug_fit_judge.py pair_10
"""
import json, os, sys, time, re
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

import instructor
from google import genai
from pydantic import BaseModel, Field
import httpx

from agents.fit_analyzer import analyze_fit
from schemas import ResumeData, JDData, SkillMatch

# ─── Config ───────────────────────────────────────────────
MODEL = "gemini-flash-latest"
CANDIDATE_KEY_ENVS = [
    "GOOGLE_API_KEY", "GOOGLE_API_KEY_FRIEND1", "GOOGLE_API_KEY_FRIEND2",
    "GOOGLE_API_KEY_FRIEND3", "GOOGLE_API_KEY_FRIEND4", "GOOGLE_API_KEY_FRIEND5",
]
valid_keys = [k for k in CANDIDATE_KEY_ENVS if os.getenv(k) and os.getenv(k).strip()]
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

# ─── Judge raw (เพื่อ expose reason field) ─────────────────
from agents.judge_agent import SYSTEM_PROMPT as JUDGE_PROMPT, _call_llm_with_retry

class VerifiedMatchWithReason(BaseModel):
    skill_index: int
    skill: str
    evidence_is_valid: bool
    reason: str = Field(default="(ไม่มี reason)")

class JudgeResultWithReason(BaseModel):
    verified_matches: list[VerifiedMatchWithReason]

def judge_with_reason(matches: list[SkillMatch], resume_text: str,
                      api_key_env_var: str = "GOOGLE_API_KEY") -> list[VerifiedMatchWithReason]:
    """เรียก Judge แบบ raw เพื่อ expose reason field"""
    httpx_client = httpx.Client(http2=False, timeout=60.0)
    genai_client = genai.Client(
        api_key=os.getenv(api_key_env_var),
        http_options={"httpx_client": httpx_client}
    )
    client = instructor.from_genai(genai_client, mode=instructor.Mode.GENAI_TOOLS)

    indexed = [{"index": i, "skill": m.skill, "status": m.status, "evidence": m.evidence}
               for i, m in enumerate(matches)]
    user_content = f"""ข้อความ Resume ต้นฉบับ:
{resume_text}

รายการ Skill Match ที่ต้องตรวจสอบ (แต่ละรายการมี [index] กำกับ — ต้องตอบกลับครบทุกรายการด้วย skill_index ตัวนั้น):
{indexed}

กรุณาตรวจสอบทีละรายการ และให้ผลลัพธ์ตาม schema ที่กำหนด (ครบ {len(matches)} รายการ)
"""
    result = _call_llm_with_retry(
        client=client,
        model=MODEL,
        response_model=JudgeResultWithReason,
        messages=[{"role": "system", "content": JUDGE_PROMPT},
                  {"role": "user", "content": user_content}],
    )
    return result.verified_matches

# ─── Main ─────────────────────────────────────────────────
pair_id = sys.argv[1] if len(sys.argv) > 1 else "pair_07"

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "gold_dataset_final.json"), encoding="utf-8") as f:
    gold = {x["pair_id"]: x for x in json.load(f)}
with open(os.path.join(BASE, "extraction_cache.json"), encoding="utf-8") as f:
    raw = json.load(f)
    cache = {k: v for k, v in raw.items() if not k.startswith("__")}

item = gold[pair_id]
pair_cache = cache.get(pair_id, {})
if "resume_data" not in pair_cache or "jd_data" not in pair_cache:
    print(f"❌ ไม่พบ {pair_id} ใน extraction_cache.json"); sys.exit(1)

resume_data = ResumeData.model_validate(pair_cache["resume_data"])
jd_data     = JDData.model_validate(pair_cache["jd_data"])
resume_text = item["resume_text"]

print(f"[Model: {MODEL}] keys: {len(valid_keys)} ตัว")
print(f"✅ โหลด extraction cache สำเร็จ (ไม่เรียก Extractor API)\n")

print("=" * 90)
print(f"  DEBUG {pair_id} — {item.get('target_role','')} (Fit + Judge only)")
print("=" * 90)

# ─── JD Requirements ──────────────────────────────────────
print("\n=== JD Requirements (จาก cache) ===")
for i, r in enumerate(jd_data.requirements):
    print(f"  [{i}] {r.priority:<12} | {r.skill}")

# ─── Fit Analyzer ─────────────────────────────────────────
print("\n=== Fit Analyzer ===")
fit_result = call_with_rotation(analyze_fit, resume_data, jd_data)
print(f"  LLM Score: Must={fit_result.must_have_score}, Nice={fit_result.nice_to_have_score}, Fit={fit_result.fit_score}")
for i, m in enumerate(fit_result.matches):
    ev_display = repr(m.evidence) if m.evidence else "None"
    print(f"\n  [{i}] skill={m.skill!r}")
    print(f"       status={m.status}  years={m.years_found}")
    print(f"       evidence={ev_display}")
time.sleep(2)

# ─── Judge Agent (raw with reason) ─────────────────────────
print("\n=== Judge Agent (with reason) ===")
for _ in range(len(valid_keys)):
    try:
        key = valid_keys[key_idx[0]]
        verdicts = judge_with_reason(fit_result.matches, resume_text, api_key_env_var=key)
        break
    except Exception as e:
        if any(k in str(e).lower() for k in ("429", "quota", "exhausted")):
            print(f"  ⚠️ Key [{key}] 429 → ลอง key ถัดไป", flush=True)
            key_idx[0] = (key_idx[0] + 1) % len(valid_keys)
            time.sleep(2)
        else:
            raise

verdict_map = {v.skill_index: v for v in verdicts}
print(f"\n{'─'*90}")
print(f"  {'idx':<4} {'skill':<35} {'valid':<6} {'before→after':<18}")
print(f"{'─'*90}")
for i, m in enumerate(fit_result.matches):
    v = verdict_map.get(i)
    after = m.status if (v and v.evidence_is_valid) else "missing"
    valid_str = "✅ YES" if (v and v.evidence_is_valid) else "❌ NO "
    changed = " ⬅ CHANGED" if after != m.status else ""
    print(f"  [{i}]  {m.skill:<35} {valid_str}  {m.status}→{after}{changed}")

print(f"\n{'─'*90}")
print("  JUDGE REASONS (ละเอียด):")
print(f"{'─'*90}")
for i, m in enumerate(fit_result.matches):
    v = verdict_map.get(i)
    if not v:
        continue
    valid_str = "✅ VALID  " if v.evidence_is_valid else "❌ INVALID"
    print(f"\n  [{i}] {m.skill}")
    print(f"       Verdict: {valid_str}")
    print(f"       Evidence: {m.evidence!r}")
    print(f"       Reason  : {v.reason}")

# ─── Resume Quote Finder ───────────────────────────────────
print(f"\n{'─'*90}")
print("  RESUME KEYWORD SEARCH (ค้นหาคำสำคัญจาก skill ที่น่าสงสัย):")
print(f"{'─'*90}")
suspicious = [m for i, m in enumerate(fit_result.matches)
              if not verdict_map.get(i, type('',(),{'evidence_is_valid':True})()).evidence_is_valid
              or m.status in ("partial","missing")]

for m in suspicious:
    keywords = re.sub(r'\b(and|or|with|of|in|for|the|a)\b', ' ', m.skill, flags=re.I).split()
    keywords = [w.strip() for w in keywords if len(w.strip()) >= 4]
    print(f"\n  Skill: {m.skill!r} (status={m.status})")
    for kw in keywords[:4]:
        hits = [line.strip() for line in resume_text.splitlines()
                if kw.lower() in line.lower() and line.strip()]
        if hits:
            print(f"    keyword '{kw}' → พบใน resume:")
            for h in hits[:3]:
                print(f"      ▸ {h[:120]}")
        else:
            print(f"    keyword '{kw}' → ไม่พบในเรซูเม่เลย")

print(f"\n{'─'*90}")
print("  GOLD MATCHES ที่ควรจะเป็น:")
for gm in item.get("gold_matches", []):
    print(f"  [{gm['status']:<7}] {gm['skill']}")
print(f"\n  Gold Score: Must={item['gold_must_have_score']}, Nice={item['gold_nice_to_have_score']}, Fit={item['gold_fit_score']}")
