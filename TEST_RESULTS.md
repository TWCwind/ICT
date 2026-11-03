# 路演维护测试结果

执行日期：2026-10-22（Asia/Shanghai）

## 1. 真实启动与接口核验

启动命令：

```powershell
cd C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区\01_ICT主工程
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-roadshow.ps1 -NoBrowser
```

结果：后端 `http://127.0.0.1:8000`、前端 `http://127.0.0.1:5173` 均 ready。

实际接口调用：

```text
GET /api/health                         200，roadshow/ready，外部模型未配置
GET /api/knowledge/map?student_id=demo  200，chapters=6，concepts=30，resources=3
GET /api/path/overview?student_id=demo   200，has_plan=true，stage_count=6
GET /api/knowledge/map?student_id=new-roadshow-user  200，nodes=0
```

## 2. 必须命令

在 `01_ICT主工程\frontend-vue` 执行：

| 命令 | 结果 |
|---|---|
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过 |
| `npm run build` | 通过，2317 modules transformed |
| `npm run test:roadshow -- --project=msedge --workers=1` | 通过，16/16 |
| `npx playwright test e2e/interaction-qa.spec.ts --project=msedge --workers=1` | 通过，3/3 |

`interaction-qa.spec.ts` 还生成了 30 张五尺寸截图，并检查控制台错误、500 API、页面统计、图谱章节/知识点、键盘缩放、错题星系和移动端表现。

在 `01_ICT主工程` 执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-all-tests.ps1 -SkipInstall
```

最终结果：

```text
Backend acceptance       12/12 passed
Integration flow           3/3 passed
Backend unit tests        44/44 passed
Frontend build             passed
Frontend E2E              16/16 passed
All tests passed
```

## 3. MCP 实际验证

安装并启动：

```powershell
cd C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区
.\install_mcp.ps1
.\start_mcp.ps1
```

协议测试：

```powershell
.\test_mcp.ps1
```

结果：业务测试 7/7，通过标准 Streamable HTTP 客户端发现并调用：

- `get_student_profile(student_id=demo)`：成功，来源为项目 demo 数据。
- `get_role_competency(role_id=job_001)`：成功，来源为结构化岗位画像。
- 工具列表还包含已完成的 `get_project_status`。

本地 smoke client 已关闭系统代理继承，避免本机代理把 `127.0.0.1` 请求错误转发为 502。

## 4. 非阻断警告

- Vite 提示 `ExerciseCenterPage`、`EvaluatePage` 等少数 chunk 超过 500 kB；构建仍成功，未影响页面或测试。
- AgentArts 公网安装未执行，原因是当前没有公网 HTTPS 地址和 AgentArts 团队空间凭据；这不是本地工程失败。
- 无真实模型密钥时不伪造模型生成内容，相关接口按项目契约返回本地数据或可解释错误。

## 5. 隔离测试数据与完整流程结果

生成命令：

```powershell
cd C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区\01_ICT主工程
python .\tests\generate_test_dataset.py --output .\test-results\generated-dataset
```

一键完整命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-all-tests.ps1 -SkipInstall -GeneratedFlow
```

生成数据集标识为 `test/generated/full-flow-v1`，包含 3 个学生、5 个岗位、1 门课程、6 个章节、30 个知识点、2 个资源、练习和错题、学习记录、学习计划、能力画像更新记录及异常输入场景。服务运行时使用独立 `test-results\runtime-data-*`，没有覆盖原有演示数据。

本轮真实结果：

| 检查项 | 结果 |
|---|---:|
| 后端验收 | 12/12 通过 |
| 集成流程 | 3/3 通过 |
| 生成数据全流程 | 6/6 通过 |
| 后端单元测试 | 44/44 通过 |
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过 |
| 前端构建 | 通过 |
| 原有路演 E2E | 16/16 通过 |
| 生成数据路演 E2E | 2/2 通过 |
| 知识图谱资源卡首屏布局 | 3/3 完整显示，均位于操作栏上方 |

