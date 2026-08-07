# Known Issues & Tech Debt

## Behavior: Pre-Judge Score (LLM) vs Post-Judge Score (Python)

- **Description**: สังเกตพบว่าหลายคู่ (pair_03, pair_04, pair_09, pair_10 เป็นต้น) มี pre-Judge score (LLM) สูงกว่า post-Judge score (Python) — นี่คือพฤติกรรมที่ถูกต้อง แสดงว่า Judge Agent กำลังปฏิเสธ evidence ที่ไม่มีหลักฐานรองรับตามที่ออกแบบไว้ ไม่ใช่บั๊ก
- **Status**: Verified behavior. Working as designed by PRD specification.

## Accuracy Optimization — Summary & Conclusion

- **Baseline achieved**: Must-Have Accuracy ~57-61% (varies slightly due to LLM non-determinism), Unsupported Claims Rate 4.82-6.02% (consistently passes ≤10% target)
- **Attempts made**:
  - **Index-based matching fix (substring → index)**: confirmed critical, kept permanently
  - **Evidence single-sentence exact-substring rule**: confirmed helps (reduced unsupported rate from 41% → ~5%), kept permanently
  - **Few-shot examples for semantic disambiguation (met/partial)**: caused -5.35% regression, reverted (commit `3885783`)
- **Conclusion**: Reached model capability ceiling for `gemini-flash-latest` via prompt engineering. Must-Have Accuracy target of 80% (PRD) not achievable with current model + prompt-only approach within project scope. Future work: evaluate `gemini-flash` (non-lite) or `gemini-pro` tier, or fine-tuning.
- **Decision**: Stop further prompt tuning for accuracy. Redirect effort to remaining PRD requirements (PII handling, prompt injection testing, demo preparation).

