import os
import json
import sys
import time
from dotenv import load_dotenv

# Ensure we can import agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.resume_extractor import extract_resume
from agents.jd_extractor import extract_jd
from agents.fit_analyzer import analyze_fit
from agents.gap_agent import analyze_gaps
from agents.judge_agent import judge_matches
from schemas import SkillMatch, SkillRequirement

load_dotenv()

# Deterministic Python scoring function
def calculate_scores_python(matches: list[SkillMatch], requirements: list[SkillRequirement]) -> tuple[int, int, int]:
    req_by_skill = {r.skill.lower(): r.priority for r in requirements}
    
    must_have_matches = []
    nice_to_have_matches = []
    
    for m in matches:
        priority = "must_have"
        m_skill_lower = m.skill.lower()
        
        # Check closest requirement
        for req_skill, prio in req_by_skill.items():
            if req_skill in m_skill_lower or m_skill_lower in req_skill:
                priority = prio
                break
        
        weight = 1.0 if m.status == "met" else (0.5 if m.status == "partial" else 0.0)
        if priority == "must_have":
            must_have_matches.append(weight)
        else:
            nice_to_have_matches.append(weight)
            
    must_have_score = int((sum(must_have_matches) / len(must_have_matches) * 100)) if must_have_matches else 0
    nice_to_have_score = int((sum(nice_to_have_matches) / len(nice_to_have_matches) * 100)) if nice_to_have_matches else 0
    
    if must_have_matches and nice_to_have_matches:
        fit_score = int(0.7 * must_have_score + 0.3 * nice_to_have_score)
    elif must_have_matches:
        fit_score = must_have_score
    else:
        fit_score = nice_to_have_score
        
    return must_have_score, nice_to_have_score, fit_score


# Client-side retry wrapper for agent calls to handle rate limit (429) & unavailable (503) errors
def call_agent_with_retry(agent_fn, *args, **kwargs):
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            return agent_fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str or "503" in err_str or "unavailable" in err_str:
                wait_time = 10 * (attempt + 1)
                print(f"  ⚠️ Hit rate limit or service unavailable. Retrying in {wait_time}s... (Attempt {attempt+1}/{max_attempts})")
                time.sleep(wait_time)
            else:
                raise e
    raise RuntimeError("Failed to complete agent call after maximum retries due to rate limits.")


def find_matching_requirement(gold_skill: str, requirements: list[SkillRequirement]) -> SkillRequirement | None:
    for req in requirements:
        if req.skill.lower() in gold_skill.lower() or gold_skill.lower() in req.skill.lower():
            return req
    return None


def main():
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gold_path = os.path.join(workspace_root, "gold_dataset_final.json")
    if not os.path.exists(gold_path):
        print(f"❌ ไม่พบไฟล์ gold dataset ใน: {gold_path}")
        return

    with open(gold_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    print(f"=== เริ่มการประเมินผลตัวอย่างจำนวน {len(dataset)} รายการ ===")
    print("โมเดลหลักที่ใช้: gemini-flash-lite-latest")
    print("ระบบจะเพิ่มความหน่วงเวลา 3 วินาทีระหว่าง API call เพื่อหลีกเลี่ยง Rate Limit 15 RPM\n")

    model_name = "gemini-flash-lite-latest"
    results = []

    # Metrics counters
    unsupported_claims_count = 0
    total_claims_count = 0

    must_have_correct = 0
    must_have_total = 0

    nice_to_have_correct = 0
    nice_to_have_total = 0

    for item in dataset:
        pair_id = item["pair_id"]
        role = item["target_role"]
        print(f"กำลังรัน: {pair_id} ({role})...")
        
        try:
            # 1. Resume Extractor
            resume_data = call_agent_with_retry(extract_resume, item["resume_text"], model=model_name)
            time.sleep(3)
            
            # 2. JD Extractor
            jd_data = call_agent_with_retry(extract_jd, item["jd_text"], model=model_name)
            time.sleep(3)
            
            # 3. Fit Analyzer
            fit_result = call_agent_with_retry(analyze_fit, resume_data, jd_data, model=model_name)
            time.sleep(3)
            
            # 4. Gap Agent
            gap_result = call_agent_with_retry(analyze_gaps, fit_result.matches, model=model_name)
            time.sleep(3)
            
            # 5. Judge Agent (Verify matches)
            verified_matches = call_agent_with_retry(judge_matches, fit_result.matches, item["resume_text"], model=model_name)
            time.sleep(3)
            
            # 6. Calculate verified Python score
            py_must, py_nice, py_fit = calculate_scores_python(verified_matches, jd_data.requirements)

            # Evaluate match accuracy & unsupported claims
            # Let's map each gold match to predicted verified matches
            for gold_m in item["gold_matches"]:
                gold_skill = gold_m["skill"]
                gold_status = gold_m["status"]
                
                # Check priority of this gold skill based on JD Extractor
                matched_req = find_matching_requirement(gold_skill, jd_data.requirements)
                priority = matched_req.priority if matched_req else "must_have"
                
                # Find the predicted status from verified_matches
                pred_match = None
                for pm in verified_matches:
                    if pm.skill.lower() in gold_skill.lower() or gold_skill.lower() in pm.skill.lower():
                        pred_match = pm
                        break
                
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

            # Count unsupported claims
            # Find claims (met/partial) from original Fit Analyzer that were changed to missing by Judge Agent
            original_matches_by_skill = {m.skill.lower(): m.status for m in fit_result.matches}
            for pm in verified_matches:
                orig_status = original_matches_by_skill.get(pm.skill.lower(), "missing")
                if orig_status in ("met", "partial"):
                    total_claims_count += 1
                    if pm.status == "missing":
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
            print(f"✅ {pair_id} เสร็จเรียบร้อย (Must={py_must}, Nice={py_nice}, Fit={py_fit})")
        except Exception as e:
            print(f"❌ {pair_id} เกิดข้อผิดพลาด: {type(e).__name__} -> {str(e)}")
            time.sleep(10)

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

    print("\n📊 === รายงานผลลัพธ์การประเมิน (Evaluation Metrics Report) ===")
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

if __name__ == "__main__":
    main()
