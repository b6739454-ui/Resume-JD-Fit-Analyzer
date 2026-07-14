"""
agents/judge_agent.py

Agent ตัวที่ 5 (ตัวสุดท้าย): Judge Agent
หน้าที่ตาม PRD: "Verify every match claim has resume evidence"
               "Judge rejects matches without resume evidence"

Judge Agent เป็นด่านสุดท้ายก่อนส่งรายงานออก:
1. ตรวจสอบทุก SkillMatch ที่มี evidence -> evidence นั้นต้องเป็นข้อความที่ปรากฏจริงใน resume ต้นฉบับ
   (ไม่ใช่ข้อความที่ LLM ตัวก่อนหน้า "แต่ง" ขึ้นมาเอง)
2. ถ้า evidence ไม่ตรงกับ resume จริง (LLM อาจ hallucinate) -> ปรับ status เป็น "missing" และล้าง evidence
3. ประกอบผลลัพธ์สุดท้ายเป็น FitReport ที่พร้อมส่งให้ frontend
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
from schemas import SkillMatch, FitReport

load_dotenv()


# ---------------------------------------------------------
# Schema เฉพาะของ agent นี้: ผลตรวจสอบทีละ match
# ---------------------------------------------------------
class VerifiedMatch(BaseModel):
    skill_index: int = Field(
        ...,
        description="index (0-based) ของ skill match ในลำดับที่ส่งมาให้ตรวจสอบ "
                    "ใช้ตัวเลขที่ระบุไว้ข้างหน้าแต่ละรายการ"
    )
    skill: str = Field(..., description="ชื่อ skill ที่ตรวจสอบ (เพื่อความชัดเจน)")
    evidence_is_valid: bool = Field(
        ..., description="true ถ้า evidence ที่อ้างมา ปรากฏอยู่จริงในข้อความ resume ต้นฉบับ "
                          "false ถ้าไม่พบข้อความนี้ใน resume เลย (ถือว่าเป็นการ hallucinate)"
    )
    reason: str = Field(..., description="เหตุผลสั้นๆ ว่าทำไมถึงตัดสินแบบนี้")


class JudgeResult(BaseModel):
    verified_matches: list[VerifiedMatch] = Field(
        default_factory=list, description="ผลตรวจสอบ evidence ทีละ skill match"
    )


SYSTEM_PROMPT = """คุณคือ Judge Agent - ด่านตรวจสอบคุณภาพสุดท้ายของระบบ
หน้าที่ของคุณคือตรวจสอบว่า evidence ที่แต่ละ skill match อ้างถึง มีอยู่จริงในข้อความ resume ต้นฉบับหรือไม่

กฎสำคัญ (เข้มงวดมาก เพราะนี่คือด่านป้องกัน hallucination):
1. รายการ skill match แต่ละรายการจะมีหมายเลข [index] กำกับ — ให้ตอบกลับด้วย skill_index ตัวเลขนั้นเสมอ (สำคัญมาก)
2. เทียบข้อความ evidence ที่ระบุมา กับข้อความ resume ต้นฉบับที่ให้มา
3. evidence_is_valid = true ก็ต่อเมื่อ ข้อความ evidence นั้น (หรือเนื้อความที่ตรงกันมาก) ปรากฏอยู่จริงในข้อความ resume
4. evidence_is_valid = false ถ้า:
   - หาข้อความนั้นในเรซูเม่ไม่เจอเลย
   - evidence เป็นการสรุป/ตีความเกินกว่าที่ resume ระบุจริง
   - evidence เป็น null แต่ status ของ match บอกว่า "met" หรือ "partial" (ต้องมี evidence เสมอถ้าไม่ใช่ missing)
5. ถ้า match เดิม status เป็น "missing" และ evidence เป็น null อยู่แล้ว ให้ถือว่า valid โดยอัตโนมัติ (ไม่มีอะไรต้องตรวจ)
6. ตรวจสอบอย่างเข้มงวด ห้ามผ่อนปรน เพราะเป้าหมายคือป้องกันไม่ให้รายงานส่งข้อมูลเท็จออกไป
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
    return client.chat.completions.create(
        model=model,
        response_model=response_model,
        messages=messages,
    )


