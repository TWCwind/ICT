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
| 前端分包三轮（three 按需 + vendor 拆块 + 练习页异步 + 目录/存储模块化 + 星系渲染 composable） | `frontend-vue/src/pages/ExerciseCenterPage.vue`、`vite.config.ts`、`src/data/practiceCatalogs.ts`、`src/utils/practiceStorage.ts`、`src/composables/useTagGalaxyScene.ts`、`src/utils/hashText.ts` | `node node_modules/vite/bin/vite.js build` 后看 chunk 体积：练习中心首屏 585KB → 43.6KB，另有 32KB `ExercisePage` 与 28KB `useTagGalaxyScene` 按需块 |

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

1. **前端分包（三轮已完成）**：①`three` 改成「历史星系」页签按需加载并把 `vue`/`markdown`/`three`/字体拆成独立 chunk；②`ExercisePage`（1346 行）改 `defineAsyncComponent`，专业目录与 localStorage 帮助函数抽成 `src/data/practiceCatalogs.ts` 与 `src/utils/practiceStorage.ts`；③星系 3D 渲染（约 1400 行）搬进 `src/composables/useTagGalaxyScene.ts`（工厂 + `TagGalaxyEngine` 类型），页面改成 `shallowRef` + `await import()` 懒加载，`hashText` 抽到 `src/utils/hashText.ts` 共享。练习中心首屏 chunk 585kB → 102kB → 70kB → **43.55kB**（另有 32kB `ExercisePage`、28kB `useTagGalaxyScene` 按需块），页面文件 3361 → **1923 行**。仍剩 `vendor-three` 705kB、`vendor-markdown` 381kB 两个懒加载大块。
2. **~~数据层 JSON → SQLite~~（已完成，分支 `feat/sqlite-storage`）**：新增 `backend/app/storage/`（协议 + JSON 实现 + SQLite 实现）与 `scripts/migrate/json_to_sqlite.py`，服务层全部改走 `app/repo.py` 门面；
   `STORAGE_BACKEND=sqlite` 下 47 单测、16 条只读 API 双后端逐字段一致、12 项验收 11/12（唯一失败项为模型生成 40s 超过客户端 25s 超时，与存储无关）；
   并发写入从 `0/20`、`1/20` 提升到 `20/20`、`20/20`（`scripts/verify/concurrency_check.py`）。JSON 后端保留这一版作为回退，下个版本再删。
   仍未做：多用户隔离（账号体系/权限）与旧库在线迁移窗口，需产品侧确认。
3. **拆 God File / 删死代码（基本完成）**：`knowledge_hub.py` 1727 → 301 行（6 模块 + 门面）；`orchestrator.py` 1786 → 927 行（`text_utils` 198 / `profile_tools` 203 / `path_tools` 221 / `content_audit` 248 / `agent_registry` 93 + 门面）。两次拆分都保持旧导入与 `patch("app.agents.orchestrator.*")` 目标不变，并逐字节验证输出等价（knowledge 四项 sha256 `184c6876…65f0`、orchestrator 26 项 `636a4ba2…4670`）。`profile-center.css`（4231 行）确认整份是上一版「学习 DNA」页的死样式（105/119 类名无组件使用、380 个选择器中仅 3 个能命中且无视觉效果、22 张全站截图像素级一致），已删除，全局 CSS 812 → 743 KB。
4. **`reference-screens.css` 重复主题块**：`/* Workshop */`（114/116/134/137/355 行）、`/* Evaluation */`（248/263/268 行）存在重复定义，我修 bug 时只删了两组重复的选择器，整块合并没做。
5. **大屏留白体验债**：旧 `final-density.spec.ts` 的固定课程/练习容器已不存在，现已迁移为当前题库表单、开始做题、空错题本与知识节点的 4 项真实行为检查（4/4 通过）。2048×1152 的短表单下方仍有较大空白；如要再提高大屏信息密度，应重新设计内容布局，不能用假数据填满。
6. **`search_knowledge` 的章节/页码锚点**：现在返回 `title / excerpt / path`，能回溯到文件但回溯不到章节页码；要补需要索引侧记录偏移量。

## 四、可由任意一方执行、但需要环境

1. **旧全量 E2E 与手动工作流**：本轮路演 19/19、扩展 36/36 已在 Windows + 本机 Edge 上通过；包含历史 45 分钟按钮探针的旧全量运行未完成，GitHub 手动 E2E 工作流也未触发。命令：
   `cd 01_ICT主工程/frontend-vue && PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npx playwright test --reporter=line --workers=1`
   前提：后端 8000 + dev server 5173 都在跑（`start-dev.ps1`）。
2. **CI 首次运行**：仓库之前没有任何 workflow，push 后第一次跑可能出现环境差异（例如 macOS/Linux 下固定时区、字体、`TMP` 目录行为）。出现红项请把日志贴给我，我按日志改，不要直接放宽断言。
3. **平台侧评估重跑**：`ict-career-agent` 的历史平台评估是 8/8 均分 0.76，但那是旧版本；当前版本重跑同样需要云端凭据。
