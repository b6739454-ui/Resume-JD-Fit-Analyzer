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

## Judgment Threshold Difference: Agile Experience Interpretation

- **Description**: ในการประเมิน `pair_15` (Senior Software Engineer) พบความแตกต่างของคะแนนระหว่าง AI และ Gold Standard (Gold Fit = 60% ขณะที่ Pred Fit = 89%):
  - **การตีความของ LLM**: ผู้สมัครมีประวัติการทำงานเป็น Team Leader คุม 3 ทีมพัฒนาซอฟต์แวร์ต่อเนื่องนาน 7.5 ปี และระบุคำว่า *"Agile Methodologies"* อยู่ในรายการ Core Qualifications ซึ่ง LLM (ทั้ง Fit Analyzer และ Judge Agent) ตีความว่าผู้สมัครมีประสบการณ์ความเป็นผู้นำทีมพัฒนาและมีทักษะ Agile เพียงพอที่จะผ่านเกณฑ์ requirement *"Agile development team leadership"* (`status: met`)
  - **การตีความของ Gold Standard (มนุษย์)**: ผู้เชี่ยวชาญมนุษย์ตั้งเกณฑ์การตัดสินที่เข้มงวดกว่า โดยกำหนดว่าคำอธิบายในประวัติการทำงาน (bullet points) ต้องมีคำศัพท์เฉพาะเจาะจงเกี่ยวกับกระบวนการทำงาน เช่น *Sprint*, *Scrum*, หรือ *Daily Standup* ปรากฏร่วมกับประสบการณ์คุมทีมโดยตรง จึงจะให้ผ่านเกณฑ์ มิฉะนั้นจะถือเป็น `status: missing`
- **Root Cause & Perspective**: นี่**ไม่ใช่บั๊กของระบบ** (Not a bug) แต่เป็นตัวอย่างจริงที่แสดงให้เห็นถึงความต่างของระดับเกณฑ์การตัดสิน (Judgment Threshold) ในกรณีที่หลักฐานมีความก้ำกึ่ง (Borderline / Ambiguous Evidence) ซึ่งมนุษย์และ AI (หรือแม้กระทั่งผู้สรรหาบุคลากรที่เป็นมนุษย์ต่างคนกัน) สามารถตีความและให้น้ำหนักความเข้มงวดต่างกันได้
- **PRD Alignment**: กรณีนี้ตอกย้ำถึงเหตุผลสำคัญที่ระบบต้องมีข้อความแจ้งเตือน **"Human Oversight Required"** และ **Bias Disclaimer** ตามข้อกำหนดของ PRD เพื่อย้ำเตือนว่าคะแนนจาก AI เป็นเพียงข้อมูลสนับสนุนการตัดสินใจเบื้องต้นเท่านั้น ไม่ใช่การตัดสินผลแพ้-ชนะที่เด็ดขาด และผู้ใช้ที่เป็นมนุษย์ต้องใช้วิจารณญาณประกอบการพิจารณาเสมอ

