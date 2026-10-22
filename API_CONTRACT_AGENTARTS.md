# AgentArts 可调用接口契约

更新时间：2026-10-22

本清单来自源码路由、服务层和本地运行结果，不以旧说明文档代替实际实现。主后端统一响应为：

```json
{
  "request_id": "string",
  "success": true,
  "data": {},
  "error": null
}
```

## 一、现有 HTTP 接口

| 能力 | 接口 | 主要输入 | 数据与持久化依据 | 本地验证 |
|---|---|---|---|---|
| 学生画像查询 | `GET /api/profile/{student_id}/overview` | 路径参数 `student_id` | `backend/data/users/{id}/student.json`、`profiles.json`；`profile_overview` 聚合 | `demo` 已通过 |
| 学生画像原始快照 | `GET /api/profile/{student_id}` | `student_id` | `get_latest_profile_snapshot` | 路由与单测通过 |
| 能力画像更新 | `POST /api/profile/chat` | `student_id`、`messages`、可选 `major/goals` | `Orchestrator.profile_chat`，写入 `profiles.json` 和 `profile_update` 学习事件 | 验收通过 |
| 项目/学习状态 | `GET /api/dashboard/overview?student_id=demo` | `student_id` | 画像、资源、练习、知识、路径和事件聚合 | 验收通过 |
| 路径项目状态 | `GET /api/path/overview?student_id=demo` | `student_id` | `path_overview` + `path_progress` | 验收与 MCP 测试通过 |
| 生成并保存学习计划 | `POST /api/path/plan` | `student_id`、`goals` | `Orchestrator.plan_path`；生成结果以 `path_plan` 事件写入 `events.json` | 单测通过 |
| 练习会话 | `GET /api/exercise/session?student_id=demo&limit=12` | `student_id`、`limit` | 已生成 `question_bank` 资源 | 无题库时明确返回空题目及来源状态 |
| 练习诊断提交 | `POST /api/exercise/answer` | `student_id`、`question_id`、`answer` | `submit_exercise_answer`；写入练习记录和阶段进度 | 单测通过 |
| 练习统计 | `GET /api/exercise/stats?student_id=demo` | `student_id` | `exercise_records.json` | `demo` 有 2 条测试记录，验收通过 |
| 错题诊断 | `GET /api/exercise/wrong-book?student_id=demo` | `student_id` | 错题记录、标签统计、能力雷达 | 验收通过 |
| 知识图谱 | `GET /api/knowledge/map?student_id=demo&max_nodes=56` | `student_id`、`max_nodes` | `knowledge_hub` 解析演示讲义、章节知识 JSON 和本地资源 | demo 实测 6 章、30 知识点、3 资源 |
| 知识检索 | `GET /api/knowledge/search` | `student_id`、`query` 等 | `knowledge_hub.search_index` | 路由与验收通过 |
| 评估状态 | `GET /api/evaluate/overview?student_id=demo` | `student_id` | 画像、知识掌握度、练习和事件证据 | 集成测试通过 |

说明：现有“保存学习计划”是“生成并持久化计划事件”，并非允许调用方提交任意计划 JSON 的独立 CRUD 接口。如果 AgentArts 后续需要修改指定阶段，应新增受校验的计划更新接口，不能直接写数据文件。

## 二、MCP 工具统一返回

三个工具均返回同一信封结构：

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {
    "source": "项目内数据和服务层说明",
    "data_mode": "bundled_demo_data | project_local_data | project_structured_data"
  }
}
```

失败时 `ok=false`、`data=null`，并返回：

```json
{
  "error": {
    "code": "稳定错误码",
    "message": "可向用户解释的信息",
    "details": {}
  }
}
```

## 三、MCP 工具契约

### `get_student_profile`

输入：

```json
{"student_id": "demo"}
```

输出 `data`：

- `student_id`
- `basic_info`：基础信息、目标和画像版本
- `abilities`：六维画像及置信度
- `weaknesses`：薄弱点
- `learning_summary`：画像完整度、证据数、事件数、练习统计和最近活动

错误码：`INVALID_STUDENT_ID`、`STUDENT_NOT_FOUND`、`STUDENT_PROFILE_SERVICE_ERROR`。

数据来源：主工程 `backend/data/users/{student_id}`，由现有 `profile_overview`、`exercise_summary`、`activity_feed` 组合，不复制画像算法。

### `get_role_competency`

输入至少提供一项；同时提供时优先 `role_id`：

```json
{"role_name": "Java开发工程师", "role_id": "job_001"}
```

输出 `data`：

- `role_id`、`role_name`、`category`
- `requirements.hard_skills/soft_skills/education/certificates/experience`
- `skill_level`：由原始 `experience_require` 映射出的展示层级，保留原值和推导说明
- `core_competencies`、`responsibilities`
- `matching_basis`：匹配方式、原查询和证据字段

错误码：`MISSING_ROLE_QUERY`、`INVALID_ROLE_QUERY`、`AMBIGUOUS_ROLE_NAME`、`ROLE_NOT_FOUND`、`ROLE_COMPETENCY_SERVICE_ERROR`。

数据来源：`02_服创岗位能力模块/结构化岗位画像.json`，通过原 `JobDatabase` 显式注入数据路径读取。

### `get_project_status`

输入：

```json
{"student_id": "demo"}
```

输出：`data.path` 为现有 `path_overview` 返回的学习路径和阶段状态。

错误码：`INVALID_STUDENT_ID`、`STUDENT_NOT_FOUND`、`PROJECT_STATUS_SERVICE_ERROR`。

## 四、数据边界

- 协作包只含通用 `demo` 测试标识，没有真实学生姓名、手机号或学校信息。
- 没有模型密钥时，不伪造模型生成结果；验收改为读取打包的真实本地数据，并验证模型能力返回可解释错误。
- MCP 查询只读。学生 ID 仅允许字母、数字、下划线和连字符，防止目录穿越。

## 五、测试数据与复现边界

本地完整验收使用 `01_ICT主工程\tests\generate_test_dataset.py` 生成的 `test/generated/full-flow-v1` 数据集，不把测试数据伪装成真实学生数据。数据集包含 3 个学生、5 个岗位、6 个章节、30 个知识点和 2 个资源；`demo` 用于路演页面，`active-learner` 用于学习记录、错题、路径和画像更新，`new-learner` 用于验证新学习者不会自动获得 demo 课程。

运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-all-tests.ps1 -SkipInstall -GeneratedFlow` 会把数据复制到隔离 runtime，启动真实本地后端和前端，并验证上述接口及页面。最近一次结果为后端验收 12/12、集成 3/3、生成流程 6/6、后端单测 44/44、原有前端 E2E 16/16、新增五尺寸 E2E 2/2 全部通过。

该测试结果只证明本地实现和本地 MCP 服务可复现，不证明已经接入 AgentArts 云端；云端接入仍需公网 HTTPS、团队空间和鉴权配置。

