# 🚀 v2.0 Phase 2 完成说明 —— server.js MCP 工具网关

> 完成日期：2026/5/17 · 上游：[v2.0 Phase 1](./RELEASE_v2.0_PHASE1.md)（Blender 插件 2.0.0 落地 16 个 MCP 原子工具）
> 目标：按 [`RELEASE_v2.0_MCP_ROADMAP.md`](./RELEASE_v2.0_MCP_ROADMAP.md) Phase 2，给 `server.js` 加上 **MCP 工具网关层**，让前端 Agent 循环只调本机 Express，由它统一代理到 Blender 插件 `http://127.0.0.1:9876/mcp/*`，并把网络/HTTP 异常归一化成结构化错误。
>
> Phase 1 把 Blender 端 16 个工具的 HTTP 端点造好了；Phase 2 把它**搬上"前端能直接调"的台面**；Phase 3（下一步）才是真正的前端 Agent 循环。

---

## ✅ 本次完成清单

### 1. 新增 4 个 HTTP 端点

`server.js` 从 **894 行 → 1060 行**（净 +166 行），在 `/api/blender/upload-local-model`（v1.9.1 历史端点）和 `/api/polyhaven/*`（v1.7.0 PolyHaven 代理）之间插入 v2.0 MCP 网关：

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/mcp/tools?url=<blender_url>` | 透传 Blender `GET /mcp/tools`，返回 16 个工具的 OpenAI tools 格式 schema |
| POST | `/api/mcp/call` | 通用调度。Body `{ blender_url, tool, args, timeout? }`，前端 Agent 主入口 |
| POST | `/api/mcp/tool/:tool_name` | RESTful 直调（便于 curl 调试），:tool_name 走 `^[a-zA-Z][a-zA-Z0-9_]*$` 白名单 |
| GET | `/api/mcp/ping?url=<blender_url>` | 轻量探活，专门挑 Blender `/ping` 里 mcp 子对象 + 给老插件返回 upgrade_hint |

注入位置：`server.js` 第 567 行起，紧挨着 `/api/blender/*` 老端点，方便维护时一眼能找到所有 Blender 相关路由。

### 2. 错误归一化机制（关键设计）

#### 2.1 Blender 端契约（Phase 1 已实现）

```
POST /mcp/call → 永远 HTTP 200
  ├─ 成功:        { ok: true,  ...其它字段 }
  ├─ 工具自身错误: { ok: false, error: "..." }   ← 包括 unknown tool / 参数缺失 / Python traceback
  └─ Blender 端 5xx（极少数）: 字符串 / HTML
```

#### 2.2 网关层错误归一化（Phase 2 新增）

所有 Phase 2 端点失败时**统一返回**：

```json
{
  "ok": false,
  "error_type": "network" | "timeout" | "bad_request" | "upstream",
  "error": "简短描述",
  "http_status": 502,
  "hint": "用户友好的解决建议",
  "upstream_data": { ... }   // 可选，保留 Blender 端原始响应
}
```

**4 种 `error_type`**：
- `network`：连不上 Blender 9876（ECONNREFUSED / ENOTFOUND / ECONNRESET）→ 提示用户开 Blender 启用插件
- `timeout`：调用超时（默认 120s）→ 提示加大 timeout 字段
- `bad_request`：网关层参数校验失败（缺 blender_url / tool / args 不是对象 / tool_name 非法字符）→ 400
- `upstream`：Blender 端返回非 2xx → 502 + 原响应

**关键设计**：工具自身错误（Blender 返回的 `{ok:false, error}`）**原样透传** HTTP 200，**不归一化**，让前端 Agent 拿到 Blender 端最原始的错误信息（包括 `available` 工具名列表、`traceback` 等扩展字段）。网关只接管"轮子根本没转起来"的纯网络/HTTP 异常。

#### 2.3 `_mcpErrorPayload(err)` 工具函数

在 axios `validateStatus: () => true` 的协助下统一处理：
- 上游若返回了 `{ok:false}` 结构 → 补全 `error_type` / `http_status` / `hint`，把上游原始结构存进 `upstream_data` 里保留
- 上游若返回不是 `{ok:false}` 结构（如 v1.x 老插件返回 `{ok:true,...}` 但 HTTP 404）→ 包装成 `{ok:false, error_type:'upstream', upstream_data}`
- 纯网络/超时错误 → 自动按 err.code 推断 type，附带友好 hint

### 3. 超时策略

| 场景 | 超时 | 理由 |
|------|------|------|
| `/api/mcp/ping` | 5s | 探活类，要快 |
| `/api/mcp/tools` | 8s | schema 静态返回，应秒回 |
| `/api/mcp/call` 默认 | **120s** | 覆盖 PolyHaven 4k 下载 + blend append 等慢操作 |
| `/api/mcp/call` 自定义 | 5~600s | body 传 `timeout` (秒) 或 `timeout_ms` (毫秒) |

### 4. Blender URL 校验

所有端点都用 `_normalizeBlenderUrl(raw)`：必须 `http(s)://` 开头，自动去尾部 `/`，否则 400 拒绝（防止 SSRF + 防止前端忘传时打到自身）。

### 5. 老端点 100% 保留

`/api/blender/exec` `/api/blender/ping` `/api/blender/export-addon` `/api/blender/upload-local-model` `/api/polyhaven/*` `/api/tripo3d/*` 全部不动。Phase 1 也已保证 Blender 插件的老 HTTP 端点（`/exec /scene_report` 等）全保留 —— 这意味着 v1.9.6 前端跑在带 v2.0 网关的 server.js 上一切照旧。

---

## 🧪 自测结果

写了 2 个验证脚本（已用完即删，保留思路）：

### 测试 A：mock Blender 9 个场景

mock 一个完整模拟 aichat_bridge 2.0.0 的 HTTP server（`/ping` `/mcp/tools` `/mcp/call`），实测 **9/9 通过**：

```
✅ GET /api/mcp/ping → mcp_ready=true, addon_version=2.0.0, tool_count=16
✅ GET /api/mcp/tools → 3 个工具, schema 透传正常
✅ POST /api/mcp/call add_primitive → ok=true, name=TestCube
✅ POST /api/mcp/call unknown tool → ok=false, error="unknown tool: ..."，HTTP 200 透传
✅ POST /api/mcp/call crash → 502, error_type=upstream（HTTP 500）
✅ POST /api/mcp/call 缺 blender_url → 400 bad_request
✅ POST /api/mcp/call 连接被拒（端口 1） → 502 error_type=network + hint
✅ POST /api/mcp/tool/list_objects → 1 个物体
✅ POST /api/mcp/tool/bad-name! → 400（tool_name 非法字符拦截）
```

### 测试 B：真 v1.2.0 Blender 兼容性（关键！）

机器上正好真跑着旧 aichat_bridge 1.2.0 插件（Blender 5.1.1），实测：

```
--- /api/mcp/ping → 真 v1.2.0 Blender ---
HTTP 200 ok=true mcp_ready=false addon_version=1.2.0
upgrade_hint: 检测到 Blender 插件未启用 MCP 工具协议，请升级到 aichat_bridge 2.0.0+

--- /api/mcp/tools → v1.2.0（v1.2 没这端点）---
HTTP 502 ok=false error_type=upstream
error: not found
```

✅ 老插件场景被优雅识别：`/api/mcp/ping` 不报错，返回 `mcp_ready=false` 加明确的升级提示；`/api/mcp/tools` 抛 502 + `error_type=upstream`，前端可以据此 fallback 到 v1.x 模式或弹窗让用户重装插件。

---

## 📐 端点详细规格

### `GET /api/mcp/tools?url=http://127.0.0.1:9876`

```bash
curl 'http://localhost:3456/api/mcp/tools?url=http%3A%2F%2F127.0.0.1%3A9876'
```

成功响应：
```json
{
  "ok": true,
  "tools": [ /* 16 个 OpenAI function tools 格式 schema */ ],
  "count": 16,
  "addon_version": "2.0.0",
  "blender_url": "http://127.0.0.1:9876"
}
```

### `POST /api/mcp/call`

```bash
curl -X POST http://localhost:3456/api/mcp/call \
  -H 'Content-Type: application/json' \
  -d '{
    "blender_url": "http://127.0.0.1:9876",
    "tool": "add_primitive",
    "args": { "type": "cube", "location": [0, 0, 1], "name": "MyCube" },
    "timeout": 30
  }'
