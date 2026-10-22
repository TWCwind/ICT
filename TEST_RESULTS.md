# 测试结果

执行日期：2026-10-03（Asia/Shanghai）

## 环境

- Python：3.12.14（验证环境）
- Node.js：24.12.0
- npm：11.6.2
- 后端：FastAPI 0.115.14
- MCP SDK：1.30.0（独立虚拟环境）

## 最终结果

| 验证项 | 结果 | 数量/说明 |
|---|---|---|
| 后端健康检查 | 通过 | `GET /api/health`，后端/知识库/数据目录均 ready |
| 后端单元测试 | 通过 | 41/41 |
| 后端验收脚本 | 通过 | 12/12 |
| 集成流程 | 通过 | 3/3 |
| MCP 业务测试 | 通过 | 7/7 |
| MCP 协议级调用 | 通过 | 工具发现成功；两个必选工具实际调用成功 |
| 前端类型检查 | 通过 | `npm run check` |
| 前端 ESLint | 通过 | `npm run lint` |
| 前端生产构建 | 通过 | 2317 个模块完成转换，生成 `dist/` |
| 前端生产文件启动 | 通过 | 本地静态服务访问首页返回 HTTP 200，且包含 `#app` 挂载节点 |

生产构建有一个非阻断警告：部分输出块超过 500 kB，后续可按页面继续拆分动态模块。

## 执行命令

主工程后端：

```powershell
cd .\01_软件杯主工程\backend
$env:PYTHONPATH = (Get-Location).Path
python -m unittest discover -s tests -p "test*.py" -v
```

服务级验收：

```powershell
cd .\01_软件杯主工程
python .\tests\backend_acceptance.py http://127.0.0.1:8000
python .\tests\integration_flow.py http://127.0.0.1:8000
```

前端：

```powershell
cd .\01_软件杯主工程\frontend-vue
npm run check
npm run lint
npm run build
```

MCP：

```powershell
cd <开发工作区根目录>
.\test_mcp.ps1
```

## 首次基线与修复

首次运行发现并修复：

1. `fastapi>=0.115` 无上限会安装 0.142，改变路由注册表现，使 4 个回归断言失败。已固定为兼容的 0.115 系列，最终 41 项全部通过。
2. Vite 在受限 Windows 目录中加载 TypeScript 配置时，esbuild 会扫描不可访问的父目录。已新增程序化构建脚本，`npm run build` 最终通过。
3. 旧验收脚本仍要求无密钥时伪造资源、题库和回答，与当前“禁止合成回退”的安全逻辑冲突。已改为验证本地 `demo` 数据和可解释错误，不把模拟内容冒充模型结果。
4. `/api/multimodal/generate` 无密钥时原本抛出 HTTP 500。已改为标准 `success=false` 和 `MULTIMODAL_GENERATION_ERROR`。
5. 健康检查原来始终报告 `demo_mode=false`。已改为根据模型配置真实反映状态。

## 未执行项

- Playwright E2E 未执行：当前任务的验收重点由前端类型检查、Lint、生产构建、生产文件 HTTP 访问和后端/集成测试覆盖；本机受限执行环境的 Vite 开发依赖预优化会扫描不可访问父目录。
- AgentArts 云端安装未执行：缺少公网 HTTPS 地址和 AgentArts 空间凭据。

