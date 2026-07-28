import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.resume_extractor import extract_resume
from agents.jd_extractor import extract_jd
from agents.fit_analyzer import analyze_fit
from agents.judge_agent import judge_matches

# โหลดเฉพาะ pair_15 จาก gold dataset
with open("tests/gold_dataset_final.json", encoding="utf-8") as f:
    dataset = json.load(f)
item = next(x for x in dataset if x["pair_id"] == "pair_15")

print("=== RAW TEXTS ===")
print("--- resume_text ---")
print(item["resume_text"])
print("--- jd_text ---")
print(item["jd_text"])

print("\n=== STEP 1: Resume Extractor ===")
resume_data = extract_resume(item["resume_text"])
print(resume_data.model_dump_json(indent=2, ensure_ascii=False))

print("\n=== STEP 2: JD Extractor ===")
jd_data = extract_jd(item["jd_text"])
print(jd_data.model_dump_json(indent=2, ensure_ascii=False))

print("\n=== STEP 3: Fit Analyzer (ก่อนเข้า Judge) ===")
fit_result = analyze_fit(resume_data, jd_data)
for m in fit_result.matches:
    print(f"  skill={m.skill!r} status={m.status} evidence={m.evidence!r} years={m.years_found}")

print(f"\n  must_have_score={fit_result.must_have_score}")
print(f"  nice_to_have_score={fit_result.nice_to_have_score}")
print(f"  fit_score={fit_result.fit_score}")

print("\n=== STEP 4: Judge Agent (หลังตรวจ evidence) ===")
verified = judge_matches(fit_result.matches, item["resume_text"])
for m in verified:
    print(f"  skill={m.skill!r} status={m.status} evidence={m.evidence!r}")

print("\n=== STEP 5: เทียบ before/after Judge ===")
changed_count = 0
for before, after in zip(fit_result.matches, verified):
    changed = "CHANGED" if before.status != after.status else "(เหมือนเดิม)"
    if before.status != after.status:
        changed_count += 1
    print(f"  {before.skill!r}: {before.status} -> {after.status} {changed}")
print(f"\n  สรุป: Judge เปลี่ยน {changed_count} / {len(fit_result.matches)} ตัว")

print("\n=== JD Requirements priority (จาก JD Extractor) ===")
for i, req in enumerate(jd_data.requirements):
    print(f"  [{i}] skill={req.skill!r} priority={req.priority} min_years={req.min_years}")

print("\n=== Gold ที่ควรจะเป็น ===")
for gm in item["gold_matches"]:
    print(f"  {gm['skill']}: ควรเป็น {gm['status']}")

print("\n=== Gold Scores ===")
print(f"  gold_must_have_score={item['gold_must_have_score']}")
print(f"  gold_nice_to_have_score={item['gold_nice_to_have_score']}")
print(f"  gold_fit_score={item['gold_fit_score']}")
