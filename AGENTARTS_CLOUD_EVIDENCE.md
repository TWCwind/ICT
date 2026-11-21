# AgentArts 云端验收记录

当前状态：**未接入、未部署、未取得云端实际调用轨迹**。仓库本地 9 工具 MCP smoke 与 `LOCAL_EVAL_REPORT.md` 只能证明本地能力。当前运行环境没有可用的 AgentArts 连接工具或已授权的团队空间会话。

完成云端验收时逐项填入真实证据，不填写密钥明文、真实学生资料或未脱敏的请求正文：

| 证据项 | 当前状态 | 验收所需材料 |
| --- | --- | --- |
| 团队空间与授权 | 未取得 | 空间标识、授权角色与时间 |
| 固定 HTTPS MCP 地址 | 未取得 | 域名、证书有效性、健康检查与鉴权结果 |
| 工具注册 | 已完成（2026-11-21） | 网关 tools/list 实测发现 9 工具，与本地 schema 完全一致，见下方进行中记录 |
| 智能体编排 | 未执行 | 工作流版本、节点与输入输出映射 |
| 部署 | 未执行 | 部署版本、状态和交互页面地址 |
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
