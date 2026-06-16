# 🚧 v2.0 MCP 架构改造接力文档（开新会话直接读）

> 创建日期：2026/5/17 · 上游：v1.9.6
> **关键词：MCP 工具协议 / Agent 循环 / 边看边干 / 拉平 blender-mcp**

---

## 📌 一句话背景

用户在 v1.9.5 之后发现：**"为什么网上看到 Claude 通过 MCP 操控 Blender 可用性那么高，我们却差得很？"**

答案：**架构本质不同**。我们走的是"LLM 一次性吐大段代码 → 推到 Blender 闷头执行"的盲写路线；blender-mcp 走的是 **MCP 工具协议 + Agent 循环**：让 LLM **每一步都看真实场景反馈再决策下一步**，像人一样"边看边干"。

v1.9.6 已经做了**临时止血**（资产选择器交给用户挑），但要真正拉平 blender-mcp 的天花板，**必须做架构层面的彻底重构**。这份文档就是 v2.0 的完整施工蓝图。

---

## 🆚 本质差距对照表

| 维度 | blender-mcp（MCP 路线） | 我们 v1.x（盲生成） |
|------|------------------------|--------------------|
| **交互模式** | LLM 多轮 `tool_call` 循环（看→决策→行动→看→继续） | LLM 一次性吐 200~500 行代码或一大块 JSON |
| **场景反馈** | 每个 tool call 后 LLM 主动调 `get_scene_info()` 拿真实状态 | 全程盲写，最后才一次性调 `/scene_report` 自检 |
| **错误恢复** | 单个 tool call 失败 → LLM 立刻换策略（"再试一个 asset_id"/"换尺寸"） | 一段代码 traceback → 整批推送崩 → 等下一轮自检整段重写 |
| **资产挑选** | LLM 调 `search_polyhaven_assets("vintage chair")` → 拿到带缩略图描述的真实候选 → 选 → 下载 | 把 200 个 asset_id 名单塞 prompt 让 LLM 在上下文里**猜** |
| **修改粒度** | "把沙发挪到 (1,0,0)" → 1 个 `update_object_location` tool_call | 重新写整段 patch 代码（≤50 行） |
| **AI 角色** | **Agent**（自主决策者，对真实场景持续观察） | **Translator**（描述→代码翻译机，写完就结束） |
| **首次成功率** | ~85%（盲点已被多轮反馈消除） | ~30~50%（猜错就要重跑） |
| **后续调整** | 自然语言追加："沙发改成黑色" → 1 个 tool_call 秒完 | 重新跑整轮自检（成本高） |

**说白了**：blender-mcp 让 Claude 像人坐在 Blender 前**一边看视口一边按键盘**；我们让 LLM **闭眼写完一整本剧本**再让 Blender 闷头表演。

---

## 🎯 v2.0 目标

**让我们的智能 Agent 路线在可用性上拉平 `ahujasid/blender-mcp`**，具体指标：

1. ✅ LLM **每一步都调用 MCP tool**，不再一次性出大段代码
2. ✅ 每个 tool 返回**真实场景状态**（含坐标/尺寸/材质 slot 列表等），LLM 拿到后再决策下一步
3. ✅ 单个 tool 失败时 LLM **立刻换策略**（不整批崩）
4. ✅ 资产选择必须经过 `search_polyhaven_assets` 真实搜索（拿到候选列表后挑），**禁止 LLM 猜 asset_id**
5. ✅ 修改粒度细化到"挪沙发"级别（1 个 tool_call = 1 个原子操作）

---

## 🏗 架构设计

### 三层架构

