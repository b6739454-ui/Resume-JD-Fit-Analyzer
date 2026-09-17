"""
agents/fit_analyzer.py

Agent ตัวที่ 3: Fit Analyzer (+ Merged Gap Agent)
หน้าที่: รับ ResumeData (จาก Resume Extractor) + JDData (จาก JD Extractor)
        -> เรียก Gemini เทียบแต่ละ skill requirement กับข้อมูลใน resume
        -> คืนค่าเป็น FitAnalysisResult (list ของ SkillMatch + คะแนนเบื้องต้น)

Gap Agent Merge (env MERGED_GAP_AGENT=true, default):
    ใช้ analyze_fit_and_gaps() แทน analyze_fit() + analyze_gaps() แยกกัน
    → ประหยัด 1 LLM call (~20% ของ quota ต่อการวิเคราะห์ 1 ครั้ง)
    → gaps + suggested_interview_questions คืนมาพร้อมกับ matches ใน LLM call เดียว
    ตั้ง MERGED_GAP_AGENT=false ใน .env เพื่อ rollback กลับแบบเดิม (2 calls แยกกัน)
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


# Schema เฉพาะโดย LLM: ไม่มี score — LLM ทำแค่ match เท่านั้น Python คำนวณคะแนน
# ---------------------------------------------------------
class LLMMatchResult(BaseModel):
    matches: list[SkillMatch] = Field(default_factory=list, description="ผลเทียบทุก skill requirement")


# Schema สำหรับ Merged Gap Agent — matches + gaps + interview questions ใน LLM call เดียว
class CombinedLLMResult(BaseModel):
    matches: list[SkillMatch] = Field(default_factory=list, description="ผลเทียบทุก skill requirement")
    gaps: list[str] = Field(
        default_factory=list,
        description="รายชื่อ skill ที่ขาด (เฉพาะ match ที่ status เป็น missing หรือ partial)"
    )
    suggested_interview_questions: list[str] = Field(
        default_factory=list,
        description="คำถามสัมภาษณ์ที่แนะนำ เพื่อเจาะลึกจุดที่ขาดหรือยังไม่ชัดเจน (ภาษาไทย)"
    )
    transferable_notes: list[str] = Field(
        default_factory=list,
        description="ข้อสังเกตว่า skill ที่ candidate มีอยู่แล้วอาจช่วยทดแทน skill ที่ขาดได้เร็วแค่ไหน"
    )


# Schema สำหรับส่งออกให้แก่ agent ถัดไป: matches + คะแนนจาก Python
class FitAnalysisResult(BaseModel):
    matches: list[SkillMatch] = Field(default_factory=list, description="ผลเทียบทุก skill requirement")
    must_have_score: int = Field(..., ge=0, le=100, description="คะแนนเฉพาะส่วน must-have skills")
    nice_to_have_score: int = Field(..., ge=0, le=100, description="คะแนนเฉพาะส่วน nice-to-have skills")
    fit_score: int = Field(..., ge=0, le=100, description="คะแนนรวม weighted ระหว่าง must-have และ nice-to-have")



SYSTEM_PROMPT = """คุณคือระบบวิเคราะห์ความเหมาะสม (Fit Analyzer)
คุณจะได้รับข้อมูล 2 ส่วน: (1) ข้อมูลที่สกัดจาก resume และ (2) รายการ skill requirement จาก JD พร้อม [index] กำกับ
หน้าที่ของคุณคือเทียบทีละ skill requirement กับข้อมูลใน resume แล้วให้ผลลัพธ์ตาม schema (เฉพาะ matches ไม่ต้องคำนวณคะแนน)

