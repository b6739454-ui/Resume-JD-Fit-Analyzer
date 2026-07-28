"""
agents/resume_extractor.py

Agent ตัวที่ 1: Resume Extractor
หน้าที่: รับข้อความ resume (plain text) -> เรียก Gemini ผ่าน instructor
        -> คืนค่าเป็น ResumeData (Pydantic model ที่ validate แล้ว)

หมายเหตุ: agent ตัวนี้ "ไม่" ทำ PDF/DOCX parsing เอง (เป็นงานของคนที่ 3 - API/Frontend)
รับแค่ text ที่ผ่านการแปลงมาแล้ว
"""

import os
import instructor
from google import genai
from dotenv import load_dotenv

# import schema จากไฟล์กลางที่ทุก agent ใช้ร่วมกัน
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schemas import ResumeData
from agents.skill_normalizer import normalize_skill_name

load_dotenv()

SYSTEM_PROMPT = """คุณคือระบบดึงข้อมูลจากเรซูเม่ (Resume Extractor)
หน้าที่ของคุณคืออ่านข้อความเรซูเม่ที่ได้รับ แล้วดึงข้อมูลออกมาให้ตรงกับ schema ที่กำหนด

กฎสำคัญ:
1. ทุก skill ที่ระบุ ต้องมี evidence เป็นข้อความที่ตัดมาจากเรซูเม่จริงเท่านั้น ห้ามแต่งขึ้นเอง
2. evidence ต้องเป็นประโยคหรือวลีที่แสดงบริบทการใช้งานจริง (เช่น "พัฒนา API ด้วย Python และ FastAPI")
   ห้ามใช้แค่ชื่อ skill โดดๆ (เช่น "Python" หรือ "FastAPI") เป็น evidence เด็ดขาด
   ถ้า skill ปรากฏเฉพาะใน keyword list และไม่มีประโยคบริบทรองรับ → evidence = null
3. ถ้าไม่สามารถระบุจำนวนปีประสบการณ์ได้ชัดเจน ให้ปล่อยเป็น null ไม่ต้องเดา
4. ดึงเฉพาะข้อมูลที่ปรากฏจริงในข้อความ ห้ามสมมติหรือเติมข้อมูลที่ไม่มี
5. skill ให้รวมทั้ง technical skills (เช่น Python, SQL) และ soft/domain skills ที่ระบุชัดเจน (เช่น Project Management)
"""


import httpx


def get_client(api_key_env_var: str = "GOOGLE_API_KEY") -> instructor.Instructor:
    """สร้าง instructor client ที่ผูกกับ Gemini ไว้ เรียกใช้ซ้ำได้ทั้งไฟล์"""
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


def extract_resume(resume_text: str, model: str = "gemini-flash-latest", api_key_env_var: str = "GOOGLE_API_KEY") -> ResumeData:
    """
    รับ resume text -> คืนค่าเป็น ResumeData ที่ผ่าน validation แล้ว
    หลัง LLM สกัด skills ออกมาแล้ว จะ normalize ชื่อ skill ทุกตัวผ่าน
    skill_taxonomy_master.csv (ESCO + O*NET) ก่อน return

    Args:
        resume_text: เนื้อหา resume แบบ plain text
        model: ชื่อโมเดล Gemini ที่จะใช้ (ค่า default คือ flash รุ่นล่าสุด)

    Returns:
        ResumeData: ข้อมูลที่สกัดออกมา พร้อม evidence อ้างอิงทุก skill (ชื่อ skill ผ่าน normalize แล้ว)
    """
    if not resume_text or not resume_text.strip():
        raise ValueError("resume_text ว่างเปล่า — ต้องมีเนื้อหาก่อนเรียก extract")

    client = get_client(api_key_env_var)

    result = client.chat.completions.create(
        model=model,
        response_model=ResumeData,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"นี่คือเนื้อหาเรซูเม่:\n\n{resume_text}"},
        ],
    )

    # Normalize ชื่อ skill ทุกตัวผ่าน taxonomy มาตรฐาน (ESCO + O*NET)
    for skill_item in result.skills:
        norm = normalize_skill_name(skill_item.skill)
        if norm["matched"]:
            skill_item.skill = norm["normalized"]

    return result


# ---------------------------------------------------------
# ทดสอบด้วยตัวเอง: python agents/resume_extractor.py
# ---------------------------------------------------------
if __name__ == "__main__":
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

    print("กำลังเรียก Gemini เพื่อสกัดข้อมูล...\n")
    data = extract_resume(sample_resume)
    print(data.model_dump_json(indent=2, ensure_ascii=False))