```
┌─────────────────────────────────────────────────────┐
│  浏览器前端 public/index.html                       │
│  - Agent 循环（while !done: 调 LLM tool_call → 执行）│
│  - tool_call 调度器                                 │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP /api/chat（OpenAI tools 格式）
                   ▼
┌─────────────────────────────────────────────────────┐
│  Express 后端 server.js                             │
│  - /api/chat 透传 LLM 调用（已支持）                │
│  - /api/mcp/*  新增 MCP 工具网关（v2.0 新增）        │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP 9876
                   ▼
┌─────────────────────────────────────────────────────┐
│  Blender 插件 aichat_bridge 2.0.0                   │
│  - /exec（保留向后兼容）                            │
│  - /scene_report（保留）                            │
│  - /mcp/* （新增 ~15 个 MCP tool 端点）              │
└─────────────────────────────────────────────────────┘
```

### MCP Tool 清单（v2.0 必做的 15 个）

| 类别 | Tool 名 | 参数 | 返回 |
|------|---------|------|------|
| **观察** | `get_scene_info` | - | 物体列表 + 灯光 + 相机 + 渲染设置 |
| 观察 | `get_object_info` | `name` | 详细：location/rotation/scale/dimensions/materials |
| 观察 | `get_viewport_screenshot` | `width=512` | base64 PNG（已有 v1.8.0） |
| **创建** | `add_primitive` | `type/location/scale/name` | 新物体名 |
| 创建 | `add_light` | `type/location/energy/color` | 灯光名 |
| 创建 | `set_camera` | `location/rotation/lens` | - |
| 创建 | `set_world_hdri` | `asset_id` | - |
| **修改** | `update_object` | `name/location?/rotation?/scale?` | 新坐标 |
| 修改 | `set_material` | `obj_name/base_color/roughness/metallic` | - |
| 修改 | `delete_object` | `name` | - |
| **PolyHaven** | `search_polyhaven_assets` | `query/type` | top10 候选（带缩略图 URL/分类/下载量） |
| PolyHaven | `download_polyhaven_asset` | `asset_id/type/resolution` | 本地路径 |
| PolyHaven | `append_polyhaven_blend` | `asset_id/name/location/scale` | 物体名 |
| **执行** | `exec_python` | `code` | stdout + 错误（保留作为兜底） |
| **质检** | `quality_check` | - | 4 维度报告（不 raise，返回 JSON） |

---

## 📝 施工任务清单（按优先级）

### Phase 1：Blender 插件 2.0.0（核心，1 周）

- [ ] **`blender_addon/aichat_bridge/__init__.py` 升级 1.2.0 → 2.0.0**
- [ ] 新增 15 个 MCP tool 端点（每个 `/mcp/<tool_name>`）
- [ ] 所有 tool 必须用 `bpy.app.timers` 投递到主线程，并通过 `threading.Event` 同步等结果（参考现有 `/hyper3d/import` 的写法）
- [ ] 每个 tool 返回结构化 JSON（`{ok: true, data: {...}}`），失败时 `{ok: false, error: "..."}`
- [ ] 老端点 `/exec /scene_report /log /ping` 全部保留（向后兼容 v1.x 用户）
- [ ] N 面板新增显示 `MCP 状态: 在线 / 已注册 15 个工具`

### Phase 2：server.js MCP 网关（半天）

- [ ] 新增 `POST /api/mcp/call`：透传到 Blender `/mcp/<tool_name>`，统一错误处理 + 超时
- [ ] 新增 `GET /api/mcp/tools`：返回所有可用 tool 的 JSON Schema（OpenAI tools 格式）
- [ ] 现有 PolyHaven 代理（`/api/polyhaven/search` 等）保留，给 Blender 端 MCP tool 内部调用

### Phase 3：前端 Agent 循环（核心，4 天）

- [ ] **新增 `agentRunMCPMode()` 函数**：完全替代 `agentRunPolyHavenMode/agentRunFinalMode` 等
- [ ] 调用 `/api/chat` 时传 `tools` 参数（OpenAI tool calling 格式），强制 LLM 走 tool_call 路线
- [ ] 主循环：
  ```js
  while (!done && round < maxRounds) {
    const resp = await callLLM({ messages, tools });
    if (resp.tool_calls?.length) {
      for (const tc of resp.tool_calls) {
        const result = await fetch('/api/mcp/call', { tool: tc.name, args: tc.arguments });
        messages.push({ role: 'tool', tool_call_id: tc.id, content: JSON.stringify(result) });
      }
    } else {
      done = true;  // LLM 没再调工具，认为完成
    }
    round++;
  }
  ```