新增前端验收生成 30 张截图，位于 `frontend-vue\test-results\generated-flow\`，覆盖 1440x900、1280x720、1024x768、768x1024、390x844 五种尺寸，以及首页、练习诊断、知识图谱、资源工坊、学习路径、评估进化六个页面。截图已人工查看，确认知识图谱在平板可见四列，手机端可纵向滚动，页面统计与接口统计一致。

## 6. 当前限制

- `npx playwright test e2e/interaction-qa.spec.ts --project=msedge --workers=1` 已单独在本地路演服务上执行并通过 3/3；若单独运行，需要先启动本地路演服务。
- AgentArts 云端尚未安装验证，因为没有公网 HTTPS 地址、团队空间和鉴权凭据；本地 MCP 已实际调用，不代表云端已接入。

## 7. 本轮视觉修复复测

人工查看截图时发现 1440x900 知识图谱右侧详情面板的第三张配套资源卡原先会被底部操作栏部分遮挡。已将配套资源区前置到节点详情首屏，并在 `full-flow-generated.spec.ts` 增加三张资源卡均位于操作栏上方的几何断言。

修复后重新执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-all-tests.ps1 -SkipInstall -GeneratedFlow
```

结果仍为：后端验收 12/12、集成 3/3、生成数据流程 6/6、后端单元测试 44/44、原有路演 E2E 16/16、新增生成数据路演 E2E 2/2。修复后的 1440x900、390x844 知识图谱截图已重新人工查看。

## 2026-10-24 连接恢复专项

使用本地路演服务，前端测试地址设置为 `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174`。

- `npm run check`：通过。
- `npm run audit:ui`：通过。
- `npm run build`：通过；练习页 chunk 大于 500 kB 的既有告警仍存在。
- `npx playwright test e2e/connection-recovery.spec.ts e2e/button-actions.spec.ts --project=msedge --workers=1`：3/3 通过（约 2.5 分钟）。
- 排除健康检查流量后，单独复跑 `e2e/button-actions.spec.ts --project=msedge --workers=1`：1/1 通过（约 2.3 分钟）。新增连接测试已纳入 `test:roadshow` 默认清单。
- 真实健康检查：5174 的 `/api/health` 返回 200、success=true。
- 实际查看 1440x900 桌面知识图谱、390x844 手机断线提示截图；后者无横向溢出且重试按钮可见，前者显示 6 章、30 知识点、3 资源。
- 本轮未重跑全量后端、MCP 和全部视口验收；上文历史结果不能当成本轮结果。按钮遍历测试验证可观察反馈/业务请求，不等于验证每项业务输出的正确性。

## 2026-10-24 总控终验结果

本轮在真实本地路演服务和隔离 `test/generated/full-flow-v1` 数据上重新执行：

```powershell
cd C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区\01_ICT主工程
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-all-tests.ps1 -SkipInstall -GeneratedFlow
```

结果：后端验收 12/12、集成流程 3/3、生成流程 6/6、后端单元测试 44/44、前端构建通过、路演 E2E 18/18、生成流程 E2E 2/2，脚本最终输出 `All tests passed`。

最终修改后的前端专项检查：

| 命令 | 结果 |
|---|---:|
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过 |
| `npm run build` | 通过 |
| `npx playwright test e2e/claude-round2-qa.spec.ts --project=msedge --workers=1` | 6/6 |
| `npx playwright test e2e/competition-responsive.spec.ts --project=msedge --workers=1` | 4/4 |
| `npx playwright test e2e/interaction-qa.spec.ts --project=msedge --workers=1` | 3/3 |

交互截图最终共 30 张，目录为 `frontend-vue\test-results\roadshow-screenshots\`，覆盖 1440x900、1280x720、1024x768、768x1024、390x844 五种尺寸以及首页、练习诊断、知识图谱、资源工坊、学习路径、评估进化。Codex 实际查看了桌面、1280 中宽屏、1024 平板和 390 手机截图。

MCP 终验：`test_mcp.ps1` 在本地服务启动后通过 7/7 单元测试；标准 Streamable HTTP 客户端发现 3 个工具，并实际调用 `get_student_profile`、`get_role_competency`、`get_project_status`，三次均 `is_error=false`。MCP 地址为 `http://127.0.0.1:8010/mcp`。这只证明本地 MCP 可调用，不代表已接入 AgentArts 云端。

