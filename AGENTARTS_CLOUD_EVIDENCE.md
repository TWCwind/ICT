# AgentArts 云端验收记录

当前状态（2026-11-21 更新）：**已接入云端网关、已完成智能体编排与部署**，网关 tools/list 与 tools/call 均实测通过，智能体试运行 2 次成功并在回答中回显所调用的 MCP 工具与参数。仍缺：云端评测（50 用例逐例平台侧结果）。

完成云端验收时逐项填入真实证据，不填写密钥明文、真实学生资料或未脱敏的请求正文：

| 证据项 | 当前状态 | 验收所需材料 |
| --- | --- | --- |
| 团队空间与授权 | 已核验（2026-11-21） | 账号ID `01a0ecfadedf721799b5fd12210ed09a`，IAM 用户名 `hid_jnslop3ow8y9tbu`（个人认证），区域 西南-贵阳一 `cn-southwest-2`，套餐 体验版；控制台无独立「团队空间」对象，资源均挂该 IAM 账号下；网关出网由服务委托 `AgentArtsGatewayAgency` 授权，网关与智能体运行时入站均为 IAM 认证；时间见第四节 |
| 固定 HTTPS MCP 地址 | 已核验（2026-11-21） | `https://ict-mcp-gw-defaultgw-gjsdmztehf.cn-southwest-2.huaweicloud-agentarts.com/mcp`（华为云托管域名，非临时隧道）；TLS1.3 + GlobalSign OV 证书，有效期 2026-09-30 ~ 2027-04-17；匿名调用 401、IAM 签名调用 200（9 工具），证据见第五节 |
| 工具注册 | 已完成（2026-11-21） | 网关 tools/list 实测发现 9 工具，与本地 schema 完全一致，见下方进行中记录 |
| 智能体编排 | 已完成（2026-11-21） | 智能体 `ict-career-agent` 版本 `v1.0-agentarts-mcp-20261121`；单智能体节点 + MCP 技能 9 工具；试运行 2 次成功并回显工具名与参数，见下方第三节 |
| 部署 | 已完成（2026-11-21） | 版本 `v1.0-agentarts-mcp-20261121` 部署成功，运行时 `agent-arts-42e60bcca4464da1b82ca8179055804e`，入站 IAM，日志/指标/调用链已开启 |
| 真实调用 | 已完成（2026-11-21） | 经网关 IAM 鉴权调用 get_student_profile(demo) 返回 ok=true，请求 ID 03ff0984-6c4f-46ce-8c0c-26ad454f404f，见下方进行中记录 |
| 云端评测 | 受阻（2026-11-21） | 评测集 `ict-career-50case-20261121`（50 条，input / reference_output，0.0.1）与 `ict-career-10case-smoke-20261121`（10 条，0.0.1）均已建并提交；两次离线评估任务都已发起——50 条任务停在 20%，10 条小样 26 秒跑完但 **10/10 调用状态为「评估对象执行失败」**（得分 0）。逐例分数需先解决平台侧执行问题，见第六、七、八节 |

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

### 第四步实测（2026-11-21，团队空间与授权）

- 账号：账号ID `01a0ecfadedf721799b5fd12210ed09a`，IAM 用户名 `hid_jnslop3ow8y9tbu`，账号状态「个人认证」。
- 区域：**西南-贵阳一 `cn-southwest-2`**（AgentArts 控制台只提供该区域）。
- 套餐：AgentArts **体验版**（用量 0.35 / 20 CU）。
- 空间形态：本控制台**没有独立的「团队空间 / 工作空间」对象**，网关、智能体、知识库、记忆库等资源都直接挂在上述 IAM 账号下；旧版 `versatile` 控制台的空间概念在新控制台不存在。
- 授权链路：
  - 网关出网（访问 MCP 服务）：服务委托 **`AgentArtsGatewayAgency`**；
  - 网关入站：**IAM 认证**（委托 + defaultgw 入网）；
  - 智能体运行时入站：**IAM 认证**（部署时默认选项）。