- [ ] System Prompt 改写：明确告诉 LLM "你有 15 个 Blender 操作工具，请通过 tool_call 一步步建造场景，每步都先 `get_scene_info` 看真实状态"
- [ ] UI 增加"工具调用历史"面板（按时间线展示每个 tool_call + 返回结果）

### Phase 4：兼容/迁移（半天）

- [ ] 设置面板加 radio：`【🤖 MCP Agent 循环（v2.0 新）】` vs `【📜 一次性生成（v1.x 兼容）】`
- [ ] 老用户默认走 v1.x 模式，老插件 1.2.0 用户也能用（v2.0 端点不存在时 fetch 失败 → fallback）
- [ ] 欢迎弹窗强调 v2.0 必须**重装 aichat_bridge 2.0.0 zip**

### Phase 5：测试 + 发布（1 天）

- [ ] 测试场景：「日式茶室」「赛博朋克酒吧」「极简北欧客厅」三个 demo
- [ ] 对比 v1.x 和 v2.0 在相同场景下的首次成功率、token 消耗、最终质量
- [ ] 写发布说明 `RELEASE_v2.0.md`
- [ ] 升级 hasLaunched key 到 v2.0
- [ ] `npm run build:mac` 打包

---

## 🚀 开新会话直接读这里

> 复制下面这段给新会话作为开场白：

```
续上 v2.0 MCP 架构改造任务，按 `RELEASE_v2.0_MCP_ROADMAP.md` 接着干。

已完成：
- v1.9.6 资产选择器（临时止血，让用户挑 PolyHaven 资产）

下一步：从 Phase 1 开始 —— Blender 插件 aichat_bridge 升级 1.2.0 → 2.0.0，
新增 15 个 MCP tool 端点。先读 blender_addon/aichat_bridge/__init__.py 了解现状，
再读 RELEASE_v2.0_MCP_ROADMAP.md 看清单。
```

---

## ⚠️ 注意事项

1. **bpy 主线程隔离**：所有 MCP tool 必须用 `bpy.app.timers` 投递到主线程，否则会崩溃（这是 v1.6.0 时已踩过的坑）
2. **OpenAI tools 格式 vs Anthropic tools 格式**：两家略有不同，要在 server.js 端做格式归一化
3. **中转 API 兼容性**：用户的 API key 大多走第三方中转，tools 参数支持度不一，需要做 fallback（不支持 tools 的模型直接报错让用户换）
4. **Token 消耗会增加**：MCP 路线每轮都要把 scene_info 喂给 LLM，单轮 token 消耗会比 v1.x 高，但因为首次成功率高，总成本反而低
5. **Cursor/Claude Desktop 兼容**：blender-mcp 是按 MCP 标准协议（stdio）实现的，我们的实现是 HTTP 简化版（不走 stdio）。如果未来想让用户直接在 Claude Desktop 里用，需要再加一层 stdio adapter

---

## 📚 参考资料

- `ahujasid/blender-mcp`（GitHub）—— 我们要拉平的对手
- OpenAI Tool Calling 文档：https://platform.openai.com/docs/guides/function-calling
- Anthropic Tool Use 文档：https://docs.anthropic.com/claude/docs/tool-use
- 我们现有的相关文件：
  - `blender_addon/aichat_bridge/__init__.py`（v1.2.0 主线程任务队列 + HTTP server）
  - `server.js` line ~568（PolyHaven 代理 API 已实现，可复用）
  - `public/index.html` line ~12230（`agentRunPolyHavenMode` 是要被替代的）

---

> v1.9.6 + v2.0 路线图已锁定，接力顺利 🚀
