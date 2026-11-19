# 50 条评测集：答案级自动判分

评分口径：2=判据要素齐全且有工具依据；1=方向正确或如实说明但要素缺失；0=不满足或臆造。
模型自评（50/50 条，非独立人工评分）：完全满足 34、部分 15、不满足 1；加权得分 0.830。
评分者：模型自评（同一 agent 编写 harness 并评分，存在自评偏差，需人工抽检复核）。

- 用例数：50
- 首步路由命中：34/50（最严口径：第一步就要选对）
- 期望工具被调用到：42/50（放宽口径：允许先读再做）
- 必需工具全部调用：42/50
- 工具调用均无异常或业务错误：35/50
- 给出最终回答：50/50
- 引用片段可逐字回溯：196/256（涉及 50 条用例）
- 疑似编造 id：0
- 平均耗时：3994 ms/条

| 用例 | 场景 | 期望工具 | 首步 | 首步命中 | 工具被调用 | 必需工具 | 引用可回溯 | 模型自评分 | 评分说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E01 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | ✓ | 5/6 | 1 部分 | 判据要岗位能力矩阵与差距项；岗位库无该岗位，如实说明但未产出差距清单 |
| E02 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | ✓ | 4/5 | 1 部分 | 判据要逐维度达标度；只给了学习评估维度，明确说不能当岗位达标度 |
| E03 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | ✓ | 0/2 | 1 部分 | 判据是先岗位再画像；实际先给画像，岗位部分 ROLE_NOT_FOUND |
| E04 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | ✓ | 2/2 | 2 完全满足 | 六阶段 status+mastery 齐全，与工具返回一致 |
| E05 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | ✓ | 4/4 | 2 完全满足 | 按阶段原样列 status/mastery，符合不总结要求 |
| E06 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | ✓ | 6/8 | 2 完全满足 | 给出 target_count=0 与 answered=0，并解释第一阶段无题量要求 |
| E07 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | ✓ | 8/9 | 2 完全满足 | 纠正提问前提并说明晋级条件，未臆断 |
| E08 | 岗位 | add_learning_branch | get_project_status | ✗ | ✓ | ✓ | 4/4 | 2 完全满足 | 返回 branch_id 与 parent_stage_id(roadshow-stage-2) |
| E09 | 岗位 | add_learning_branch | get_project_status | ✗ | ✗ | ✗ | 5/7 | 1 部分 | 判据要求实际新增分支；只给建议与确认问题，未写入 |
| E10 | 岗位 | get_learning_evaluation | get_student_profile | ✗ | ✓ | ✓ | 6/8 | 2 完全满足 | 投入分 13、证据 7 条及构成齐全 |
| E11 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | ✓ | 15/18 | 1 部分 | 判据要基于岗位能力差距排序；岗位库无数据，退化为画像/路径排序并声明 |
| E12 | 岗位 | get_wrong_book | get_wrong_book | ✓ | ✓ | ✓ | 1/1 | 2 完全满足 | 六维雷达含当前分/证据条数/计分依据 |
| E13 | 岗位 | get_wrong_book | get_wrong_book | ✓ | ✓ | ✓ | 3/3 | 2 完全满足 | 两条薄弱标签 + 说明错题本为空、标签来自画像 |
| E14 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | ✓ | 11/11 | 2 完全满足 | 阶段标题、目标、检查点、任务齐全 |
| E15 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | ✓ | 12/12 | 2 完全满足 | 明确不能晋级并给出阈值与当前缺口 |
| E16 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | ✓ | 1/1 | 2 完全满足 | 只读状态，未改数据 |
| E17 | 岗位 | get_role_competency | get_student_profile | ✗ | ✓ | ✓ | 5/6 | 1 部分 | 判据要列出达标项；岗位库无该岗位，未得出达标清单 |
| E18 | 岗位 | add_learning_branch | get_project_status | ✗ | ✗ | ✗ | 4/4 | 2 完全满足 | 说明挂到 current_stage_id=roadshow-stage-2 |
| E19 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | ✓ | 2/2 | 2 完全满足 | target_count=0 与 pass_threshold=80 明确 |
| E20 | 岗位 | get_project_status | get_project_status | ✓ | ✓ | ✓ | 9/12 | 2 完全满足 | 引用 pass_threshold/current_stage_id/answered_count 解释规则 |
| E21 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | ✓ | 1/2 | 2 完全满足 | 六维画像 + 学习摘要齐全 |
| E22 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | ✓ | 1/3 | 2 完全满足 | 认知风格与两条薄弱点明确，附六维表 |
| E23 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | ✓ | 2/2 | 2 完全满足 | learning_summary.exercise 计数齐全 |
| E24 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | ✓ | 9/9 | 1 部分 | 给出处与排序，但未逐条给出 resource_id 与 score 数值 |
| E25 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | ✓ | 2/3 | 2 完全满足 | 如实说无专门内容，给出唯一命中及其弱相关分 0.0762 |
| E26 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | ✓ | 5/11 | 2 完全满足 | 相关度数值 + 出处路径齐全 |
| E27 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | ✓ | 1/3 | 2 完全满足 | 区分「命中但不讲解」，并给出 alternative 关键词 |
| E28 | 学习 | get_exercise_session | get_exercise_session | ✓ | ✓ | ✓ | 1/1 | 1 部分 | 环境无题库（NO_QUESTION_BANK），如实说明但没出题 |
| E29 | 学习 | get_exercise_session | get_project_status | ✗ | ✓ | ✓ | 7/7 | 1 部分 | 环境无题库；额外查证 stage-1 未绑题库 |
| E30 | 学习 | get_exercise_session | get_exercise_session | ✓ | ✓ | ✓ | 1/1 | 0 不满足 | 判据要求未给学号时反问；实际擅自假定 demo 作答 |
| E31 | 学习 | submit_exercise_answer | get_exercise_session | ✗ | ✗ | ✗ | 1/2 | 1 部分 | 无题库故未提交，拒绝编造 question_id |
| E32 | 学习 | submit_exercise_answer | get_exercise_session | ✗ | ✗ | ✗ | 1/2 | 1 部分 | 无题库故未提交，提出可代查资料核对该选项 |
| E33 | 学习 | submit_exercise_answer | get_exercise_session | ✗ | ✗ | ✗ | 1/3 | 1 部分 | 无题库故未提交，说明需真实题目 ID |
| E34 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | ✓ | 3/3 | 2 完全满足 | 错题明细空 + 统计齐全 |
| E35 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | ✓ | 0/1 | 2 完全满足 | 说明无错题故无标签，给出统计与雷达参考 |
| E36 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | ✓ | 1/1 | 2 完全满足 | 当前分/上次分/证据数/计分依据齐全 |
| E37 | 学习 | get_learning_evaluation | get_learning_evaluation | ✓ | ✓ | ✓ | 1/1 | 2 完全满足 | mastery=0.0 与 accuracy=100% 及口径说明齐全 |
| E38 | 学习 | get_learning_evaluation | get_learning_evaluation | ✓ | ✓ | ✓ | 7/10 | 2 完全满足 | confidence=medium + 证据构成 + 空值拉低分析 |
| E39 | 学习 | get_learning_evaluation | get_student_profile | ✗ | ✗ | ✗ | 1/2 | 2 完全满足 | 指出无「五维」口径并按实际六维列出取值 |
| E40 | 学习 | get_learning_evaluation | get_learning_evaluation | ✓ | ✓ | ✓ | 3/4 | 2 完全满足 | 引用 weak_points 并说明来自画像标注而非错题 |
| E41 | 学习 | get_learning_evaluation | get_student_profile | ✗ | ✗ | ✗ | 0/1 | 2 完全满足 | 给出 2 条并说明工具无按周统计能力 |
| E42 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | ✓ | 5/6 | 2 完全满足 | 先读画像再回答，指出画像无岗位目标 |
| E43 | 学习 | get_exercise_session | get_exercise_session | ✓ | ✓ | ✓ | 1/1 | 1 部分 | 环境无题库，未跳步但也没能出题 |
| E44 | 学习 | get_exercise_session | get_exercise_session | ✓ | ✓ | ✓ | 4/5 | 1 部分 | 环境无题库；补查资料库说明无 include 专讲 |
| E45 | 学习 | submit_exercise_answer | get_project_status | ✗ | ✗ | ✗ | 3/3 | 2 完全满足 | 返回未变的 path_progress 并给 updated_at 佐证 |
| E46 | 学习 | search_knowledge | search_knowledge | ✓ | ✓ | ✓ | 4/7 | 2 完全满足 | 五条命中均带出处路径与内容定位 |
| E47 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | ✓ | 1/2 | 1 部分 | 无错题数据，无法判断重复出错 |
| E48 | 学习 | get_wrong_book | get_wrong_book | ✓ | ✓ | ✓ | 8/9 | 2 完全满足 | 错题本为空时改依据画像薄弱点给建议，并声明来源 |
| E49 | 学习 | get_learning_evaluation | get_learning_evaluation | ✓ | ✓ | ✓ | 2/8 | 2 完全满足 | 明确区分「无数据」与「0 分」，引用 mastery_source |
| E50 | 学习 | get_student_profile | get_student_profile | ✓ | ✓ | ✓ | 12/18 | 2 完全满足 | 七步链路逐步列工具与结果，含失败环节 |
