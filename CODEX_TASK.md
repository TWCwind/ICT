# Codex → Claude Code：ICT 路演质量第二轮——真实数据、后端、MCP 与视觉验收

你是执行工程师，Codex 是总控验收者。第一轮已经解决按钮无响应问题并通过前端路演套件，但不能据此宣布项目整体完成。本轮只处理第一轮报告中明确未覆盖的后端、生成数据、MCP、全尺寸截图和交付文档。

## 工作区

- 仓库：`C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区`
- 主工程：`C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区\01_ICT主工程`
- 前端：`C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区\01_ICT主工程\frontend-vue`
- 原始 ZIP：`C:\Users\xiajun\Desktop\ICT赛题2-AgentArts协作包-v1.zip`，只读，不修改、不删除
- 先阅读根目录 `CLAUDE_REPORT.md`、`A_TASK_REPORT.md`、`MCP_INTEGRATION.md`、`TEST_RESULTS.md`、`API_CONTRACT_AGENTARTS.md` 和 `git diff`；保留已有改动，不使用 `git reset --hard`。

## 协作与安全

1. Codex 正在审查第一轮差异；你可以修复真实问题，但不要重写或撤销已验证的按钮修复。
2. 不覆盖用户已有改动，不删除 `e2e/claude-smoke.spec.ts`；若它不是本轮创建，记录归属和是否应保留。
3. 不提交 `node_modules`、缓存、日志、真实密钥、个人运行数据或大批量截图临时目录；不硬编码 API Key、Token、密码。
4. 不依赖外部大模型、在线服务或真实密钥。所有新增测试数据必须位于独立的 `test/generated` 或等价隔离目录，并在数据中明确标记 `test/generated`，不能覆盖 `roadshow-data`。
5. 不伪造 AgentArts 云端已经接入。只能报告实际完成的本地 MCP 启动和调用。
6. 本轮先不要提交 commit、不要推送 PR；等 Codex 读取你的报告、差异、测试输出和截图后再决定提交。

## 一、生成隔离测试数据并验证后端真实流程

1. 检查当前后端启动脚本、配置、数据目录、FastAPI 路由、服务层和 MCP 目录。不要只相信文档，必须以源码和真实 HTTP 返回为准。
2. 在独立测试目录生成结构化 `test/generated` 数据，不覆盖路演数据，至少包括：
   - 3 个学生：demo 学生、普通新学习者、存在学习/练习/错题记录的学生；
   - 5 个岗位及岗位能力要求；
   - 1 门课程；至少 6 个语义化章节；至少 18 个知识点；至少 2 个资源；
   - 练习题、错题、学习记录、学习计划、能力画像更新记录；
   - 缺失学生、错误岗位、空数据和非法参数场景。
3. 课程章节和知识点必须来自演示讲义正文，不能使用文件哈希、`book_`、`textbook_`、上传文件内部 ID、`第1部分`、B站/腾讯视频/视频推荐标题。
4. 启动或使用本地路演后端，实际调用并记录：健康检查、学生画像查询、岗位能力查询、项目状态查询、练习/测试诊断、学习计划保存、能力画像更新、知识图谱数据、资源筛选和排序、普通新学习者不能自动获得 demo 课程；参数错误、无数据、服务异常必须有可解释返回。
5. 执行后端现有 unit/integration/acceptance 测试以及：
   ```powershell
   cd "C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区\01_ICT主工程"
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-all-tests.ps1 -SkipInstall -GeneratedFlow
   ```
   如果命令参数或脚本不存在，先查明真实原因，再使用项目实际等价命令；不得把未执行写成通过。

## 二、MCP 本地真实调用

1. 找到现有 MCP 服务入口和依赖，基于现有业务逻辑实现或修复独立、可测试的服务，不复制一套伪造业务数据。
2. 至少真实调用并记录：`get_student_profile(student_id)`、`get_role_competency(role_name 或 role_id)`、`get_project_status()`。
3. 每个工具必须有明确输入、输出、错误结构；缺失数据、参数错误、服务异常都返回可解释信息。
4. 添加或运行 MCP 单元测试、本地调用脚本或 HTTP/stdio 验证；记录启动方式、传输方式、地址和真实返回摘要。
5. 不得声称已接入 AgentArts 云端，除非本轮确实完成真实云端调用；没有云端就明确写“未接入云端”。

## 三、前端必跑命令与全路由复核

在 `frontend-vue` 目录真实执行并保存结果：

```powershell
npm run check
npm run audit:ui
npm run build
npm run test:roadshow -- --project=msedge --workers=1
npx playwright test e2e/interaction-qa.spec.ts --project=msedge --workers=1
npm run test:generated-flow -- --project=msedge --workers=1
```

用真实 Playwright 访问并操作：`/`、`/profile`、`/workshop`、`/path`、`/exercise`、`/knowledge`、`/multimodal`、`/tutor`、`/evaluate`，以及练习页签“题库定制、智能做题、错题本、历史星系、知识点诊断”。检查控制台错误、500、空按钮、不可见遮罩、`undefined`/`null`、错误状态重试、弹窗/抽屉 Escape、焦点返回、移动端滚动。

知识图谱必须覆盖缩放、适配窗口、Ctrl/Cmd+滚轮、普通滚轮、节点点击、Tab/Enter/Space/方向键/Home/End/Escape、`+ - 0 F`、输入框不抢快捷键、全屏降级、ARIA 和移动端；错题星系必须覆盖 Canvas tabindex/role/aria-describedby、高 DPI 点击、键盘缩放、空状态、卸载资源释放、`prefers-reduced-motion`。

## 四、截图与人工视觉验收

用真实本地路演服务生成截图，尺寸必须包含：`1440x900`、`1280x720`、`1024x768`、`768x1024`、`390x844`。每种尺寸至少截取：首页、练习诊断、知识图谱、资源工坊、学习路径、评估进化。

截图放到已被 `.gitignore` 排除的测试产物目录，并在报告列出准确路径。你必须查看截图，不得只判断文件存在。重点检查：视觉层级、字号、对比度、间距、大片空白、遮挡、裁切、哈希/内部 ID、乱码、横向溢出、手机滚动、图谱四列、统计数字与接口一致、是否像正式路演产品。发现问题直接修改后重新启动、截图和测试。

## 五、交付文档

基于真实执行结果更新根目录：`A_TASK_REPORT.md`、`MCP_INTEGRATION.md`、`TEST_RESULTS.md`、`API_CONTRACT_AGENTARTS.md`。

报告必须写明：测试数据规模及 `test/generated` 来源、真实接口统计、修改文件、每条命令的真实结果、通过/失败数量、截图尺寸和页面、人工视觉结论、MCP 是否真实调用、AgentArts 云端是否接入、未修复限制。不得把静态检查或计划写成真实通过。

完成后写根目录 `CLAUDE_REPORT.md`，补充本轮变更、命令、测试输出、截图位置、失败原因、修复状态和剩余问题。不要提交或推送，等待 Codex 验收。
