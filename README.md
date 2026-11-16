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

## 验证状态（2026-11-16 实测）

| 项 | 结果 |
| --- | --- |
| 后端单元测试 | 46 项全部通过 |
| 后端验收脚本 `tests/backend_acceptance.py` | 12/12 通过 |
| 前端生产构建（`vue-tsc -b` + `vite build`） | 通过 |
| Playwright e2e 全量 | 62 个用例通过（含 2 条已知体验债，以 `test.fail` 标注） |

复现方式见 `01_ICT主工程/README_TESTING.md`；线上/内网部署前请先读 `MCP_INTEGRATION.md` 的云端限制。

## 当前明确的限制（不要当成已完成能力对外宣称）

1. **数据层是演示级的**：以 JSON 文件承载状态，无数据库迁移、无并发控制、无多用户隔离
   （`backend/app/repo.py` 直接按学号建目录）。多人同时使用会互相覆盖，上生产必须换数据库。
2. **AgentArts 云端接入未完成**：MCP 服务已完成加固（API Key + 限流 + 日志脱敏，9 个工具），
   并在本机与临时公网隧道下实测通过；正式注册仍缺固定公网 HTTPS 域名、团队空间与网关注册。
3. **实时语音 / 数字人处于禁用状态**：未配置实时语音通道时会回退到浏览器语音，并在页面上如实提示。
4. **超大单文件仍在**：`backend/app/agents/orchestrator.py`、`backend/app/services/knowledge_hub.py`、
   `frontend-vue/src/profile-center.css`、`frontend-vue/src/pages/ExerciseCenterPage.vue` 等尚未拆分。
5. **前端部分 chunk 超过 500KB**（`ExerciseCenterPage`、评估页），后续需要按路由或依赖手工分包。

## 仓库约定

- 不要把本机绝对路径、临时文件、`.env`、API Key 提交进仓库。
- 文档里写的技术栈、接口、目录结构必须能在仓库里指到具体文件；计划中的内容要标注「计划中」。
- 提交信息用中文说明改了什么、为什么。
- 本仓库尚未添加开源许可证文件；如需公开复用，先与参赛团队确认授权方式。
