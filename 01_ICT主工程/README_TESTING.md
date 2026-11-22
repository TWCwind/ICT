# 测试与验收说明

以下命令均从源码包根目录执行。

## 一键测试

首次运行先执行 `.\安装依赖.ps1`，然后：

```powershell
.\scripts\run-all-tests.ps1 -SkipInstall
```

脚本会依次启动前后端并执行：

1. 后端验收脚本；
2. 集成闭环脚本；
3. 后端单元测试；
4. 前端类型检查与生产构建；
5. Playwright 端到端测试。

如本机没有可用的 Edge/Playwright 浏览器，可先跳过 E2E：

```powershell
.\scripts\run-all-tests.ps1 -SkipInstall -SkipE2E
```

## 分项执行

后端服务启动后，可执行：

```powershell
$env:PYTHONPATH = (Resolve-Path .\backend).Path
python .\tests\backend_acceptance.py http://127.0.0.1:8000
python .\tests\integration_flow.py http://127.0.0.1:8000
```

后端单元测试：

```powershell
Push-Location .\backend
$env:PYTHONPATH = (Get-Location).Path
python -m unittest discover -s tests -p "test*.py" -v
Pop-Location
```

前端检查与构建：

```powershell
Push-Location .\frontend-vue
npm run check
npm run lint
npm run build
Pop-Location
```

前端 E2E：

```powershell
Push-Location .\frontend-vue
$env:PLAYWRIGHT_BASE_URL = "http://127.0.0.1:5173"
npm run test:e2e -- --project=msedge --workers=1
Pop-Location
```

## 存储后端与数据迁移

后端支持两种存储后端，通过环境变量 `STORAGE_BACKEND` 选择（默认 `json`）：

| 后端 | 元数据落点 | 正文文件 | 适用场景 |
| --- | --- | --- | --- |
| `json` | `<DATA_DIR>/users/<学号>/*.json` | 磁盘（`content_uri` 指向） | 演示、离线、回退 |
| `sqlite` | `<DATA_DIR>/app.db`（SQLite，WAL） | 磁盘（`content_uri` 指向） | 并发写入、多用户 |

两种后端共用 `app/repo.py` 同一组签名，路由与服务不感知差异；表结构见 `backend/app/db/sqlite.py`。

迁移与核对：

```powershell
# 1) 摸底：每类 JSON 的条数、字段并集、体积分布（只读）
python .\scripts\migrate\report.py --data-dir <DATA_DIR>

# 2) 迁移前先看会写多少行（不写库）
python .\scripts\migrate\json_to_sqlite.py --data-dir <DATA_DIR> --dry-run

# 3) 正式回填（幂等，主键已存在则跳过；--force 才覆盖）
python .\scripts\migrate\json_to_sqlite.py --data-dir <DATA_DIR>

# 4) 条数核对（逐表逐学号比对 JSON 与 DB）
python .\scripts\migrate\json_to_sqlite.py --data-dir <DATA_DIR> --verify-only
```

迁移口径（`docs` 之外必须知道的四点）：

1. `exercise_records.json` 历史上不带 `created_at`，迁移时用文件 mtime 补齐（`quiz_attempt.created_at` 为 NOT NULL）；
2. `quiz_attempt` 用 `detail_json` 保存整条原始记录，列表读回时优先返回它，保证字段零丢失；
3. `path_progress.json`、`knowledge_state.json` 第一版整块进 `state_json` / `nodes_json`，不做规范化；
4. 同一 id 被复制到多个学号目录时，主键去重后只保留首次出现（`--verify-only` 会单独报出这些重复）。

并发写入验收（20 线程写事件 + 20 线程追加错题）：

```powershell
python .\scripts\verify\concurrency_check.py sqlite <DATA_DIR>
```

期望输出 `events=20/20 quizzes=20/20 errors=0`；把参数换成 `json` 即改造前基线，会看到大量覆盖丢失（实测 0/20、1/20）。

两后端对照的实测结论（2026-11-20，数据目录各复制一份 `ict-data` 起跑）：

| 项 | json 后端 | sqlite 后端 | 备注 |
| --- | --- | --- | --- |
| 后端单测 | 75/75 | 75/75 | 同一套 `backend/tests`（47 旧 + 13 鉴权隔离 + 13 迁移窗口 + 2 页码锚点新增） |
| 16 条只读 API | — | — | 两个后端逐字段一致（忽略 `created_at` 等易变字段） |
| Playwright e2e 全量 | 64/65（修复前） | 65/65（修复后） | 曾同败于 `full-flow-generated.spec.ts:72`，去掉面板 4 条上限后修复 |
| 并发写入 | 0/20、1/20 | 20/20、20/20 | `scripts/verify/concurrency_check.py` |

`full-flow-generated.spec.ts:72` 曾在两个后端稳定失败：同一套用例里 `claude-round1-repro.spec.ts` 的按钮探针会点「生成资源」，
往 demo 学号追加第 6 个资源，使该课程资源统计变成 5，而知识中枢详情面板的「配套资源」按 UI 规则最多渲染 4 条
（`KnowledgePage.vue` 的 `relatedResources` 取 `slice(0, 4)`）。用例断言「按钮数 == 统计资源数」，因此只要前面跑过生成就必然失败；
两个后端在同一轮跑出完全相同的失败，说明与存储层无关。2026-11-20 按「面板不设上限」的取舍修复：删除 `relatedResources`
两处 `slice(0, 4)`——所有资源节点都直连课程根节点，去上限后按钮数恒等于 `stats.resources`；先造 6 资源状态单跑该用例通过（6.8s），
sqlite 后端全量回归 65/65（18.8m）。

### 在线迁移窗口（不停机切库）

