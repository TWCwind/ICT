# 辅助模块：岗位图谱子系统

本目录是 ICT 赛题 2 主工程之外的**辅助模块**，为「人岗匹配 / 岗位能力映射」提供结构化岗位数据与查询接口，
数据与主工程 `01_ICT主工程` 完全独立，不参与主工程启动。

## 目录结构

```
02_服创岗位能力模块/
└─ 岗位图谱子系统/
   ├─ main.py                  # 应用入口，把岗位图谱 API 挂到 /api
   ├─ job_api.py               # 对外 HTTP 接口（FastAPI）
   ├─ job_database.py          # 岗位数据加载与增删改查（JSON 文件）
   ├─ job_schema.py            # Pydantic 数据模型
   ├─ job_graph.py             # 晋升 / 换岗图谱（50 个岗位全量）
   ├─ job_vector.py            # 语义向量库（faiss + sentence-transformers，中文模型）
   ├─ job_extractor.py         # 招聘文本 → 结构化岗位画像
   ├─ structured_job_data.json # 已提交的岗位画像数据（50 条，53KB）
   └─ requirements.txt         # 依赖清单
```

## 技术栈（与代码一致）

- Python 3.10+、FastAPI 0.111、Uvicorn 0.30、Pydantic 2.8
- 数据层：**JSON 文件**（`structured_job_data.json`），无数据库
- 语义检索：`sentence-transformers`（paraphrase-multilingual-MiniLM-L12-v2）+ `faiss-cpu`
- 数据处理：pandas / numpy / scikit-learn；图谱：`job_graph.py` 内建的静态路径数据

## 接口一览（`main.py` 挂载到 `/api`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/` | 服务健康检查 |
| GET | `/api/job/list` | 全量岗位列表（支持分页、分类筛选） |
| GET | `/api/job/detail/{job_id}` | 单个岗位画像详情 |
| POST | `/api/job/similar` | 相似岗位向量检索 |
| GET | `/api/job/path/{job_id}` | 岗位晋升 / 换岗路径 |

## 本地运行

```bash
cd 岗位图谱子系统
python -m pip install -r requirements.txt   # 含 torch/faiss，体积较大（约 800MB+）
python main.py                              # 默认 0.0.0.0:8000
# 或：uvicorn main:app --host 127.0.0.1 --port 8000
```

数据文件路径由 `job_database.py` 自动探测（优先本目录的 `structured_job_data.json`），
找不到时**直接报错**而不是静默返回空列表。

## 已知限制

- 依赖较重（torch + faiss + transformers），未安装依赖时 `job_api` 无法导入，接口不可用；本机仅验证到数据加载层（50 条岗位正常读取）。
- 数据为只读快照，`_save_data()` 会直接覆盖 JSON 文件，没有并发控制与多用户隔离。
- 本模块不对外暴露公网服务，也不含鉴权；如要接入 AgentArts，需要另外套网关鉴权与限流。

## 历史说明

本目录早期文档描述过「职途AI / Spring Boot 3.5 + MyBatis + MySQL + Redis」的登录模块，
那是**服创项目历史材料的残留**，对应代码从未进入本仓库；本仓库的 02 模块只有上面的 Python 岗位图谱子系统。
相关说明已在本次整理中替换，旧稿不再保留。
