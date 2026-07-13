"""
agents/fit_analyzer.py

Agent ตัวที่ 3: Fit Analyzer
หน้าที่: รับ ResumeData (จาก Resume Extractor) + JDData (จาก JD Extractor)
        -> เรียก Gemini เทียบแต่ละ skill requirement กับข้อมูลใน resume
        -> คืนค่าเป็น FitAnalysisResult (list ของ SkillMatch + คะแนนเบื้องต้น)

หมายเหตุ: agent ตัวนี้ยังไม่ใส่ gaps / suggested_interview_questions / bias_disclaimer
เต็มรูปแบบ (นั่นเป็นหน้าที่ของ Gap Agent และขั้นตอนรวมผลสุดท้าย)
ตัวนี้โฟกัสที่ "matches" และคะแนนที่คำนวณจาก matches เท่านั้น
"""

import os
import instructor
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.genai.errors import ServerError

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schemas import ResumeData, JDData, SkillMatch

load_dotenv()


# ---------------------------------------------------------
# Schema เฉพาะของ agent นี้ (ผลลัพธ์ก่อนส่งต่อให้ Gap Agent / Judge Agent)
# ---------------------------------------------------------
class FitAnalysisResult(BaseModel):
    matches: list[SkillMatch] = Field(default_factory=list, description="ผลเทียบทุก skill requirement")
    must_have_score: int = Field(..., ge=0, le=100, description="คะแนนเฉพาะส่วน must-have skills")
    nice_to_have_score: int = Field(..., ge=0, le=100, description="คะแนนเฉพาะส่วน nice-to-have skills")
    fit_score: int = Field(..., ge=0, le=100, description="คะแนนรวม weighted ระหว่าง must-have และ nice-to-have")


SYSTEM_PROMPT = """คุณคือระบบวิเคราะห์ความเหมาะสม (Fit Analyzer)
คุณจะได้รับข้อมูล 2 ส่วน: (1) ข้อมูลที่สกัดจาก resume และ (2) รายการ skill requirement จาก JD
หน้าที่ของคุณคือเทียบทีละ skill requirement กับข้อมูลใน resume แล้วให้ผลลัพธ์ตาม schema

กฎสำคัญ:
1. เทียบ skill requirement ทุกตัวจาก JD กับ skills/work_experience ใน resume
2. status ของแต่ละ match ให้เลือกจาก:
   - "met" = resume มี skill นี้ชัดเจน และปีประสบการณ์ (ถ้า JD กำหนด) เพียงพอหรือไม่ได้กำหนด
   - "partial" = resume มี skill ที่เกี่ยวข้อง/ใกล้เคียง แต่ไม่ตรงเป๊ะ หรือมีประสบการณ์ไม่ถึงที่กำหนด
   - "missing" = ไม่พบ skill นี้ หรือสิ่งที่เกี่ยวข้องใน resume เลย
3. evidence ต้องคัดลอกมาจาก evidence ที่มีอยู่แล้วใน resume data เท่านั้น ห้ามแต่งขึ้นเอง
   ถ้า status เป็น "missing" ให้ evidence เป็น null
4. years_found ใส่ตามข้อมูลจริงที่พบใน resume สำหรับ skill นั้น ถ้าไม่มีให้เป็น null
5. คำนวณคะแนน:
   - must_have_score = สัดส่วน must-have skills ที่ status เป็น met (คิด partial เป็นครึ่งคะแนน) คูณ 100
   - nice_to_have_score = สัดส่วน nice-to-have skills ที่ status เป็น met (คิด partial เป็นครึ่งคะแนน) คูณ 100
   - fit_score = weighted average โดยให้น้ำหนัก must_have_score 70% และ nice_to_have_score 30%
   - ถ้าไม่มี nice-to-have skills เลย ให้ fit_score = must_have_score
   - ถ้าไม่มี must-have skills เลย ให้ fit_score = nice_to_have_score
"""


