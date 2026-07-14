# System Architecture — Resume ↔ JD Fit Analyzer

## Agent Pipeline (Flowchart จาก PRD-6)

```mermaid
flowchart LR
    A[Resume Extractor] --> C[Fit Analyzer]
    B[JD Extractor] --> C
    C --> D[Gap Agent]
    D --> E[Judge Agent]
    E --> F[FitReport<br/>ส่งกลับให้ API/UI]

    style A fill:#dbeafe,stroke:#2563eb
    style B fill:#dbeafe,stroke:#2563eb
    style C fill:#fef3c7,stroke:#d97706
    style D fill:#fef3c7,stroke:#d97706
    style E fill:#fee2e2,stroke:#dc2626
    style F fill:#dcfce7,stroke:#16a34a
```

## End-to-End Request Flow

```mermaid
sequenceDiagram
    participant U as Recruiter (Client)
    participant API as FastAPI Server
    participant RE as Resume Extractor
    participant JE as JD Extractor
    participant FA as Fit Analyzer
    participant GA as Gap Agent
    participant JA as Judge Agent
    participant DB as Skill Taxonomy<br/>(ESCO + O*NET)

    U->>API: POST /fit/analyze<br/>{resume_text, jd_text}
    API->>RE: extract_resume(resume_text)
    RE->>DB: normalize_skill_name()
    RE-->>API: ResumeData
    API->>JE: extract_jd(jd_text)
    JE->>DB: normalize_skill_name()
    JE-->>API: JDData
    API->>FA: analyze_fit(ResumeData, JDData)
    FA-->>API: FitAnalysisResult (matches + scores)
    API->>GA: analyze_gaps(matches)
    GA-->>API: gaps + interview questions
    API->>JA: judge_matches(matches, resume_text)
    JA-->>API: verified_matches (evidence-checked)
    API-->>U: FitReport (JSON)
```

## Component Responsibility Table

| Component | Input | Output | Notes |
|---|---|---|---|
| Resume Extractor | Resume text | `ResumeData` | LLM + Pydantic (`instructor`) |
| JD Extractor | JD text | `JDData` | Must-have / nice-to-have split |
| Skill Normalizer | Raw skill name | Canonical skill name | Embedding similarity vs ESCO/O*NET taxonomy |
| Fit Analyzer | `ResumeData` + `JDData` | `matches` + scores | Scores computed in Python (deterministic), not by LLM |
| Gap Agent | `matches` | `gaps` + interview questions | Only reasons about missing/partial skills |
| Judge Agent | `matches` + original resume text | `verified_matches` | Rejects claims without textual evidence |

## Data Stores

- **Skill Taxonomy**: `skill_taxonomy_master.csv` (ESCO + O*NET, 22.7k skills) + cached embeddings (`.npy`)
- **Occupation-Skill Mapping**: `occupation_skill_mapping.csv` (used to cross-check JD-implied role requirements)
- **Gold Dataset**: `gold_dataset_final.json` (15 resume-JD pairs with gold labels, for evaluation)
