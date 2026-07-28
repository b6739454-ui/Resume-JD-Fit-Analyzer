import json
import os
import sys

def audit_gold_scores():
    gold_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gold_dataset_final.json")
    if not os.path.exists(gold_path):
        print(f"❌ ไม่พบไฟล์ gold dataset ใน: {gold_path}")
        return

    with open(gold_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    print(f"=== ตรวจสอบความถูกต้องของ Gold Scores ใน Dataset ({len(dataset)} รายการ) ===\n")
    
    discrepancies = []

    for item in dataset:
        pair_id = item["pair_id"]
        role = item.get("target_role", "Unknown")
        jd_text = item.get("jd_text", "")
        gold_matches = item.get("gold_matches", [])
        
        gold_must = item.get("gold_must_have_score")
        gold_nice = item.get("gold_nice_to_have_score")
        gold_fit = item.get("gold_fit_score")

        # Parse jd_text for must-have vs nice-to-have bullet counts
        must_bullets = []
        nice_bullets = []
        current_section = None
        
        for line in jd_text.splitlines():
            line_str = line.strip()
            line_lower = line_str.lower()
            if "required" in line_lower or "must-have" in line_lower:
                current_section = "must"
                continue
            elif "preferred" in line_lower or "nice-to-have" in line_lower:
                current_section = "nice"
                continue
            elif any(line_str.startswith(kw) for kw in ["We ", "Join ", "Help ", "Job Description", "About"]):
                current_section = None
                continue

            if line_str.startswith("-"):
                bullet_content = line_str[1:].strip()
                if current_section == "must":
                    must_bullets.append(bullet_content)
                elif current_section == "nice":
                    nice_bullets.append(bullet_content)

        n_must = len(must_bullets)
        n_nice = len(nice_bullets)
        total_matches = len(gold_matches)

        # If JD bullet count matches gold_matches length
        if n_must + n_nice == total_matches:
            must_matches = gold_matches[:n_must]
            nice_matches = gold_matches[n_must:]
            parsed_ok = True
        else:
            # Fallback: if not matching, let's see why
            parsed_ok = False
            must_matches = []
            nice_matches = []

        must_weights = [1.0 if m["status"] == "met" else (0.5 if m["status"] == "partial" else 0.0) for m in must_matches]
        nice_weights = [1.0 if m["status"] == "met" else (0.5 if m["status"] == "partial" else 0.0) for m in nice_matches]

        calc_must = int(sum(must_weights) / len(must_weights) * 100) if must_weights else 0
        calc_nice = int(sum(nice_weights) / len(nice_weights) * 100) if nice_weights else 0

        if must_weights and nice_weights:
            calc_fit = int(0.7 * calc_must + 0.3 * calc_nice)
        elif must_weights:
            calc_fit = calc_must
        else:
            calc_fit = calc_nice

        has_mismatch = False
        mismatch_reasons = []

        if not parsed_ok:
            has_mismatch = True
            mismatch_reasons.append(f"JD bullets (Must:{n_must} + Nice:{n_nice} = {n_must+n_nice}) != gold_matches ({total_matches})")
        else:
            if gold_must != calc_must:
                has_mismatch = True
                mismatch_reasons.append(f"Must-have Score: JSON={gold_must} vs Calc={calc_must} (Matches: {[m['status'] for m in must_matches]})")
            if gold_nice != calc_nice:
                has_mismatch = True
                mismatch_reasons.append(f"Nice-to-have Score: JSON={gold_nice} vs Calc={calc_nice} (Matches: {[m['status'] for m in nice_matches]})")
            if gold_fit != calc_fit:
                has_mismatch = True
                mismatch_reasons.append(f"Fit Score: JSON={gold_fit} vs Calc={calc_fit}")

        status_str = "❌ MISMATCH" if has_mismatch else "✅ OK"
        print(f"[{pair_id}] {role:<45} | Must: {gold_must:<3} (Calc: {str(calc_must) if parsed_ok else '?'}) | Nice: {gold_nice:<3} (Calc: {str(calc_nice) if parsed_ok else '?'}) | Fit: {gold_fit:<3} (Calc: {str(calc_fit) if parsed_ok else '?'}) | {status_str}")
        if mismatch_reasons:
            for r in mismatch_reasons:
                print(f"    └── {r}")

        if has_mismatch:
            discrepancies.append({
                "pair_id": pair_id,
                "role": role,
                "gold_must": gold_must,
                "calc_must": calc_must if parsed_ok else None,
                "gold_nice": gold_nice,
                "calc_nice": calc_nice if parsed_ok else None,
                "gold_fit": gold_fit,
                "calc_fit": calc_fit if parsed_ok else None,
                "reasons": mismatch_reasons
            })

    print("\n" + "="*85)
    print(f"สรุป: พบข้อผิดพลาดทั้งหมด {len(discrepancies)} / {len(dataset)} รายการ")
    print("="*85)

if __name__ == "__main__":
    audit_gold_scores()