กฎสำคัญ:
1. requirements แต่ละตัวมี [index] กำกับ — ต้องตอบ matches ครบทุกตัว เรียงตาม index เดียวกันเป๊ะ (สำคัญมาก — ระบบใช้ index จับคู่)
2. status ของแต่ละ match ให้เลือกจาก:
   - "met" = resume แสดงหลักฐานการใช้ skill จริงในบริบทงาน ซึ่งรวมถึง 2 แหล่ง:
     (ก) ประโยคบริบทใน work_experience หรือ education ที่แสดงการใช้งานจริง
     (ข) ข้อความใน highlights หรือ summary ที่เป็น experience statement — เช่น "Experience of working with X", "Proficient in X with Y years", "X years experience in Y", "Worked extensively with X", "Expertise in X" (ไม่ใช่แค่ชื่อ skill โดดๆ)
   - "partial" = resume มีชื่อ skill เท่านั้น โดยไม่มีบริบทการใช้งาน เช่น:
     (ก) ชื่อ skill โดดๆ ใน skills list (เช่น "Adobe Photoshop", "Python" ในลิสต์ skills)
     (ข) มี skill ที่เกี่ยวข้องแต่ไม่ตรงทีเดียว หรือประสบการณ์ไม่ถึงที่กำหนด
   - "missing" = ไม่พบ skill นี้หรือสิ่งที่เกี่ยวข้องใน resume เลย
   - ตัวอย่าง met (Highlights แบบ experience statement): evidence='Experience of working with branding, packaging, and printmaking' → met
   - ตัวอย่าง partial (skills list bare name): evidence='Adobe Creative Suite' (เพียงชื่อเดียว ไม่มีบริบท) → partial
3. evidence ต้องเป็นข้อความที่คัดลอกมาจาก resume ต้นฉบับตรงๆ แบบ exact substring ตัวอักษรต่อตัวอักษรเท่านั้น — ห้าม paraphrase สรุป หรือแต่งขึ้นมาเอง:
   - สำหรับ status="met": ต้องเป็นประโยคหรือวลีที่แสดงบริบทการใช้งานจริง คัดลอกมาจาก work_experience, education, หรือ highlights/summary ที่มี experience statement
   - สำหรับ status="partial": evidence เป็นชื่อ skill หรือกลุ่ม skill จาก skills list ที่ยกมาตรงๆ (เช่น 'Adobe Creative Suite (Illustrator, Photoshop, InDesign)')
   - ห้ามปล่อย evidence เป็น null เว้นแต่ status='missing' เท่านั้น — ทุก match ที่ status เป็น 'met' หรือ 'partial' ต้องมี evidence เสมอ ไม่มีข้อยกเว้น
   - ถ้า status เป็น "missing" ให้ evidence เป็น null
   - **กฎเหล็กการคัดลอก evidence (สำคัญมากที่สุด — หากผิดแค่ตัวอักษรเดียวระบบ Judge จะปัดทิ้งเป็น missing ทันที)**:
     - **เลือกเพียง 1 bullet point หรือ 1 วลีเดี่ยวๆ ที่สั้นและตรงที่สุดเพียงอันเดียวเท่านั้น**: ห้ามนำหลาย bullet points หรือหลายผลงานมาร้อยต่อกันด้วยเครื่องหมายจุลภาค (,), อัฒภาค (;), หรือคำว่า 'and' / 'as well as' เด็ดขาด (เช่น หากเจอ 'Blueprint fluency' ให้ใช้แค่ 'Blueprint fluency' หรือหากเจอ 'reviewed drawings' ให้ใช้แค่ 'reviewed drawings' ห้ามรวบเอาประโยคอื่นรอบข้างมารวมเป็นข้อความยาว)
     - **ห้ามรวม/เชื่อมหลายประโยคเข้าด้วยกัน**: ห้ามนำข้อความที่แยกกันอยู่คนละประโยคหรือคนละหัวข้อในเรซูเม่มารวมเป็นประโยคเดียว แม้เนื้อหาจะเกี่ยวข้องกันก็ตาม — หากมีหลักฐานอยู่ในหลายประโยค ให้เลือกยกมาแค่ 1 ประโยคที่ตรงและสมบูรณ์ที่สุด คัดลอกตรงตัวอักษรต่อตัวอักษร ห้ามยำหลายประโยคมารวมกันเด็ดขาด
     - **ห้ามดัดแปลงตัวอักษรเด็ดขาด**: ห้ามแก้รูปกริยา (เช่น เปลี่ยน "Managing" เป็น "Managed"), ห้ามตัดทอนข้อความกลางประโยค, ห้ามเปลี่ยนคำแม้ความหมายเหมือนเดิม — evidence ต้องเป็น substring ที่พบได้ตรงเป๊ะใน resume_text ต้นฉบับ ไม่ใช่แค่ "สื่อความหมายเดียวกัน"
     - **ตัวอย่างที่ห้ามทำ (ผิด)**: เรซูเม่มี 2 ประโยคแยกกันคือ 'Managed Major Accounts worth more than $50k in four territories.' และ 'Reviewed and grew account base by 18%...' — ห้ามรวมเป็น 'Managed major accounts worth over $50k across four territories, grew account base by 18%' เพราะเป็นการ paraphrase ให้เลือกยกมาแค่ประโยคเดียวที่ตรงที่สุดแทน
   - **กฎการเลือกภาษา evidence**:
     - สำหรับ resume ที่เขียนเป็นภาษาอังกฤษล้วน → evidence ต้องเป็นภาษาอังกฤษเท่านั้น คัดลอกตรงจาก resume
     - สำหรับ resume ที่เขียนเป็นภาษาไทยล้วน → evidence ต้องเป็นภาษาไทยเท่านั้น คัดลอกตรงจาก resume
     - สำหรับ resume แบบ bilingual (มีทั้งภาษาไทยและอังกฤษในเล่มเดียว) → **ให้ prefer English evidence ก่อนเสมอ** ถ้า skill นั้นมีคำอธิบายเป็นภาษาอังกฤษอยู่ใน resume ให้ใช้ส่วนนั้น; ใช้ Thai evidence ก็ต่อเมื่อ skill นั้นปรากฏเฉพาะในส่วนภาษาไทยของ resume เท่านั้น
     - ห้ามแปล ห้าม paraphrase ไม่ว่ากรณีใด — copy ตรงจากต้นฉบับเท่านั้น
     - ตัวอย่างที่ถูกต้อง (bilingual resume, prefer English): "Managed Major Accounts worth more than $50k in four territories" (จากส่วน English ของ resume)
     - ตัวอย่างที่ผิด (bilingual resume): เลือก Thai evidence ทั้งที่มี English section อธิบายเรื่องเดียวกัน หรือแปล English เป็น Thai ขึ้นมาเอง
