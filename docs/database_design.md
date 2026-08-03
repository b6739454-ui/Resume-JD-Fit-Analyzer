# Database Design & Architecture Document

เอกสารอธิบายการออกแบบฐานข้อมูลเชิงสัมพันธ์ (Relational Database Design) สำหรับระบบ **Resume <-> JD Fit Analyzer** เพื่อใช้ประกอบการนำเสนอ

---

## 📌 ภาพรวมสถาปัตยกรรมข้อมูล (Data Architecture Overview)

ฐานข้อมูลถูกออกแบบตามหลัก Relational Database (PostgreSQL compatible) โดยมีโครงสร้าง 1-to-1 Mapping กับ Pydantic Data Models ใน `schemas.py` ดังนี้:

```
[resumes] ───< [resume_skills]
    │  └────< [work_experiences]
    │
    ├──────────┐
    ▼          ▼
[job_descriptions] ───< [skill_requirements]
    │
    ▼
[fit_reports] ───< [skill_matches]
    │  ├─────────< [fit_report_gaps]
    │  └─────────< [suggested_interview_questions]
```

---

## 🗄️ คำอธิบายตารางและ Mapping กับ Pydantic Schema

### 1. ตาราง `resumes` & `resume_skills` & `work_experiences`
- **ตาราง `resumes`**: เก็บข้อมูลดิบของ Resume ต้นฉบับ และประสบการณ์รวม
  - **Pydantic Mapping**: `ResumeData`
- **ตาราง `resume_skills`**: เก็บรายการทักษะที่ extracted ได้พร้อมข้อความหลักฐาน
  - **Pydantic Mapping**: `ResumeSkill` (`skill`, `years`, `evidence`)
- **ตาราง `work_experiences`**: เก็บประวัติการทำงานย้อนหลัง
  - **Pydantic Mapping**: `WorkExperience` (`role`, `company`, `years`, `description`)

### 2. ตาราง `job_descriptions` & `skill_requirements`
- **ตาราง `job_descriptions`**: เก็บประกาศรับสมัครงานดิบ และชื่อตำแหน่ง
  - **Pydantic Mapping**: `JDData`
- **ตาราง `skill_requirements`**: เก็บความต้องการแต่ละทักษะ พร้อมหมวดความสำคัญ (`must_have` / `nice_to_have`)
  - **Pydantic Mapping**: `SkillRequirement` (`skill`, `priority`, `min_years`)

### 3. ตาราง `fit_reports` & `skill_matches` & `fit_report_gaps` & `suggested_interview_questions`
- **ตาราง `fit_reports`**: เก็บผลสรุปคะแนน Fit Score, Must-Have Score, Nice-To-Have Score และ Bias Disclaimer
  - **Pydantic Mapping**: `FitReport`
- **ตาราง `skill_matches`**: เก็บผลการจับคู่ทักษะแบบละเอียด พร้อม `category` และ `requirement_index`
  - **Pydantic Mapping**: `SkillMatch` (`status`, `evidence`, `years_found`, `category`, `requirement_index`)
- **ตาราง `fit_report_gaps` & `suggested_interview_questions`**: เก็บรายการทักษะที่ขาดและคำถามสัมภาษณ์ที่แนะนำ

---

## ⚖️ Design Trade-offs: 9-Table Normalization vs. JSONB Embedded Columns

ในการออกแบบโครงสร้างเก็บข้อมูลรายงานผลลัพธ์ (`fit_reports`) มี 2 แนวทางหลักในการตัดสินใจเชิงสถาปัตยกรรม (Architectural Trade-offs):

| ประเด็นที่พิจารณา | แนวทาง 1: 9-Table Normalization (เลือกใช้ใน `db_schema.sql`) | แนวทาง 2: JSONB Embedded Columns |
|---|---|---|
| **การรองรับ RDBMS** | 🟢 ใช้ได้กับ RDBMS ทุกตัว (SQLite, MySQL, MariaDB, PostgreSQL) | 🔴 ผูกติดกับ PostgreSQL Native JSONB เท่านั้น |
| **การทำ SQL Aggregations & Analytics** | 🟢 เขียน SQL ธรรมดาคัดกรองหรือนับจำนวนทักษะที่แคนดิเดตขาดบ่อยๆ ได้สะดวก | 🟡 ต้องใช้ JSON Path syntax เช่น `jsonb_array_elements_text()` |
| **การดึงข้อมูลทั้งรายงาน** | 🟡 ต้องใช้ `JOIN` หลายตาราง | 🟢 ดึงแถวเดียวจาก `fit_reports` ได้ข้อมูลครบทั้งรายงาน |
| **ความซับซ้อนของ Schema** | 🟡 เพิ่มตารางย่อย `fit_report_gaps` และ `suggested_interview_questions` | 🟢 โครงสร้างตารางกระชับกว่า (8 ตาราง) |

> **ข้อสรุปสำหรับการนำเสนอ:** โครงสร้างใน `db_schema.sql` ถูกออกแบบแบบ Fully Normalized เพื่อรองรับฐานข้อมูลทุกประเภทและสะดวกต่อการทำ SQL Analytics เพิ่มเติม แต่หากระบบ deploy บน PostgreSQL เป็นหลัก สามารถรวม `gaps` และ `suggested_interview_questions` เป็นคอลัมน์ชนิด `JSONB` ภายในตาราง `fit_reports` เพื่อลด overhead ในการ JOIN ได้เช่นกัน

---

## 📄 SQL Script Reference

ไฟล์ SQL ฉบับเต็มอยู่ที่ [db_schema.sql](file:///c:/Users/supha/Downloads/Resume-JD-Fit-Analyzer/db_schema.sql)