```

成功响应：直接透传 Blender 端 `_mcp_call()` 的返回（如 `{ok:true, name:"MyCube", ...}`）。

工具失败响应：HTTP 200 + `{ok:false, error: "..."}`（前端按 `ok` 字段判断，**不要**按 HTTP 状态码）。

### `POST /api/mcp/tool/:tool_name`

```bash
curl -X POST http://localhost:3456/api/mcp/tool/list_objects \
  -H 'Content-Type: application/json' \
  -d '{ "blender_url": "http://127.0.0.1:9876", "args": {} }'
```

### `GET /api/mcp/ping?url=http://127.0.0.1:9876`

```json
{
  "ok": true,
  "mcp_ready": true,
  "addon_version": "2.0.0",
  "blender_version": [4, 2, 0],
  "tool_count": 16,
  "tools": ["get_scene_info", "list_objects", ...],
  "upgrade_hint": null,
  "raw": { /* Blender /ping 完整原始响应 */ }
}
```

老插件场景（v1.2.0）：`mcp_ready=false`，`upgrade_hint` 文案明确指引升级，前端可据此决定是否亮起 v2.0 Agent 模式按钮。

---

## 📋 兼容性说明

- **v1.9.6 前端**：完全不受影响，没人调 `/api/mcp/*` 所以零变化
- **v1.2.0 Blender 插件**：通过 `/api/mcp/ping` 仍能识别（返回 `mcp_ready=false`），但调 `/api/mcp/tools`/`call` 会拿到 502，符合预期
- **依赖**：仅复用已有 `axios`（v1.6.0 就引入了），零新依赖
- **代码风格**：保持与 `/api/blender/*` `/api/polyhaven/*` 一致（同样的 `ok:false`/`error_type` 风格、async/await、超时常量提取）

