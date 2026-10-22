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

## 5. 隔离测试数据与完整流程结果

生成命令：

```powershell
cd C:\Users\xiajun\Desktop\ICT赛题2-AgentArts-A开发工作区\01_ICT主工程
python .\tests\generate_test_dataset.py --output .\test-results\generated-dataset
```

一键完整命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-all-tests.ps1 -SkipInstall -GeneratedFlow
```

生成数据集标识为 `test/generated/full-flow-v1`，包含 3 个学生、5 个岗位、1 门课程、6 个章节、30 个知识点、2 个资源、练习和错题、学习记录、学习计划、能力画像更新记录及异常输入场景。服务运行时使用独立 `test-results\runtime-data-*`，没有覆盖原有演示数据。

本轮真实结果：

| 检查项 | 结果 |
|---|---:|
| 后端验收 | 12/12 通过 |
| 集成流程 | 3/3 通过 |
| 生成数据全流程 | 6/6 通过 |
| 后端单元测试 | 44/44 通过 |
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过 |
| 前端构建 | 通过 |
| 原有路演 E2E | 16/16 通过 |
| 生成数据路演 E2E | 2/2 通过 |
| 知识图谱资源卡首屏布局 | 3/3 完整显示，均位于操作栏上方 |

新增前端验收生成 30 张截图，位于 `frontend-vue\test-results\generated-flow\`，覆盖 1440x900、1280x720、1024x768、768x1024、390x844 五种尺寸，以及首页、练习诊断、知识图谱、资源工坊、学习路径、评估进化六个页面。截图已人工查看，确认知识图谱在平板可见四列，手机端可纵向滚动，页面统计与接口统计一致。

## 6. 当前限制

- `npx playwright test e2e/interaction-qa.spec.ts --project=msedge --workers=1` 已单独在本地路演服务上执行并通过 3/3；若单独运行，需要先启动本地路演服务。
- AgentArts 云端尚未安装验证，因为没有公网 HTTPS 地址、团队空间和鉴权凭据；本地 MCP 已实际调用，不代表云端已接入。

## 7. 本轮视觉修复复测

人工查看截图时发现 1440x900 知识图谱右侧详情面板的第三张配套资源卡原先会被底部操作栏部分遮挡。已将配套资源区前置到节点详情首屏，并在 `full-flow-generated.spec.ts` 增加三张资源卡均位于操作栏上方的几何断言。

修复后重新执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-all-tests.ps1 -SkipInstall -GeneratedFlow
```

结果仍为：后端验收 12/12、集成 3/3、生成数据流程 6/6、后端单元测试 44/44、原有路演 E2E 16/16、新增生成数据路演 E2E 2/2。修复后的 1440x900、390x844 知识图谱截图已重新人工查看。