补充说明：构建仍有少数 chunk 大于 500 kB 的既有警告；实时语音/数字人因没有真实外部凭据保持禁用并显示中文原因；无公网 HTTPS、团队空间和鉴权凭据，AgentArts 云端安装未执行。

针对用户原先打开的地址 `http://127.0.0.1:5174/`，额外执行 `e2e/claude-smoke.spec.ts`，真实登录后点击画像、工坊、练习、知识、路径、评估和用户设置：1/1 通过，控制台错误 0，所有页面主内容可见。

## 2026-10-24 晚间补充回归

| 命令 / 测试 | 结果 |
|---|---|
| `npm run check` | 通过 |
| `npm run build` | 通过；保留既有大体积 chunk 警告 |
| `e2e/claude-round1-api-failure.spec.ts` | 2/2 通过 |
| `e2e/claude-round1-repro.spec.ts` | 1/1 通过；146 个按钮、135 个点击、0 个无结果、0 个命中遮挡、0 个控制台错误 |

本轮全按钮探针先将按钮滚入当前视口再执行 `elementFromPoint` 命中判断，避免把页面底部按钮误判为遮挡。Claude Code 非交互回归会话未返回最终报告，未将其未输出的测试结果计入本表；MCP 结果沿用前文已记录的本地 7/7 和 3 次真实调用。

## 2026-10-25 国奖级优化回归

本轮基于最新 `origin/main` 创建 `codex/national-award-upgrade`，重新启动本地路演版并调用真实接口：

| 检查项 | 实际结果 |
|---|---:|
| `/api/health` | 200，`success=true`，`mode=roadshow`，本地 demo 模式 |
| demo 知识图谱 | 6 章、30 个知识点、3 个资源、44 条关系 |
| 普通新学习者图谱 | 0 个节点、0 个章节 |
| 前端类型检查 | 通过 |
| UI 契约审计 | 通过 |
| 前端生产构建 | 通过，2321 modules transformed |
| 后端单元测试 | 45/45 通过 |
| MCP 单元测试 | 7/7 通过 |
| 路演 E2E | 19/19 通过 |
| 响应式验收 | 4/4 通过 |

截图目录为 `01_ICT主工程\frontend-vue\test-results\roadshow-screenshots\`，共 30 张，尺寸为 `1440x900`、`1280x720`、`1024x768`、`768x1024`、`390x844`，覆盖首页、练习诊断、知识图谱、资源工坊、学习路径和评估进化。已实际查看代表性桌面、平板和手机截图。

本轮发现并修复：无标题教材的“第1部分”回退命名、哈希课程标题风险、健康检查旧图谱地址、流式请求断线错误，以及 MCP 读取陈旧 `backend/data` 导致的数据不一致。构建仍有少数大 chunk 警告，但未影响路演功能或测试。

## 2026-10-29 队友现场问题回归

本轮最终代码验证：

| 命令 | 结果 |
|---|---|
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过 |
| `npm run build` | 通过，2321 modules；ExerciseCenter 约 582 kB，有非阻塞 chunk 警告 |
| `npm run test:roadshow -- --project=msedge --workers=1 --reporter=line` | 19/19 通过 |
| `npx playwright test e2e/teammate-bug-regression.spec.ts --project=msedge --workers=1 --reporter=line` | 8/8 通过 |
| `python -m unittest discover -s tests -p "test*.py" -v` | 45/45 通过 |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\test_mcp.ps1` | MCP 7/7；`get_student_profile`、`get_role_competency`、`get_project_status` 均 `is_error=false` |

