# Known Issues & Tech Debt

## Bug: Discrepancy between LLM Score and Python Score for pair_04 and pair_09

- **Symptom**: In the Gold Dataset evaluation (`evaluate_gold.py`), `pair_04` and `pair_09` exhibit a large discrepancy between `pred_llm_score` and `pred_py_score`:
  - `pair_04`: `pred_llm_must` = 100 vs `pred_py_must` = 25 (difference of 75 points)
  - `pair_09`: `pred_llm_must` = 100 vs `pred_py_must` = 50 (difference of 50 points)
  - All other 13 evaluation pairs show identical or nearly identical LLM vs Python scores.
- **Suspected Cause**: Possible mismatch or indexing issue related to the newly added `category` and `requirement_index` fields in `SkillMatch` schema during index-based score calculation or vector similarity requirement lookup in `find_matching_requirement()`.
- **Status**: Documented for post-demo debugging. Core pipeline functionally valid.
