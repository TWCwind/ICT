# 剩余工作清单（截至 2026-11-18）

本文件只列**我这边做不了或不该替你做**的项，以及它们的解锁条件。
已完成的项见 `A_TASK_REPORT.md`、`LOCAL_EVAL_REPORT.md`、`TEST_RESULTS.md` 与下面的「本轮新增」。

## 一、本轮新增（可复核）

| 产出 | 位置 | 复核方式 |
| --- | --- | --- |
| CI（4 个 job：后端单测、MCP 测试、评测静态校验、前端类型检查+构建） | `.github/workflows/ci.yml` | push 后看 Actions；本地等价命令见文件内 `run:` |
| e2e 手动工作流（windows-latest + msedge，默认只跑无障碍用例） | `.github/workflows/e2e.yml` | Actions → E2E (manual) → Run workflow |
| 答案级自动判分（真跑工具、落盘 trace、可核验项打分、`human_score` 留白） | `01_ICT主工程/scripts/eval/answer_eval.py` | `python scripts/eval/answer_eval.py --list-tools`（不调模型，CI 用的就是这条） |
| 答案级判分结果（50 条，含每条答案与工具调用 trace） | `01_ICT主工程/scripts/eval/evidence/answer_eval_2026*.{jsonl,md,summary.json}` | 直接打开 md；jsonl 里每条 `trace` 是完整证据链 |
| 50 条模型自评（非独立人工评分） | 同上 jsonl 的 `model_self_score` / `model_self_note`；`human_score` / `human_note` 保持空白 | 看 md 表格；口径：2=判据要素齐全且有工具依据，1=方向正确或如实说明但要素缺失，0=不满足或臆造 |
| 前端分包第一轮（three 按需加载 + vendor 拆块） | `01_ICT主工程/frontend-vue/src/pages/ExerciseCenterPage.vue`、`vite.config.ts` | `node node_modules/vite/bin/vite.js build` 后看 chunk 体积：练习页 585KB → 102KB |

判分口径：**自动判分只覆盖路由、必需工具、工具业务错误、引用片段能否在工具返回中找到及疑似编造 id；诊断正确性尚无独立人工评分**。18 次工具返回业务错误，涉及 15/50 条；35/50 条没有工具异常或业务错误。

### 模型自评结果（2026-11-18，50/50 条；未经独立人工评分）

- 完全满足 34 条、部分 15 条、不满足 1 条，加权得分 **0.83**（满分按每条 2 分计）。
- 15 条「部分」的原因由模型自评给出，包括环境无题库、岗位缺失、写操作未执行和字段缺失；尚待独立人工复核，不应直接归因为数据侧。
- 1 条 0 分是**行为层缺陷**：E30「给我出 3 道诊断练习题」未给学号，模型擅自假定 `demo` 作答，而判据明确要求反问学号。修法是在系统提示词里加一条硬规则（缺 `student_id` 时必须先问），这属于 `ref/ict_agent` 提示词侧改动，未在本仓库内生效。
- 评分者声明：这批评分由同一个模型完成（它也是 harness 的编写者），存在自评偏差，**答辩前建议抽检 10 条**（随机取即可，md 表里每条都写了判定理由，便于反驳）。

## 二、我做不了的（需要你或你的凭据）

1. **当前版本的 AgentArts 云端实证**（队友第 1 条，也是他说的「最缺的证据」）
   - 缺什么：团队空间权限、可访问的 HTTPS MCP 地址、能在云端跑一次真实调用链的凭据。
   - 你能做的：用 `ict-mcp-server` 当前代码部署一次，然后按 `AGENTARTS_CLOUD_EVIDENCE.md` 的 7 个空位填：部署时间与版本（git commit）、Runtime ID、端点 URL、`tools/list` 返回的工具数、一次成功调用的请求/响应（脱敏）、一次失败调用的处理、平台侧评估结果。
   - 注意：`D:\工作区\AgentArts-第4步-…实测报告.md` 里第七节附近有 AK 前缀片段，**不要整篇贴进仓库**，脱敏后再引用。
