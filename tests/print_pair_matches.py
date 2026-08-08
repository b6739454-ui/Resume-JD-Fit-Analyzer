"""
tests/print_pair_matches.py

Print matches before & after Judge for pair_09, pair_10, pair_11, pair_06
"""

import json
import os
import sys
import time

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agents.resume_extractor import ResumeData
from agents.jd_extractor import JDData
from agents.fit_analyzer import analyze_fit
from agents.judge_agent import judge_matches

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

GOLD_PATH = "tests/gold_dataset_final.json"
CACHE_PATH = "tests/extraction_cache.json"

with open(GOLD_PATH, encoding="utf-8") as f:
    gold_data = {x["pair_id"]: x for x in json.load(f)}

with open(CACHE_PATH, encoding="utf-8") as f:
    raw_cache = json.load(f)
    cache_data = {k: v for k, v in raw_cache.items() if not k.startswith("__")}

DIVIDER = "=" * 90


def inspect_pair(pid: str):
    item = gold_data[pid]
    c = cache_data[pid]
    
    resume_data = ResumeData.model_validate(c["resume_data"])
    jd_data = JDData.model_validate(c["jd_data"])
    resume_text = item["resume_text"]
    
    print(f"\n{DIVIDER}")
    print(f"  INSPECT MATCHES FOR {pid} ({item.get('target_role', '')})")
    print(DIVIDER)
    
    fit_res = call_with_rotation(analyze_fit, resume_data, jd_data, model=MODEL)
    verified_matches = call_with_rotation(judge_matches, fit_res.matches, resume_text, model=MODEL)
    
    print(f"\n  Fit Analyzer Score (ก่อน Judge): Must={fit_res.must_have_score} Nice={fit_res.nice_to_have_score} Fit={fit_res.fit_score}")
    
    from evaluate_gold import calculate_scores_python
    py_must, py_nice, py_fit = calculate_scores_python(verified_matches, jd_data.requirements)
    print(f"  Python Score (หลัง Judge):       Must={py_must} Nice={py_nice} Fit={py_fit}")
    print(f"  Gold Score:                      Must={item['gold_must_have_score']} Nice={item['gold_nice_to_have_score']} Fit={item['gold_fit_score']}")

    print(f"\n--- รายละเอียดการจับคู่ทีละ Requirement ---")
    for i, (req, m_before, m_after) in enumerate(zip(jd_data.requirements, fit_res.matches, verified_matches)):
        in_resume = bool(m_before.evidence and m_before.evidence.strip() in resume_text)
        print(f"\n  [{i}] Requirement: {req.skill!r} ({req.priority})")
        print(f"      - Fit Analyzer: status={m_before.status!r}")
        print(f"        evidence={m_before.evidence!r}")
        print(f"        is exact substring in resume_text: {in_resume}")
        print(f"      - Judge Verified: status={m_after.status!r}")
        if m_before.status != m_after.status:
            print(f"      ⚠️ Judge Changed Status from {m_before.status!r} -> {m_after.status!r}")

if __name__ == "__main__":
    for pid in ["pair_09", "pair_10", "pair_11", "pair_06"]:
        inspect_pair(pid)
