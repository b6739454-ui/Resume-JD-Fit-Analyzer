"""
agents/jd_extractor.py

Agent ตัวที่ 2: JD Extractor
หน้าที่: รับข้อความ Job Description (plain text) -> เรียก Gemini ผ่าน instructor
        -> คืนค่าเป็น JDData (ชื่อตำแหน่ง + list ของ SkillRequirement)

โครงสร้างเหมือน resume_extractor.py เกือบทั้งหมด ต่างกันที่ prompt และ schema เป้าหมาย
"""

import os
import instructor
from google import genai
from dotenv import load_dotenv

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schemas import JDData
from agents.skill_normalizer import normalize_skill_name

load_dotenv()

SYSTEM_PROMPT = """คุณคือระบบดึงข้อมูลจากประกาศรับสมัครงาน (JD Extractor)
หน้าที่ของคุณคืออ่านข้อความ Job Description ที่ได้รับ แล้วดึงข้อมูลออกมาให้ตรงกับ schema ที่กำหนด

กฎสำคัญ:
1. แยกแยะให้ชัดว่า skill ไหนเป็น "must_have" (จำเป็น/บังคับ) และ "nice_to_have" (พึงมี/เป็นข้อได้เปรียบ)
   - คำเช่น "ต้องมี", "จำเป็นต้อง", "Required" -> must_have
   - คำเช่น "จะพิจารณาเป็นพิเศษ", "เป็นข้อได้เปรียบ", "Preferred", "Nice to have" -> nice_to_have
   - ถ้า JD ไม่ได้ระบุชัดเจนว่าเป็นแบบไหน ให้ใช้ดุลยพินิจจากบริบท แต่ให้ default เป็น must_have หากเป็นทักษะหลักของตำแหน่ง
2. ถ้า JD ระบุจำนวนปีประสบการณ์ขั้นต่ำของ skill ใดชัดเจน ให้ใส่ min_years ตามนั้น ถ้าไม่ระบุให้ปล่อย null
3. ดึงเฉพาะข้อมูลที่ปรากฏจริงในข้อความ ห้ามสมมติหรือเติม skill ที่ไม่มีในประกาศ
4. overall_min_years ใช้เฉพาะกรณีที่ JD ระบุประสบการณ์รวมโดยไม่ผูกกับ skill ใด skill หนึ่ง (เช่น "มีประสบการณ์ทำงานอย่างน้อย 3 ปี")
5. กฎ 1 bullet = 1 requirement (สำคัญมาก):
   - bullet 1 บรรทัดใน JD ให้สกัดออกมาเป็น requirement เดียวเท่านั้น ห้ามแตกย่อยเป็นหลาย requirement จาก 1 bullet
   - ถ้า bullet กล่าวถึงหลาย tool พร้อมกัน (เช่น "Adobe Illustrator, Photoshop, InDesign") ให้ตั้งชื่อ skill รวมจาก bullet นั้นเป็น requirement เดียว (เช่น "Adobe Creative Suite")
   - ตัวอย่างที่ถูกต้อง: bullet "Experience with branding, packaging, and typography" → requirement เดียว ชื่อว่า "branding and packaging design"
   - ตัวอย่างที่ผิด: bullet เดียวกัน → แตกเป็น "trademarks", "packaging functions", "typography" (ห้ามทำแบบนี้)
6. ห้าม hallucinate ชื่อ tool/software จาก bullet ที่ไม่ได้ระบุชื่อ tool ชัดเจน:
   - ถ้า bullet พูดถึงทักษะทั่วไป เช่น "Experience with account management" → ชื่อ requirement คือ "account management" ไม่ใช่ชื่อ software ที่ LLM คิดขึ้นเอง
   - ถ้า bullet ระบุชื่อ software ชัดเจน เช่น "Proficiency in Salesforce" → ใช้ชื่อนั้นได้
"""


import httpx


def get_client(api_key_env_var: str = "GOOGLE_API_KEY") -> instructor.Instructor:
    """สร้าง instructor client ที่ผูกกับ Gemini ไว้"""
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


def extract_jd(jd_text: str, model: str = "gemini-flash-latest", api_key_env_var: str = "GOOGLE_API_KEY") -> JDData:
    """
    รับ JD text -> คืนค่าเป็น JDData ที่ผ่าน validation แล้ว
    หลัง LLM สกัด requirements ออกมาแล้ว จะ normalize ชื่อ skill ทุกตัวผ่าน
    skill_taxonomy_master.csv (ESCO + O*NET) ก่อน return

    Args:
        jd_text: เนื้อหา Job Description แบบ plain text
        model: ชื่อโมเดล Gemini ที่จะใช้

    Returns:
        JDData: ชื่อตำแหน่ง + รายการ skill requirement ทั้งหมด (ชื่อ skill ผ่าน normalize แล้ว)
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("jd_text ว่างเปล่า — ต้องมีเนื้อหาก่อนเรียก extract")

    client = get_client(api_key_env_var)

    result = client.chat.completions.create(
        model=model,
        response_model=JDData,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"นี่คือเนื้อหา Job Description:\n\n{jd_text}"},
        ],
    )

    # หมายเหตุ: ไม่ normalize ชื่อ skill ใน JD Extractor
    # เพราะ JD ต้นฉบับมีชื่อ skill ที่ถูกต้องอยู่แล้ว
    # การ normalize ทำให้เกิด false mapping (เช่น "B2B sales" → "bMobile Technology Sales")
    # ที่ทำให้ Fit Analyzer หา evidence ผิด และ Judge reject ทั้งหมด

    return result


# ---------------------------------------------------------
# ทดสอบด้วยตัวเอง: python agents/jd_extractor.py
# ---------------------------------------------------------
if __name__ == "__main__":
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

    print("กำลังเรียก Gemini เพื่อสกัดข้อมูล JD...\n")
    data = extract_jd(sample_jd)
    print(data.model_dump_json(indent=2, ensure_ascii=False))