4. years_found ใส่ตามข้อมูลจริงที่พบใน resume สำหรับ skill นั้น ถ้าไม่มีให้เป็น null
5. ต้องตอบ matches ครบทุก requirement (จำนวนเท่ากับ requirements ที่ส่งมา ไม่เพิ่มไม่ลด) — ไม่ต้องคำนวณคะแนนใดๆ
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
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=30, max=60),
    retry=retry_if_exception_type(ServerError),
    reraise=True,
)
def _call_llm_with_retry(client, model, response_model, messages):
    """เรียก LLM พร้อม retry อัตโนมัติเมื่อเจอ 503 (server ไม่ว่างชั่วคราว / high demand)
    รอ backoff 30-60 วินาทีสำหรับ 503 โดยเฉพาะ ก่อนลองใหม่ สูงสุด 3 ครั้ง"""
    return client.chat.completions.create(
        model=model,
        response_model=response_model,
        messages=messages,
    )


def _compute_scores_python(matches: list[SkillMatch], requirements: list) -> tuple[int, int, int]:
    """
    คำนวณ must_have_score, nice_to_have_score, fit_score ด้วย Python (deterministic)
    จับคู่ matches[i] กับ requirements[i] ด้วย index ตรง — ไม่มี substring matching
    เป็นไปได้ต่อเมื่อ LLM ตอบครบทุก requirement เรียงตาม index
    """
    if not matches or not requirements:
        return 0, 0, 0

    must_have_weights: list[float] = []
    nice_to_have_weights: list[float] = []

    # จับคู่ด้วย index ตรง matches[i] ↔ requirements[i]
    for i, req in enumerate(requirements):
        if i < len(matches):
            weight = 1.0 if matches[i].status == "met" else (0.5 if matches[i].status == "partial" else 0.0)
        else:
            # LLM ตอบไม่ครบ (validate จะหยุดก่อนถึงตรงนี้เสมอ) — conservative fallback
            weight = 0.0

        if req.priority == "must_have":
            must_have_weights.append(weight)
        else:
            nice_to_have_weights.append(weight)

    must = int(sum(must_have_weights) / len(must_have_weights) * 100) if must_have_weights else 0
    nice = int(sum(nice_to_have_weights) / len(nice_to_have_weights) * 100) if nice_to_have_weights else 0

    if must_have_weights and nice_to_have_weights:
        fit = int(0.7 * must + 0.3 * nice)
    elif must_have_weights:
        fit = must
    else:
        fit = nice

    return must, nice, fit


