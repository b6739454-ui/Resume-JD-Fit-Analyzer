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

import io
import docx
import pdfplumber
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from schemas import FitReport, SkillMatch
from utils.pii_handler import anonymize_pii

app = FastAPI(
    title="Resume <-> JD Fit Analyzer API",
    description="PRD-6: วิเคราะห์ความเหมาะสมระหว่าง resume และ job description แบบมีหลักฐานอ้างอิง",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    text_parts = []
    doc = docx.Document(io.BytesIO(file_bytes))
    for p in doc.paragraphs:
        if p.text.strip():
            text_parts.append(p.text.strip())
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    text_parts.append(cell.text.strip())
    return "\n".join(text_parts).strip()


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    ext = (filename or "").lower().split(".")[-1]
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return extract_text_from_docx(file_bytes)
    elif ext == "txt":
        return file_bytes.decode("utf-8", errors="ignore").strip()
    else:
        try:
            return extract_text_from_pdf(file_bytes)
        except Exception:
            return file_bytes.decode("utf-8", errors="ignore").strip()


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
                category="must_have",
                requirement_index=0,
            ),
            SkillMatch(
                skill="Sarbanes-Oxley (SOX) audit",
                status="met",
                evidence="Led SOX audit documentation and control testing for three consecutive fiscal years",
                years_found=3.0,
                category="must_have",
                requirement_index=1,
            ),
            SkillMatch(
                skill="Executive presentation",
                status="partial",
                evidence="Presented quarterly budget summaries to department leads",
                years_found=None,
                category="must_have",
                requirement_index=2,
            ),
            SkillMatch(
                skill="Capital budget cycle development",
                status="missing",
                evidence=None,
                years_found=None,
                category="must_have",
                requirement_index=3,
            ),
            SkillMatch(
                skill="Advanced Excel / VBA",
                status="met",
                evidence="Built automated Excel dashboards with VBA macros for month-end close",
                years_found=4.0,
                category="nice_to_have",
                requirement_index=4,
            ),
            SkillMatch(
                skill="Power BI or Tableau",
                status="partial",
                evidence="Basic familiarity with Power BI for reporting",
                years_found=None,
                category="nice_to_have",
                requirement_index=5,
            ),
            SkillMatch(
                skill="CPA certification",
                status="missing",
                evidence=None,
                years_found=None,
                category="nice_to_have",
                requirement_index=6,
            ),
        ],
        gaps=[
            "Capital budget cycle development",
            "CPA certification",
        ],
        suggested_interview_questions=[
            "คุณเคยมีส่วนร่วมในการพัฒนา capital budget cycle ทั้งกระบวนการหรือไม่ ถ้ายัง เคยเห็นหรือเรียนรู้จากที่ไหนบ้าง",
            "ปัจจุบันกำลังสอบหรือเตรียมตัวสอบ CPA certification อยู่หรือไม่ มีกรอบเวลาอย่างไร",
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

    # PRD Section 8: PII Handling
    # 1. Original resume_text is kept separated if needed for extraction
    original_resume_text = request.resume_text

    # 2. Anonymize PII before any logging / DB storage
    pii_result = anonymize_pii(original_resume_text)
    anonymized_resume_text = pii_result["anonymized_text"]

    # Safe logging (Anonymized version only)
    print(f"[PII Handler] Detected PII: {pii_result['detected_pii']}")
    print(f"[PII Handler] Anonymized Resume Text sample: {anonymized_resume_text[:100]}...")

    return _build_mock_fit_report()


@app.post("/fit/analyze-file", response_model=FitReport)
async def analyze_file(
    resume_file: UploadFile = File(..., description="ไฟล์ Resume (.pdf หรือ .docx)"),
    jd_file: UploadFile = File(..., description="ไฟล์ Job Description (.pdf หรือ .docx)"),
) -> FitReport:
    """
    รับไฟล์ Resume + JD (.pdf หรือ .docx) -> สกัดข้อความและวิเคราะห์ความเหมาะสม (FitReport)
    """
    resume_bytes = await resume_file.read()
    jd_bytes = await jd_file.read()

    try:
        resume_text = extract_text_from_file(resume_file.filename, resume_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"ไม่สามารถอ่านไฟล์ Resume '{resume_file.filename}' ได้: {str(e)}"
        )

    if not resume_text or not resume_text.strip():
        raise HTTPException(
            status_code=400,
            detail=f"ไม่สามารถดึงข้อความจากไฟล์ Resume '{resume_file.filename}' ได้ กรุณาตรวจสอบว่าเป็นไฟล์ที่มีข้อความ ไม่ใช่ภาพสแกน"
        )

    try:
        jd_text = extract_text_from_file(jd_file.filename, jd_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"ไม่สามารถอ่านไฟล์ JD '{jd_file.filename}' ได้: {str(e)}"
        )

    if not jd_text or not jd_text.strip():
        raise HTTPException(
            status_code=400,
            detail=f"ไม่สามารถดึงข้อความจากไฟล์ JD '{jd_file.filename}' ได้ กรุณาตรวจสอบว่าเป็นไฟล์ที่มีข้อความ ไม่ใช่ภาพสแกน"
        )

    # PRD Section 8: PII Handling
    pii_result = anonymize_pii(resume_text)
    print(f"[PII Handler] Detected PII: {pii_result['detected_pii']}")

    return _build_mock_fit_report()


@app.post("/fit/batch", response_model=list[FitReport])
def analyze_batch(request: BatchAnalyzeRequest) -> list[FitReport]:
    """
    รับหลายคู่ resume-JD พร้อมกัน -> คืน list ของ FitReport

    Iteration 1: คืน mock response ตัวเดียวกันซ้ำตามจำนวนคู่ที่ส่งมา
    """
    if not request.pairs:
        raise HTTPException(status_code=400, detail="ต้องส่งอย่างน้อย 1 คู่ resume-JD")

    results = []
    for pair in request.pairs:
        if not pair.resume_text.strip() or not pair.jd_text.strip():
            raise HTTPException(status_code=400, detail="resume_text และ jd_text ต้องไม่ว่างเปล่า")

        # PRD Section 8: PII Handling
        original_resume_text = pair.resume_text
        pii_result = anonymize_pii(original_resume_text)
        anonymized_resume_text = pii_result["anonymized_text"]

        print(f"[PII Handler Batch] Detected PII: {pii_result['detected_pii']}")
        results.append(_build_mock_fit_report())

    return results



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
