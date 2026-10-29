# MCP 启动、测试与 AgentArts 接入

最近本地验证：2026-10-25。业务测试 7/7，标准 Streamable HTTP 客户端已发现并调用三个工具；没有声称已完成 AgentArts 云端接入。

## 1. 实现概况

- 服务目录：`mcp_server/`
- 协议：MCP Streamable HTTP
- 本地端点：`http://127.0.0.1:8010/mcp`
- 模式：`stateless_http=True`、`json_response=True`
- 已实现工具：`get_student_profile`、`get_role_competency`、`get_project_status`
- 已实际验证三个工具；没有声称已部署或已接入 AgentArts 云端。

AgentArts 官方文档说明远程自定义 MCP 可使用 Streamable HTTP/SSE，且 AgentArts 是公有云服务，不能直接访问本机或内网地址；生产接入必须提供公网可访问地址。参考：

- [自定义接入 MCP](https://support.huaweicloud.com/usermanual-agentarts0/agentarts_05_0136.html)
- [AgentArts MCP 入站协议](https://support.huaweicloud.com/highcode-agentarts/agentarts_10_069.html)

## 2. 本地安装

在本工作区根目录运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_mcp.ps1
```

该脚本创建独立 `.venv-mcp`，避免 MCP SDK 的 Starlette 版本与主 FastAPI 工程互相影响。

## 3. 本地启动

```powershell
.\start_mcp.ps1
```

也可显式指定地址：

```powershell
$env:MCP_HOST = "127.0.0.1"
$env:MCP_PORT = "8010"
.\start_mcp.ps1
```

## 4. 实际调用验证

保持 MCP 服务运行，在另一个 PowerShell 窗口执行：

```powershell
.\test_mcp.ps1
```

或只执行协议客户端：

```powershell
.\.venv-mcp\Scripts\python.exe .\mcp_server\smoke_client.py --url http://127.0.0.1:8010/mcp
```

smoke client 对本地 HTTP 客户端关闭系统代理继承，避免代理将 `127.0.0.1` 请求错误转发为 502。

本次实测工具发现结果：

```json
{
  "available_tools": [
    "get_student_profile",
    "get_role_competency",
    "get_project_status"
  ]
}
```

调用示例：

```json
{"name": "get_student_profile", "arguments": {"student_id": "demo"}}
```

```json
{"name": "get_role_competency", "arguments": {"role_id": "job_001"}}
```

三次调用均通过标准 MCP 客户端完成，`is_error=false`；学生画像和项目状态来自当前 `01_ICT主工程\roadshow-data`（无运行目录时回退到 `roadshow-seed`），岗位能力来自结构化岗位画像。MCP 与前端路演版不再读取陈旧的 `backend/data`。

## 5. 部署为 AgentArts 可访问服务

本地验证地址不能直接填入 AgentArts。部署时：

1. 将不含 `.env`、虚拟环境和依赖缓存的工作区部署到云主机或容器。
2. 设置 `MCP_HOST=0.0.0.0`、`MCP_PORT=8010`。
3. 用 HTTPS 反向代理或 API 网关暴露 `https://你的域名/mcp`。
4. 在网关配置 API Key、OAuth2 或访问控制；当前示例服务本身没有硬编码密钥，也没有内置公网鉴权。
5. AgentArts 中进入“开发中心 > 组件库 > MCP > 创建 MCP > 空白创建”。
6. 安装方式选择 `Streamable HTTP`，服务地址填写公网 HTTPS 的 `/mcp` 地址。
7. 如网关需要鉴权，在 AgentArts 的请求头/API Key 配置中填写，不写入源码。
8. 安装后检查工具列表，再分别测试 `get_student_profile` 和 `get_role_competency`。

AgentArts 为兼容负载均衡会携带会话头；服务已按其官方建议采用无状态 HTTP 模式。

## 6. Agent 提示词建议

```text
当需要了解学生当前能力、薄弱点或学习证据时，调用 get_student_profile，student_id 使用业务上下文中的学生标识。
当需要做岗位能力映射时，调用 get_role_competency；优先传 role_id，只有岗位名称时传完整 role_name。
工具返回 ok=false 时，不猜测缺失数据，应向用户说明 error.message 并要求补充正确标识。
```

## 7. 尚未完成的外部步骤

- 未获得 AgentArts 账号、空间和公网 HTTPS 地址，因此没有执行云端安装测试。
- 公网部署前必须补充网关鉴权、TLS、日志脱敏、速率限制和真实学生数据授权策略。

## 2026-10-24 终验记录

本地 MCP 服务在 `http://127.0.0.1:8010/mcp` 启动后，`test_mcp.ps1` 的业务单元测试为 7/7；标准 Streamable HTTP 客户端发现 3 个工具，并实际调用：

- `get_student_profile({"student_id":"demo"})`：`is_error=false`；
- `get_role_competency({"role_name":"Java开发工程师"})`：`is_error=false`；
- `get_project_status({"student_id":"demo"})`：`is_error=false`。

本次 MCP 验证使用项目内 bundled demo 数据；主路演页面和完整平台验收使用隔离的 `test/generated/full-flow-v1` runtime。两者都属于本地验证，不能表述为已完成 AgentArts 云端接入。云端仍需公网 HTTPS、团队空间和鉴权配置。

## 8. 本地完整流程验证

可在 ICT 主工程目录执行以下命令生成隔离数据并运行全套平台验证：

```powershell
cd C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区\01_ICT主工程
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-all-tests.ps1 -SkipInstall -GeneratedFlow
```

生成器写入 `test-results\generated-dataset`，路演服务使用临时 `runtime-data-*`；数据集包含 3 个学生、5 个岗位、6 个章节、30 个知识点和 2 个明确标记为 `test/generated` 的资源。该流程会真实启动后端和前端，调用健康检查、画像、岗位、项目状态、练习、学习计划、能力更新和知识图谱接口，并运行五种尺寸的 Playwright 页面验收。最近一次结果为全部通过：后端验收 12/12、集成 3/3、生成数据流程 6/6、单测 44/44、原有 E2E 16/16、新增 E2E 2/2。

截图位于 `01_ICT主工程\frontend-vue\test-results\generated-flow\`，覆盖 `1440x900`、`1280x720`、`1024x768`、`768x1024`、`390x844` 下的首页、练习诊断、知识图谱、资源工坊、学习路径和评估进化。截图仅用于本地验收，不应提交到仓库。

## 2026-10-25 数据一致性修复

MCP 服务启动后实际列出并调用三个工具，三次均 `is_error=false`。MCP 优先使用当前 `DATA_DIR`，未指定时按 `roadshow-data`、`roadshow-seed`、`backend/data` 顺序选择包含 `users/demo/student.json` 的数据目录，因此与路演前端使用同一份运行数据。

## 2026-10-29 本机 MCP 回归

在当前路演工作区执行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\test_mcp.ps1`：MCP 单元测试 7/7 通过，服务实际列出并调用 `get_student_profile`、`get_role_competency`、`get_project_status`，三次均 `is_error=false`。调用数据来自打包项目数据/本地路演数据；这不代表已经配置 AgentArts 云端。

