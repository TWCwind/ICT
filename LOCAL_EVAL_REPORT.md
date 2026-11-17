# 50 条用例的本地 MCP 执行证据

执行日期：2026-11-17。数据分类：`test/generated`；服务绑定 loopback，使用临时随机 API Key。脚本复制 `01_ICT主工程/roadshow-seed` 到临时目录，注入测试题库和学习路径；答题与新增分支只写临时副本，运行结束后删除。

## 复现

在仓库根目录安装 MCP 依赖后执行：

```powershell
.\install_mcp.ps1
.\.venv-mcp\Scripts\python.exe .\01_ICT主工程\scripts\eval\run_eval.py --json
.\.venv-mcp\Scripts\python.exe .\01_ICT主工程\scripts\eval\run_local_mcp_eval.py --output .\01_ICT主工程\scripts\eval\evidence\local_eval_20261117.jsonl
```

输出为每例一行的 JSONL，包含原始用例提示、预期、按顺序调用的工具、实际参数、成功/错误码、返回顶层字段和应核对的参考字段。`human_rubric` 四项保持 `null`，供有授权的评审者依据实际回答与出处填写；本脚本不生成或评分 Agent 自然语言回答。

## 本轮真实结果

| 项目 | 结果 |
| --- | ---: |
| 用例 | 50 |
| 本地 MCP 工具调用 | 62 |
| 成功调用 | 61 |
| 成功调用缺少约定参考字段 | 0 |
| 预期边界错误 | 1（E30，故意不传学生 ID，MCP 参数校验拒绝） |
| 非预期调用错误 | 0 |
| 已人工评分的语义用例 | 0 |

E50 的轨迹顺序包含画像、岗位、项目状态、知识检索、出题、错题和评估。读取到的路径中已有 1 个由前面用例新增并持久化到临时副本的分支；评估返回练习作答记录计数。该轨迹只证明工具链在本地能运行，尚不能证明岗位差距判断准确、建议有效或学生实际学得更好。

证据文件：`01_ICT主工程/scripts/eval/evidence/local_eval_20261117.jsonl`。SHA-256：`1EE23F72CF9C1BE4F2657C2AE38582AB6564AA4C230C04C5476CD66E121676A8`。

## 人工评分口径

- `task_completion`：0=缺关键步骤或未回应任务，1=完成且可在工具轨迹中核对。
- `citation_correctness`：0=引用缺失或无法定位，1=每个关键结论有可定位来源；不涉及引用的用例记 `null`。
- `parameter_suitability`：0=参数与请求不符，1=学生、岗位、检索词和写入对象均符合请求。
- `unsupported_claims`：记录无法从工具结果或项目产物核对的断言数量；未审查时记 `null`。

每例须由人工或真实 Agent 回答补充原始输出、出处及评分者标识后才能汇总语义指标；不能把 61/62 工具执行率称为 50 条任务成功率。
