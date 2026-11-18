# 答辩主线（一页版）

> 目的：把「做了什么」讲成「一个可复现的判断链条」，每个结论都能点回原始证据。
> 本文件只给结构与指向，不新增任何未经测量的数字。

## 一句话主线

**学生的项目产物 → 抽取可核验的能力证据 → 对照岗位能力标准算出差距 → 给出可执行的补强任务 → 复评闭环，全程可回溯到原始文件与出处。**

## 五段式讲法（建议 6 分钟）

### 1. 问题（30 秒）

学生的学习成果散落在作业、项目文档、练习记录里，教师和企业都很难回答三个问题：他到底会什么？离目标岗位差多少？下一步该练什么？
现有工具两条路都走不通：纯 LLM 提问会编（没有出处），纯规则系统不会看非结构化产物。

### 2. 做法（90 秒）

- **能力证据来自项目产物本身**：`backend/app/services/knowledge_hub.py` 把上传的教材/项目文档切块建索引，`search_knowledge` 返回的每条片段都带 `title / excerpt / path`。
- **对照岗位标准**：`02_服创岗位能力模块/岗位图谱子系统` 的 50 条岗位画像（`structured_job_data.json`）给出能力维度，`get_role_competency` 按岗位名或 id 取维度。
- **编排在 AgentArts 上**：`ict-mcp-server`（9 个工具，Runtime 见 `AGENTARTS_CLOUD_EVIDENCE.md`）作为工具服务；`ict-career-agent` 用 LangGraph ReAct 动态发现工具，另有九步「角色流水线」做代码驱动的确定性编排（`scripts/eval/test_role_pipeline.py` 17 条守它的确定性）。
- **可回溯**：`scripts/eval/cite_check.py` 校验引用片段能在源文件里找到；`ANSWER_EVAL` 的 `grounded_ratio` 校验回答里的引用能否在工具返回体里逐字回溯。

### 3. 证据（90 秒，只讲能当场打开的）

| 结论 | 证据位置 | 怎么打开 |
| --- | --- | --- |
| 工具服务 9 个工具可用 | `mcp_server/server.py`、`MCP_INTEGRATION.md` | `python scripts/eval/answer_eval.py --list-tools` |
| 工具执行不是纸上谈兵 | `scripts/eval/evidence/local_eval_20261117.jsonl`（队友） | 逐行看 `tool` 与 `ok` |
| 路由选得对不对 | `scripts/eval/evidence/route_eval_2026*.md` | 单步命中、计划覆盖两栏 |
| 答案能不能验 | `scripts/eval/evidence/answer_eval_2026*.md` | 引用回溯比例、编造 id 一栏 |
| 前后端不是 PPT | `01_ICT主工程/TEST_RESULTS.md` | 46 单测 / 12 验收 / 62 e2e |
| 改动本身没把东西弄坏 | `.github/workflows/ci.yml` | PR 页面的 check 结果 |

### 4. 边界（60 秒，主动说，别等人问）

- 云端部署的当前版本实证由团队在补齐（`AGENTARTS_CLOUD_EVIDENCE.md` 逐条为空的地方就是没验的）。
- 50 条用例的「判断是否正确」目前只有自动可核验项，人工评分列留白。
- 数据层是 JSON 快照（无事务/无并发控制），试点规模有限。
- 实时语音、数字人因无凭据处于禁用状态。

### 5. 现场演示（90 秒，一条链走完）

1. 上传一份项目文档 → 知识库索引（`/api/resources` 可见新增条目）。
2. 问「我这个项目离前端开发工程师还差什么」→ 展示工具调用链 + 引用片段 + 出处路径。
3. 点「生成补强任务」→ 展示题目来自刚生成的题库（这是修掉的真实 bug：`exercise_bank.py` 曾无条件忽略题库）。
4. 提交一题 → 错题本出现记录 → 评估页面分数变化。

## 讲的时候不要做的事

- 不要念功能列表（页面截图自己会说话），只讲**因果链**：这个能力证据来自哪里、凭什么可信、下一步怎么用。
- 不要说「支持多 Agent」而不给对照：没有三组跑数就只说「两条编排路径，规则流水线有 17 条确定性测试」。
- 不要把「工具执行成功率」说成「任务成功率」——队友已经指出过一次。
