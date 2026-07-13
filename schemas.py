"""
schemas.py
Pydantic data models สำหรับโปรเจกต์ Resume <-> JD Fit Analyzer
ทุก Agent (Resume Extractor, JD Extractor, Fit Analyzer, Gap Agent, Judge Agent)
ใช้ schema ชุดนี้ร่วมกัน เพื่อให้ output ของแต่ละ agent ส่งต่อกันได้ตรง format เสมอ
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional


# ---------------------------------------------------------
# 1. JD-side schema: ความต้องการของ Job Description แต่ละ skill
# ---------------------------------------------------------
class SkillRequirement(BaseModel):
    skill: str = Field(..., description="ชื่อ skill ที่ JD ต้องการ เช่น 'Python', 'Project Management'")
    priority: Literal["must_have", "nice_to_have"] = Field(
        ..., description="ระดับความจำเป็นของ skill นี้ตาม JD"
    )
    min_years: Optional[float] = Field(
        None, description="จำนวนปีประสบการณ์ขั้นต่ำที่ JD ระบุ (ถ้ามี)"
    )


# ---------------------------------------------------------
# 1b. Resume-side schema: ข้อมูลดิบที่ดึงออกมาจาก resume
#     (output ของ Resume Extractor agent)
# ---------------------------------------------------------
class ResumeSkill(BaseModel):
    skill: str = Field(..., description="ชื่อ skill ที่พบใน resume")
    years: Optional[float] = Field(None, description="จำนวนปีประสบการณ์ที่ระบุ/ประเมินได้ (ถ้ามี)")
    evidence: str = Field(..., description="ข้อความต้นฉบับใน resume ที่พบ skill นี้ (ต้องมีเสมอ ห้ามแต่งเอง)")


class WorkExperience(BaseModel):
    role: str = Field(..., description="ตำแหน่งงาน")
    company: Optional[str] = Field(None, description="ชื่อบริษัท (ถ้าระบุ)")
    years: Optional[float] = Field(None, description="ระยะเวลาทำงานในตำแหน่งนี้ (ปี)")
    description: Optional[str] = Field(None, description="สรุปหน้าที่/ผลงานสั้นๆ")


class ResumeData(BaseModel):
    skills: list[ResumeSkill] = Field(default_factory=list, description="รายการ skill ทั้งหมดที่พบใน resume")
    work_experience: list[WorkExperience] = Field(
        default_factory=list, description="ประวัติการทำงานที่พบใน resume"
    )
    total_years_experience: Optional[float] = Field(
        None, description="ประสบการณ์ทำงานรวมโดยประมาณ (ปี)"
    )
    education: list[str] = Field(default_factory=list, description="วุฒิการศึกษาที่พบใน resume")


# ---------------------------------------------------------
# 1c. JD-side wrapper schema: ผลลัพธ์รวมทั้งหมดจาก JD Extractor
# ---------------------------------------------------------
class JDData(BaseModel):
    job_title: Optional[str] = Field(None, description="ชื่อตำแหน่งงานตามที่ระบุใน JD")
    requirements: list[SkillRequirement] = Field(
        default_factory=list, description="รายการ skill requirement ทั้งหมดที่ JD ระบุ"
    )
    overall_min_years: Optional[float] = Field(
        None, description="จำนวนปีประสบการณ์รวมขั้นต่ำที่ JD ต้องการ (ถ้าระบุแยกจาก skill ใดๆ)"
    )


# ---------------------------------------------------------
# 2. ผลการจับคู่ resume กับแต่ละ skill requirement
# ---------------------------------------------------------
class SkillMatch(BaseModel):
    skill: str = Field(..., description="ชื่อ skill ที่กำลังเทียบ")
    status: Literal["met", "partial", "missing"] = Field(
        ..., description="ผลเทียบ: met=มีครบ, partial=มีบางส่วน, missing=ไม่มีเลย"
    )
    evidence: Optional[str] = Field(
        None, description="ข้อความอ้างอิงจาก resume ที่สนับสนุน status นี้ (สำคัญมาก — Judge Agent ต้องเช็คว่ามีจริง)"
    )
    years_found: Optional[float] = Field(
        None, description="จำนวนปีประสบการณ์ที่พบจริงใน resume สำหรับ skill นี้"
    )


# ---------------------------------------------------------
# 3. ผลลัพธ์สุดท้ายที่ระบบส่งออก (จาก Fit Analyzer + Gap Agent + Judge Agent)
# ---------------------------------------------------------
class FitReport(BaseModel):
    fit_score: int = Field(..., ge=0, le=100, description="คะแนนความเหมาะสมโดยรวม 0-100")
    must_have_score: int = Field(..., ge=0, le=100, description="คะแนนเฉพาะส่วน must-have skills")
    nice_to_have_score: int = Field(..., ge=0, le=100, description="คะแนนเฉพาะส่วน nice-to-have skills")
    matches: list[SkillMatch] = Field(default_factory=list, description="รายละเอียดผลจับคู่ทุก skill")
    gaps: list[str] = Field(default_factory=list, description="รายชื่อ skill ที่ขาด (จาก Gap Agent)")
    suggested_interview_questions: list[str] = Field(
        default_factory=list, description="คำถามสัมภาษณ์ที่แนะนำ โดยเฉพาะจุดที่เป็น gap"
    )
    bias_disclaimer: str = Field(
        default="รายงานนี้เป็นเครื่องมือช่วยตัดสินใจเบื้องต้นเท่านั้น ไม่ใช่การตัดสินรับ/ไม่รับที่เป็นทางการ "
                "ผู้ใช้ควรพิจารณาปัจจัยอื่นประกอบและหลีกเลี่ยงอคติในการคัดกรอง",
        description="ข้อความแจ้งเตือนเรื่อง bias ที่ต้องแนบทุก output"
    )


# ---------------------------------------------------------
# ตัวอย่างการใช้งานเบื้องต้น (ลบทิ้งได้เมื่อเริ่มเขียน agent จริง)
# ---------------------------------------------------------
if __name__ == "__main__":
    # ทดสอบสร้าง instance ตรวจว่า schema ทำงานถูกต้อง
    example_requirement = SkillRequirement(skill="Python", priority="must_have", min_years=2)
    example_match = SkillMatch(
        skill="Python",
        status="met",
        evidence="มีประสบการณ์เขียน Python 3 ปีในโปรเจกต์ backend",
        years_found=3,
    )
    example_report = FitReport(
        fit_score=85,
        must_have_score=90,
        nice_to_have_score=70,
        matches=[example_match],
        gaps=["Docker"],
        suggested_interview_questions=["เคยใช้ Docker ในงานจริงหรือไม่ ถ้าไม่เคย เรียนรู้ยังไง"],
    )
    print(example_report.model_dump_json(indent=2, ensure_ascii=False))
