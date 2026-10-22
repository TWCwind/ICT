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
