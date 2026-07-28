import os
import json
import sys
import time
import argparse
from dotenv import load_dotenv

# Ensure we can import agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.skill_normalizer import normalize_skill_name
from agents.resume_extractor import extract_resume
from agents.jd_extractor import extract_jd
from agents.fit_analyzer import analyze_fit
from agents.gap_agent import analyze_gaps
from agents.judge_agent import judge_matches
from schemas import SkillMatch, SkillRequirement

load_dotenv()

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


# Client-side retry wrapper for agent calls to handle rate limit (429), unavailable (503) & timeout errors
def call_agent_with_retry(agent_fn, *args, **kwargs):
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            return agent_fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if any(k in err_str for k in ("429", "resource_exhausted", "quota")):
                raise e
            elif any(k in err_str for k in ("503", "unavailable", "timeout", "timed out")):
                wait_time = 10 * (attempt + 1)
                print(f"  ⚠️ Server transient error ({err_str[:60]}...). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_attempts})", flush=True)
                time.sleep(wait_time)
            else:
                raise e
    raise RuntimeError("Failed to complete agent call after maximum retries due to rate limits or timeouts.")


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
    parser = argparse.ArgumentParser(description="Run evaluation against Gold Dataset")
    parser.add_argument("--api-key-env", type=str, default="GOOGLE_API_KEY", help="Environment variable name for GOOGLE_API_KEY")
    args = parser.parse_args()
    api_key_env = args.api_key_env

    gold_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gold_dataset_final.json")
    progress_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation_progress.json")

    if not os.path.exists(gold_path):
        print(f"❌ ไม่พบไฟล์ gold dataset ใน: {gold_path}")
        return

    with open(gold_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    print(f"=== เริ่มการประเมินผลตัวอย่างจำนวน {len(dataset)} รายการ ===")
    print("โมเดลหลักที่ใช้: gemini-flash-latest (โมเดลเต็ม)")
    print(f"API Key Environment Variable: {api_key_env}")
    print("ระบบจะเพิ่มความหน่วงเวลา 2 วินาทีระหว่าง API call\n")

    model_name = "gemini-flash-latest"
    results = []
    failed_pairs = []

    # Metrics counters
    unsupported_claims_count = 0
    total_claims_count = 0

    must_have_correct = 0
    must_have_total = 0

    nice_to_have_correct = 0
    nice_to_have_total = 0

    # Load progress if exists
    if os.path.exists(progress_path):
        try:
            with open(progress_path, 'r', encoding='utf-8') as pf:
                progress_data = json.load(pf)
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
        
        try:
            # 1. Resume Extractor
            resume_data = call_agent_with_retry(extract_resume, item["resume_text"], model=model_name, api_key_env_var=api_key_env)
            print(f"  [1/5] Resume Extractor done", flush=True)
            time.sleep(2)
            
            # 2. JD Extractor
            jd_data = call_agent_with_retry(extract_jd, item["jd_text"], model=model_name, api_key_env_var=api_key_env)
            print(f"  [2/5] JD Extractor done ({len(jd_data.requirements)} reqs)", flush=True)
            time.sleep(2)
            
            # 3. Fit Analyzer
            fit_result = call_agent_with_retry(analyze_fit, resume_data, jd_data, model=model_name, api_key_env_var=api_key_env)
            print(f"  [3/5] Fit Analyzer done", flush=True)
            time.sleep(2)
            
            # 4. Gap Agent
            gap_result = call_agent_with_retry(analyze_gaps, fit_result.matches, model=model_name, api_key_env_var=api_key_env)
            print(f"  [4/5] Gap Agent done", flush=True)
            time.sleep(2)
            
            # 5. Judge Agent (Verify matches)
            verified_matches = call_agent_with_retry(judge_matches, fit_result.matches, item["resume_text"], model=model_name, api_key_env_var=api_key_env)
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
        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)}"
            err_str = str(e).lower()
            if any(k in err_str for k in ("429", "resource_exhausted", "quota", "max retries exceeded")):
                print(f"\n🛑 หยุดการทำงานชั่วคราวเนื่องจากชน Quota/Rate Limit ที่ {pair_id}: {err_msg}", flush=True)
                print(f"   รันสำเร็จแล้ว {len(results)}/{len(dataset)} คู่ (เก็บไว้ใน evaluation_progress.json แล้ว)", flush=True)
                print(f"   รันคำสั่งเดิมซ้ำได้เมื่อ quota รีเซ็ต จะรันต่อจากคู่ที่ {len(results)+1} อัตโนมัติ", flush=True)
                save_progress()
                return
            else:
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
    report_output_path = os.path.join(os.path.dirname(__file__), "evaluation_results.json")
    with open(report_output_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"Saved evaluation report to: {report_output_path}")

    # Keep evaluation_progress.json updated as backup
    save_progress()

if __name__ == "__main__":
    main()