def get_client() -> instructor.Instructor:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("ไม่เจอ GOOGLE_API_KEY ใน .env — เช็คไฟล์ .env ก่อน")

    genai_client = genai.Client(api_key=api_key)
    client = instructor.from_genai(
        genai_client,
        mode=instructor.Mode.GENAI_TOOLS,
    )
    return client


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(ServerError),
    reraise=True,
)
def _call_llm_with_retry(client, model, response_model, messages):
    """เรียก LLM พร้อม retry อัตโนมัติเมื่อเจอ 503 (server ไม่ว่างชั่วคราว)
    รอเพิ่มขึ้นทีละรอบ (2s -> 4s -> 8s -> ...) ก่อนลองใหม่ สูงสุด 4 ครั้ง"""
    return client.chat.completions.create(
        model=model,
        response_model=response_model,
        messages=messages,
    )


def analyze_fit(
    resume_data: ResumeData,
    jd_data: JDData,
    model: str = "gemini-flash-latest",
) -> FitAnalysisResult:
    """
    รับ ResumeData + JDData -> คืนค่าเป็น FitAnalysisResult

    Args:
        resume_data: ผลลัพธ์จาก Resume Extractor
        jd_data: ผลลัพธ์จาก JD Extractor
        model: ชื่อโมเดล Gemini ที่จะใช้

    Returns:
        FitAnalysisResult: matches + คะแนนแต่ละส่วน
    """
    client = get_client()

    user_content = f"""
ข้อมูลจาก Resume:
{resume_data.model_dump_json(indent=2, ensure_ascii=False)}

Skill Requirements จาก JD (ตำแหน่ง: {jd_data.job_title}):
{[r.model_dump() for r in jd_data.requirements]}

กรุณาเทียบและให้ผลลัพธ์ตาม schema ที่กำหนด
"""

    result = _call_llm_with_retry(
        client=client,
        model=model,
        response_model=FitAnalysisResult,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    return result


# ---------------------------------------------------------
# ทดสอบด้วยตัวเอง: python agents/fit_analyzer.py
# รันต่อจาก resume_extractor.py และ jd_extractor.py จริง
# ---------------------------------------------------------
if __name__ == "__main__":
    from resume_extractor import extract_resume
    from jd_extractor import extract_jd

    sample_resume = """
    สมชาย ใจดี
    Backend Developer

    ประสบการณ์ทำงาน:
    - Junior Backend Developer ที่ บริษัท เอบีซี จำกัด (2565-2567)
      พัฒนา API ด้วย Python และ FastAPI, ทำงานกับฐานข้อมูล PostgreSQL
      มีประสบการณ์เขียน Python มาแล้ว 2 ปี

    การศึกษา:
    - ปริญญาตรี วิทยาการคอมพิวเตอร์ มหาวิทยาลัยตัวอย่าง

    ทักษะ:
    - Python, FastAPI, PostgreSQL, Git
    - เคยใช้ Docker ในบางโปรเจกต์เล็กๆ
    """

    sample_jd = """
    ตำแหน่ง: Backend Developer

    คุณสมบัติที่ต้องมี:
    - เขียน Python ได้อย่างน้อย 2 ปี
    - มีประสบการณ์ใช้งาน FastAPI หรือ Flask
    - เข้าใจการทำงานกับฐานข้อมูลเชิงสัมพันธ์ เช่น PostgreSQL หรือ MySQL

    เป็นข้อได้เปรียบ:
    - มีประสบการณ์ใช้ Docker
    - เคยทำงานกับระบบ CI/CD

    ประสบการณ์ทำงานรวมอย่างน้อย 2 ปีในสายงาน backend
    """

    print("ขั้นที่ 1: สกัดข้อมูล resume...")
    resume_data = extract_resume(sample_resume)
    print("เสร็จแล้ว\n")

    print("ขั้นที่ 2: สกัดข้อมูล JD...")
    jd_data = extract_jd(sample_jd)
    print("เสร็จแล้ว\n")

    print("ขั้นที่ 3: วิเคราะห์ความเหมาะสม (Fit Analyzer)...")
    fit_result = analyze_fit(resume_data, jd_data)
    print(fit_result.model_dump_json(indent=2, ensure_ascii=False))