def judge_matches(
    matches: list[SkillMatch],
    original_resume_text: str,
    model: str = "gemini-flash-latest",
) -> list[SkillMatch]:
    """
    ตรวจสอบทุก match ว่า evidence มีจริงใน resume ต้นฉบับไหม
    ถ้าไม่จริง -> ปรับ match นั้นเป็น status="missing", evidence=None

    การ lookup ใช้ index (ตัวเลข) ไม่ใช่ชื่อ skill string เพื่อป้องกัน
    mismatch หลังผ่าน skill normalization

    ถ้า LLM ตอบกลับ verdict ไม่ครบ — raise ValueError ทันที ไม่เดา default
    (ตาม PRD: "Judge rejects matches without resume evidence" — ถ้าไม่รู้ ต้องรู้ ไม่ใช่เดา)

    Args:
        matches: ผลเทียบ skill ทั้งหมดจาก Fit Analyzer
        original_resume_text: ข้อความ resume ต้นฉบับ
        model: ชื่อโมเดล Gemini ที่จะใช้

    Returns:
        list[SkillMatch]: matches ที่ผ่านการตรวจสอบแล้ว (ตัวที่ evidence ปลอมจะถูกแก้เป็น missing)

    Raises:
        ValueError: ถ้า LLM ตอบ verdict ไม่ครบตามจำนวน matches ที่ส่งไป
    """
    if not matches:
        return []

    client = get_client()

    # สร้างรายการพร้อม index กำกับ เพื่อให้ LLM ตอบกลับด้วย index แทนชื่อ
    indexed_matches = [
        {"index": i, "skill": m.skill, "status": m.status, "evidence": m.evidence}
        for i, m in enumerate(matches)
    ]

    user_content = f"""
ข้อความ Resume ต้นฉบับ:
{original_resume_text}

รายการ Skill Match ที่ต้องตรวจสอบ (แต่ละรายการมี [index] กำกับ — ต้องตอบกลับครบทุกรายการด้วย skill_index ตัวนั้น):
{indexed_matches}

กรุณาตรวจสอบทีละรายการ และให้ผลลัพธ์ตาม schema ที่กำหนด (ครบ {len(matches)} รายการ)
"""

    judge_result = _call_llm_with_retry(
        client=client,
        model=model,
        response_model=JudgeResult,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    # ตรวจสอบความครบถ้วนก่อนใช้ผลลัพธ์ — ไม่เดา default ไม่ว่าทิศทางไหน
    n_expected = len(matches)
    n_returned = len(judge_result.verified_matches)
    if n_returned != n_expected:
        raise ValueError(
            f"Judge Agent ตอบกลับไม่ครบ: ส่งไป {n_expected} รายการ "
            f"แต่ได้ verdict กลับมาแค่ {n_returned} รายการ "
            f"— ต้อง retry ไม่ใช่เดา default"
        )

    # Build lookup ด้วย index — ชื่อ skill ไม่ต้องตรงเป๊ะ
    verdict_by_index: dict[int, bool] = {}
    for v in judge_result.verified_matches:
        verdict_by_index[v.skill_index] = v.evidence_is_valid

    corrected_matches: list[SkillMatch] = []
    for i, m in enumerate(matches):
        is_valid = verdict_by_index.get(i, False)  # ถ้า index หายไปจาก dict (จำนวนครบแล้วแต่ index ผิด) → conservative
        if is_valid:
            corrected_matches.append(m)
        else:
            corrected_matches.append(
                SkillMatch(
                    skill=m.skill,
                    status="missing",
                    evidence=None,
                    years_found=None,
                )
            )

    return corrected_matches


def build_final_report(
    verified_matches: list[SkillMatch],
    must_have_score: int,
    nice_to_have_score: int,
    fit_score: int,
    gaps: list[str],
    suggested_interview_questions: list[str],
) -> FitReport:
    """ประกอบผลลัพธ์จากทุก agent เป็น FitReport สุดท้าย พร้อม bias_disclaimer อัตโนมัติ"""
    return FitReport(
        fit_score=fit_score,
        must_have_score=must_have_score,
        nice_to_have_score=nice_to_have_score,
        matches=verified_matches,
        gaps=gaps,
        suggested_interview_questions=suggested_interview_questions,
    )


# ---------------------------------------------------------
# ทดสอบด้วยตัวเอง: python agents/judge_agent.py
# รัน pipeline เต็มรูปแบบ: resume -> jd -> fit -> gap -> judge -> final report
# ---------------------------------------------------------
if __name__ == "__main__":
    from resume_extractor import extract_resume
    from jd_extractor import extract_jd
    from fit_analyzer import analyze_fit
    from gap_agent import analyze_gaps

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
    print("เสร็จแล้ว\n")

    print("ขั้นที่ 5: ตรวจสอบหลักฐาน (Judge Agent)...")
    verified_matches = judge_matches(fit_result.matches, sample_resume)
    print("เสร็จแล้ว\n")

    print("ประกอบรายงานสุดท้าย...\n")
    final_report = build_final_report(
        verified_matches=verified_matches,
        must_have_score=fit_result.must_have_score,
        nice_to_have_score=fit_result.nice_to_have_score,
        fit_score=fit_result.fit_score,
        gaps=gap_result.gaps,
        suggested_interview_questions=gap_result.suggested_interview_questions,
    )

    print("=" * 50)
    print("FIT REPORT ฉบับสมบูรณ์")
    print("=" * 50)
    print(final_report.model_dump_json(indent=2, ensure_ascii=False))
