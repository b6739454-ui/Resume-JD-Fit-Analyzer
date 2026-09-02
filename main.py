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
import time
import io
import json
import hashlib
import logging
import docx
import pdfplumber
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from schemas import FitReport, SkillMatch
from utils.pii_handler import anonymize_pii

from agents.resume_extractor import extract_resume, SYSTEM_PROMPT as RESUME_EXTRACTOR_PROMPT
from agents.jd_extractor import extract_jd, SYSTEM_PROMPT as JD_EXTRACTOR_PROMPT
from agents.fit_analyzer import analyze_fit, analyze_fit_and_gaps
from agents.gap_agent import analyze_gaps
from agents.judge_agent import judge_matches
from tests.evaluate_gold import calculate_scores_python

logger = logging.getLogger(__name__)


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
# Extraction Cache — ใช้ SHA-256 hash ของ resume+jd text เป็น key
# Shared cache กับ evaluate_gold.py เพื่อประโยชน์ตอนซ้อม demo ด้วย gold dataset
# ตั้ง EXTRACTION_CACHE_ENABLED=false ใน .env เพื่อปิด cache
# ---------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_EXTRACTION_CACHE_PATH = os.getenv(
    "EXTRACTION_CACHE_PATH",
    os.path.join(_PROJECT_ROOT, "tests", "extraction_cache.json")
)
_CACHE_ENABLED: bool = os.getenv("EXTRACTION_CACHE_ENABLED", "true").lower() == "true"

# คำนวณ prompt hash สำหรับ cache invalidation (เหมือน evaluate_gold.py)
def _get_api_prompt_hash() -> str:
    combined = (RESUME_EXTRACTOR_PROMPT + JD_EXTRACTOR_PROMPT).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()[:16]

_CURRENT_PROMPT_HASH: str = _get_api_prompt_hash()

# โหลด cache เข้า memory ตอน startup
_extraction_cache: dict = {}
if _CACHE_ENABLED and os.path.exists(_EXTRACTION_CACHE_PATH):
    try:
        with open(_EXTRACTION_CACHE_PATH, "r", encoding="utf-8") as _f:
            _raw = json.load(_f)
        if _raw.get("__prompt_hash__") == _CURRENT_PROMPT_HASH:
            _extraction_cache = {k: v for k, v in _raw.items() if not k.startswith("__")}
            print(
                f"[ExtractionCache] ✅ โหลด cache สำเร็จ ({len(_extraction_cache)} pairs) "
                f"[prompt hash: {_CURRENT_PROMPT_HASH}]"
            )
        else:
            print(
                f"[ExtractionCache] ⚠️ Prompt hash เปลี่ยน "
                f"(เก่า: {_raw.get('__prompt_hash__')} → ใหม่: {_CURRENT_PROMPT_HASH}) "
                f"— cache ถูก invalidate"
            )
    except Exception as _e:
        print(f"[ExtractionCache] ⚠️ อ่าน cache ไม่สำเร็จ: {_e}")


def _save_extraction_cache() -> None:
    """บันทึก _extraction_cache ลง disk (เรียกหลัง cache miss ทุกครั้ง)"""
    if not _CACHE_ENABLED:
        return
    try:
        os.makedirs(os.path.dirname(_EXTRACTION_CACHE_PATH), exist_ok=True)
        to_save = {"__prompt_hash__": _CURRENT_PROMPT_HASH, **_extraction_cache}
        with open(_EXTRACTION_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ExtractionCache] ⚠️ บันทึก cache ไม่สำเร็จ: {e}")


def _make_cache_key(resume_text: str, jd_text: str) -> str:
    """สร้าง cache key จาก SHA-256 ของ resume + jd text"""
    combined = (resume_text.strip() + "\n|||JD|||\n" + jd_text.strip()).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()[:16]


# Merged Gap Agent feature flag
# ✅ ผ่านการทดสอบกับ Gold Dataset 15/15 คู่ (Must-Have Accuracy: 58.18% >= 55.2%, Unsupported Rate ลดลงเหลือ 3.57%)
# Default: true (ประหยัด 1 LLM call ~20% quota) | ตั้ง MERGED_GAP_AGENT=false ใน .env เพื่อ rollback
_MERGED_GAP_AGENT: bool = os.getenv("MERGED_GAP_AGENT", "true").lower() == "true"


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
    """เรียกใช้ agent function โดยรองรับการ retry พร้อม delay และสลับ API Key อัตโนมัติเมื่อเจอ 429/503"""
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
        kwargs["api_key_env_var"] = key_env
        # ลองสูงสุด 2 ครั้งต่อ key พร้อมรอ 2 วินาทีหากเจอ 503/429
        for attempt in range(2):
            try:
                return agent_fn(*args, **kwargs)
            except Exception as e:
                err_str = str(e).lower()
                last_error = e
                if any(k in err_str for k in ("429", "503", "resource_exhausted", "quota", "unavailable", "service_unavailable")):
                    print(f"[Key Rotation] Key [{key_env}] attempt {attempt+1} encountered 503/rate limit. Retrying in 2s...", flush=True)
                    time.sleep(2)
                    continue
                else:
                    raise e
    raise last_error


