# CHANGELOG

ประวัติการเปลี่ยนแปลงทั้งหมดของ Resume-JD Fit Analyzer
จัดทำตามหลัก [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [v1.0.0] — 2026-08-08 · Production-Ready Release

### 🔗 เชื่อม Frontend เข้ากับ Pipeline จริง (ไม่ใช่ Mock แล้ว)

ก่อนหน้านี้ endpoint `/fit/analyze` คืนข้อมูล hardcoded เสมอ ใน v1.0.0 ได้เดินสาย
5-agent pipeline จริงเข้ากับ API ทั้งหมด ผู้ใช้ที่ส่ง Resume + JD เข้ามาจะได้รับผล
ที่วิเคราะห์จาก LLM จริงทุกครั้ง

**ไฟล์ที่เปลี่ยน:** `main.py` (commit `2930d48`)

### 📤 PDF และ DOCX Upload

เพิ่ม endpoint `/fit/analyze-file` ที่รับไฟล์ Resume และ JD จริงแทนการพิมพ์ข้อความ
รองรับ `.pdf` (ผ่าน pdfplumber) และ `.docx` (ผ่าน python-docx)

**ไฟล์ที่เปลี่ยน:** `main.py`, `requirements.txt`
**commit:** `1ffdbeb`

### 🖥️ Frontend UI

เพิ่มหน้า React สำหรับ upload Resume + JD และแสดง FitReport ในรูปแบบที่อ่านง่าย
พร้อม score breakdown และ evidence card

**commit:** `1ffdbeb`

### 🔒 PII Handling (PRD Section 8)

ก่อน Resume ถูกส่งเข้า pipeline จะถูก anonymize ชื่อ, email, เบอร์โทรออกก่อน
เพื่อป้องกัน PII รั่วไหลเข้าไปใน LLM prompt หรือ log

**ไฟล์ที่เปลี่ยน:** `utils/pii_handler.py`, `main.py`

### 🛡️ Prompt Injection Testing (PRD Section 8)

เพิ่มชุดทดสอบความปลอดภัย 3 scenarios:
- Prompt ที่พยายาม override system instruction
- Resume ที่ฝัง jailbreak text
- Input ที่พยายาม exfiltrate data

ผลลัพธ์: **3/3 ผ่าน** — pipeline ไม่ถูก hijack

**ไฟล์ใหม่:** `tests/test_prompt_injection.py` (commit `63efe6c`)

### 🔧 กู้คืนโค้ดจากการ Revert ผิดพลาด

commit `3885783` ตั้งใจ revert เฉพาะ few-shot examples (ที่ทำ accuracy แย่ลง −5.35%)
แต่พา code 4 จุดหายไปด้วย ได้แก่:
- PDF upload endpoint
- `category` / `requirement_index` fields ใน `SkillMatch`
- Cache invalidation logic ใน Judge Agent
- Logistic scoring function

กู้คืนทั้งหมดกลับมาใน commit `391e6c0` โดยไม่เอา few-shot กลับมา

### ⚡ Admin Toggle-Mock Endpoint (Zero-Downtime Demo Fallback)

เพิ่ม endpoint `/admin/toggle-mock` สำหรับสลับ pipeline mode แบบ runtime
โดยไม่ต้อง restart server — ออกแบบมาเป็น emergency fallback กลาง demo
ถ้า API quota หมด

```bash
# เปิด mock (0ms downtime)
curl -X POST "http://localhost:8000/admin/toggle-mock?enable=true"

# กลับ real pipeline
curl -X POST "http://localhost:8000/admin/toggle-mock?enable=false"
```

**ป้องกันด้วย:** localhost whitelist + `X-Admin-Secret` header สำหรับการเรียกจาก IP ภายนอก

**ไฟล์ที่เปลี่ยน:** `main.py` (commit `47ff6cd`, `2dadccf`)

### 🗄️ Database Schema Design

ออกแบบ schema สำหรับ PostgreSQL เพื่อเก็บ FitReport, SkillMatch, Gap
รองรับการ query ย้อนหลังและ audit log

**commit:** `1ffdbeb`

### 📋 Demo Script + Contingency Plan

สร้าง `docs/demo_script.md` ครอบคลุม 4 scenarios (3 นาที) พร้อม
สคริปต์คำพูดและแผนสำรองกรณีฉุกเฉินระหว่าง demo

**ไฟล์ใหม่:** `docs/demo_script.md` (commit `2dadccf`)

### 🧪 Test Coverage เพิ่มเติม

| Test file | Scope | ผล |
|-----------|-------|-----|
| `test_pii_handler.py` | PII anonymization | 7/7 PASSED |
| `test_prompt_injection.py` | Security | 3/3 PASSED |
| `test_demo_fallback.py` | Fallback scenarios | 5/5 PASSED |
| `test_single_key.py` | Single API key mode | 5/5 PASSED |
| `test_admin_auth.py` | Admin auth + mock toggle | 9/9 PASSED |

---

## [v0.2.0] — 2026-07-30 · AI Core Release

### 🧠 RAG-Based Skill Normalization (ESCO + O*NET)

แทนที่ exact string matching ด้วย semantic skill normalization โดยดึง
skill taxonomy จาก ESCO และ O*NET มาเป็น reference คำศัพท์

ผลที่ได้: "React.js" match กับ "ReactJS", "node" match กับ "Node.js"
โดยไม่ต้องเขียน synonym list เอง

**ไฟล์ใหม่:** `data/skill_taxonomy_master.csv`, `utils/skill_normalizer.py`
**commit:** `5aa73b4`

### 🤖 5-Agent Pipeline ทำงานด้วย LLM จริง

เปลี่ยนจากโครงสร้างเปล่า (Walking Skeleton) มาเป็น pipeline ที่ทำงานจริงทุกขั้น:

1. **Resume Extractor** — สกัด skills, experience, education
2. **JD Extractor** — แยก must-have / nice-to-have requirements
3. **Fit Analyzer** — จับคู่ skills กับ requirements
4. **Gap Agent** — ระบุสิ่งที่ขาด + สร้าง interview questions
5. **Judge Agent** — ตรวจสอบ evidence ก่อนให้คะแนน

**ไฟล์ใหม่:** `agents/resume_extractor.py`, `agents/jd_extractor.py`,
`agents/fit_analyzer.py`, `agents/gap_agent.py`, `agents/judge_agent.py`
**commit:** `f7625b3`, `5aa73b4`

### ⚖️ Judge Agent Evidence-Grounding

Judge Agent ตรวจสอบว่า skill ที่ Fit Analyzer claim ว่า match นั้น
มี evidence จริงใน Resume หรือไม่ ถ้าไม่มี → mark `verified=false` → ไม่นับคะแนน

สิ่งนี้ป้องกัน LLM hallucination และ resume keyword-stuffing ได้ในตัว

> ข้อสังเกต: pre-Judge score (LLM) มักสูงกว่า post-Judge score เสมอ
> นั่นคือพฤติกรรมที่ถูกต้อง ไม่ใช่บั๊ก — ดู [KNOWN_ISSUES.md](KNOWN_ISSUES.md)

**commit:** `5aa73b4`

### 🔧 แก้บั๊ก Substring-Matching → Index-Based Matching

การ matching เดิมใช้ substring ทำให้เกิด false match เช่น
"Java" match กับ "JavaScript" ได้โดยไม่ตั้งใจ

เปลี่ยนเป็น index-based matching ที่ Judge Agent ใช้ `requirement_index`
อ้างอิงตรงตำแหน่งใน JD array — ทำให้ match แม่นยำขึ้นอย่างมีนัยสำคัญ

แก้ไข 4 จุดใน `judge_agent.py` และ `fit_analyzer.py`

**commit:** `5aa73b4`

### 🌐 แก้บั๊ก JD Extractor Normalization + Resume ภาษาไทย

- JD ที่เขียนภาษาไทยถูก extract ผิด → แก้ prompt ให้ handle bilingual ได้
- Evidence จาก Resume ภาษาไทยไม่ถูก quote → แก้ให้ quote ต้นฉบับ
- เพิ่ม cache invalidation ตาม prompt hash เพื่อป้องกัน stale cache

**commit:** `cf3d741`

### 📊 Gold Dataset Evaluation — 15 คู่ครบ

รัน evaluation กับ gold dataset 15 คู่พร้อม label จาก human rater
บันทึกผลใน `tests/evaluation_results.json`

ผลสรุป:
- **Must-Have Accuracy: 58.93%** (ก่อน optimization)
- **Unsupported Claims Rate: 7.23%**
- Pearson correlation กับ human label: r ≈ 0.87

**ไฟล์:** `tests/evaluate_gold.py`, `tests/gold_dataset_final.json`

### ❌ Few-Shot Examples — ถูก Revert (เหตุผล: ทำ Accuracy แย่ลง)

เพิ่ม few-shot examples เข้า prompt เพื่อช่วย model แต่หลังทดสอบ
พบว่า accuracy ลดลง −5.35% จึง revert กลับและยืนยันผ่านการรัน 15 คู่ใหม่

**commit:** `3885783`

---

## [v0.1.0] — 2026-07-13 · Walking Skeleton

### 🏗️ โครงสร้าง API (FastAPI)

สร้าง endpoint หลักตาม PRD Section 6:
- `POST /fit/analyze` — รับ Resume + JD text คืน FitReport
- `POST /fit/batch` — Batch screening
- `POST /evaluate` — เทียบกับ gold labels

ทุก endpoint ใน v0.1.0 คืน mock data เพื่อพิสูจน์ว่า schema ถูกต้อง

**ไฟล์:** `main.py`, `schemas.py`

### 📐 Pydantic Schemas

ออกแบบ data model ครบ:
- `FitReport` — คะแนน fit, must-have, nice-to-have
- `SkillMatch` — skill, match type, score, evidence
- `GapReport` — missing skills, interview questions

### 🗂️ Repository Setup

- `.env.example` สำหรับ setup guide
- `.gitignore` ป้องกัน `.env` และ cache files ถูก commit
- Architecture diagram

---

## 📌 หมายเหตุด้านความแม่นยำ

**Must-Have Accuracy ณ เวลา Demo: ~58.18%**
(ต่ำกว่าเป้าหมาย PRD ที่ 80%)

ตัวเลขนี้ต่ำกว่าเป้าหมาย แต่มีเหตุผลที่บันทึกไว้ชัดเจน:

1. **Judge Agent ทำงานเกินเป้า** — ปฏิเสธ evidence ที่ implicit เกินไป
   แม้แต่ resume ที่ match จริง หากไม่ quote ตรงๆ ก็ถูกลด score
2. **Free-Tier Quota จำกัด** — ไม่สามารถรัน hyperparameter sweep เต็มรูปแบบได้
3. **Few-shot ทดลองแล้วไม่ช่วย** — ทดสอบแล้ว accuracy ลดลงจริง จึงไม่ใช้

ดูรายละเอียดเพิ่มเติมและแผนการปรับปรุงได้ที่ → **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)**

---

*Auto-generated from `git log` — last updated 2026-08-08*