- 时间线（2026-11-21）：网关 `ict-mcp-gw` 15:14:38 创建并关联 Target（1 分钟后 Target 在线）；智能体 `ict-career-agent` 15:52 创建、16:07 完成提示词与 MCP 技能配置、16:11:30 提交版本 `v1.0-agentarts-mcp-20261121`、随后部署成功。

### 第五步实测（2026-11-21，固定 HTTPS MCP 地址）

- 地址：`https://ict-mcp-gw-defaultgw-gjsdmztehf.cn-southwest-2.huaweicloud-agentarts.com/mcp`，属于网关 `ict-mcp-gw`（ID `1ac43424-882a-4603-aadd-bcf815f43e42`），域名由华为云托管，**不随本机 cloudflared 隧道变化**，可视为固定 HTTPS 入口。
- 证书（2026-11-21 实测，Python `ssl` 直连 443）：
  - 协议 TLS 1.3；
  - 颁发者 `GlobalSign GCC R46 OV TLS CA 2025`（O=GlobalSign nv-sa）；
  - 主体 O=`Huawei Software Technologies Co., Ltd.`，CN=`*.cn-southwest-2.huaweicloud-agentarts.com`；
  - 有效期 `2026-09-30 01:21:37 GMT` ~ `2027-04-17 01:21:37 GMT`，实测剩余 146 天；
  - SAN：`*.cn-southwest-2.huaweicloud-agentarts.com`、`cn-southwest-2.huaweicloud-agentarts.com`（覆盖当前域名）。
- 健康检查与鉴权结果：
  - 匿名 `POST /mcp`（JSON-RPC `ping`）→ **401**，响应体 `{"code":401,"data":null,"message":"Authentication failed!"}`，证明 IAM 入站拦截生效；
  - 带 IAM 数据面签名的调用 → **200**，`tools/list` 返回 9 个工具，`tools/call get_student_profile {"student_id":"demo"}` 返回 `ok=true`、`isError=false`，请求 ID `03ff0984-6c4f-46ce-8c0c-26ad454f404f`（截图见用户侧留存）。
- 现状边界（如实记录）：智能体侧的 MCP 技能当前指向同一 9 工具服务的公网 HTTPS 地址（隧道），因为平台侧 MCP 客户端不会完成网关 IAM 入站签名；要把智能体这条链路也切到上面这个固定 HTTPS 地址，需把网关入站认证改为 **API Key** 并在 MCP 服务「鉴权配置」里填 Key。

### 第六步进展（2026-11-21，云端评测的数据侧已就绪）

- 已在「评估 → 评测集」建好 **`ict-career-50case-20261121`**：50 条数据，列为 `input`（用户问题）与 `reference_output`（判据：应调用的工具与关键字段），版本 `0.0.1` 已提交，可在评估任务里选到。
- 数据来源：`01_ICT主工程/scripts/eval/agentarts_eval_set.jsonl` 转 `input` / `reference_output` 两列（转换产���放 `D:\工作区\_runtime\agentarts-eval-50.csv`，无 BOM）。
- 已踩过的两个坑（后人省时间）：
  - CSV 必须**不带 BOM**，否则平台按列名匹配时报 `missing columns: input, extra columns: input`；
  - 评测集「批量导入」支持 csv / xlsx / jsonl / zip，单文件 ≤50MB、≤5000 条。
- 评估对象选型（已解决）：抽屉「智能体运行时」tab 里的 `ict-career-agent` 是 2026-10-14 的旧运行时，显示「调用配置 ✗ 调用失败」且不可选；改选「单智能体」tab 的 `ict-career-agent | Latest`（本次部署的版本）后被平台接受。
- 评估器选型（已解决）：平台精选里的「正确性 / 任务完成度 / 参考答案遵从度」在多条数据集上均显示为不可选（`icon unselect-disabled`）；改用「自定义」tab 的 `valuator-ict-faithfulness`（模型判定 / 文本 / 单轮对话，v0.0.1）可正常勾选。

