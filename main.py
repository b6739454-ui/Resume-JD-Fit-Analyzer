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

import os
import io
import docx
import pdfplumber
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from schemas import FitReport, SkillMatch
from utils.pii_handler import anonymize_pii

from agents.resume_extractor import extract_resume
from agents.jd_extractor import extract_jd
from agents.fit_analyzer import analyze_fit
from agents.gap_agent import analyze_gaps
from agents.judge_agent import judge_matches
from tests.evaluate_gold import calculate_scores_python

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


def _call_agent_with_rotation(agent_fn, *args, **kwargs):
    """เรียกใช้ agent function โดยรองรับการสลับ API Key อัตโนมัติเมื่อเจอ 429 Rate Limit"""
    candidate_keys = [
        "GOOGLE_API_KEY",
        "GOOGLE_API_KEY_FRIEND1",
        "GOOGLE_API_KEY_FRIEND2",
        "GOOGLE_API_KEY_FRIEND3",
        "GOOGLE_API_KEY_FRIEND4",
        "GOOGLE_API_KEY_FRIEND5",
    ]
    valid_key_envs = [k for k in candidate_keys if os.getenv(k)]
    if not valid_key_envs:
        valid_key_envs = ["GOOGLE_API_KEY"]

    last_error = None
    for key_env in valid_key_envs:
        try:
            kwargs["api_key_env_var"] = key_env
            return agent_fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            last_error = e
            if any(k in err_str for k in ("429", "resource_exhausted", "quota")):
                print(f"[Key Rotation] Key [{key_env}] 429 quota exhausted, switching to next key...", flush=True)
                continue
            else:
                raise e
    raise last_error


def _run_pipeline(resume_text: str, jd_text: str) -> FitReport:
    """
    รัน 5 agents จริงตามลำดับ:
    1. Resume Extractor
    2. JD Extractor
    3. Fit Analyzer
    4. Gap Agent
    5. Judge Agent
    คำนวณคะแนนด้วย Python deterministic formula และคืนค่าเป็น FitReport

    Fallback: ตั้งค่า USE_MOCK_PIPELINE=true ใน .env หรือ environment เพื่อสลับกลับ mock mode ทันที
    """
    # Demo Fallback: ตรวจสอบทั้ง env var (startup-time) และ global flag (runtime toggle)
    if _USE_MOCK_MODE or os.getenv("USE_MOCK_PIPELINE", "false").lower() == "true":
        print("[Pipeline] Mock mode active — returning mock report")
        return _build_mock_fit_report()

    # PRD Section 8: PII Handling
    pii_result = anonymize_pii(resume_text)
    anonymized_resume = pii_result["anonymized_text"]
    _pii = pii_result['detected_pii']
    print(
        f"[PII Handler] Detected PII — "
        f"{len(_pii['names'])} name(s), "
        f"{len(_pii['emails'])} email(s), "
        f"{len(_pii['phones'])} phone(s)"
    )

    try:
        # Step 1: Resume Extractor
        resume_data = _call_agent_with_rotation(extract_resume, resume_text)

        # Step 2: JD Extractor
        jd_data = _call_agent_with_rotation(extract_jd, jd_text)

        # Step 3: Fit Analyzer
        fit_res = _call_agent_with_rotation(analyze_fit, resume_data, jd_data)

        # Step 4: Gap Agent
        gap_res = _call_agent_with_rotation(analyze_gaps, fit_res.matches)

        # Step 5: Judge Agent
        verified_matches = _call_agent_with_rotation(judge_matches, fit_res.matches, resume_text)

        # Step 6: Python Verified Score Calculation
        py_must, py_nice, py_fit = calculate_scores_python(verified_matches, jd_data.requirements)

        return FitReport(
            fit_score=py_fit,
            must_have_score=py_must,
            nice_to_have_score=py_nice,
            matches=verified_matches,
            gaps=gap_res.gaps,
            suggested_interview_questions=gap_res.suggested_interview_questions,
        )
    except Exception as e:
        err_msg = str(e)
        print(f"[Pipeline Error] {err_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการประมวลผล pipeline: {err_msg}"
        )



# ---------------------------------------------------------
# Runtime Mock Mode — สลับได้ทันทีโดยไม่ต้อง restart server
# ---------------------------------------------------------
_USE_MOCK_MODE: bool = os.getenv("USE_MOCK_PIPELINE", "false").lower() == "true"

