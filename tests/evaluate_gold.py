import os
import json
import sys
import time
import argparse
import hashlib
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure we can import agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.skill_normalizer import normalize_skill_name
from agents.resume_extractor import extract_resume, SYSTEM_PROMPT as RESUME_PROMPT
from agents.jd_extractor import extract_jd, SYSTEM_PROMPT as JD_PROMPT
from agents.fit_analyzer import analyze_fit, analyze_fit_and_gaps, SYSTEM_PROMPT as FIT_PROMPT
from agents.gap_agent import analyze_gaps
from agents.judge_agent import judge_matches, SYSTEM_PROMPT as JUDGE_PROMPT
from schemas import SkillMatch, SkillRequirement, ResumeData, JDData


def _get_prompt_hash() -> str:
    """คำนวณ SHA-256 hash ของ SYSTEM_PROMPT จากทุก agent ที่เกี่ยวข้องกับ extraction cache
    (resume_extractor + jd_extractor) — ถ้า hash เปลี่ยน แปลว่า prompt เปลี่ยน cache ต้อง invalidate
    รวม fit_analyzer และ judge_agent ไว้ด้วยเพื่อ future-proof
    """
    combined = (RESUME_PROMPT + JD_PROMPT + FIT_PROMPT + JUDGE_PROMPT).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()[:16]  # 16 chars เพียงพอสำหรับ cache key

load_dotenv()

# Candidate API key environment variables in .env (up to 6 keys)
CANDIDATE_KEY_ENVS = [
    "GOOGLE_API_KEY",
    "GOOGLE_API_KEY_FRIEND1",
    "GOOGLE_API_KEY_FRIEND2",
    "GOOGLE_API_KEY_FRIEND3",
    "GOOGLE_API_KEY_FRIEND4",
    "GOOGLE_API_KEY_FRIEND5",
]


class AllKeysExhaustedError(Exception):
    """Raised when all available API keys have hit rate limits/quotas."""
    pass


# Deterministic Python scoring function — index-based
def calculate_scores_python(matches: list[SkillMatch], requirements: list[SkillRequirement]) -> tuple[int, int, int]:
    if len(matches) != len(requirements):
        raise ValueError(
            f"matches ({len(matches)}) กับ requirements ({len(requirements)}) จำนวนไม่เท่ากัน "
            f"— ไม่ควรเกิดขึ้นถ้า pipeline ก่อนหน้าตรวจสอบไปแล้ว"
        )

    must_have_weights: list[float] = []
    nice_to_have_weights: list[float] = []

    for m, req in zip(matches, requirements):
        weight = 1.0 if m.status == "met" else (0.5 if m.status == "partial" else 0.0)
        if req.priority == "must_have":
            must_have_weights.append(weight)
        else:
            nice_to_have_weights.append(weight)

    must = int(sum(must_have_weights) / len(must_have_weights) * 100) if must_have_weights else 0
    nice = int(sum(nice_to_have_weights) / len(nice_to_have_weights) * 100) if nice_to_have_weights else 0

    if must_have_weights and nice_to_have_weights:
        fit = int(0.7 * must + 0.3 * nice)
    elif must_have_weights:
        fit = must
    else:
        fit = nice

    return must, nice, fit


def find_matching_requirement(gold_skill: str, requirements: list[SkillRequirement]) -> SkillRequirement | None:
    from agents.skill_normalizer import _normalizer
    _normalizer._lazy_load()
    emb_gold = _normalizer.model.encode([gold_skill], normalize_embeddings=True)[0]

    best_req = None
    best_sim = -1.0
    for req in requirements:
        emb_req = _normalizer.model.encode([req.skill], normalize_embeddings=True)[0]
        sim = float(emb_gold @ emb_req)
        if sim > best_sim:
            best_sim = sim
            best_req = req
    return best_req if best_sim >= 0.4 else None


