"""
main.py

FastAPI stub สำหรับ Iteration 1 (v0.1.0 "Walking skeleton")
ตาม PRD-6 API Contract:
    POST /fit/analyze  -> Resume + JD text -> FitReport
    POST /fit/batch    -> Batch screening -> list[FitReport]
    POST /evaluate     -> คืนค่า metrics เทียบกับ gold labels

ตาม requirement ของ Iteration 1: ยังไม่ต้องเรียก LLM จริง แค่ต้อง
"return a valid Pydantic response" ที่ตรง schema เพื่อพิสูจน์ว่าโครง API ถูกต้อง
Iteration 2 ค่อยเปลี่ยนจาก mock เป็นเรียก agent จริง (resume_extractor, jd_extractor, ...)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from schemas import FitReport, SkillMatch

app = FastAPI(
    title="Resume <-> JD Fit Analyzer API",
    description="PRD-6: วิเคราะห์ความเหมาะสมระหว่าง resume และ job description แบบมีหลักฐานอ้างอิง",
    version="0.1.0",
)


# ---------------------------------------------------------
# Request schemas (ฝั่งรับ input จาก client)
# ---------------------------------------------------------
class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., description="เนื้อหา resume แบบ plain text")
    jd_text: str = Field(..., description="เนื้อหา job description แบบ plain text")


class BatchAnalyzeRequest(BaseModel):
    pairs: list[AnalyzeRequest] = Field(..., description="รายการคู่ resume-JD ที่จะวิเคราะห์พร้อมกัน")


class EvaluateRequest(BaseModel):
    dataset_name: str = Field(
        default="gold_dataset_final",
        description="ชื่อชุดข้อมูล gold ที่จะใช้ประเมิน (ปัจจุบันรองรับแค่ gold set เดียว)",
    )


class EvaluateResponse(BaseModel):
    skill_extraction_f1: float = Field(..., description="F1 score ของการดึงทักษะ เทียบ gold")
    must_have_match_accuracy: float = Field(..., description="% ความแม่นยำของ must-have match (เป้าหมาย >= 80%)")
    unsupported_match_claims_rate: float = Field(..., description="% ของ match ที่ไม่มีหลักฐานรองรับ (เป้าหมาย <= 10%)")
    score_mae: float = Field(..., description="Mean Absolute Error ของ fit_score เทียบ gold")
    n_samples_evaluated: int = Field(..., description="จำนวนคู่ resume-JD ที่ใช้ประเมิน")


# ---------------------------------------------------------
# Mock data: ตัวอย่าง FitReport ที่ "hard-coded" ไว้ล่วงหน้า
# (อิงจากรูปแบบจริงที่จะได้จาก pipeline ใน Iteration 2 แต่ยังไม่เรียก LLM จริงตอนนี้)
# ---------------------------------------------------------
def _build_mock_fit_report() -> FitReport:
    return FitReport(
        fit_score=88,
        must_have_score=92,
        nice_to_have_score=80,
        matches=[
            SkillMatch(
                skill="Financial planning & analysis",
                status="met",
                evidence="5+ years of financial planning and analysis experience in IT budget management",
                years_found=5.0,
            ),
            SkillMatch(
                skill="Sarbanes-Oxley (SOX) audit",
                status="met",
                evidence="Led SOX audit documentation and control testing for three consecutive fiscal years",
                years_found=3.0,
            ),
            SkillMatch(
                skill="Executive presentation",
                status="partial",
                evidence="Presented quarterly budget summaries to department leads",
                years_found=None,
            ),
            SkillMatch(
                skill="Capital budget cycle development",
                status="missing",
                evidence=None,
                years_found=None,
            ),
        ],
        gaps=["Capital budget cycle development"],
        suggested_interview_questions=[
            "คุณเคยมีส่วนร่วมในการพัฒนา capital budget cycle ทั้งกระบวนการหรือไม่ ถ้ายัง เคยเห็นหรือเรียนรู้จากที่ไหนบ้าง",
        ],
    )


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@app.get("/")
def root():
    """Health check ง่ายๆ เช็คว่า server รันอยู่"""
    return {"status": "ok", "service": "resume-jd-fit-analyzer", "version": "0.1.0"}


@app.post("/fit/analyze", response_model=FitReport)
def analyze(request: AnalyzeRequest) -> FitReport:
    """
    รับ resume + JD (text) -> คืน FitReport

    Iteration 1: คืน mock response เสมอ (ไม่สนใจเนื้อหาจริงของ request)
    Iteration 2: จะเปลี่ยนมาเรียก resume_extractor -> jd_extractor -> fit_analyzer
                 -> gap_agent -> judge_agent ตามลำดับจริง
    """
    if not request.resume_text.strip() or not request.jd_text.strip():
        raise HTTPException(status_code=400, detail="resume_text และ jd_text ต้องไม่ว่างเปล่า")

    return _build_mock_fit_report()


@app.post("/fit/batch", response_model=list[FitReport])
def analyze_batch(request: BatchAnalyzeRequest) -> list[FitReport]:
    """
    รับหลายคู่ resume-JD พร้อมกัน -> คืน list ของ FitReport

    Iteration 1: คืน mock response ตัวเดียวกันซ้ำตามจำนวนคู่ที่ส่งมา
    """
    if not request.pairs:
        raise HTTPException(status_code=400, detail="ต้องส่งอย่างน้อย 1 คู่ resume-JD")

    return [_build_mock_fit_report() for _ in request.pairs]


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(request: EvaluateRequest) -> EvaluateResponse:
    """
    รันประเมินผลเทียบกับ gold dataset -> คืนค่า metrics

    Iteration 1: คืนตัวเลข mock (สะท้อนผลจริงที่เคยรันไว้ล่าสุด เพื่อให้ response shape ถูกต้อง)
    Iteration 2: จะเปลี่ยนมาเรียก tests/evaluate_gold.py จริงแบบ async หรือ background task
    """
    return EvaluateResponse(
        skill_extraction_f1=0.0,  # ยังไม่ได้คำนวณจริงใน Iteration 1
        must_have_match_accuracy=39.73,
        unsupported_match_claims_rate=5.56,
        score_mae=12.0,
        n_samples_evaluated=15,
    )


# ---------------------------------------------------------
# รันด้วย: uvicorn main:app --reload
# แล้วเปิด http://127.0.0.1:8000/docs เพื่อดู interactive API docs (Swagger UI)
# ---------------------------------------------------------
