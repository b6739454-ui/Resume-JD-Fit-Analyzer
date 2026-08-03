-- =========================================================
-- db_schema.sql — Database Schema for Resume <-> JD Fit Analyzer
-- Designed to mirror Pydantic Schemas in schemas.py
-- =========================================================

-- 1. Resumes Table
CREATE TABLE resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_text TEXT NOT NULL,
    total_years_experience NUMERIC(4,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Resume Skills Table (maps to ResumeSkill)
CREATE TABLE resume_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    skill VARCHAR(255) NOT NULL,
    years NUMERIC(4,2),
    evidence TEXT NOT NULL
);

-- 3. Work Experience Table (maps to WorkExperience)
CREATE TABLE work_experiences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    role VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    years NUMERIC(4,2),
    description TEXT
);

-- 4. Job Descriptions Table (maps to JDData)
CREATE TABLE job_descriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_title VARCHAR(255),
    raw_text TEXT NOT NULL,
    overall_min_years NUMERIC(4,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Skill Requirements Table (maps to SkillRequirement)
CREATE TABLE skill_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jd_id UUID NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
    skill VARCHAR(255) NOT NULL,
    priority VARCHAR(50) NOT NULL CHECK (priority IN ('must_have', 'nice_to_have')),
    min_years NUMERIC(4,2),
    requirement_index INTEGER NOT NULL DEFAULT 0
);

-- 6. Fit Reports Table (maps to FitReport)
CREATE TABLE fit_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    jd_id UUID NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
    fit_score INTEGER NOT NULL CHECK (fit_score BETWEEN 0 AND 100),
    must_have_score INTEGER NOT NULL CHECK (must_have_score BETWEEN 0 AND 100),
    nice_to_have_score INTEGER NOT NULL CHECK (nice_to_have_score BETWEEN 0 AND 100),
    bias_disclaimer TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Skill Matches Table (maps to SkillMatch)
CREATE TABLE skill_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fit_report_id UUID NOT NULL REFERENCES fit_reports(id) ON DELETE CASCADE,
    skill VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('met', 'partial', 'missing')),
    evidence TEXT,
    years_found NUMERIC(4,2),
    category VARCHAR(50) NOT NULL CHECK (category IN ('must_have', 'nice_to_have')),
    requirement_index INTEGER NOT NULL DEFAULT 0
);

-- 8. Skill Gaps Table (maps to gaps array in FitReport)
CREATE TABLE fit_report_gaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fit_report_id UUID NOT NULL REFERENCES fit_reports(id) ON DELETE CASCADE,
    gap_skill VARCHAR(255) NOT NULL
);

-- 9. Interview Questions Table (maps to suggested_interview_questions in FitReport)
CREATE TABLE suggested_interview_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fit_report_id UUID NOT NULL REFERENCES fit_reports(id) ON DELETE CASCADE,
    question TEXT NOT NULL
);

-- Indexes for performance
CREATE INDEX idx_resume_skills_resume_id ON resume_skills(resume_id);
CREATE INDEX idx_work_experiences_resume_id ON work_experiences(resume_id);
CREATE INDEX idx_skill_requirements_jd_id ON skill_requirements(jd_id);
CREATE INDEX idx_fit_reports_resume_jd ON fit_reports(resume_id, jd_id);
CREATE INDEX idx_skill_matches_fit_report_id ON skill_matches(fit_report_id);
