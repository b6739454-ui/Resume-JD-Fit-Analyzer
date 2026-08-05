# Known Issues & Tech Debt

## Bug: Discrepancy between LLM Score and Python Score for pair_04 and pair_09

- **Symptom**: In the Gold Dataset evaluation (`evaluate_gold.py`), `pair_04` and `pair_09` exhibit a large discrepancy between `pred_llm_score` and `pred_py_score`:
  - `pair_04`: `pred_llm_must` = 100 vs `pred_py_must` = 25 (difference of 75 points)
  - `pair_09`: `pred_llm_must` = 100 vs `pred_py_must` = 50 (difference of 50 points)
  - All other 13 evaluation pairs show identical or nearly identical LLM vs Python scores.
- **Suspected Cause**: Possible mismatch or indexing issue related to the newly added `category` and `requirement_index` fields in `SkillMatch` schema during index-based score calculation or vector similarity requirement lookup in `find_matching_requirement()`.
- **Status**: Documented for post-demo debugging. Core pipeline functionally valid.

## Accuracy Optimization — Summary & Conclusion

- **Baseline achieved**: Must-Have Accuracy ~57-61% (varies slightly due to LLM non-determinism), Unsupported Claims Rate 4.82-6.02% (consistently passes ≤10% target)
- **Attempts made**:
  - **Index-based matching fix (substring → index)**: confirmed critical, kept permanently
  - **Evidence single-sentence exact-substring rule**: confirmed helps (reduced unsupported rate from 41% → ~5%), kept permanently
  - **Few-shot examples for semantic disambiguation (met/partial)**: caused -5.35% regression, reverted (commit `3885783`)
- **Conclusion**: Reached model capability ceiling for `gemini-flash-latest` via prompt engineering. Must-Have Accuracy target of 80% (PRD) not achievable with current model + prompt-only approach within project scope. Future work: evaluate `gemini-flash` (non-lite) or `gemini-pro` tier, or fine-tuning.
- **Decision**: Stop further prompt tuning for accuracy. Redirect effort to remaining PRD requirements (PII handling, prompt injection testing, demo preparation).