2. **独立人工评分**（目前只有模型自评）
   - 现在有：50 条模型自评分与理由，以及完整的工具调用轨迹。
   - 需要人做的：按预先确定的标准独立判分并填写 `human_score` / `human_note`，记录复核人和分歧；至少覆盖失败、边界和随机抽样用例。模型自评 0.83 不能作为人工验收成绩。
3. **多 Agent 对照实验**（队友第 3 条）
   - 缺什么：同一批项目产物 + 统一评分标准 + 三组跑数（规则流程 / 单 Agent / 多 Agent 九步）。
   - 你能做的：用同一份学生产物跑三组，记录引用准确数、诊断正确数、人工纠错次数、耗时、token 成本；仓库里 `scripts/eval/test_multi_agent*.py` 只保证流程可复现，不产出对照结论。
4. **教师真实效果证据**（队友第 4 条）
   - 需要 1~2 位真实教师对真实学生产物独立评分，记录试用前后、建议采纳/驳回原因、样本量。这件事只能在有真人的场景做。
5. **LICENSE 选型**
   - 我按惯例不建议擅自替你选（涉及你对作品的授权意图）。常见选择：MIT（最宽松，利于传播）、Apache-2.0（带专利条款）、或暂不添加（保留全部权利）。你定一个，我 1 分钟加进去。

## 三、工程债（我能做但没做，需要你点头）

1. **前端分包（第一轮已完成，剩第二轮）**：已把 `three` 从练习页首屏改为「历史星系」页签按需加载（练习页 chunk 585kB → **102kB**），并把 `vue` / `markdown`(含 katex+dompurify) / `three` / 字体拆成独立 chunk（`vite.config.ts` 的 `manualChunks`）。仍未解决的是 `vendor-three` 705kB 与 `vendor-markdown` 381kB 这两个**懒加载**大块——它们不影响首屏，但要继续降体积只能拆 `ExerciseCenterPage.vue`（3353 行）本身或换更轻的 3D/公式方案。
2. **数据层 JSON → SQLite**：`backend/app/repo.py` 现在按学号建目录写 JSON，没有事务、没有并发控制。这是结构性改动，会牵动所有接口与 e2e 的数据准备，属于「一天起步」的量级。
3. **拆 God File**：`orchestrator.py` 1786 行、`knowledge_hub.py` 1613 行、`ExerciseCenterPage.vue` 3353 行、`profile-center.css` 4231 行。纯重构，收益是可维护性，风险是回归面大。
4. **`reference-screens.css` 重复主题块**：`/* Workshop */`（114/116/134/137/355 行）、`/* Evaluation */`（248/263/268 行）存在重复定义，我修 bug 时只删了两组重复的选择器，整块合并没做。
5. **两条首屏密度体验债**（已用 `test.fail(true, …)` 标注在 `final-density.spec.ts`）：课程总览首屏覆盖率 0.596（要求 ≥0.78）、空题态进度栏高度 1px。要改版面布局，超出「低成本修复」的范围。
6. **`search_knowledge` 的章节/页码锚点**：现在返回 `title / excerpt / path`，能回溯到文件但回溯不到章节页码；要补需要索引侧记录偏移量。

## 四、可由任意一方执行、但需要环境

1. **e2e 62 条**：Windows + 本机 Edge 才能跑（`channel: 'msedge'`）。命令：
   `cd 01_ICT主工程/frontend-vue && PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npx playwright test --reporter=line --workers=1`
   前提：后端 8000 + dev server 5173 都在跑（`start-dev.ps1`）。
2. **CI 首次运行**：仓库之前没有任何 workflow，push 后第一次跑可能出现环境差异（例如 macOS/Linux 下固定时区、字体、`TMP` 目录行为）。出现红项请把日志贴给我，我按日志改，不要直接放宽断言。
3. **平台侧评估重跑**：`ict-career-agent` 的历史平台评估是 8/8 均分 0.76，但那是旧版本；当前版本重跑同样需要云端凭据。
