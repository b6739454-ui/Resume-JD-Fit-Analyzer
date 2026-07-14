"""
examples/load_sample_corpus.py

ตอบโจทย์ Iteration 1 ข้อ optional: "load 1-2 sample corpus files from the data pack"

โหลด 2 คู่แรกจาก tests/gold_dataset_final.json (instructor-provided gold set)
มาลองยิงเข้า POST /fit/analyze (mock endpoint ของ Iteration 1) เพื่อพิสูจน์ว่า
รูปแบบข้อมูลจริงจาก data pack ใช้กับ API stub ได้โดยไม่ error

รันด้วย: python examples/load_sample_corpus.py
(ต้องรัน `uvicorn main:app --reload` ไว้ก่อนในอีก terminal หนึ่ง)
"""

import json
import os
import requests

GOLD_PATH = os.path.join(os.path.dirname(__file__), "..", "tests", "gold_dataset_final.json")
API_URL = "http://127.0.0.1:8000/fit/analyze"
N_SAMPLES = 2


def main():
    with open(GOLD_PATH, encoding="utf-8") as f:
        gold_data = json.load(f)

    print(f"โหลด gold dataset สำเร็จ: {len(gold_data)} คู่ทั้งหมด")
    print(f"จะทดสอบยิง {N_SAMPLES} คู่แรกเข้า {API_URL}\n")

    for item in gold_data[:N_SAMPLES]:
        pair_id = item["pair_id"]
        print(f"--- {pair_id} ({item['target_role']}) ---")

        payload = {
            "resume_text": item["resume_text"],
            "jd_text": item["jd_text"],
        }

        try:
            response = requests.post(API_URL, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            print(f"✅ status={response.status_code}  fit_score(mock)={result['fit_score']}")
            print(f"   gold_fit_score จริงคือ: {item['gold_fit_score']} (Iteration 1 ยังไม่เทียบกันจริง แค่โชว์ shape)")
        except requests.exceptions.ConnectionError:
            print("❌ เชื่อมต่อ API ไม่ได้ — ต้องรัน `uvicorn main:app --reload` ก่อน")
            return
        except Exception as e:
            print(f"❌ error: {e}")

        print()


if __name__ == "__main__":
    main()
