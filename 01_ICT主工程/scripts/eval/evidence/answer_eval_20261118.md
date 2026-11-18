# 50 条评测集：答案级自动判分

判分口径见 `scripts/eval/answer_eval.py` 顶部说明；`human_score` 全部留空，
「判断是否正确」需要人工逐条填写，本文不给出该结论。

- 用例数：50
- 首步路由命中：34/50（最严口径：第一步就要选对）
- 期望工具被调用到：42/50（放宽口径：允许先读再做）
- 必需工具全部调用：42/50
- 工具调用无异常：50/50
- 给出最终回答：50/50
- 引用片段可逐字回溯：196/256（涉及 50 条用例）
- 疑似编造 id：0
- 平均耗时：3994 ms/条

| 用例 | 场景 | 期望工具 | 首步 | 首步命中 | 工具被调用 | 必需工具 | 引用可回溯 | 人工评分 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E01 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | 5/6 |  |
| E02 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | 4/5 |  |
| E03 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | 0/2 |  |
| E04 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | 2/2 |  |
| E05 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | 4/4 |  |
| E06 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | 6/8 |  |
| E07 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | 8/9 |  |
| E08 | 岗位 | add_learning_branch | get_project_status | ✗ | ✓ | 4/4 |  |
| E09 | 岗位 | add_learning_branch | get_project_status | ✗ | ✗ | 5/7 |  |
| E10 | 岗位 | get_learning_evaluation | get_student_profile | ✗ | ✓ | 6/8 |  |
| E11 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | 15/18 |  |
| E12 | 岗位 | get_wrong_book | get_wrong_book | ✓ | ✓ | 1/1 |  |
| E13 | 岗位 | get_wrong_book | get_wrong_book | ✓ | ✓ | 3/3 |  |
| E14 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | 11/11 |  |
| E15 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | 12/12 |  |
| E16 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | 1/1 |  |
| E17 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | 5/6 |  |
| E18 | 岗位 | add_learning_branch | get_project_status | ✗ | ✗ | 4/4 |  |
| E19 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | 2/2 |  |
| E20 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | 9/12 |  |
| E21 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | 1/2 |  |
| E22 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | 1/3 |  |
| E23 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | 2/2 |  |
| E24 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | 9/9 |  |
| E25 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | 2/3 |  |
| E26 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | 5/11 |  |
| E27 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | 1/3 |  |
| E28 | 学习 | get_exercise_session | get_exercise_session | ✓ | ✓ | 1/1 |  |
| E29 | 学习 | get_exercise_session | get_project_status | ✗ | ✓ | 7/7 |  |
| E30 | 学习 | get_exercise_session | get_exercise_session | ✓ | ✓ | 1/1 |  |
| E31 | 学习 | submit_exercise_answer | get_exercise_session | ✗ | ✗ | 1/2 |  |
| E32 | 学习 | submit_exercise_answer | get_exercise_session | ✗ | ✗ | 1/2 |  |
| E33 | 学习 | submit_exercise_answer | get_exercise_session | ✗ | ✗ | 1/3 |  |
| E34 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | 3/3 |  |
| E35 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | 0/1 |  |
| E36 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | 1/1 |  |
| E37 | 学习 | get_learning_evaluation | get_learning_evaluation | ✓ | ✓ | 1/1 |  |
| E38 | 学习 | get_learning_evaluation | get_learning_evaluation | ✓ | ✓ | 7/10 |  |
| E39 | 学习 | get_learning_evaluation | get_student_profile | ✗ | ✗ | 1/2 |  |
| E40 | 学习 | get_learning_evaluation | get_learning_evaluation | ✓ | ✓ | 3/4 |  |
| E41 | 学习 | get_learning_evaluation | get_student_profile | ✗ | ✗ | 0/1 |  |
| E42 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | 5/6 |  |
| E43 | 学习 | get_exercise_session | get_exercise_session | ✓ | ✓ | 1/1 |  |
| E44 | 学习 | get_exercise_session | get_exercise_session | ✓ | ✓ | 4/5 |  |
| E45 | 学习 | submit_exercise_answer | get_project_status | ✗ | ✗ | 3/3 |  |
| E46 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | 4/7 |  |
| E47 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | 1/2 |  |
| E48 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | 8/9 |  |
| E49 | 学习 | get_learning_evaluation | get_learning_evaluation | ✓ | ✓ | 2/8 |  |
| E50 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | 12/18 |  |