智能做题真实接口验证：进入“智能做题”页签时请求数为 0；点击“开始做题”后请求 `/api/exercise/session`，返回 HTTP 200、`success=true`、题目数 0。当前 demo 学生无已生成题库，页面转为空题提示，没有伪造题目。

截图：`01_ICT主工程\frontend-vue\test-results\roadshow-screenshots\` 下五种分辨率、六个页面共 30 张；另有 1024x768 和 390x844 的智能做题开始前/点击后 4 张。截图已通过图像查看工具人工检查，目录被 Git 忽略，不提交。

说明：此前隔离生成流记录仍按历史结果保留（后端验收 12/12、集成 3/3、生成流程 6/6、生成流程 E2E 2/2）；本轮没有在最终 UI 变更后重跑整个生成流脚本。AgentArts 云端仍未接入。

## 2026-10-29 智能做题体验增量复验

针对真实使用中的等待与失败反馈，再次执行：

| 命令 / 检查 | 结果 |
|---|---|
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过 |
| `npm run build` | 通过，2321 modules；ExerciseCenter 约 583 kB，仍有非阻塞 chunk 警告 |
| `npx playwright test e2e/teammate-bug-regression.spec.ts --project=msedge --workers=1 --reporter=line` | 9/9 通过 |
| 实际本地练习接口恢复 | 人为触发一次 503 后点击“重试加载”，真实本地接口返回成功；无未捕获页面异常 |
| 键盘焦点与截图检查 | 加载、错误、空题状态均将焦点移至对应标题；桌面/手机截图已人工查看 |

本次没有重跑前端路演全套、后端单测或 MCP 测试：改动只涉及练习页的状态呈现、焦点管理和样式；此前记录的路演 19/19、后端 45/45、MCP 7/7 属于前序提交结果。最终 7 张桌面/手机截图仅存于被忽略的 `01_ICT主工程/frontend-vue/test-results/ux-followup-human-flow-reviewed-e99f48784d9d4d7bb8877646f2466bb5/`，没有进入 Git。之前路演全套测试生成的临时截图已被 Playwright 清理。

## 2026-10-30 前端图表与响应式复验

| 检查 | 真实结果 |
|---|---|
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过 |
| `npm run build` | 通过；ExerciseCenter 约 583.26 kB，仍有非阻塞 chunk 体积提示 |
| `npm run test:roadshow -- --project=msedge --workers=1` | 19/19 通过 |
| `npx playwright test e2e/teammate-bug-regression.spec.ts --project=msedge --workers=1` | 10/10 通过；新增真实 API 图表语义用例 |
| 本地健康检查 | `GET /api/health` 成功，FastAPI ready、roadshow 模式；模型未配置，demo 模式开启 |
| 画像图表数据 | 回归用例读取 `GET /api/profile/demo/overview`，逐项核对画像接口置信度与页面进度条；无数据维度显示待采集 |
| 评估图表数据 | 回归用例读取 `GET /api/evaluate/overview?student_id=demo`，核对维度数量、实际分值和证据缺失状态 |
| 截图与人工查看 | 39 张 PNG；九个页面 1440×900，五个重点页面再覆盖 1280×720、1024×768、768×1024、390×844。截图及总览在 `%TEMP%\ict-ui-review-20261030\`；已人工查看，无页面级横向溢出或明显裁切、遮挡、乱码 |

本轮是前端可视化改进，没有重跑后端单元测试和 MCP 套件；本地健康接口及图表依赖的两个真实 API 已在本轮检查中验证。AgentArts 云端未接入。

## 2026-11-03 企业级前端体验回归

| 检查 | 实际结果 |
|---|---|
| 本地路演启动 | 初始检查时前后端均未监听，Playwright 首次专项探针遇到连接拒绝；运行 start-roadshow.ps1 -NoBrowser 后，5173/8000 恢复，GET /api/health 返回 success=true、FastAPI ready、roadshow 模式 |
| npm run check | 通过 |
| npm run audit:ui | 通过；可见按钮均有交互绑定，页面未发现已知固定数据回退 |
| npm run build | 通过，1768 modules transformed；ExerciseCenterPage 583.26 kB，保留非阻塞 chunk 警告 |
| npm run test:roadshow -- --project=msedge --workers=1 | 19/19 通过（约 5.4 分钟） |
| npx playwright test e2e/teammate-bug-regression.spec.ts --project=msedge --workers=1 | 11/11 通过 |
| 企业体验专项用例 | 1/1 通过；验证手机触控高度、语音未配置时的真实状态与敏感配置过滤、工坊侧栏高度 |
| 页面截图采样 | 29/29；九个路由桌面尺寸及五个重点路由的四种附加尺寸；页面级横向溢出 0，控制台错误 0，4xx/5xx API 响应 0 |
| 触控尺寸检查 | 390×844 和 768×1024 下可见按钮中低于 44px 的数量均为 0 |
| 人工截图复核 | 已查看桌面、平板、手机总览以及工坊、评估原尺寸；无明显裁切、遮挡、横向溢出或内部配置泄露 |

截图路径：C:\Users\xiajun\AppData\Local\Temp\ict-enterprise-review-20261030。截图和临时脚本均未放入仓库。

路演测试最初因服务已经退出而遇到连接拒绝；重新运行项目路演启动脚本并确认真实健康接口恢复后，完整路演套件与队友回归均通过。当前未重跑后端单测和 MCP 测试；AgentArts 云端仍未接入。'

## 2026-11-03 合并 main 后最终复验

本次在 PR #3 分支合并 `origin/main` 后，对合并结果及随后的缺陷修复重新执行检查。使用本地路演数据和真实 FastAPI；没有调用在线模型或 AgentArts 云端。

| 命令 / 检查 | 实际结果 |
|---|---|
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过 |
| `npm run build` | 通过；ExerciseCenterPage 和 Markdown 渲染器仍有非阻塞大 chunk 提示 |
| `npm run test:roadshow -- --project=msedge --workers=1` | 19/19 通过 |
| `npx playwright test e2e/teammate-bug-regression.spec.ts --project=msedge --workers=1` | 11/11 通过 |
| `npx playwright test e2e/competition-responsive.spec.ts --project=msedge --workers=1` | 4/4 通过 |
| `python -m unittest discover -s tests -p "test*.py" -v` | 45/45 通过 |
| 本地 `GET /api/health` | ready；roadshow 模式；外部模型未配置 |
| 本地 `GET /api/knowledge/graph` | 1 门课程、6 章、30 个知识点、2 个资源、43 条关系 |
| 本地 `POST /api/tutor/ask` | 按预期返回“模型尚未配置”，没有伪造回答或学习分析 |
| 页面截图采样 | 29 张；九个页面 1440×900，五个重点页面另覆盖 1280×720、1024×768、768×1024、390×844 |
| 人工截图复核 | 查看五种尺寸总览与问题页原图；修复后手机工坊宽度等于视口，无明显遮挡、裁切或页面横向溢出 |

截图位于 `C:\Users\xiajun\AppData\Local\Temp\ict-enterprise-review-20261103-final`，不在仓库。知识图谱窄屏使用图谱画布内部横向滑动。MCP 套件本轮未运行；AgentArts 云端未接入。Build 的 chunk 体积提示是已知非阻塞限制。

## 2026-11-03 页面结构与视觉整理复测

### 本地服务与截图

- `GET http://127.0.0.1:8000/api/health`：HTTP 200，FastAPI `ready`，`mode=roadshow`，`demo_mode=true`，未配置真实模型。
- 最终截图：33 张 PNG，位于系统临时目录 `C:\Users\xiajun\AppData\Local\Temp\ict-design-restructure\after-verified`；九页桌面和手机各一张，五个重点页面再覆盖 1280×720、1024×768、768×1024。
- 检查视口宽度：33 个截图记录均未出现页面宽度超过视口的情况；390px 评估页宽度为 390px。
- 已人工查看桌面和手机总览，以及评估页 1024×768/390×844、工坊 1280×720/768×1024、画像 1440×900、知识图谱页面。知识图谱画布在窄屏内部横向滚动，页面本身不横向溢出。
- 首页 `HomePage.vue` 没有代码差异；首页长篇宣传正文未改写、删减或重新排序。

