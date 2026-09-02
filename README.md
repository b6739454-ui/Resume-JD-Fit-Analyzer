# Resume ↔ JD Fit Analyzer

> PRD-6 · Building AI-Enabled Software Systems · Term Project  
> Category: Analysis & Scoring · Difficulty: Easy

Extracts structured skills/experience from a resume and a job description,
computes an evidence-based fit score, and surfaces skill gaps with quoted
evidence — **decision support only, not a hire/reject decision.**

---

## Current Status: `v1.0.0` (Complete & Verified)

All phases complete: Full 4-Agent Pipeline, RAG-based Skill Taxonomy Normalization, Evidence Judge Agent, React Recruiter UI, Extraction Caching, and Merged Gap Agent (Gold Dataset 15/15 Pairs Verified ✅).

| Iteration | Tag | Status | Description |
|---|---|:---:|---|
| Iteration 1 | `v0.1.0` | Done | Schemas + API contract + Mock stubs |
| Iteration 2 | `v0.2.0` | Done | Real Agent Pipeline + RAG skill normalizer + Judge Agent + Eval script |
| Iteration 3 | `v1.0.0` | **Done (Latest)** | Recruiter UI (Vite+React) + Guardrails + Key Rotation + Merged Gap Agent + Production Caching |

---

## Key Performance & Evaluation Results

Evaluated against the **Gold Dataset (15 resume-JD pairs)** with deterministic Python scoring:

| Metric | Target (PRD) | Baseline (Separate Calls) | Merged Mode (Default) | Status |
|---|:---:|:---:|:---:|:---:|
| **Must-Have Match Accuracy** | $\ge 80\%$ | 58.18% | **58.18%** | Ceiling reached for prompt-engineering |
| **Unsupported Match Claims Rate** | $\le 10\%$ | 5.00% | **3.57%** | ✅ **Passes target** (low hallucination) |
| **Score MAE (Fit - Python)** | — | 17.93 | **14.73** | ✅ Improved accuracy |
| **Score MAE (Must-Have - Python)**| — | 16.47 | **10.93** | ✅ Improved accuracy |
| **LLM Calls per Analysis** | — | 5 calls | **4 calls** | ✅ **20% Quota Reduction** |

*Detailed benchmark logs and findings: see [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) and [`tests/evaluation_results_merged.json`](tests/evaluation_results_merged.json).*

---

## Project Layout

```
.
├── main.py                      # FastAPI app — /fit/analyze, /fit/batch, /admin/toggle-mock
├── schemas.py                   # Pydantic models shared by every agent (source of truth)
├── requirements.txt             # Pinned dependencies (including jsonref, instructor, etc.)
├── agents/
│   ├── resume_extractor.py      # Agent 1: Resume -> ResumeData
│   ├── jd_extractor.py          # Agent 2: JD -> JDData
│   ├── fit_analyzer.py          # Agent 3: Fit Analyzer (+ Combined Merged Gap Agent)
│   ├── gap_agent.py             # Agent 4: Standalone Gap Agent (fallback if merged=false)
│   ├── judge_agent.py           # Agent 5: Evidence verification & keyword-stuffing rejection
│   └── skill_normalizer.py      # RAG skill taxonomy normalization (ESCO + O*NET, SentenceTransformers)
├── frontend/                    # Recruiter Web UI (React, Vite, TypeScript)
├── data/
│   ├── skill_taxonomy_master.csv       # 22.7k normalized skills (ESCO + O*NET)
│   ├── skill_taxonomy_embeddings.npy   # Precomputed embeddings for fast similarity search
│   └── occupation_skill_mapping.csv    # Occupation -> required skills
├── tests/
│   ├── gold_dataset_final.json         # 15 resume-JD pairs with human gold labels
│   ├── evaluate_gold.py                # Evaluation benchmark runner with key rotation
│   ├── extraction_cache.json           # SHA-256 prompt-validated extraction cache
│   └── benchmark_reload_vs_noreload.py # Timing benchmark script
├── docs/
│   ├── architecture.md          # Pipeline architecture & sequence diagram
│   └── demo_script.md           # 3-minute presentation & demo runbook
├── KNOWN_ISSUES.md              # Technical debt, accuracy analysis, and judgment thresholds
├── .env.example                 # Environment variables template
└── README.md
```

---

## Quick Start & Setup

### 1. Environment & Dependencies

```bash
# Create & activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install all dependencies (pinned in requirements.txt)
pip install -r requirements.txt
```

> **Note**: `jsonref==1.1.0` is required by `instructor` for schema resolution. It is already included in `requirements.txt`.

### 2. Configuration (`.env`)

Copy `.env.example` to `.env` and set your Google Gemini API Key:

```bash
cp .env.example .env
```

Key configuration flags:
- `GOOGLE_API_KEY`: Your Gemini API key (supports multi-key rotation: `GOOGLE_API_KEY_FRIEND1`, etc.)
- `MERGED_GAP_AGENT`: `true` (default) — merges Fit Analyzer + Gap Agent into 1 call (saves 20% quota)
- `EXTRACTION_CACHE_ENABLED`: `true` (default) — caches extracted JSON using SHA-256 content & prompt hash
- `USE_MOCK_PIPELINE`: `false` (default) — set `true` for instant UI testing without consuming quota

### 3. Running the Server (Important Performance Note)

```bash
# ✅ RECOMMENDED (Production / Demo):
uvicorn main:app --port 8000

# ⚠️ WARNING on --reload:
# Running with --reload causes uvicorn to restart and reload the 22.7k SentenceTransformer
# embeddings on every code change (~66s cold start overhead).
```

### 4. Running the Frontend (Recruiter UI)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** to use the Recruiter UI.  
Interactive API docs available at **http://127.0.0.1:8000/docs**.

---

## Evaluation Benchmark

Run the full 15-pair gold set evaluation with automatic key rotation:

```bash
# Run merged mode evaluation (default)
python tests/evaluate_gold.py --merged

# Run separate mode evaluation (baseline)
python tests/evaluate_gold.py
```

---

## Disclaimer

This tool is designed for **decision support only**. It does not make hire/reject decisions, and every generated report carries an explicit bias disclaimer per PRD-6 §3 and §8.