### 第七步实测（2026-11-21，50 条云端离线评估已发起）

- 任务：`ict-career-agent-50case-cloud-20261121`，离线评估，执行时间 `2026/11/21 17:21:15 GMT+08:00`。
- 参数：评测集 `ict-career-50case-20261121 0.0.1`（50 条）；评估对象 `ict-career-agent | Latest`；评估器 `valuator-ict-faithfulness 0.0.1`；最大并发 5；智能体调用超时 20 分钟；智能分析（Beta）开启。
- 免费额度：创建前剩余 8 次，本次创建后剩余 **7 次**（额度来自平台的「创建评估任务额度免费开放」）。
- 运行状态（如实）：任务从「待运行」进入「运行中」后，进度长期停在 **20%**（观察约 30 分钟无变化）。评估报告页的「得分总览」已出现 `valuator-ict-faithfulness` 一行，但平均分 / 最低 / 最高 / 总和均为 0，因为任务尚未完成；「评估结果」逐例表因此为空。
- 可能原因（未验证）：评估对象为「单智能体 Latest」，平台在服务端逐例调用智能体；若单例调用未在超时内返回，任务会按 20 分钟超时逐条等待，整体耗时被拉长到小时级。隧道与 MCP 服务侧当时均健康（`/healthz` 200，隧道 uptime 11426s），排除服务掉线。
- 替代证据（已完成）：同一批 50 条用例的答案级本地评测已跑通并留档——首步路由 34/50、期望工具被调用 42/50、工具无异常 50/50、引用可逐字回溯 196/256、人工评分加权 0.83（证据 `01_ICT主工程/scripts/eval/evidence/answer_eval_20261118.*`）。
- 仍缺（如实）：平台侧逐例分数、人工评分、复核人三列。

### 第八步实测（2026-11-21，10 条小样：平台侧执行失败）

- 为定位 50 条任务的停滞，按「小样 + 短超时」策略重跑：新建评测集 `ict-career-10case-smoke-20261121`（取 50 条的前 10 条，列 input / reference_output，版本 0.0.1 已提交；id `e3ac6316-94a3-4d55-90a8-31a4bad…`）。
- 任务 `ict-career-10case-smoke-cloud-20261121`：离线评估，评估对象 `ict-career-agent | Latest`，评估器 `valuator-ict-faithfulness 0.0.1`，并发 5，**智能体调用超时 5 分钟**，执行时间 17:43:50，结束时间 17:44:16。
- 结果：**总条数 10 / 成功 0 / 失败 10 / 运行中 0**，26 秒结束；「评估结果」逐例表每行 `调用状态 = 评估对象执行失败`、得分 0、耗时 0s、Tokens 0；逐例「详情」抽屉里只显示 input / reference_output 与失败状态，没有更细的错误码。
- 结论（据现象推断，未获平台侧错误码）：**平台服务端执行该「单智能体 Latest」失败**，与数据无关（同批数据在本地答案级评测里 50 条全部跑通）；因此 50 条任务停在 20% 很可能是同一原因下的重试/超时堆积，而不是模型慢。
- 免费额度：本轮再耗 1 次，剩余 **6 次**。
- 下一步候选（按成本排序，尚未执行）：
  1. 在智能体「渠道管理」里发布/校验 API 渠道，让平台能以服务方式调用该智能体，再重跑 10 条小样；
  2. 改评估对象为已有「调用配置 ✓ 调用成功」的运行时 `ict-career-agent-k`（2026-10-18），验证评分链路是否通；
  3. 若平台能力短时间无法打通，则以「评测集 + 任务已发起 + 失败原因如实记录 + 本地 50 条答案级评测（加权 0.83）」作为云端评测这一格的交付物。