### 前端命令与 Playwright

| 命令 | 结果 |
|---|---:|
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过，按钮交互契约和已知静态数据回退检查通过 |
| `npm run build` | 通过；ExerciseCenter 分包约 585 kB，保留非阻断 chunk 警告 |
| `npm run test:roadshow -- --project=msedge --workers=1` 首轮 | 15/19 通过；768×1024 页面导航超时 1 项，另有一次 500 控制台提示导致截图用例失败；2 项未运行 |
| `npx playwright test e2e/competition-responsive.spec.ts --project=msedge --workers=1` 复跑 | 4/4 通过 |
| `npx playwright test e2e/interaction-qa.spec.ts --project=msedge --workers=1` 复跑 | 3/3 通过，含五尺寸截图、图谱键盘与错题星系状态 |
| `npm run test:roadshow -- --project=msedge --workers=1` 完整复跑 | 19/19 通过，3.7 分钟 |
| `npx playwright test e2e/teammate-bug-regression.spec.ts --project=msedge --workers=1` | 11/11 通过 |

队友回归首轮为 10/11：失败项要求已经移除的重复 `.shot-evidence-version` 卡片。现改为展开 `.evaluation-evidence` 并验证实际证据列表；该专项和全套回归均通过。路演首轮的一次 500 提示没有捕获完整 URL；同期后端日志中的本轮业务 API 均为 200，独立页面错误采集与完整套件复跑都没有复现。不能据此将首轮错误归因到某个具体资源。

