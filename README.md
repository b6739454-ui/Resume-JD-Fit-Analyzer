# Resume ↔ JD Fit Analyzer

> PRD-6 · Building AI-Enabled Software Systems · Term Project
> Category: Analysis & Scoring · Difficulty: Easy

Extracts structured skills/experience from a resume and a job description,
computes an evidence-based fit score, and surfaces skill gaps with quoted
evidence — **decision support only, not a hire/reject decision.**

---

## Status: Iteration 2 (v0.2.0) complete — Iteration 3 (v1.0.0) in progress

All 5 agents make real LLM calls (Gemini) with RAG-based skill normalization
(ESCO + O*NET) and Judge Agent evidence-grounding wired in and tested against
the full 15-pair gold set. Frontend UI + PDF/DOCX upload are partially built
(Iteration 3 work). See table below for what's done per iteration.

| Iteration | Tag | What's done |
|---|---|---|
| 1 | `v0.1.0` | Schemas + API stub + mock responses ✅ |
| 2 | `v0.2.0` | Real agent pipeline (RAG, LLM, judge) + eval on full gold set ✅ |
| 3 | `v1.0.0` | UI (in progress) + guardrails + full eval + demo (not yet tagged) |

---

## Project layout

```
.
├── main.py                      # FastAPI app — /fit/analyze, /fit/batch, /evaluate
├── schemas.py                   # Pydantic models shared by every agent (source of truth)
├── agents/
│   ├── resume_extractor.py      # Agent 1 — resume -> ResumeData
│   ├── jd_extractor.py          # Agent 2 — JD -> JDData
│   ├── fit_analyzer.py          # Agent 3 — matches + scores
│   ├── gap_agent.py             # Agent 4 — gaps + interview questions
│   ├── judge_agent.py           # Agent 5 — evidence verification
│   └── skill_normalizer.py      # RAG skill taxonomy normalization (ESCO + O*NET)
├── data/
│   ├── skill_taxonomy_master.csv       # 22.7k normalized skills (ESCO + O*NET)
│   └── occupation_skill_mapping.csv    # occupation -> required skills
├── tests/
│   ├── gold_dataset_final.json  # 15 resume-JD pairs with gold labels (incl. 5 edge cases)
│   └── evaluate_gold.py         # Evaluation script vs gold set
├── examples/
│   ├── sample_request.json      # Example /fit/analyze request
│   └── sample_response.json     # Example FitReport response
├── docs/
│   └── architecture.md          # Agent pipeline + sequence diagram (Mermaid)
├── .env.example
└── README.md
```

---

## Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install fastapi uvicorn pydantic instructor google-genai python-dotenv \
            sentence-transformers pandas numpy

# 3. Copy env file and fill in your key
cp .env.example .env
# edit .env -> set GOOGLE_API_KEY

# 4. Run the API
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000/docs** for interactive Swagger UI.

---

## Try it

```bash
curl -X POST http://127.0.0.1:8000/fit/analyze \
  -H "Content-Type: application/json" \
  -d @examples/sample_request.json
```

See [`examples/sample_response.json`](examples/sample_response.json) for the
expected shape of the response.

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full agent
pipeline diagram and sequence flow.

Short version: `Resume Extractor` + `JD Extractor` → `Fit Analyzer` →
`Gap Agent` → `Judge Agent` → `FitReport`.

---

## Evaluation

> **Model Requirement**: The pipeline **MUST use `gemini-flash-latest`** (full model). Using `gemini-flash-lite-latest` drops requirements on concise JDs and fails PRD accuracy targets. See [`eval_report.md`](eval_report.md) for full benchmark findings.

```bash
python tests/evaluate_gold.py
```

Runs the full pipeline against all 15 gold resume-JD pairs and reports:
- Must-Have Match Accuracy (target ≥ 80%)
- Unsupported Match Claims Rate (target ≤ 10%)
- Score MAE (fit score vs gold)

Latest recorded run and evaluation report: see [`eval_report.md`](eval_report.md) and [`tests/evaluation_results.json`](tests/evaluation_results.json).

---

## Team & roles

| Role | Responsibility |
|---|---|
| Agent Core | `agents/*.py` — resume/JD extraction, fit analysis, gap analysis, judge |
| Data / RAG / Eval | Skill taxonomy, gold dataset, `evaluate_gold.py` |
| API / Frontend | `main.py`, FastAPI contract, (later) recruiter UI |

---

## Disclaimer

This tool produces **decision support only**. It does not make hire/reject
decisions and every report carries a bias disclaimer. See PRD-6 §3 (Out of
Scope) and §8 (Security & Guardrails).