---

## 📝 关键文件清单

| 文件 | 改动 |
|------|------|
| `server.js` | 894 → **1060 行**：在 v1.9.1 上传端点 + v1.7.0 PolyHaven 代理之间新增 MCP 网关段（4 端点 + 错误归一化 + URL 校验工具函数） |
| `RELEASE_v2.0_PHASE2.md` | 本文件 |
| `CHANGELOG.md` | 新增 v2.0 Phase 2 段落 |

`package.json` 版本号**不动**（仍 1.9.6），按计划 Phase 2/3 完成后再统一发 v2.0.0 正式版。

---

## 🚧 下一步：Phase 3（核心，4 天工作量）

按 [`RELEASE_v2.0_MCP_ROADMAP.md`](./RELEASE_v2.0_MCP_ROADMAP.md) Phase 3：

- 在 `public/index.html` 新增 `agentRunMCPMode()`，完全替代现有 `agentRunPolyHavenMode/agentRunFinalMode`
- 调 `/api/chat` 时传 OpenAI `tools` 参数，强制 LLM 走 tool_call 路线
- 主循环：`while (!done && round < 20)` 接收 LLM 的 `tool_calls`，每次都调 `/api/mcp/call`，结果以 `role:'tool'` 喂回对话
- System Prompt 改写："你有 16 个 Blender 工具，每步先 `get_scene_info` 看真实状态，再决定下一步"
- UI：工具调用历史面板（按时间线展示 tool_call + 返回结果）

**Phase 2 已为 Phase 3 准备好的基础设施**：
- ✅ 4 个稳定的网关端点
- ✅ 统一 `{ok, error_type, hint}` 错误结构，前端 Agent 可直接拿来做策略分支
- ✅ 兼容老插件场景的探活机制（`mcp_ready=false + upgrade_hint`），前端可优雅降级

---

## 🔗 相关文档

- 上游：[`RELEASE_v2.0_PHASE1.md`](./RELEASE_v2.0_PHASE1.md)（Blender 插件 2.0.0 + 16 个 MCP 原子工具）
- 全景蓝图：[`RELEASE_v2.0_MCP_ROADMAP.md`](./RELEASE_v2.0_MCP_ROADMAP.md)
- 临时止血方案：[`RELEASE_v1.9.6.md`](./RELEASE_v1.9.6.md)（PolyHaven 模式资产选择器）
- 参考：[`blender-mcp-main/addon.py`](./blender-mcp-main/addon.py)（ahujasid/blender-mcp）

> Phase 1 ✅ · **Phase 2 ✅ 完成** · Phase 3 🚧 待启动（前端 Agent 循环，4 天）

---

## 📨 给下一会话的开场白

```
按 RELEASE_v2.0_MCP_ROADMAP.md 开始 Phase 3。

已完成：
- Phase 1：Blender 插件 2.0.0（16 个 MCP 原子工具，详见 RELEASE_v2.0_PHASE1.md）
- Phase 2：server.js MCP 网关（4 个端点 + 错误归一化，详见 RELEASE_v2.0_PHASE2.md）

下一步：前端 Agent 循环，在 public/index.html 新增 agentRunMCPMode()，
走 OpenAI tool calling 多轮循环，每步调 /api/mcp/call。
先读 public/index.html 里的 agentRunPolyHavenMode/agentRunFinalMode 了解现状，
再读 RELEASE_v2.0_PHASE2.md 知道 4 个网关端点的契约。
```