本轮只改前端和文档，没有运行后端单测或 MCP 测试；历史测试结果不计入本轮。AgentArts 云端没有接入。

## 2026-11-03 隔离样例全流程验收（当前工作区）

### 环境与数据

- 原路演端口 `5173/8000` 来自当前工作区且健康检查成功；避免污染路演数据，本轮可写流程改用隔离前端 `5174`、后端 `8010`。
- 隔离目录：`C:\Users\xiajun\AppData\Local\Temp\ict-acceptance-20261103-018daa3`，通过 `python tests/generate_test_dataset.py --output C:\Users\xiajun\AppData\Local\Temp\ict-acceptance-20261103-018daa3` 生成，manifest 标记 `test/generated/full-flow-v1`；3 个学生、5 个岗位、1 门课程、6 章、30 个知识点、2 个资源，并包含练习/错题/学习记录及错误输入案例。
- 独立后端启动命令：`$env:PYTHONPATH='C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区\01_ICT主工程\backend'; $env:DATA_DIR='C:\Users\xiajun\AppData\Local\Temp\ict-acceptance-20261103-018daa3'; $env:DEMO_MODE='true'; $env:APP_ENV='roadshow'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8010`。独立 Vite 进程从 `frontend-vue` 启动，`configFile:false`，将 `/api`、`/files`、`/exports` 代理到 8010。
- 健康接口返回 ready、roadshow 模式、demo 数据标识开启、外部模型未配置。所有有写入操作只落在隔离目录。

### 修复记录

| 发现 | 根因与修复 | 复测 |
|---|---|---|
| 辅导页将模型未配置错误显示为“HTTP 200” | API 使用 HTTP 200 传递业务失败，消息位于 `error.message`；客户端只取顶层 `message`。现在按错误结构提取中文后端说明 | `e2e/real-processing.spec.ts` 2/2、路演套件 19/19 |
| 1024px 学习路径阶段被裁切 | 后加载的三栏固定宽样式覆盖了中屏两栏规则，六个节点只有四个完全可见。覆盖为中屏两栏，并把推荐资源放到下一行，阶段卡片压缩至容器内 | `claude-round2-qa.spec.ts` 最终 6/6；1024×768 修复截图已人工查看 |
| 评估页专项找不到 `.shot-capability__body` | 页面已从雷达图改为 `.shot-capability-bars`，专项仍查旧类名 | 断言已更新并随专项 6/6 通过 |
| 生成图谱测试把资源数固定为 3 | 隔离图谱接口真实统计是 2，页面按接口返回渲染 | 改为从真实 API 读取统计并逐项核对，生成数据流程 2/2 |

