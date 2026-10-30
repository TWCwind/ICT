# 队友使用问题现场回归

更新时间：2026-10-29
工程目录：`01_ICT主工程`
验证方式：当前工作区启动的本地路演服务、真实本地 API、Microsoft Edge Playwright；未调用在线大模型。

## 结果摘要

- 修复并回归了用户设置焦点管理、平板导航重叠、手机导航隐藏、平板评估证据栏裁切、知识图谱全屏 Escape 退出、智能做题误自动开始，以及空题状态下答题区留空列等问题。
- 智能做题页签现在先显示开始前信息；切换到该页签不会创建练习会话。只有点击“开始做题”后，答题组件才挂载并请求本地接口。
- 做题页面把加载中、接口失败和成功但无题分成三个状态；错误提供重试/返回题库入口，加载和状态变化会把键盘焦点移至对应提示。没有题目时隐藏暂停、考试模式与空统计，并不再把计划题量显示成已有题量。
- 现有路演演示账号没有已生成的练习题库。开始按钮触发真实接口后，接口返回 `200 / success=true / questions=[]`，页面如实显示空题状态和“前往定制题库”入口；没有伪造题目。
- 本轮新增专项回归 9/9 通过；既有路演回归 19/19 通过；后端单测 45/45；MCP 单测 7/7。
- AgentArts 云端未接入。

## 问题复现与修复

| 队友可见问题 | 复现证据与根因 | 修改与回归 |
|---|---|---|
| 打开用户设置后键盘焦点不进入输入框，Escape 行为不完整 | Playwright 打开设置面板后发现输入框没有获得焦点；面板缺少一致的关闭和焦点返回流程 | 打开后聚焦第一个输入框；Escape、关闭按钮会关闭面板并把焦点还给触发按钮；点击外部关闭；监听器在卸载时移除。覆盖键盘、关闭按钮、外部点击和刷新后设置持久化 |
| 1024px 下主导航挤在一行，和设置按钮相撞 | 录屏紧凑样式的 `!important` 覆盖了原有 1180px 响应式表头；几何测试复现 2px 垂直重叠 | 平板导航调整为独立第二行；1024px 下九个入口均处于可见滚动区域，导航与设置不重叠 |
| 手机端只能看到部分主导航，其他入口藏在无提示的横向滚动区 | 390px 实际截图只显示前几个入口；触控高度又被旧 `!important` 样式压到 34px | 820px 以下改为三列网格，九个入口全部可见；每个触控入口至少 44px。回归检查无横向溢出、所有链接位置和尺寸 |
| 平板评估页证据栏超出卡片 | 768px 截图和元素几何显示三列内容宽于父卡片 | 761–900px 调整评分和证据布局；768px 下所有证据项落在卡片内 |
| 知识图谱降级全屏后 Escape 不能退出 | 模拟 Fullscreen API 拒绝后打开页面内全屏，按 Escape 仍保留全屏类和 `body` 滚动锁 | 全屏 Escape 在快捷键输入焦点过滤前处理；退出恢复滚动和触发按钮焦点；原生全屏与降级全屏分别回归 |
| 点“智能做题”页签立即进入答题界面 | `ExercisePage` 原先始终挂载，父级仅用 `v-show` 隐藏；子组件 `onMounted` 会提前请求练习会话 | 改为显式开始状态；未点按钮前 `ExercisePage` 不挂载且练习会话请求数为 0；点击“开始做题”后才发出 `/api/exercise/session` 请求 |
| 无题库时答题区右侧留大片空白 | 当前路演账号无题库，隐藏侧栏后两列 CSS 网格仍保留第二列 | 空题状态切换为单列宽布局，主内容占满可用宽度；Playwright 校验卡片宽度大于父容器的 90% |
| 加载时误显示“没有题目”，接口失败被空状态掩盖 | 会话请求未完成时 `current` 为空，模板直接进入空状态；错误提示只在有题时渲染 | 区分加载、失败、成功无题三种状态；失败提供重试和返回题库入口，恢复时调用真实本地接口；键盘焦点随状态移动 |
| 无题状态显示不可用控件和 0/0 统计 | 练习模式、暂停和统计区在空题时仍然展示 | 无题时隐藏暂停/模式切换/统计侧栏；标题准确反映“载入中、载入失败、暂无题库” |
| 设置、筛选和服务故障恢复状态不明确 | 现场按钮测试需观察页面变化及 API，而不是只判断 click 是否抛错 | 回归覆盖页签选中态、知识图谱筛选与节点选择、缩放、后端 502 中文提示和恢复重试、控制台异常和 5xx |

