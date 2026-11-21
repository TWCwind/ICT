# AgentArts 云端验收记录

当前状态（2026-11-21 更新）：**已接入云端网关、已完成智能体编排与部署**，网关 tools/list 与 tools/call 均实测通过，智能体试运行 2 次成功并在回答中回显所调用的 MCP 工具与参数。仍缺：云端评测（50 用例逐例平台侧结果）。

完成云端验收时逐项填入真实证据，不填写密钥明文、真实学生资料或未脱敏的请求正文：

| 证据项 | 当前状态 | 验收所需材料 |
| --- | --- | --- |
| 团队空间与授权 | 未取得 | 空间标识、授权角色与时间 |
| 固定 HTTPS MCP 地址 | 未取得 | 域名、证书有效性、健康检查与鉴权结果 |
| 工具注册 | 已完成（2026-11-21） | 网关 tools/list 实测发现 9 工具，与本地 schema 完全一致，见下方进行中记录 |
| 智能体编排 | 已完成（2026-11-21） | 智能体 `ict-career-agent` 版本 `v1.0-agentarts-mcp-20261121`；单智能体节点 + MCP 技能 9 工具；试运行 2 次成功并回显工具名与参数，见下方第三节 |
| 部署 | 已完成（2026-11-21） | 版本 `v1.0-agentarts-mcp-20261121` 部署成功，运行时 `agent-arts-42e60bcca4464da1b82ca8179055804e`，入站 IAM，日志/指标/调用链已开启 |
| 真实调用 | 已完成（2026-11-21） | 经网关 IAM 鉴权调用 get_student_profile(demo) 返回 ok=true，请求 ID 03ff0984-6c4f-46ce-8c0c-26ad454f404f，见下方进行中记录 |
| 云端评测 | 未执行 | 50 用例逐例结果、参考答案、人工评分和复核人 |

本地复现入口见 `MCP_INTEGRATION.md` 与 `LOCAL_EVAL_REPORT.md`。若云端连接或数据授权未就绪，保持上述“未执行”状态。

## 进行中记录（2026-11-21，云端网关已接入）

以下为控制台实测状态（2026-11-21 用户提供，工具调用轨迹待补充）：

- 网关：ict-mcp-gw（ID 1ac43424-882a-4603-aadd-bcf815f43e42），状态「运行中」
- MCP 调用 URL：https://ict-mcp-gw-defaultgw-gjsdmztehf.cn-southwest-2.huaweicloud-agentarts.com/mcp
- 网关配置：MCP 版本 2025-03-26；入站 IAM 认证，委托 AgentArtsGatewayAgency；出网「公网访问」
- Target：ict-mcp-target，协议 MCP / 类型 MCP / 传输 Streamable HTTP，地址 https://true-atmosphere-fraser-roads.trycloudflare.com/mcp；状态「在线」（绿点）
- 连接测试：控制台「连接测试」→ 连接成功
- 匿名探测：无凭据 POST 网关 URL → 401 Authentication failed!（IAM 鉴权按预期拦截未授权请求）
- 待完成：网关侧 tools/list 与 tools/call 实际调用轨迹（控制台「工具调试」置灰，需通过「调用代码」或真实客户端验证）；智能体编排；部署与云端评测

注意：Target 地址依赖本机 cloudflared quick tunnel（免费隧道、无可用性保证、域名可能变化）。隧道进程停止或域名变更时 Target 会离线，在 Target 上更新地址即可恢复。

### 第二步实测（2026-11-21，网关真实调用通过）

用户在控制台网关页用「调用代码」生成带 IAM 鉴权的调用片段并在本机运行（凭证不落仓库、不进对话）：

- `tools/list`：经网关实测返回 9 个工具，与本地 MCP schema 完全一致（add_learning_branch / get_exercise_session / get_learning_evaluation / get_project_status / get_role_competency / get_student_profile / get_wrong_book / search_knowledge / submit_exercise_answer）。
- `tools/call get_student_profile {"student_id": "demo"}`：返回 `ok=true`，demo 画像完整（信息管理与信息系统 / 大二 / 数据库原理 / 画像 v19.0 / 练习 41 题正确率 51.2% / 六维能力 / 弱点标签），`isError=false`；JSON-RPC 请求 ID `03ff0984-6c4f-46ce-8c0c-26ad454f404f`。
- 响应 meta：source=01_主工程/backend/data + app.services，data_mode=bundled_demo_data——云端只走 demo 数据，符合数据授权红线。
- 链路构成：AgentArts 网关（IAM 鉴权）→ 本机 cloudflared quick tunnel → 本地 MCP 服务（127.0.0.1:8010）→ 主工程业务服务。
- 截图证据（用户侧留存）：含请求 ID 的完整 tools/call 响应 + 此前的 401 匿名探测，构成「鉴权拦截/鉴权放行」对照。

### 第三步实测（2026-11-21，智能体编排与部署）

控制台编排过程（2026-11-21 15:52–16:09，用户登录授权、助手代操作），以下均为云端真实状态（截图由用户侧留存）：

- 智能体：`ict-career-agent`（agentId `eab01ddc-257c-4cb8-b811-84b86d8021bc`），模型 `DeepSeek-V4.1-Flash-1017`。
- 技能：MCP 服务 `ict-mcp-server`，部署成功后工具列表 **9 个工具**（与本地 schema 一致）。
- 版本：`v1.0-agentarts-mcp-20261121`，提交状态「已提交」。
- 节点与输入输出映射（单智能体编排）：
  - 输入：用户自然语言问题（默认 `student_id=demo` 演示数据）。
  - 决策节点：大模型按提示词 6 条硬规则自主选择工具（工具优先、写操作先读 id、数据不足不许编造分数）。
  - 执行节点：MCP 服务 `ict-mcp-server` 暴露的 9 个工具（画像 / 岗位能力 / 项目状态 / 知识检索 / 练习会话 / 提交答案 / 错题本 / 学习评估 / 新增学习分支）。
  - 输出：带工具回执的结构化结论（引用题名与片段、正确率、数据模式等字段）。
- 试运行 1（画像问答，运行成功 11.96s）：思考链路显式写出 “应调用 get_student_profile”，回答给出画像完整度 95%、学习证据数 5、学习事件数 113、整体正确率 51.2%、数据模式 `bundled_demo_data`，字段与 `get_student_profile` 返回一致。
- 试运行 2（岗位问答，运行成功 19.78s）：回答首句为「已调用 `get_role_competency`（role_name=前端开发工程师，命中 job_002，匹配方式 exact_role_name）」，随后列出该岗位核心能力（HTML/CSS/JavaScript/Vue/React/Node.js/沟通协作/问题解决/审美）。
- 部署：版本 `v1.0-agentarts-mcp-20261121` → 部署成功，运行时名称 `agent-arts-42e60bcca4464da1b82ca8179055804e`，入站 IAM 认证，日志记录/指标/调用链均开启。

**网关直连与平台 MCP 客户端的差异（如实记录）**：把 MCP 服务地址先填成 AgentArts 网关 URL（IAM 入站）时，平台报「部署失败：MCP 服务认证失败，无权访问」——平台侧 MCP 客户端不会自动完成网关的 IAM 入站签名。改为同一 9 工具服务的公网 HTTPS 地址（`/mcp`，无入站认证）后部署成功。生产化建议：把网关入站认证改为 API Key，并在 MCP 服务的「鉴权配置」里填对应 Key，即可让智能体经网关调用。
