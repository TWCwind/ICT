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

## 2026-11-03 隔离样例端到端验收补充

本轮在独立临时数据目录 `C:\Users\xiajun\AppData\Local\Temp\ict-acceptance-20261103-018daa3` 生成并使用带 `test/generated` 标记的数据。未写入路演数据目录。原路演服务 `5173/8000` 仍在运行并通过健康检查；有写入的浏览器流程使用从当前工作区代码启动的隔离前端 `5174` 和后端 `8010`。

- 隔离数据包含 3 个学生、5 个岗位、1 门课程、6 个语义化章节、30 个知识点、2 个资源及学习/练习/错题记录。图谱接口统计与页面一致；普通新学习者没有 demo 课程节点。
- 登录、退出后重新进入、导航、用户设置、九个路由、练习页签、错题历史星系、图谱筛选/节点/键盘与缩放、平板与手机操作都经过真实 Edge 操作。
- 用户画像、学习路径和评估结果通过真实 API 保存后再次读取核对。练习走本地模板题库接口（`meta.local_template=true`），提交答案后核对答题统计并进入错题页。
- 当前模型未配置。资源生成、智能辅导和多模态生成均实际请求本地接口；服务明确返回未配置原因，未伪造内容，也没有新增假资源。辅导页面原先只显示“HTTP 200”，本轮修复为读取并显示后端 `error.message`。
- 额外专项发现学习路径在 1024px 宽度下阶段卡片被裁切。修复中屏布局后六个阶段均可见；将已换成条形图的评估页旧选择器更新为当前 `.shot-capability-bars`。

本轮修复文件：`01_ICT主工程/frontend-vue/src/components/TutorBrowserCall.vue`、`src/reference-screens.css`、`e2e/full-flow-generated.spec.ts`、`e2e/real-processing.spec.ts`、`e2e/claude-round2-qa.spec.ts`。有效截图共 36 张，外加两张总览图，位于 `C:\Users\xiajun\AppData\Local\Temp\ict-live-acceptance-20261103-018daa3`；已人工查看桌面/手机总览、九个页面代表图和 1024px 学习路径修复图。

最终结果：前端检查、UI 审计、构建通过；路演 E2E 19/19、队友回归 11/11、真实写入流程 2/2、生成数据截图与图谱流程 2/2、练习/图谱专项 6/6；隔离后端单测 45/45、生成数据接口验收 6/6。构建仍有 ExerciseCenter 584.98 kB 和 Markdown renderer 385.05 kB 的非阻塞 chunk 警告。本轮未运行 MCP 套件，AgentArts 云端未接入。

尚未验证成功项：没有真实模型密钥，不能验证资源工坊、辅导和多模态生成成功后的内容质量及新资源导出；本轮验证了它们的真实未配置错误状态。其余流程的通过项和限制见 `TEST_RESULTS.md`。

## 2026-11-03 企业级前端复核补充

### 本轮真实发现与修复

| 页面/场景 | 复现与根因 | 修复与验证 |
|---|---|---|
| 用户画像时间线 | 在 1280×720、1024×768 下只有一条记录，卡片仍保留 190–240px 最小高度，并受同一网格行高度拉伸，造成明显空白 | 移除时间线固定最小高度并设置内容对齐起点；768×1024 下同样按记录数展开。新增几何回归，验证 1280、1024、768 三种尺寸面板高度不超出内容 |
| 用户画像平板推荐区 | 768px 时底部是两列网格，第三张推荐卡孤立在下一行，右侧留空 | 621–900px 时推荐区跨整行，三项推荐横向排列；五视口截图人工确认 |
| 智能做题初始化 | 延迟 `/api/path/overview` 与 `/api/resources` 时点击“智能做题”，初始化完成后异步恢复函数会重置回“题库定制”，开始按钮消失；按钮也曾在初始化未完成时提前可点 | 记录用户已选页签，不让初始化覆盖；数据就绪前按钮显示“正在准备练习…”且禁用，并提供读取状态。回归用 Promise gate 控制真实本地接口时序：确认所选页签不变、就绪后按钮启用、点击后才请求练习 session。最终 12/12 队友回归通过 |

### 页面审查与截图

逐页检查 `/`、`/profile`、`/workshop`、`/path`、`/exercise`、`/knowledge`、`/multimodal`、`/tutor`、`/evaluate`。本轮修复后人工查看画像五种尺寸原图，以及工坊、图谱、路径和桌面/手机总览。截图目录：`C:\Users\xiajun\AppData\Local\Temp\ict-enterprise-recheck-20261103-650120e`。所有写操作由隔离 `test/generated/full-flow-v1` 数据承载；真实图谱接口统计为 6 章、30 知识点、2 资源，页面统计与接口一致。首页宣传文案未修改，工作区 `HomePage.vue` blob 与起始提交一致。

### 最终回归

- `npm run check`、`npm run audit:ui`、`npm run build`：通过；构建仍有 ExerciseCenterPage 585.26 kB 的非阻塞 chunk 警告。
- 路演 Playwright 19/19；本文件队友回归 12/12；真实处理 2/2；生成数据流程 2/2；Claude 第二轮 QA 6/6。
- 浏览器 console 与 5xx 检查包含在路演、队友回归与生成流程用例中，最终均通过。
- 本轮未运行后端单测或 MCP。模型未配置，模型生成成功后的内容质量和导出流程未验证；AgentArts 云端未接入。

验证详表见根目录 `TEST_RESULTS.md`；整体修改摘要见 `A_TASK_REPORT.md`。

## 2026-11-03 画像卡片复核与练习断言修正

复现：在画像页打开“画像判断置信度”，路演数据原先把六个维度都显示为 50%，且条形同色；卡片受统一网格行高影响，内容之外留下大块空白。检查 `GET /api/profile/demo/overview` 与 `learning_state.py` 后确认：50 是无证据时的算法基线，且同一快照级证据又被重复用于各维度。seed 实际没有 `evidence.dimensions` 来源，因此六维没有可单独核验的置信度。

修复：后端仅从明确关联的维度证据列表计算置信度；无维度证据时返回 null。前端显示“暂无维度级证据”和六项简洁采集状态，不以 0、50 或空白进度条表示。证据存在时按维度使用蓝、青绿、琥珀、紫、青、绿，数值仍来自 API。卡片不再强制等高，字号和间距层级统一。独立 `test/generated` 数据的本地真实 API 返回 55–80，已通过页面及截图核对配色。

回归中练习页曾因测试只定位 radio 而失败。失败截图显示多选题已正确选中；页面 input 是 checkbox。已将测试断言调整为支持 radio/checkbox，专项和最终路演套件均通过。

最终验证：队友 Bug 回归 13/13、路演 19/19、后端单元测试 46/46；类型检查、UI 审计和构建通过。截图 39 张覆盖九个路由桌面/手机、七个重点页面五种尺寸，另有画像生成数据对照图，目录为 `C:\Users\xiajun\AppData\Local\Temp\ict-enterprise-ui-audit-20261103-e3dfeb7\after`。人工查看了总览及画像原尺寸多视口；测量无页面级溢出，浏览器控制台和 API 失败计数均为 0。首页宣传内容未修改。

模型服务未配置；MCP 本轮未执行，AgentArts 云端未接入。构建保留 ExerciseCenterPage 585.26 kB 非阻塞 chunk 警告。
