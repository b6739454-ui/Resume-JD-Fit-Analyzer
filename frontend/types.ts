/**
 * types.ts — aligned with backend schemas.py (Pydantic)
 * SkillMatch.category/requirement_index mirrors SkillRequirement.priority
 */

// ─── Core match result (mirrors schemas.py SkillMatch) ─────────────────────
export interface SkillMatch {
  skill: string;
  status: 'met' | 'partial' | 'missing';
  evidence: string | null;
  years_found: number | null;
  category: 'must_have' | 'nice_to_have'; // mirrors SkillRequirement.priority
  requirement_index: number;               // 0-based position in requirements list
}

// ─── Top-level report (mirrors schemas.py FitReport) ───────────────────────
export interface FitReportData {
  fit_score: number;
  must_have_score: number;
  nice_to_have_score: number;
  matches: SkillMatch[];
  gaps: string[];                         // simple string list — gap skill names
  suggested_interview_questions: string[]; // simple string list
  bias_disclaimer: string;
}

// ─── API request (mirrors main.py AnalyzeRequest) ──────────────────────────
export interface AnalyzeRequest {
  resume_text: string;
  jd_text: string;
}

// ─── Pipeline step state (frontend-only, not from backend) ─────────────────
export type PipelineStepStatus = 'idle' | 'running' | 'done' | 'error';

export interface PipelineStep {
  id: string;
  label: string;
  status: PipelineStepStatus;
}