### 命令与结果

| 命令 / 检查 | 实际结果 |
|---|---|
| `GET http://127.0.0.1:8000/api/health` 与隔离 `GET http://127.0.0.1:8010/api/health` | 两者 HTTP 200；隔离数据状态 ready；模型未配置 |
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过：可见按钮动作契约与静态数据回退审计通过 |
| `npm run build` | 通过；ExerciseCenter 584.98 kB、Markdown renderer 385.05 kB 有非阻塞 chunk 体积提示 |
| `npm run test:roadshow -- --project=msedge --workers=1 --reporter=line` | 19/19 通过（最终代码复测，6.5 分钟） |
| `npx playwright test e2e/teammate-bug-regression.spec.ts --project=msedge --workers=1 --reporter=line` | 11/11 通过 |
| `npx playwright test e2e/real-processing.spec.ts --project=msedge --workers=1 --reporter=line` | 2/2 通过；画像、路径、评估写入读回，题库生成、答题和错题入口可操作；未配置模型的错误如实展示 |
| `npm run test:generated-flow -- --project=msedge --workers=1 --reporter=line` | 2/2 通过；五种视口截图，图谱统计按接口、最后章节可选择、资源数按接口且处于详情面板内 |
| `npx playwright test e2e/claude-round2-qa.spec.ts --project=msedge --workers=1 --reporter=line` | 初次 4/6：一个旧评估选择器断言过期、一个 1024px 时间线确实裁切；修复 CSS 和断言后 6/6 通过 |
| 临时截图专项 `e2e/_acceptance-extra-screenshots.spec.ts` | 1/1；补出画像、辅导、多模态桌面与手机截图；临时 spec 已移除 |
| `$env:DATA_DIR='C:\Users\xiajun\AppData\Local\Temp\ict-acceptance-20261103-018daa3'; python -m unittest discover -s tests -p "test*.py" -v`（backend 目录） | 45/45 通过 |
| `$env:DATA_DIR='C:\Users\xiajun\AppData\Local\Temp\ict-acceptance-20261103-018daa3'; python tests/generated_full_flow.py http://127.0.0.1:8010`（主工程目录） | 6/6 通过：数据契约、健康/学生、图谱语义统计、新学习者隔离、生成学生状态写入、异常响应 |

### 真实用户流程与限制

实际浏览覆盖 `/`、`/profile`、`/workshop`、`/path`、`/exercise`、`/knowledge`、`/multimodal`、`/tutor`、`/evaluate`。路演核心流程使用测试登录并覆盖退出/重新进入；完成画像、路径计划和评估报告 API 写入并读回。练习使用明确标记的本地模板题库、提交答案并检查结果统计。练习页签、历史星系、知识图谱节点/键盘/滚轮/全屏和中屏路径均做真实交互。

模型未配置期间，资源生成、辅导回答和多模态资源生成都不能走成功分支；三者实际请求后均呈现服务端未配置原因，不生成伪内容。故新生成资源的成功预览/导出闭环无法在当前服务配置下验收。MCP 本轮未运行；AgentArts 云端未接入。

### 截图人工验收

最终截图位于 `C:\Users\xiajun\AppData\Local\Temp\ict-live-acceptance-20261103-018daa3`：六个主要页面在 1440×900、1280×720、1024×768、768×1024、390×844 共 30 张；画像、辅导、多模态在桌面和手机另 6 张；两张总览 JPEG。已使用图像查看工具查看两张总览、九个页面代表图、手机路径、桌面辅导/画像、多模态提示和 1024px 路径修复图。首页长篇宣传文本及版式均未改动，`HomePage.vue` 无 diff。