def main():
    parser = argparse.ArgumentParser(description="Run evaluation against Gold Dataset with automatic API key rotation")
    parser.add_argument("--api-key-env", type=str, default="GOOGLE_API_KEY", help="Preferred starting environment variable for GOOGLE_API_KEY")
    parser.add_argument("--merged", action="store_true", default=False,
                        help="ใช้ analyze_fit_and_gaps() (merged 1-call) แทน analyze_fit() + analyze_gaps() แยกกัน "
                             "เพื่อทดสอบ MERGED_GAP_AGENT=true — ต้องการตัวเลขเปรียบเทียบก่อนตั้งเป็น default")
    parser.add_argument("--suffix", type=str, default="",
                        help="เพิ่ม suffix ต่อท้ายชื่อไฟล์ progress/results เช่น --suffix=merged → evaluation_progress_merged.json")
    args = parser.parse_args()
    preferred_api_key_env = args.api_key_env
    use_merged_gap_agent: bool = args.merged
    file_suffix = f"_{args.suffix}" if args.suffix else ("_merged" if use_merged_gap_agent else "")

    _tests_dir = os.path.dirname(os.path.abspath(__file__))
    gold_path = os.path.join(_tests_dir, "gold_dataset_final.json")
    progress_path = os.path.join(_tests_dir, f"evaluation_progress{file_suffix}.json")
    results_path = os.path.join(_tests_dir, f"evaluation_results{file_suffix}.json")
    extraction_cache_path = os.path.join(_tests_dir, "extraction_cache.json")
    rotation_state_path = os.path.join(_tests_dir, "key_rotation_state.json")

    if not os.path.exists(gold_path):
        print(f"❌ ไม่พบไฟล์ gold dataset ใน: {gold_path}")
        return

    with open(gold_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    # 1. Scan .env for non-empty API keys (skip missing ones without throwing errors)
    valid_key_envs = [env for env in CANDIDATE_KEY_ENVS if os.getenv(env) and os.getenv(env).strip()]

    # If preferred key is specified and valid, put it first in the list
    if preferred_api_key_env in valid_key_envs:
        valid_key_envs.remove(preferred_api_key_env)
        valid_key_envs.insert(0, preferred_api_key_env)

    gap_mode_label = "MERGED (1 LLM call, MERGED_GAP_AGENT=true)" if use_merged_gap_agent else "SEPARATE (2 LLM calls, MERGED_GAP_AGENT=false)"
    print(f"=== เริ่มการประเมินผลตัวอย่างจำนวน {len(dataset)} รายการ ===")
    print(f"Gap Agent Mode: {gap_mode_label}")
    print("โมเดลหลักที่ใช้: gemini-flash-latest (โมเดลเต็ม)")
    print(f"🔑 พบ API key ที่ใช้งานได้ {len(valid_key_envs)} ตัว: {', '.join(valid_key_envs)}")

    print("ระบบจะเพิ่มความหน่วงเวลา 2 วินาทีระหว่าง API call\n")

    if not valid_key_envs:
        print("❌ ไม่พบ API Key ที่ใช้งานได้ใน .env เลย — กรุณาใส่ GOOGLE_API_KEY ก่อน")
        return

    model_name = "gemini-flash-latest"
    results = []
    failed_pairs = []

    # 2. Key Rotation State Management
    exhausted_keys = set()
    if os.path.exists(rotation_state_path):
        try:
            with open(rotation_state_path, 'r', encoding='utf-8') as rf:
                rot_data = json.load(rf)
                exhausted_keys = set(rot_data.get("exhausted_keys", []))
            if exhausted_keys:
                print(f"🔄 โหลด key rotation state: key ที่เคยหมดโควต้า = {list(exhausted_keys)}")
        except Exception as re_err:
            print(f"⚠️ อ่าน key_rotation_state.json ไม่สำเร็จ ({re_err})")

    def save_rotation_state():
        with open(rotation_state_path, 'w', encoding='utf-8') as rf:
            json.dump({"exhausted_keys": list(exhausted_keys)}, rf, indent=2, ensure_ascii=False)

    # Find initial non-exhausted key
    active_key_index = 0
    while active_key_index < len(valid_key_envs) and valid_key_envs[active_key_index] in exhausted_keys:
        active_key_index += 1

    if active_key_index >= len(valid_key_envs):
        print("⚠️ ทุก API key ที่ใช้งานได้สะสมชนโควต้าครบทั้งหมดแล้ว!")
        print("กรุณารอโควต้ารีเซ็ตหรือลบ key_rotation_state.json เพื่อเริ่มนับใหม่")
        return

    current_api_key_env = valid_key_envs[active_key_index]
    print(f"▶️ เริ่มต้นด้วย API Key: {current_api_key_env}\n")

    # Helper for agent calls with automatic key rotation on 429 and 503
    def call_agent_with_rotation(agent_fn, *args, **kwargs):
        nonlocal active_key_index, current_api_key_env

        max_attempts = 18
        attempt_503 = 0
        for attempt in range(max_attempts):
            try:
                kwargs["api_key_env_var"] = current_api_key_env
                return agent_fn(*args, **kwargs)
            except Exception as e:
                err_str = str(e).lower()

                # ตรวจ 503/unavailable/timeout ก่อน — transient error
                # หมุนเวียนลอง key ถัดไปที่ยังไม่ exhausted และเพิ่ม backoff 30-60s สำหรับ 503 โดยเฉพาะ
                if any(k in err_str for k in ("503", "unavailable", "high demand", "overloaded", "timeout", "timed out")):
                    attempt_503 += 1
                    wait_time = min(30 + (attempt_503 - 1) * 15, 60)
                    print(f"  ⚠️ Server transient 503/unavailable บน [{current_api_key_env}] (attempt {attempt+1}/{max_attempts}, 503 retry {attempt_503}). รอ backoff {wait_time}s และสลับ key...", flush=True)
                    time.sleep(wait_time)

                    # สลับ key ไปยัง key ถัดไปในรายการที่ยังไม่ exhausted
                    available_keys = [k for k in valid_key_envs if k not in exhausted_keys]
                    if available_keys:
                        if current_api_key_env in available_keys:
                            curr_idx = available_keys.index(current_api_key_env)
                            current_api_key_env = available_keys[(curr_idx + 1) % len(available_keys)]
                        else:
                            current_api_key_env = available_keys[0]
                        print(f"  🔄 สลับ key ไปที่: [{current_api_key_env}]", flush=True)

                # 429/quota exhausted — เฉพาะ key นี้หมดโควต้า ต้องบันทึกว่า exhausted
                elif any(k in err_str for k in ("429", "resource_exhausted", "quota")):
                    print(f"  ⚠️ Key [{current_api_key_env}] ชนโควต้า 429 RESOURCE_EXHAUSTED", flush=True)
                    exhausted_keys.add(current_api_key_env)
                    save_rotation_state()

                    # Find next non-exhausted key
                    active_key_index += 1
                    while active_key_index < len(valid_key_envs) and valid_key_envs[active_key_index] in exhausted_keys:
                        active_key_index += 1

                    if active_key_index < len(valid_key_envs):
                        current_api_key_env = valid_key_envs[active_key_index]
                        print(f"  🔄 สลับไปใช้ API Key ถัดไป: [{current_api_key_env}] และลองทำใหม่...", flush=True)
                        time.sleep(2)
                        continue
                    else:
                        raise AllKeysExhaustedError("ทุก API key ที่ใช้งานได้ชนโควต้า 429 หมดแล้ว")
                else:
                    raise e
        raise RuntimeError("Failed to complete agent call after maximum retries due to rate limits or timeouts.")

    # Metrics counters
    unsupported_claims_count = 0
    total_claims_count = 0

    must_have_correct = 0
    must_have_total = 0

    nice_to_have_correct = 0
    nice_to_have_total = 0

    # Load extraction cache if exists — พร้อม prompt-hash validation
    extraction_cache = {}
    current_prompt_hash = _get_prompt_hash()
    if os.path.exists(extraction_cache_path):
        try:
            with open(extraction_cache_path, 'r', encoding='utf-8') as ef:
                raw_cache = json.load(ef)
            cached_hash = raw_cache.get("__prompt_hash__", None)
            if cached_hash == current_prompt_hash:
                # hash ตรง — ใช้ cache ได้ปกติ
                extraction_cache = {k: v for k, v in raw_cache.items() if not k.startswith("__")}
                print(f"📦 โหลด extraction cache ได้สำเร็จ ({len(extraction_cache)} pairs) [prompt hash: {current_prompt_hash}]", flush=True)
            else:
                # hash ไม่ตรง — prompt เปลี่ยนไปแล้ว cache เก่าใช้ไม่ได้
                print(f"⚠️ Prompt hash เปลี่ยน (เก่า: {cached_hash} → ใหม่: {current_prompt_hash})", flush=True)
                print(f"   Cache เก่าถูก invalidate อัตโนมัติ — จะรัน Resume/JD Extractor ใหม่ทั้งหมด", flush=True)
                extraction_cache = {}  # ทิ้ง cache เก่าทั้งหมด
        except Exception as ee:
            print(f"⚠️ อ่านไฟล์ extraction_cache.json ไม่สำเร็จ ({ee})", flush=True)

    def save_extraction_cache():
        # บันทึก hash ไว้ใน cache เสมอ เพื่อ validate ในรอบถัดไป
        data_to_save = {"__prompt_hash__": current_prompt_hash, **extraction_cache}
        with open(extraction_cache_path, 'w', encoding='utf-8') as ef:
            json.dump(data_to_save, ef, indent=2, ensure_ascii=False)

    # Load progress if exists — แต่ต้อง invalidate ถ้า prompt hash เปลี่ยน
    # (progress เก่าใช้ Fit/Judge prompt เก่า ผลลัพธ์ไม่ถูกต้องกับ prompt ใหม่)
    if os.path.exists(progress_path):
        try:
            with open(progress_path, 'r', encoding='utf-8') as pf:
                progress_data = json.load(pf)
            cached_progress_hash = progress_data.get("__prompt_hash__", None)
            if cached_progress_hash != current_prompt_hash:
                # prompt เปลี่ยน → ผล Fit/Judge เก่าใช้ไม่ได้ ต้องรันใหม่ทั้งหมด
                print(f"⚠️ evaluation_progress.json ถูก invalidate (prompt hash เปลี่ยน: {cached_progress_hash} → {current_prompt_hash})", flush=True)
                print(f"   จะรัน Fit + Judge ใหม่ทั้งหมด (Extractor ใช้ cache ได้ถ้า hash ตรง)", flush=True)
                # results / counters ยังคงเป็นค่า default (ว่างเปล่า) จากข้างบน
            else:
                results = progress_data.get("results", [])
                failed_pairs = progress_data.get("failed_pairs", [])
                must_have_correct = progress_data.get("must_have_correct", 0)
                must_have_total = progress_data.get("must_have_total", 0)
                nice_to_have_correct = progress_data.get("nice_to_have_correct", 0)
                nice_to_have_total = progress_data.get("nice_to_have_total", 0)
                unsupported_claims_count = progress_data.get("unsupported_claims_count", 0)
                total_claims_count = progress_data.get("total_claims_count", 0)
                print(f"📂 พบไฟล์ evaluation_progress.json — โหลดผลลัพธ์เดิมที่สำเร็จแล้ว {len(results)}/{len(dataset)} รายการ", flush=True)
        except Exception as pe:
            print(f"⚠️ อ่านไฟล์ evaluation_progress.json ไม่สำเร็จ ({pe}) — เริ่มรันใหม่ทั้งหมด", flush=True)

    completed_pair_ids = {r["pair_id"] for r in results}

    def save_progress():
        prog_data = {
            "__prompt_hash__": current_prompt_hash,  # บันทึก hash เพื่อ validate ในรอบถัดไป
            "results": results,
            "failed_pairs": failed_pairs,
            "must_have_correct": must_have_correct,
            "must_have_total": must_have_total,
            "nice_to_have_correct": nice_to_have_correct,
            "nice_to_have_total": nice_to_have_total,
            "unsupported_claims_count": unsupported_claims_count,
            "total_claims_count": total_claims_count,
        }
        with open(progress_path, 'w', encoding='utf-8') as pf:
            json.dump(prog_data, pf, indent=2, ensure_ascii=False)

    for item in dataset:
        pair_id = item["pair_id"]
        role = item["target_role"]

        if pair_id in completed_pair_ids:
            print(f"⏭️ {pair_id} ({role}) โหลดจาก progress cache เรียบร้อย (ข้าม LLM call)", flush=True)
            continue

        print(f"กำลังรัน: {pair_id} ({role})...", flush=True)
        pair_cache = extraction_cache.get(pair_id, {})
        
        try:
            # 1. Resume Extractor (cache vs LLM)
            if "resume_data" in pair_cache:
                resume_data = ResumeData.model_validate(pair_cache["resume_data"])
                print(f"  [1/5] Resume Extractor loaded from cache", flush=True)
            else:
                resume_data = call_agent_with_rotation(extract_resume, item["resume_text"], model=model_name)
                pair_cache["resume_data"] = resume_data.model_dump()
                extraction_cache[pair_id] = pair_cache
                save_extraction_cache()
                print(f"  [1/5] Resume Extractor done (cached)", flush=True)
                time.sleep(2)
            
            # 2. JD Extractor (cache vs LLM)
            if "jd_data" in pair_cache:
                jd_data = JDData.model_validate(pair_cache["jd_data"])
                print(f"  [2/5] JD Extractor loaded from cache ({len(jd_data.requirements)} reqs)", flush=True)
            else:
                jd_data = call_agent_with_rotation(extract_jd, item["jd_text"], model=model_name)
                pair_cache["jd_data"] = jd_data.model_dump()
                extraction_cache[pair_id] = pair_cache
                save_extraction_cache()
                print(f"  [2/5] JD Extractor done ({len(jd_data.requirements)} reqs, cached)", flush=True)
                time.sleep(2)
            
            # 3+4. Fit Analyzer (+ Gap Agent — merged or separate)
            if use_merged_gap_agent:
                # MERGED MODE: 1 LLM call แทน 2 — ทดสอบว่า quality ลดลงไหม
                fit_result, gap_result = call_agent_with_rotation(analyze_fit_and_gaps, resume_data, jd_data, model=model_name)
                print(f"  [3+4/5] Fit+Gap (merged) done", flush=True)
                time.sleep(2)
            else:
                # SEPARATE MODE: แบบเดิม 2 calls แยกกัน (baseline)
                fit_result = call_agent_with_rotation(analyze_fit, resume_data, jd_data, model=model_name)
                print(f"  [3/5] Fit Analyzer done", flush=True)
                time.sleep(2)

                gap_result = call_agent_with_rotation(analyze_gaps, fit_result.matches, model=model_name)
                print(f"  [4/5] Gap Agent done", flush=True)
                time.sleep(2)

            # 5. Judge Agent (Verify matches)
            verified_matches = call_agent_with_rotation(judge_matches, fit_result.matches, item["resume_text"], model=model_name)
            print(f"  [5/5] Judge Agent done", flush=True)
            time.sleep(2)
            
            # 6. Calculate verified Python score
            py_must, py_nice, py_fit = calculate_scores_python(verified_matches, jd_data.requirements)

            # Evaluate match accuracy & unsupported claims
            for gold_m in item["gold_matches"]:
                gold_skill_raw = gold_m["skill"]
                gold_status = gold_m["status"]

                norm_gold = normalize_skill_name(gold_skill_raw)
                gold_skill = norm_gold["normalized"] if norm_gold["matched"] else gold_skill_raw

                matched_req = find_matching_requirement(gold_skill, jd_data.requirements)
                priority = matched_req.priority if matched_req else "must_have"
                
                from agents.skill_normalizer import _normalizer
                _normalizer._lazy_load()
                emb_gold = _normalizer.model.encode([gold_skill], normalize_embeddings=True)[0]

                pred_match = None
                best_pred_sim = -1.0
                for pm in verified_matches:
                    emb_pm = _normalizer.model.encode([pm.skill], normalize_embeddings=True)[0]
                    sim = float(emb_gold @ emb_pm)
                    if sim >= 0.60 and sim > best_pred_sim:
                        best_pred_sim = sim
                        pred_match = pm

                pred_status = pred_match.status if pred_match else "missing"
                
                is_correct = (pred_status == gold_status)
                if priority == "must_have":
                    must_have_total += 1
                    if is_correct:
                        must_have_correct += 1
                else:
                    nice_to_have_total += 1
                    if is_correct:
                        nice_to_have_correct += 1

            for idx, (orig_m, verified_m) in enumerate(zip(fit_result.matches, verified_matches)):
                if orig_m.status in ("met", "partial"):
                    total_claims_count += 1
                    if verified_m.status == "missing":
                        unsupported_claims_count += 1

            results.append({
                "pair_id": pair_id,
                "gold_must": item["gold_must_have_score"],
                "gold_nice": item["gold_nice_to_have_score"],
                "gold_fit": item["gold_fit_score"],
                "pred_llm_must": fit_result.must_have_score,
                "pred_llm_nice": fit_result.nice_to_have_score,
                "pred_llm_fit": fit_result.fit_score,
                "pred_py_must": py_must,
                "pred_py_nice": py_nice,
                "pred_py_fit": py_fit,
            })
            completed_pair_ids.add(pair_id)
            save_progress()
            print(f"✅ {pair_id} เสร็จเรียบร้อย (Must={py_must}, Nice={py_nice}, Fit={py_fit}) [บันทึก progress แล้ว]", flush=True)
        except AllKeysExhaustedError as e:
            print(f"\n🛑 หยุดการทำงานชั่วคราวเนื่องจาก API Keys ทั้งหมด ({len(valid_key_envs)} ตัว) หมดโควต้าที่ {pair_id}: {e}", flush=True)
            print(f"   รันสำเร็จแล้ว {len(results)}/{len(dataset)} คู่ (เก็บไว้ใน evaluation_progress.json แล้ว)", flush=True)
            print(f"   รันคำสั่งเดิมซ้ำได้เมื่อ quota รีเซ็ต จะรันต่อจากคู่ที่ {len(results)+1} อัตโนมัติ", flush=True)
            save_progress()
            return
        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)}"
            print(f"❌ {pair_id} เกิดข้อผิดพลาด: {err_msg} — ข้ามคู่นี้ในการคำนวณ", flush=True)
            failed_pairs.append({"pair_id": pair_id, "error": err_msg})
            save_progress()
            time.sleep(5)

    # Calculate overall metrics
    must_have_acc = (must_have_correct / must_have_total * 100) if must_have_total > 0 else 0
    nice_to_have_acc = (nice_to_have_correct / nice_to_have_total * 100) if nice_to_have_total > 0 else 0
    unsupported_rate = (unsupported_claims_count / total_claims_count * 100) if total_claims_count > 0 else 0

    mae_llm_fit = sum(abs(r["gold_fit"] - r["pred_llm_fit"]) for r in results) / len(results) if results else 0
    mae_py_fit = sum(abs(r["gold_fit"] - r["pred_py_fit"]) for r in results) / len(results) if results else 0
    mae_py_must = sum(abs(r["gold_must"] - r["pred_py_must"]) for r in results) / len(results) if results else 0
    mae_py_nice = sum(abs(r["gold_nice"] - r["pred_py_nice"]) for r in results) / len(results) if results else 0

    # Print Report Table
    print("\n" + "="*95)
    print(f"{'Pair ID':<10} | {'Must-Have Score':<25} | {'Nice-To-Have Score':<25} | {'Fit Score':<25}")
    print(f"{'':<10} | {'Gold / LLM / Py':<25} | {'Gold / LLM / Py':<25} | {'Gold / LLM / Py':<25}")
    print("="*95)
    for r in results:
        must_str = f"{r['gold_must']} / {r['pred_llm_must']} / {r['pred_py_must']}"
        nice_str = f"{r['gold_nice']} / {r['pred_llm_nice']} / {r['pred_py_nice']}"
        fit_str = f"{r['gold_fit']} / {r['pred_llm_fit']} / {r['pred_py_fit']}"
        print(f"{r['pair_id']:<10} | {must_str:<25} | {nice_str:<25} | {fit_str:<25}")
    print("="*95)

    if failed_pairs:
        print(f"\n⚠️ มี {len(failed_pairs)} คู่ที่ไม่สามารถประมวลผลได้สำเร็จ:")
        for fp in failed_pairs:
            print(f"   - {fp['pair_id']}: {fp['error']}")

    print("\n📊 === รายงานผลลัพธ์การประเมิน (Evaluation Metrics Report) ===")
    print(f"ประมวลผลสำเร็จ: {len(results)} / {len(dataset)} รายการ")
    print(f"1. Must-Have Match Accuracy: {must_have_acc:.2f}% (เป้าหมาย: >= 80%)")
    print(f"2. Nice-To-Have Match Accuracy: {nice_to_have_acc:.2f}%")
    print(f"3. Unsupported Match Claims Rate: {unsupported_rate:.2f}% (เป้าหมาย: <= 10%)")
    print(f"4. Score MAE (Fit Score - LLM Calculated): {mae_llm_fit:.2f}")
    print(f"5. Score MAE (Fit Score - Python Calculated): {mae_py_fit:.2f}")
    print(f"6. Score MAE (Must-Have Score - Python): {mae_py_must:.2f}")
    print(f"7. Score MAE (Nice-To-Have Score - Python): {mae_py_nice:.2f}")
    print("==============================================================")

    # Save to JSON
    report_data = {
        "n_pairs_completed": f"{len(results)} / {len(dataset)}",
        "failed_pairs": failed_pairs,
        "metrics": {
            "must_have_match_accuracy_pct": must_have_acc,
            "nice_to_have_match_accuracy_pct": nice_to_have_acc,
            "unsupported_match_claims_rate_pct": unsupported_rate,
            "mae_llm_fit": mae_llm_fit,
            "mae_py_fit": mae_py_fit,
            "mae_py_must": mae_py_must,
            "mae_py_nice": mae_py_nice,
        },
        "details": results
    }
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"Saved evaluation report to: {results_path}")

    # Keep progress updated as backup
    save_progress()

if __name__ == "__main__":
    main()