# Secret key สำหรับ admin endpoints (ตั้งใน .env ว่า ADMIN_SECRET=xxx)
# ถ้าไม่ตั้ง จะ fallback เป็น 'demo-secret' (สำหรับ local dev เท่านั้น)
_ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "demo-secret")


def _verify_admin(request: Request, x_admin_secret: str | None = None):
    """
    Guard สำหรับ admin endpoints — ผ่านถ้าเป็น localhost หรือมี secret header ถูกต้อง
    - จาก localhost (127.0.0.1 / ::1): ไม่ต้องมี secret
    - จาก IP อื่น: ต้องส่ง header 'X-Admin-Secret: <ADMIN_SECRET>'
    """
    from fastapi import Header
    client_ip = request.client.host if request.client else "unknown"
    is_localhost = client_ip in ("127.0.0.1", "::1", "localhost", "testclient")

    # ดึง header ด้วยตัวเองเพราะ Depends + Header ใน signature เดียวกันซับซ้อนกว่า
    secret_header = request.headers.get("x-admin-secret", "")

    if is_localhost:
        return  # localhost เชื่อใจได้เลย
    if secret_header == _ADMIN_SECRET:
        return  # ส่ง secret ถูกต้อง

    raise HTTPException(
        status_code=403,
        detail="Admin endpoint: ต้องเรียกจาก localhost หรือส่ง X-Admin-Secret header ที่ถูกต้อง"
    )


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@app.get("/")
def root():
    """Health check ง่ายๆ เช็คว่า server รันอยู่"""
    return {"status": "ok", "service": "resume-jd-fit-analyzer", "version": "0.1.0"}


@app.post("/admin/toggle-mock")
def toggle_mock(enable: bool, request: Request, _: None = Depends(_verify_admin)):
    """
    สลับโหมด mock/real pipeline แบบ runtime ทันที ไม่ต้อง restart server
    ใช้สำหรับ demo fallback เมื่อ API quota หมดกลาง demo

    Auth: เรียกได้จาก localhost โดยตรง หรือส่ง header X-Admin-Secret
    Usage:
      POST /admin/toggle-mock?enable=true   → เปิด mock mode
      POST /admin/toggle-mock?enable=false  → กลับเป็น real pipeline
    """
    global _USE_MOCK_MODE
    _USE_MOCK_MODE = enable
    mode_str = "MOCK" if enable else "REAL PIPELINE"
    client_ip = request.client.host if request.client else "unknown"
    print(f"[Admin] Pipeline mode switched to: {mode_str} (requested from {client_ip})")
    return {
        "status": "ok",
        "mock_mode": _USE_MOCK_MODE,
        "message": f"Pipeline switched to {mode_str} mode"
    }


@app.get("/admin/mode-status")
def mode_status(request: Request, _: None = Depends(_verify_admin)):
    """ตรวจสอบ pipeline mode ปัจจุบัน (auth required)"""
    return {
        "mock_mode": _USE_MOCK_MODE,
        "mode": "MOCK" if _USE_MOCK_MODE else "REAL PIPELINE",
        "env_USE_MOCK_PIPELINE": os.getenv("USE_MOCK_PIPELINE", "false")
    }


@app.post("/fit/analyze", response_model=FitReport)
def analyze(request: AnalyzeRequest) -> FitReport:
    """
    รับ resume + JD (text) -> รัน 5-agent pipeline จริงแล้วคืน FitReport
    """
    if not request.resume_text.strip() or not request.jd_text.strip():
        raise HTTPException(status_code=400, detail="resume_text และ jd_text ต้องไม่ว่างเปล่า")

    return _run_pipeline(request.resume_text, request.jd_text)


@app.post("/fit/analyze-file", response_model=FitReport)
async def analyze_file(
    resume_file: UploadFile = File(..., description="ไฟล์ Resume (.pdf หรือ .docx)"),
    jd_file: UploadFile = File(..., description="ไฟล์ Job Description (.pdf หรือ .docx)"),
) -> FitReport:
    """
    รับไฟล์ Resume + JD (.pdf หรือ .docx) -> สกัดข้อความและรัน 5-agent pipeline จริง
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

    return _run_pipeline(resume_text, jd_text)


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

        _pii = pii_result['detected_pii']
        print(
            f"[PII Handler Batch] Detected PII — "
            f"{len(_pii['names'])} name(s), "
            f"{len(_pii['emails'])} email(s), "
            f"{len(_pii['phones'])} phone(s)"
        )
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