def analyze_fit(
    resume_data: ResumeData,
    jd_data: JDData,
    model: str = "gemini-flash-latest",
    api_key_env_var: str = "GOOGLE_API_KEY",
) -> FitAnalysisResult:
    """
    รับ ResumeData + JDData -> คืนค่าเป็น FitAnalysisResult
    LLM ทำแค่ match skill (ให้ status ทีละ skill) เรียงตาม index เดียวกับ requirements
    Python คำนวณคะแนนสุดท้ายตามสูตร 70/30 เสมอ

    Args:
        resume_data: ผลลัพธ์จาก Resume Extractor
        jd_data: ผลลัพธ์จาก JD Extractor
        model: ชื่อโมเดล Gemini ที่จะใช้

    Returns:
        FitAnalysisResult: matches + คะแนนแต่ละส่วน (คำนวณด้วย Python)

    Raises:
        ValueError: ถ้า LLM ตอบ matches ไม่ครบตามจำนวน requirements ที่ส่งไป
    """
    client = get_client(api_key_env_var)

    # เพิ่ม index กำกับใน prompt — บังคับให้ LLM ตอบตาม index เดียวกับนี้เป๊ะ
    indexed_requirements = [
        {"index": i, **r.model_dump()}
        for i, r in enumerate(jd_data.requirements)
    ]

    user_content = f"""
ข้อมูลจาก Resume:
{resume_data.model_dump_json(indent=2, ensure_ascii=False)}

Skill Requirements จาก JD (ตำแหน่ง: {jd_data.job_title}) — ต้องตอบ matches เรียงตาม [index] เป๊ะ ครบ {len(indexed_requirements)} รายการ:
{indexed_requirements}

กรุณาเทียบทุก requirement และให้ผลลัพธ์ matches ครบ {len(indexed_requirements)} ตัว เรียงตามลำดับ index เดียวกันเป๊ะ
"""

    # LLM สร้างแค่ matches ไม่ต้องคำนวณคะแนน
    llm_result = _call_llm_with_retry(
        client=client,
        model=model,
        response_model=LLMMatchResult,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    # Validate ความครบถ้วน — ไม่เดา default ไม่ว่าทิศทางไหน
    n_expected = len(jd_data.requirements)
    n_returned = len(llm_result.matches)
    if n_returned != n_expected:
        raise ValueError(
            f"Fit Analyzer ตอบ matches ไม่ครบ: ส่งไป {n_expected} requirements "
            f"แต่ได้ matches กลับมาแค่ {n_returned} ตัว "
            f"— ต้อง retry ไม่ใช่เดา"
        )

    # เติม category และ requirement_index เข้าไปใน SkillMatch ตามลำดับใน jd_data.requirements
    for i, (req, match) in enumerate(zip(jd_data.requirements, llm_result.matches)):
        match.category = req.priority
        match.requirement_index = i

    # Python คำนวณคะแนนตามสูตร 70/30 — index-based, deterministic
    must, nice, fit = _compute_scores_python(llm_result.matches, jd_data.requirements)

    return FitAnalysisResult(
        matches=llm_result.matches,
        must_have_score=must,
        nice_to_have_score=nice,
        fit_score=fit,
    )


# ---------------------------------------------------------
# Merged Gap Agent — รวม Gap analysis เข้ามาใน Fit Analyzer
# ใช้งาน: analyze_fit_and_gaps() แทน analyze_fit() + analyze_gaps() แยกกัน
# ตั้ง env MERGED_GAP_AGENT=false เพื่อ rollback กลับแบบ 2 calls
# ---------------------------------------------------------

MERGED_SYSTEM_PROMPT = SYSTEM_PROMPT + """

เพิ่มเติม — Gap Analysis (รวมในคำตอบเดียวกัน):
หลังจากให้ matches ครบแล้ว ให้วิเคราะห์ช่องว่างทักษะเพิ่มเติม โดย:

A. gaps: ดึงเฉพาะชื่อ skill ที่ status เป็น "missing" หรือ "partial" เท่านั้น
   ห้ามใส่ skill ที่ status เป็น "met" ลงใน gaps

B. suggested_interview_questions: เขียนคำถามสัมภาษณ์ที่ recruiter ใช้ถามเพื่อตรวจสอบจุดที่ขาด
   - คำถามต้องเจาะจง อ้างอิงจาก skill ที่ขาดจริง ไม่ใช่คำถามทั่วไป
   - เขียนเป็นภาษาไทย สุภาพ เหมาะกับการสัมภาษณ์งานจริง

C. transferable_notes: ถ้า skill ที่ candidate มีอยู่แล้ว (status="met") เกี่ยวข้องกับ skill ที่ขาด
   ให้ตั้งข้อสังเกตว่าอาจช่วยให้เรียนรู้ skill ที่ขาดได้เร็วขึ้น
   ถ้าไม่มีความเกี่ยวข้องที่สมเหตุสมผล ให้ปล่อย list ว่างได้ ห้ามเดามั่ว
   ห้ามให้ความเห็นเรื่องการตัดสินใจรับ/ไม่รับ
"""


def analyze_fit_and_gaps(
    resume_data: ResumeData,
    jd_data: JDData,
    model: str = "gemini-flash-latest",
    api_key_env_var: str = "GOOGLE_API_KEY",
) -> tuple["FitAnalysisResult", "CombinedLLMResult"]:
    """
    Merged version: รัน Fit Analyzer + Gap Analysis ใน LLM call เดียว
    ประหยัด ~20% quota เทียบกับการเรียก analyze_fit() + analyze_gaps() แยกกัน

    Returns:
        tuple[FitAnalysisResult, CombinedLLMResult]:
            - FitAnalysisResult: matches + คะแนน (เหมือน analyze_fit() เดิม)
            - CombinedLLMResult: gaps + suggested_interview_questions + transferable_notes
    """
    client = get_client(api_key_env_var)

    indexed_requirements = [
        {"index": i, **r.model_dump()}
        for i, r in enumerate(jd_data.requirements)
    ]

    user_content = f"""
ข้อมูลจาก Resume:
{resume_data.model_dump_json(indent=2, ensure_ascii=False)}

Skill Requirements จาก JD (ตำแหน่ง: {jd_data.job_title}) — ต้องตอบ matches เรียงตาม [index] เป๊ะ ครบ {len(indexed_requirements)} รายการ:
{indexed_requirements}

กรุณาเทียบทุก requirement และให้ผลลัพธ์ matches ครบ {len(indexed_requirements)} ตัว เรียงตามลำดับ index เดียวกันเป๊ะ
จากนั้นวิเคราะห์ gaps + suggested_interview_questions + transferable_notes ตามที่ระบุใน system prompt
"""

    llm_result = _call_llm_with_retry(
        client=client,
        model=model,
        response_model=CombinedLLMResult,
        messages=[
            {"role": "system", "content": MERGED_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    # Validate matches count
    n_expected = len(jd_data.requirements)
    n_returned = len(llm_result.matches)
    if n_returned != n_expected:
        raise ValueError(
            f"Fit Analyzer (merged) ตอบ matches ไม่ครบ: ส่งไป {n_expected} requirements "
            f"แต่ได้ matches กลับมาแค่ {n_returned} ตัว — ต้อง retry ไม่ใช่เดา"
        )

    # เติม category และ requirement_index
    for i, (req, match) in enumerate(zip(jd_data.requirements, llm_result.matches)):
        match.category = req.priority
        match.requirement_index = i

    # Python คำนวณคะแนน
    must, nice, fit = _compute_scores_python(llm_result.matches, jd_data.requirements)

    fit_result = FitAnalysisResult(
        matches=llm_result.matches,
        must_have_score=must,
        nice_to_have_score=nice,
        fit_score=fit,
    )

    return fit_result, llm_result



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