## 本轮修改文件

- `01_ICT主工程/frontend-vue/src/components/AppShell.vue`
- `01_ICT主工程/frontend-vue/src/pages/EvaluatePage.vue`
- `01_ICT主工程/frontend-vue/src/pages/KnowledgePage.vue`
- `01_ICT主工程/frontend-vue/src/pages/ExerciseCenterPage.vue`
- `01_ICT主工程/frontend-vue/src/pages/ExercisePage.vue`
- `01_ICT主工程/frontend-vue/src/exercise.css`
- `01_ICT主工程/frontend-vue/src/presentation-tight.css`
- `01_ICT主工程/frontend-vue/src/final-acceptance.css`
- `01_ICT主工程/frontend-vue/e2e/teammate-bug-regression.spec.ts`
- 根目录交付文档：`A_TASK_REPORT.md`、`TEST_RESULTS.md`、`MCP_INTEGRATION.md`、`API_CONTRACT_AGENTARTS.md`、`NATIONAL_AWARD_READINESS.md`

## 最终执行结果

| 命令 / 检查 | 结果 |
|---|---|
| `npm run check` | 通过 |
| `npm run audit:ui` | 通过：可见按钮均有动作，无已知固定数据回退 |
| `npm run build` | 通过，2321 个模块；ExerciseCenter 产物约 582 kB，仍有 chunk 体积警告 |
| `npm run test:roadshow -- --project=msedge --workers=1 --reporter=line` | 前序提交时 19/19 通过；本次 UX 增量未重跑 |
| `npx playwright test e2e/teammate-bug-regression.spec.ts --project=msedge --workers=1 --reporter=line` | 9/9 通过（含失败恢复和焦点检查） |
| `python -m unittest discover -s tests -p "test*.py" -v` | 前序提交时 45/45 通过；本次仅改前端，未重跑 |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\test_mcp.ps1` | 前序提交时 MCP 单测 7/7，三个工具 smoke 均 `is_error=false`；本次未重跑 |
| 本地健康检查与知识图谱接口 | `/api/health` 成功；demo 图谱 6 章、30 概念、3 资源、44 关系 |
| 智能做题真实接口 | 点击前 0 次请求；点击后 200、`success=true`、0 道题。页面显示无题提示 |

既有隔离生成流测试（此前在基础完整流程中执行，非当前这轮代码修改后重跑）：后端验收 12/12、集成 3/3、生成流程 6/6、生成流程 E2E 2/2。该结果与本轮当前代码回归分开记录。

## 截图人工检查

前序验收曾在 `test-results/roadshow-screenshots/` 生成五种分辨率、六个页面的 30 张截图和 4 张做题状态截图并人工查看。后续 Playwright 运行会清理其输出目录，这组临时文件目前不在工作区；本次保留了 7 张智能做题开始前、加载中、错误和真实空题状态截图。

人工查看结论：导航在桌面、平板和手机端均完整可见或按设计网格排列；手机页面无整页横向溢出；评估证据未裁切；知识图谱列和节点仍可在图谱内部视口滚动。新增查看了桌面/手机的开始前、加载中、接口失败和真实空题状态截图；错误提示、重试入口和题库入口清楚，空题状态不再展示无效控件，焦点有明确落点。当前 7 张截图位于 `01_ICT主工程/frontend-vue/test-results/ux-followup-human-flow-reviewed-e99f48784d9d4d7bb8877646f2466bb5/`，仍是本地 ignored 产物。

## 未解决限制

1. demo 学生当前没有练习题库；点击开始按钮会真实加载并得到空题列表。现场做题演示前需先在题库定制中生成可用题库，或使用隔离的 `test/generated` 数据走生成流程。
2. 构建仍报告 ExerciseCenter 约 582 kB 的大 chunk 警告；不阻塞当前功能验收。
3. MCP 已在本机实际调用三个工具；未接入 AgentArts 云端。
