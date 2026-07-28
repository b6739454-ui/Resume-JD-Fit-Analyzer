"""
agents/gap_agent.py

Agent ตัวที่ 4: Gap Agent
หน้าที่: รับ list ของ SkillMatch (จาก Fit Analyzer) -> เรียก Gemini วิเคราะห์
        -> คืนค่าเป็น GapAnalysisResult:
           - gaps: รายชื่อ skill ที่ขาด (เฉพาะที่ status = missing หรือ partial)
           - suggested_interview_questions: คำถามสัมภาษณ์ที่ช่วยเจาะลึกจุดที่ขาด
           - transferable_notes: ข้อสังเกตว่า skill ที่มีอยู่ช่วยทดแทน skill ที่ขาดได้แค่ไหน (ถ้ามี)
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
from schemas import SkillMatch

load_dotenv()


# ---------------------------------------------------------
# Schema เฉพาะของ agent นี้
# ---------------------------------------------------------
class GapAnalysisResult(BaseModel):
    gaps: list[str] = Field(
        default_factory=list,
        description="รายชื่อ skill ที่ขาด (มาจาก match ที่ status เป็น missing หรือ partial)"
    )
    suggested_interview_questions: list[str] = Field(
        default_factory=list,
        description="คำถามสัมภาษณ์ที่แนะนำ เพื่อเจาะลึกจุดที่ขาดหรือยังไม่ชัดเจน"
    )
    transferable_notes: list[str] = Field(
        default_factory=list,
        description="ข้อสังเกตว่า skill ที่ candidate มีอยู่แล้ว อาจช่วยทดแทน/เรียนรู้ skill ที่ขาดได้เร็วแค่ไหน "
                    "(เช่น มี Python มาก่อน น่าจะเรียนรู้ FastAPI ได้เร็ว)"
    )


SYSTEM_PROMPT = """คุณคือระบบวิเคราะห์ช่องว่างทักษะ (Gap Agent)
คุณจะได้รับผลการเทียบ skill ทั้งหมด (matches) ระหว่าง resume กับ JD
หน้าที่ของคุณคือวิเคราะห์เฉพาะส่วนที่เป็นช่องว่าง แล้วให้ผลลัพธ์ตาม schema

กฎสำคัญ:
1. gaps: ดึงเฉพาะชื่อ skill ที่ status เป็น "missing" หรือ "partial" เท่านั้น
   ห้ามใส่ skill ที่ status เป็น "met" ลงใน gaps
2. suggested_interview_questions: เขียนคำถามที่ recruiter ใช้ถามสัมภาษณ์เพื่อตรวจสอบเพิ่มเติมในจุดที่ขาด
   - คำถามต้องเจาะจง อ้างอิงจาก skill ที่ขาดจริง ไม่ใช่คำถามทั่วไป
   - เขียนเป็นภาษาไทย สุภาพ เหมาะกับการสัมภาษณ์งานจริง
3. transferable_notes: ถ้ามี skill อื่นที่ candidate มีอยู่แล้ว (จาก match ที่ status เป็น met) ที่เกี่ยวข้อง/ใกล้เคียงกับ
   skill ที่ขาด ให้ตั้งข้อสังเกตว่าอาจช่วยให้เรียนรู้ skill ที่ขาดได้เร็วขึ้น
   ถ้าไม่มีความเกี่ยวข้องที่สมเหตุสมผล ให้ปล่อย list ว่างได้ ห้ามเดามั่ว
4. ห้ามให้ความเห็นเรื่องการตัดสินใจรับ/ไม่รับ งานนี้เป็นแค่การสนับสนุนข้อมูลเท่านั้น
"""


import httpx


def get_client(api_key_env_var: str = "GOOGLE_API_KEY") -> instructor.Instructor:
    api_key = os.getenv(api_key_env_var)
    if not api_key:
        raise ValueError(f"ไม่เจอ {api_key_env_var} ใน .env — เช็คไฟล์ .env ก่อน")

    httpx_client = httpx.Client(http2=False, timeout=60.0)
    genai_client = genai.Client(api_key=api_key, http_options={"httpx_client": httpx_client})
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
    """เรียก LLM พร้อม retry อัตโนมัติเมื่อเจอ 503 (server ไม่ว่างชั่วคราว)"""
    return client.chat.completions.create(
        model=model,
        response_model=response_model,
        messages=messages,
    )


def analyze_gaps(
    matches: list[SkillMatch],
    model: str = "gemini-flash-latest",
    api_key_env_var: str = "GOOGLE_API_KEY",
) -> GapAnalysisResult:
    """
    รับ list ของ SkillMatch (จาก Fit Analyzer) -> คืนค่าเป็น GapAnalysisResult

    Args:
        matches: ผลเทียบ skill ทั้งหมดจาก Fit Analyzer
        model: ชื่อโมเดล Gemini ที่จะใช้

    Returns:
        GapAnalysisResult: gaps + คำถามสัมภาษณ์ + ข้อสังเกตเรื่อง transferable skills
    """
    if not matches:
        raise ValueError("matches ว่างเปล่า — ต้องมีผลจาก Fit Analyzer ก่อนเรียก Gap Agent")

    client = get_client(api_key_env_var)

    user_content = f"""
ผลการเทียบ skill ทั้งหมด (matches):
{[m.model_dump() for m in matches]}

กรุณาวิเคราะห์ช่องว่างและให้ผลลัพธ์ตาม schema ที่กำหนด
"""

    result = _call_llm_with_retry(
        client=client,
        model=model,
        response_model=GapAnalysisResult,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    return result


# ---------------------------------------------------------
# ทดสอบด้วยตัวเอง: python agents/gap_agent.py
# รันต่อจาก resume_extractor -> jd_extractor -> fit_analyzer -> gap_agent
# ---------------------------------------------------------
if __name__ == "__main__":
    from resume_extractor import extract_resume
    from jd_extractor import extract_jd
    from fit_analyzer import analyze_fit

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
    print("เสร็จแล้ว\n")

    print("ขั้นที่ 4: วิเคราะห์ช่องว่างทักษะ (Gap Agent)...")
    gap_result = analyze_gaps(fit_result.matches)
    print(gap_result.model_dump_json(indent=2, ensure_ascii=False))
