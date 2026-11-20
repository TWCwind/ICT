# 华为 ICT 赛题 2 · AgentArts 协作包

软件工程项目实践与岗位胜任力提升多智能体。本仓库包含主工程与一个辅助数据模块，
两者代码独立、互不依赖，可分别运行。

```
.
├─ 00_给队友的项目说明.md      # 赛题背景、方案与迁移计划
├─ 01_ICT主工程/               # 主工程：用户画像 / 知识中枢 / 资源工坊 / 学习路径 / 练习诊断 / 效果评估
│  ├─ backend/                 # FastAPI 后端（含多智能体编排、题库、路线图、评估）
│  ├─ frontend-vue/            # Vue 3 + Vite 前端（含 Playwright e2e）
│  ├─ tests/                   # 后端验收脚本
│  ├─ roadshow-seed/           # demo 学号基线数据（随仓库提交）
│  ├─ roadshow-data/           # 演示用教材与知识数据
│  ├─ start-dev.ps1            # 一键启动后端 + 前端
│  └─ README.md                # 主工程详细说明
├─ 02_服创岗位能力模块/          # 辅助模块：岗位图谱子系统（FastAPI + JSON 数据 + faiss 语义检索）
├─ mcp_server/                 # 主工程对外暴露的 MCP 工具（画像/岗位能力/项目状态）
├─ API_CONTRACT_AGENTARTS.md          # AgentArts 侧接口契约（主工程内部还有 01_ICT主工程/API_CONTRACT.md）
├─ MCP_INTEGRATION.md          # MCP 与 AgentArts 接入说明
├─ README_TESTING.md、TEST_RESULTS.md
└─ NATIONAL_AWARD_READINESS.md、TEAMMATE_BUG_REGRESSION.md
```

## 快速开始（主工程）

```powershell
cd 01_ICT主工程
./安装依赖.ps1        # 首次：安装后端 venv 与前端 node_modules
./start-dev.ps1       # 后端 http://127.0.0.1:8000，前端 http://127.0.0.1:5173
```

登录（demo）：手机号 `10000000000`，密码 `demo123`，验证码取登录框上方四个字符。
切换 demo 学号：首页「切换演示学号」（课程、练习记录、评估证据都挂在学号下）。

## 验证状态（2026-11-20 实测）

| 项 | 结果 |
| --- | --- |
| 后端单元测试 | 47 项全部通过（`STORAGE_BACKEND=json` 与 `sqlite` 各跑一遍，均 47/47） |
| 后端验收脚本 `tests/backend_acceptance.py` | 11/12 通过——`generate-resources` 生成耗时 40s，超过脚本 25s 的客户端超时，json 与 sqlite 后端耗时一致，与存储层无关 |
| 双后端 API 对比 | 16 条只读接口逐字段一致（profile / resources / exercise / path / knowledge / evaluate / dashboard / delivery / push / tutor） |
| 并发写入 | 20 线程写学习事件 20/20、20 线程追加错题 20/20；json 基线 0/20、1/20（读-改-写覆盖丢失） |
| 前端生产构建（`vue-tsc -b` + `vite build`） | 通过 |
| Playwright e2e 全量 | 64/65 通过（Edge，约 18–19 分钟/轮）。唯一失败 `full-flow-generated.spec.ts:72` 是既有用例与 UI 规则冲突：按钮探针 spec 会调用生成接口追加第 6 个资源，使该课程资源数变成 5，而详情面板「配套资源」最多渲染 4 条；json 与 sqlite 两后端结果一致，与本次改动无关 |
| 50 条评测集：工具路由 | 首步命中 36/50，计划覆盖 42/50（`scripts/eval/route_eval.py`） |
| 50 条评测集：答案级可核验项 | 见 `scripts/eval/evidence/answer_eval_2026*.md`；工具无业务错误 35/50；模型自评 50/50 条：完全满足 34、部分 15、不满足 1，加权 0.83。尚无独立人工评分。 |
| CI | `.github/workflows/ci.yml`：后端单测、MCP 测试、评测静态校验、前端类型检查+构建 |

复现方式见 `01_ICT主工程/README_TESTING.md`；线上/内网部署前请先读 `MCP_INTEGRATION.md` 的云端限制。
e2e 依赖 Edge（`channel: 'msedge'`）与本地数据，因此放在手动工作流 `.github/workflows/e2e.yml`，
不挂在每次 push 上——避免把「跑不动」误读成「不需要」。
**还没做的、需要人做的清单**见 `REMAINING_WORK.md`。

## 当前明确的限制（不要当成已完成能力对外宣称）

1. **数据层已切到 SQLite，JSON 保留一个版本作回退**：元数据落 `<DATA_DIR>/app.db`（SQLite + WAL），
   正文内容文件仍留在磁盘（`content_uri` 指向），表结构见 `backend/app/db/sqlite.py`；
   两种后端（`STORAGE_BACKEND=json|sqlite`）共用 `backend/app/repo.py` 同一组签名，路由与服务不感知差异，
   迁移与核对命令见 `01_ICT主工程/README_TESTING.md`。并发写入已由单条 INSERT 与 `busy_timeout` 兜住
   （20 线程写事件 20/20、20 线程追加错题 20/20；JSON 基线为 0/20、1/20，读-改-写覆盖丢失已消除）。
   仍未做：多用户隔离只有学号级目录/单库文件，账号体系与权限边界不在本版本范围内。
2. **AgentArts 云端接入未完成**：MCP 服务已完成加固（API Key + 限流 + 日志脱敏，9 个工具），
   并在本机与临时公网隧道下实测通过；正式注册仍缺固定公网 HTTPS 域名、团队空间与网关注册。
3. **实时语音 / 数字人处于禁用状态**：未配置实时语音通道时会回退到浏览器语音，并在页面上如实提示。
4. **超大单文件已拆分，死样式已删除**：`knowledge_hub.py` 1727 → 301 行（6 模块 + 门面）、`orchestrator.py` 1786 → 927 行（`text_utils`/`profile_tools`/`path_tools`/`content_audit`/`agent_registry` + 门面），旧导入路径与测试 patch 目标全部保持不变；`profile-center.css`（4231 行）实测 119 个类名中 105 个无任何组件使用、380 个选择器只有 3 个能命中且无视觉效果，已整份删除，**全局 CSS 减少 68.7 KB（812 KB → 743 KB）**。
5. **前端已做三轮分包**：①`three` 改成「历史星系」页签按需加载，`vue`/`markdown`/`three`/字体各自独立 chunk；②练习页 `ExercisePage`（1346 行）改异步，专业目录与 localStorage 帮助函数抽成模块；③星系 3D 渲染（约 1400 行）搬进 `src/composables/useTagGalaxyScene.ts` 并改为打开页签时才 `import()`。练习中心首屏 chunk 585KB → 102KB → 70KB → **43.6KB**，页面文件 3361 → **1923 行**；仍剩 `vendor-three` 705KB 与 `vendor-markdown` 381KB 两个懒加载大块。

## 仓库约定

- 不要把本机绝对路径、临时文件、`.env`、API Key 提交进仓库。
- 文档里写的技术栈、接口、目录结构必须能在仓库里指到具体文件；计划中的内容要标注「计划中」。
- 提交信息用中文说明改了什么、为什么。
- 本仓库尚未添加开源许可证文件；如需公开复用，先与参赛团队确认授权方式。
