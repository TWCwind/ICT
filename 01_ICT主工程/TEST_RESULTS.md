
## PR #4 integration verification (2026-11-16)

- Conflict resolution on latest main kept PR #3 learner/API behavior and PR #4 macaron theme/login accessibility changes.
- Frontend: `npm ci --no-audit`, `npm run check`, `npm run audit:ui`, and `npm run build` passed. Build retains the existing >500 kB chunk warning for ExerciseCenterPage and markdown renderer.
- Browser: `npm run test:roadshow -- --project=msedge --workers=1` passed 19/19 after fixing tablet path-flow horizontal overflow; `npx playwright test e2e/captcha-accessibility.spec.ts --project=msedge --workers=1` passed 1/1.
- Backend: `python -m unittest discover -s tests -p "test*.py" -v` passed 46/46.
- MCP: `test_mcp.ps1` passed 7/7 unit tests and completed real Streamable HTTP smoke calls for `get_student_profile`, `get_role_competency`, and `get_project_status` using an isolated temporary environment. AgentArts cloud integration is not claimed.
- Visual review: inspected login, home, workshop, evaluation and tablet path screenshots under `%TEMP%\ict-pr4-visual-review`. Fixed stale fixed-height styling on workshop and the empty evaluation diagnosis/score decorations. Screenshots remain outside the repository.
- One initial roadshow run exposed `/path` document overflow of 191 px at 768×1024; the agent-chain row now scrolls within its panel. Responsive rerun passed all 4 tested viewports.

## 50-condition routing evaluation (2026-11-17)

`scripts/eval/run_eval.py` deliberately reports only static cross-checks and a documented cloud baseline, so the 50-condition set in `scripts/eval/agentarts_eval_set.jsonl` had no per-condition routing number. Two runners were added to close that gap without cloud IAM credentials.

- `python scripts/eval/route_eval.py` -- sends each of the 50 prompts to the configured OpenAI-compatible model with `temperature=0` and the FastMCP `tools/list` schema, then compares the emitted `tool_calls[0].function.name` with the condition's `tool` field. A second request asks for a 1-3 step execution plan.
  - Single-step top-1: **36/50 (72.0%)**; execution-plan coverage: **42/50 (84.0%)**; multi-tool conditions (`required_tools` with more than one entry, 7 of them): plan covers every required tool in **6/7**; 0 request errors; mean **866 ms** per condition (deepseek-chat, 2026-11-17, measured on `0ea746a`).
  - Per tool: `get_project_status` 9/9 top-1 (5/9 plan), `get_wrong_book` 7/7 (6/7), `get_student_profile` 5/5 (5/5), `search_knowledge` 5/5 (5/5), `get_exercise_session` 5/5 (4/5), `get_learning_evaluation` 5/7 (5/7), `get_role_competency` 0/5 top-1 but 5/5 plan, `submit_exercise_answer` 0/4 but 3/4 plan, `add_learning_branch` 0/3 but 3/3 plan.
  - Reading: the write tools score zero on single-step by construction (a real ReAct turn must read ids first) and the role-condition prompts never name a role while `role_name` is required. Four unplanned conditions (E14/E19/E20/E44) ask for rules or retrieval and are arguably mislabeled in the set.
- `python scripts/eval/cite_check.py` -- executes `search_knowledge` for the five retrieval conditions: 5/5 conditions verifiable, every chunk carries `title` + `excerpt` + source `path`.
  - Chapter anchors: `backend/app/services/knowledge_hub.py` now splits an uploaded textbook into one document per chapter (`_chapter_documents`) when every chapter title can be located in the body, so textbook hits expose `chapter` + `chapter_index` and `format_references` prints `章节：第N章 <名称>`. Before the change no result carried a chapter field at all.
  - Measured on a data root that contains the demo textbook: **3/13 citations carry an explicit chapter anchor** (the ones whose ranked source is a chaptered textbook). Generated resources are single documents, so they have no chapter by construction; this is reported as-is rather than back-filled from `tags`.
- `python scripts/eval/test_role_pipeline.py` -- 17/17 pass (nine-step role pipeline: ordering, cross-step value passing, abort-on-tool-failure, explicit errors for missing tool/weakness).
- `python scripts/eval/run_eval.py` -- static cross-check still passes: 20 job / 30 learning conditions, 9/9 tool coverage, no illegal tool or path-stage references.

These numbers are routing-layer only. Answer quality remains covered by the AgentArts platform evaluation (8/8, mean 0.76) and is not claimed to be human-scored.
