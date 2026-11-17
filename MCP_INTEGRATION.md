# MCP 服务：启动、加固、测试与 AgentArts 接入

最近验证：**2026-11-17**。当前 MCP 自动化测试 **30/30 通过**，隔离临时数据上的 Streamable HTTP smoke **9/9 工具调用通过**。
**没有**完成 AgentArts 云端网关注册（缺固定公网域名 + TLS + 团队空间）。

## 1. 实现概况

| 项目 | 内容 |
| --- | --- |
| 目录 | `mcp_server/`（`server.py` 工具定义、`services.py` 业务适配、`hardening.py` 加固层、`tests/`） |
| 协议 | MCP Streamable HTTP（`stateless_http=True`，SSE 响应） |
| 端点 | `/mcp`；健康检查 `/healthz` |
| 数据来源 | 复用主工程 `backend/data`，缺失时回退 `backend/roadshow-seed`（全新克隆可用） |
| 依赖 | `mcp` SDK + `uvicorn`，装在独立 `.venv-mcp` 里，避免与主工程 Starlette 版本冲突 |

已实现工具（9 个）：

| 工具 | 作用 |
| --- | --- |
| `get_student_profile` | 学生画像与基本信息 |
| `get_role_competency` | 岗位能力模型（默认取岗位图谱第一个岗位） |
| `get_project_status` | 学习路径与项目进度 |
| `search_knowledge` | 课程知识库检索 |
| `get_exercise_session` | 取一次练习会话题目 |
| `submit_exercise_answer` | 提交答案并回写记录 |
| `get_wrong_book` | 错题本 |
| `get_learning_evaluation` | 学习评估与证据 |
| `add_learning_branch` | 新增学习分支 |

## 2. 安装

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_mcp.ps1
```

## 3. 启动

```powershell
.\start_mcp.ps1
```

启动脚本会自动处理三件事：导出 `PYTHONPATH`；没有 `MCP_API_KEY` 时从 `.mcp_api_key` 读取，
文件不存在就现场生成（该文件已写进 `.gitignore`，**不要提交、不要贴进任何文档**）；
打印端点、健康检查与限流配置。

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8010` | 监听地址；对公网必须经网关或 TLS 终结，不要直接开 `0.0.0.0` |
| `MCP_API_KEY` | 无 | 对外暴露时必填；支持 `X-API-Key` 或 `Authorization: Bearer <key>` |
| `MCP_RATE_LIMIT_PER_MIN` | `240` | 每客户端每分钟请求上限，`0` 关闭限流 |
| `MCP_DATA_DIR` | 自动探测项目数据 | 显式指定 MCP 读写的数据目录；集成测试使用临时 `test/generated` 副本 |
| `MCP_HEALTH_PATH` | `/healthz` | 健康检查路径 |
| `MCP_LOG_REQUESTS` / `MCP_LOG_LEVEL` | 开 / `INFO` | 访问日志开关与级别 |
| `MCP_TRANSPORT_DIRECT` | 无 | 只有显式设为 `1` 且监听地址是 loopback 时，才允许本地排障绕过加固 |

## 4. 加固行为（`hardening.py`）

1. **鉴权**：`HardeningMiddleware` 在 ASGI 层校验 key，用 `hmac.compare_digest` 常量时间比较；
   缺失或错误统一 `401`，响应体不含任何关于 key 的细节。
2. **限流**：60 秒滑动窗口，按 key 指纹（`sha256[:8]`）或客户端 IP 分桶，超限返回 `429` 并带 `Retry-After`。
3. **日志脱敏**：访问日志只记录方法、路径、状态码、耗时与客户端指纹；请求头与请求体不落日志，
   key 明文一次都不会出现。
4. **健康检查**：`/healthz` 不需要 key（否则网关无从探活），且不占用限流配额。
5. 只拦截 `/mcp` 路径，其他路径原样放行，方便与反代共存。
6. **Fail closed**：非 loopback 监听必须配置 API Key 和正数限流；加固层初始化失败时服务停止，
   不会退回无保护的原生 MCP。`MCP_TRANSPORT_DIRECT=1` 在非 loopback 地址上会被拒绝。

## 5. 验证记录（2026-11-17）

| 验证项 | 结果 |
| --- | --- |
| 自动化测试 | `powershell -NoProfile -ExecutionPolicy Bypass -File .\test_mcp.ps1` → **30 tests OK** |
| 隔离 HTTP smoke | 脚本自行启动本机服务，`tools/list` 发现 **9 个工具**，业务调用 **9/9 通过** |
| 写操作隔离 | 题库、作答和学习分支只写入临时 `test/generated` 数据副本，脚本退出后清理 |
| 启动失败安全 | 单测覆盖加固初始化失败不降级、direct 模式仅 loopback、非 loopback 必须有 key 和限流 |
| 本轮未重测 | 公网隧道与 AgentArts 网关注册未在本轮验证；没有声称已接入 AgentArts 云端 |

未验证：AgentArts 网关注册、TLS 证书签发、团队空间鉴权、公网部署与并发压测。

## 6. 客户端直连示例

```bash
# 健康检查（无需 key）
curl -s http://127.0.0.1:8010/healthz

# 列工具（需要 key 与 SSE 的 Accept 头）
curl -s -X POST http://127.0.0.1:8010/mcp \
  -H "content-type: application/json" \
  -H "accept: application/json, text/event-stream" \
  -H "X-API-Key: $MCP_API_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# 调业务工具
curl -s -X POST http://127.0.0.1:8010/mcp \
  -H "content-type: application/json" \
  -H "accept: application/json, text/event-stream" \
  -H "X-API-Key: $MCP_API_KEY" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_student_profile","arguments":{"student_id":"demo"}}}'
```

## 7. 接入 AgentArts 还差什么

AgentArts 是公有云服务，无法访问本机或内网地址，因此注册前必须补齐：

1. **固定公网域名 + HTTPS**：临时隧道（trycloudflare）随时失效，只能用于验证；正式环境要部署到
   云主机或容器并配好证书，域名写进 AgentArts 自定义 MCP 配置。
2. **密钥托管**：`MCP_API_KEY` 走云端密钥管理，不要写在镜像或仓库里；轮换后同步更新网关配置。
3. **网关侧限流与日志**：本服务的 60s 窗口是最后一道保险，公网入口还需要网关级配额。
4. **团队空间鉴权**：AgentArts 团队空间成员的访问控制与 MCP 的 key 鉴权是两层，需分别配置。
5. 注册完成后回填 `API_CONTRACT_AGENTARTS.md` 里的实际端点与工具清单。

## 8. 已知限制

- 数据层仍是 JSON 文件（`backend/app/repo.py`），无并发控制与多用户隔离，MCP 只是同一份数据的另一个入口。
- 服务当前 `stateless_http=True`，不保存会话状态；需要多轮上下文的工具要把状态显式传参。
- 临时隧道域名与进程同生命周期，进程退出即失效，不能作为交付物。