离线迁移之外，后端提供进程内迁移窗口，可在服务运行中把 JSON 数据切到 SQLite：

```powershell
# 1) 查看当前窗口状态与后端
GET /api/storage/migration-window

# 2) 冻结写（同步写排队等待，async 端点写返回 503 + Retry-After: 5）
POST /api/storage/migrate {"action": "prepare"}

# 3) 迁移 + 逐学号核对 + 切换到 sqlite（核对不过保持 json 并解冻，差异进 status.errors）
POST /api/storage/migrate {"action": "commit"}

# 4) 放弃本次迁移（解冻，JSON 数据不动）
POST /api/storage/migrate {"action": "abort"}
```

要点：

- 冻结是进程内 `threading.Lock`：同步写（线程池端点/MCP/脚本）排队不拒绝；跑在事件循环上的 async 端点写会立刻拿到 503（`MIGRATION_FROZEN`，带 `Retry-After`），解冻后重试即可；
- commit 先复用离线脚本的核对口径（逐学号去重 id 比对），核对不过不切换、保持 json 后端并解冻，差异写入 status.errors；
- 窗口有 TTL 看门狗（`MIGRATION_WINDOW_TTL_SEC`，默认 300 秒），超时自动 abort，防止忘了解冻；
- commit 之后 abort 会被拒绝并提示人工回退；JSON 文件迁移后原样保留，作为回退快照。

实测（2026-11-20，真实 uvicorn 起服务 + 并发写 + 断言落库，`_runtime/live_migration_probe.py`）：happy/abort/TTL 三组共 20 个场景全部通过——含冻结期 3 个并发写全部 503、解冻后重试全部成功、commit 后 SQLite 逐表断言、abort 后写进 JSON、TTL 超时自动解冻。新增 13 项单测（`backend/tests/test_migration_window.py`），双后端全量 60→73 全绿。

## 知识检索页码锚点验收

`search_knowledge` 的引用现在能落到「第几章（第 X-Y 页）」（2026-11-21 交付）：PDF 教材提取时逐页记录
字符偏移并随教材 payload 持久化，章节切分把字符区间映射为物理页区间，`search_index` 结果带
`page_start / page_end`，`format_references` 输出「（第 X-Y 页）」。非 PDF 教材（md/txt/docx）与旧数据
无页概念，字段为 0 诚实降级；页码是 PDF 物理页序，非印刷页码。

单测（`backend/tests/test_page_anchor.py`，2 项：fitz 生成多页中文 PDF → ingest → 检索断言页码递增与
输出格式；md 语义切分无页码降级）双后端 73→75 全绿。

```powershell
cd backend
$env:DATA_DIR="<DATA_DIR>"; python -m unittest discover -s tests -p "test_page_anchor.py" -v
```

## 多用户隔离（会话级）验收

后端新增会话级隔离（2026-11-20）：`AUTH_REQUIRED=1` 开启后，所有带 `student_id` 的接口都要求
`X-Session-Token`（或 `Authorization: Bearer`）头，且令牌绑定的学号必须与请求学号一致——
query 参数、path 参数、JSON body 三处提取；不一致返回 403，缺/坏令牌返回 401；`/health` 与
`/api/auth/*` 豁免。登录走 `POST /api/auth/login`（学号 + 服务端 SVG 验证码，一次性消费），
令牌默认有效期 12 小时（`AUTH_TOKEN_TTL_SEC`），签名密钥 `AUTH_SECRET`（生产必须显式配置）。

单测（13 项，双后端各跑一遍均通过；含后续迁移窗口新增后总数 47→73）：

```powershell
cd backend
$env:DATA_DIR="<DATA_DIR>"; python -m unittest discover -s tests -p "test_auth_isolation.py" -v
```

开态实测矩阵（`AUTH_REQUIRED=1` 起第二后端，16 项全过）：config 上报 auth_required、/health 放行、
无令牌 401、坏令牌 401、非学号接口放行、验证码 SVG 4 字符、错验证码拒登、小写验证码可登录、
匹配令牌 200（query/path/body 三型）、跨学号 403（三型）、Bearer 头 200、`/api/auth/me` 返回学号。
关态（默认）实测：无令牌访问 200。

## 验收重点

- 登录页能够进入系统；
- 所有主导航页面可访问且无白屏；
- 用户画像、资源工坊、练习诊断、知识中枢、路径推送、智能辅导和评估进化页面可正常加载；
- 无外部密钥时，受影响功能给出安全提示或使用演示回退，不泄露配置；
- 前端生产构建和后端自动化测试通过。
# PR #7 鉴权与在线迁移安全修复

默认演示模式保持 `AUTH_REQUIRED=0`。启用用户身份验证前，需要在服务端环境配置 `AUTH_REQUIRED=1`、随机 `AUTH_SECRET` 和 `AUTH_STUDENT_KEYS_JSON`（学号到各自独立凭据的 JSON 映射）；只提供学号或验证码无法登录。请勿将实际凭据提交到仓库。此模式仍不具备账号注册、密码找回和角色管理，部署时应对凭据分发和轮换作单独安排。

在线迁移管理接口始终要求独立的 `MIGRATION_ADMIN_KEY`，通过 `X-Migration-Admin-Key` 请求头传入；未配置时返回 503，错误凭据返回 403。该密钥与学习者令牌无关。迁移窗口仅适用于单进程服务；所有经过 `app.repo` 的写入会持有写入门锁直到落盘结束，再允许 prepare 开始迁移。部署前还应审计绕过 `app.repo` 的直接文件写入路径。

回归命令：在 `backend` 目录运行 `python -m unittest tests.test_auth_isolation tests.test_migration_window -q`；完整后端测试运行 `python -m unittest discover -s tests -p "test*.py" -q`。