def _run_pipeline(resume_text: str, jd_text: str) -> FitReport:
    """
    รัน agents จริงตามลำดับ พร้อม:
    - Extraction Cache: ถ้า resume+jd text เดิมเคยถูกวิเคราะห์ไปแล้ว ดึง resume_data/jd_data
      จาก cache แทนเรียก LLM ซ้ำ (ประหยัด ~40% ตอนซ้อม demo)
    - Merged Gap Agent: ถ้า MERGED_GAP_AGENT=true (default) ใช้ analyze_fit_and_gaps()
      แทน analyze_fit() + analyze_gaps() แยกกัน (ประหยัด ~20% quota)
    - Pipeline Timing: log เวลาแต่ละ step + เวลารวม

    Fallback: ตั้งค่า USE_MOCK_PIPELINE=true ใน .env เพื่อสลับกลับ mock mode ทันที
    """
    _t_pipeline_start = time.perf_counter()

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
        # ── Extraction Cache ────────────────────────────────────────────────
        cache_key = _make_cache_key(resume_text, jd_text)
        cached_extraction = _extraction_cache.get(cache_key) if _CACHE_ENABLED else None

        if cached_extraction:
            print(f"[ExtractionCache] ✅ HIT (key={cache_key}) — ข้าม Resume/JD Extractor LLM call", flush=True)
            from schemas import ResumeData, JDData
            resume_data = ResumeData.model_validate(cached_extraction["resume_data"])
            jd_data = JDData.model_validate(cached_extraction["jd_data"])
        else:
            if _CACHE_ENABLED:
                print(f"[ExtractionCache] MISS (key={cache_key}) — จะเรียก LLM extractors", flush=True)

            # Step 1: Resume Extractor
            _t1 = time.perf_counter()
            resume_data = _call_agent_with_rotation(extract_resume, resume_text)
            print(f"[Pipeline] Step 1 Resume Extractor: {time.perf_counter()-_t1:.1f}s", flush=True)

            # Step 2: JD Extractor
            _t2 = time.perf_counter()
            jd_data = _call_agent_with_rotation(extract_jd, jd_text)
            print(f"[Pipeline] Step 2 JD Extractor: {time.perf_counter()-_t2:.1f}s", flush=True)

            # บันทึกผล extraction ลง cache
            if _CACHE_ENABLED:
                _extraction_cache[cache_key] = {
                    "resume_data": resume_data.model_dump(),
                    "jd_data": jd_data.model_dump(),
                }
                _save_extraction_cache()
                print(f"[ExtractionCache] 💾 บันทึก cache key={cache_key}", flush=True)

        # ── Fit Analyzer + Gap Agent ────────────────────────────────────────
        _t3 = time.perf_counter()
        if _MERGED_GAP_AGENT:
            # Merged mode: 1 LLM call แทน 2 calls — ประหยัด ~20% quota
            print("[Pipeline] Step 3+4 Fit Analyzer + Gap Agent (merged): กำลังวิเคราะห์...", flush=True)
            fit_res, gap_res = _call_agent_with_rotation(analyze_fit_and_gaps, resume_data, jd_data)
            print(f"[Pipeline] Step 3+4 Fit+Gap (merged): {time.perf_counter()-_t3:.1f}s", flush=True)
        else:
            # Fallback: แบบเดิม 2 calls แยกกัน
            print("[Pipeline] Step 3 Fit Analyzer: กำลังวิเคราะห์...", flush=True)
            fit_res = _call_agent_with_rotation(analyze_fit, resume_data, jd_data)
            print(f"[Pipeline] Step 3 Fit Analyzer: {time.perf_counter()-_t3:.1f}s", flush=True)

            _t4 = time.perf_counter()
            print("[Pipeline] Step 4 Gap Agent: กำลังวิเคราะห์...", flush=True)
            gap_res = _call_agent_with_rotation(analyze_gaps, fit_res.matches)
            print(f"[Pipeline] Step 4 Gap Agent: {time.perf_counter()-_t4:.1f}s", flush=True)

        # ── Judge Agent ────────────────────────────────────────────────────
        _t5 = time.perf_counter()
        print("[Pipeline] Step 5 Judge Agent: กำลังตรวจสอบหลักฐาน...", flush=True)
        verified_matches = _call_agent_with_rotation(judge_matches, fit_res.matches, resume_text)
        print(f"[Pipeline] Step 5 Judge Agent: {time.perf_counter()-_t5:.1f}s", flush=True)

        # ── Python Verified Score Calculation ──────────────────────────────
        py_must, py_nice, py_fit = calculate_scores_python(verified_matches, jd_data.requirements)

        _t_total = time.perf_counter() - _t_pipeline_start
        print(
            f"[Pipeline] ✅ เสร็จสิ้น — รวมเวลา {_t_total:.1f}s | "
            f"fit_score={py_fit} must={py_must} nice={py_nice} | "
            f"cache={'HIT' if cached_extraction else 'MISS'} | "
            f"merged_gap={_MERGED_GAP_AGENT}",
            flush=True
        )

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
        _t_total = time.perf_counter() - _t_pipeline_start
        print(f"[Pipeline Error] หลัง {_t_total:.1f}s — {err_msg}")
        if "503" in err_msg or "unavailable" in err_msg.lower() or "high demand" in err_msg.lower():
            raise HTTPException(
                status_code=503,
                detail="Google Gemini API กำลังมีผู้ใช้งานจำนวนมากชั่วคราว (503 High Demand) กรุณารอ 5-10 วินาทีแล้วลองใหม่อีกครั้ง หรือเปิดใช้งาน Mock Mode (POST /admin/toggle-mock?enable=true) เพื่อทดสอบหน้าเว็บ"
            )
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการประมวลผล pipeline: {err_msg}"
        )


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
