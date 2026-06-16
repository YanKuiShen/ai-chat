# v2.0 Phase 3 完成报告 — 前端 MCP Agent 循环

> **发版时间**：2026-05-17
> **前端版本号**：`package.json` 1.9.7 → **1.10.0**
> **三阶段完整周期**：Phase 1（插件 4 天）+ Phase 2（网关 1 天）+ Phase 3（前端 3 天）= **共 8~9 天**，与 [`RELEASE_v2.0_MCP_ROADMAP.md`](./RELEASE_v2.0_MCP_ROADMAP.md) 原始估时（8~12 天）一致
> **里程碑**：v2.0「LLM 多轮 tool calling 边看边干」从 ROADMAP 想法 → 真实可点击的产品功能

---

## 🎯 一句话总结

让用户在「智能 Agent 实时渲染」面板勾上 **🛠 MCP Agent 循环** radio 后，按下「🎬 开始实时建模 ▶」，前端就会让 LLM 像 [blender-mcp](https://github.com/ahujasid/blender-mcp) 一样，通过 16 个原子工具（`get_scene_info` / `add_primitive` / `search_polyhaven_assets` / `import_polyhaven_model` / `set_material` 等）**多轮 tool_call 边看边干**地造出 Blender 场景。**用户全程能在「🛠 工具调用历史」面板看 LLM 调了什么、Blender 回了什么、每步耗时多少**。

---

## 📦 三阶段交付物对照（与 ROADMAP 一致）

| Phase | 工作 | 估时 | 实际 | 产物 |
|-------|------|------|------|------|
| 1 | Blender 插件 `aichat_bridge` 2.0.0：实现 16 个 `/mcp/*` 端点 | 4 天 | ✅ 4 天 | [`RELEASE_v2.0_PHASE1.md`](./RELEASE_v2.0_PHASE1.md) |
| 2 | `server.js` MCP 网关：4 个 `/api/mcp/*` 代理 + 错误归一化 | 1 天 | ✅ 1 天 | [`RELEASE_v2.0_PHASE2.md`](./RELEASE_v2.0_PHASE2.md) |
| **3** | **前端 Agent 循环：`/api/chat` 透传 tools + `agentRunMCPMode` + UI 面板** | **3~4 天** | **✅ 3 天** | **本文档** |

---

## 🆕 Phase 3 具体改动

### 1. `server.js /api/chat` 透传 OpenAI tool calling（约 +40 行）

**位置**：`server.js` 既有的 `/api/chat` SSE 流式接口内（v1.9.4 加 `max_tokens` 那段后面）

**改动**：

#### 入参解析（新增）
```js
// v1.10.0 / v2.0 Phase 3：OpenAI tool calling 透传
let toolsParam = undefined;
let toolChoiceParam = undefined;
if (Array.isArray(tools) && tools.length > 0) {
  // 白名单：必须是 {type:'function', function:{name, ...}} 结构
  const cleaned = [];
  for (const t of tools) {
    if (!t || typeof t !== 'object') continue;
    if (t.type !== 'function' || !t.function || typeof t.function.name !== 'string') continue;
    cleaned.push(t);
  }
  if (cleaned.length > 0) {
    toolsParam = cleaned;
    if (typeof tool_choice === 'string' && ['auto', 'none', 'required'].includes(tool_choice)) {
      toolChoiceParam = tool_choice;
    } else if (tool_choice && typeof tool_choice === 'object' && tool_choice.type === 'function') {
      toolChoiceParam = tool_choice;
    } else {
      toolChoiceParam = 'auto';  // 默认让 LLM 自主决定
    }
  }
}
```

**关键点**：
- 严格白名单（防止前端误传任意对象给上游 API）
- 任一关键字段缺失就完全不透传（向后兼容：老 caller `一键3D` / `普通聊天` / `工作流` 不需要 tools 完全不受影响）
- `tool_choice` 默认 `'auto'`（让 LLM 自己决定）

#### 请求体注入（条件性）
```js
const reqBody = { model, messages, stream: true };
if (maxTokensParam !== undefined) reqBody.max_tokens = maxTokensParam;
if (toolsParam !== undefined) {
  reqBody.tools = toolsParam;
  reqBody.tool_choice = toolChoiceParam;
}
```

只在用户真传了 tools 时才注入 `tools` / `tool_choice`，最大限度保证兼容性。

#### SSE 流转发（新增两个事件）
```js
if (Array.isArray(delta.tool_calls) && delta.tool_calls.length > 0) {
  sendEvent({ tool_calls: delta.tool_calls });
}
if (choice.finish_reason) {
  sendEvent({ finish_reason: choice.finish_reason });
}
```

**前端拿到的两个新 SSE 事件**：
- `data: {tool_calls: [{index, id, type, function:{name, arguments}}]}` —— OpenAI 流式协议：`arguments` 是字符串增量，前端需按 `index` 累加拼接成完整 JSON
- `data: {finish_reason: 'stop'|'tool_calls'|'length'|'content_filter'}` —— Agent 循环判断本轮该停还是继续

---

### 2. 前端 `m3dCallLLMTools()` 函数（约 +90 行）

**位置**：`public/index.html` 既有 `m3dCallLLM` 之外的并列函数（不替换它，让普通聊天 / 一键3D 继续用老函数）

**核心逻辑**：
```js
async function m3dCallLLMTools(configId, model, messages, tools, signal, onReasoning, onContent, maxTokens = 16000) {
  const response = await fetch('/api/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({ config_id: configId, model, messages, tools, tool_choice: 'auto', ... })
  });
  
  // 流式累加 tool_calls（关键：按 index 累加，arguments 是字符串拼接）
  const toolCallMap = {};
  while (...) {
    if (Array.isArray(data.tool_calls)) {
      for (const tc of data.tool_calls) {
        const idx = tc.index !== undefined ? tc.index : 0;
        if (!toolCallMap[idx]) toolCallMap[idx] = { id: '...', type: 'function', function: { name: '', arguments: '' } };
        if (tc.function?.name) toolCallMap[idx].function.name += tc.function.name;
        if (tc.function?.arguments) toolCallMap[idx].function.arguments += tc.function.arguments;
      }
    }
    if (data.finish_reason) finishReason = data.finish_reason;
    if (data.content) content += data.content;
    if (data.reasoning && onReasoning) onReasoning(data.reasoning);
  }
  
  return { content, tool_calls: Object.values(toolCallMap), finish_reason: finishReason };
}
```

**为什么不能用现有 `m3dCallLLM`**：现有函数只支持 `content` 流式，不识别 `tool_calls` 增量；按 `index` 累加 `arguments` 字符串拼接是 OpenAI 流式协议特有的，必须专门处理。

---

### 3. `agentRunMCPMode()` MCP Agent 主循环（约 +180 行，**Phase 3 核心**）

**位置**：`public/index.html` 既有 `agentRunPolyHavenMode` 函数之前

**完整流程**：

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1：探活                                               │
│ GET /api/mcp/ping?url=http://127.0.0.1:9876                 │
│ → 确认 aichat_bridge 2.0.0+，否则给升级提示                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 2：拉工具 schema                                      │
│ GET /api/mcp/tools?url=...                                  │
│ → 16 个 OpenAI tools 格式定义                               │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 3：主循环（最多 30 轮 LLM 调用，防失控）              │
│                                                              │
│ for round in 1..30:                                          │
│   ┌──────────────────────────────────────────┐              │
│   │ 1) 调 m3dCallLLMTools(messages, tools)   │              │
│   │    LLM 输出 tool_calls + 可选 content    │              │
│   └──────────────────────────────────────────┘              │
│                       │                                      │
│   if tool_calls 空 + content 非空:                          │
│     ✅ Agent 输出最终总结，循环结束                          │
│   else:                                                      │
│     ┌──────────────────────────────────────────┐            │
│     │ 2) 执行所有 tool_calls：                  │            │
│     │    POST /api/mcp/call                     │            │
│     │      { blender_url, tool, args, timeout } │            │
│     │    把工具结果 {role:'tool', ...} 加 msgs  │            │
│     │    记录到 🛠 工具调用历史面板             │            │
│     └──────────────────────────────────────────┘            │
│                       │                                      │
│   3) 下一轮 →                                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**关键设计点**：

1. **每个 tool_call 单独调用网关**（不批量并发）：保证 messages 历史的 `tool_call_id` 一一对应，且失败一个不会拖垮其他
2. **长操作动态超时**：`import_polyhaven_model` / `set_world_hdri` / `exec_python` 用 300s，其他 60s
3. **视口截图特殊处理**：`get_viewport_screenshot` 返回的 base64 太大不直接塞回 LLM（防 token 爆），给文字摘要 `{_viewport_image_b64_len: N, _note: '...'}`；LLM 还需要看视觉再次确认时会主动调 `get_scene_info` 看结构化数据
4. **30 轮上限**：防止 LLM 死循环失控烧 token；达到上限给警告但已完成的工具调用不会回滚
5. **状态阶段同步**：每轮 LLM 思考时 `agentSetStage('push')` 让原有的 5 阶段进度条工作；UI 文案动态显示「Round X / 30 · 工具调用 Y 次」

---

### 4. 核心 System Prompt 设计（≈80 行精华）

让 LLM 真的会用工具的关键 —— 之前如果只把 16 个 schema 抛给 LLM 不教它怎么用，会得到一堆乱七八糟的调用顺序。

**6 条核心工作范式**：
1. **每轮决策前先观察**：第一步永远调 `get_scene_info` 拿场景真实状态，不要靠想象
2. **PolyHaven 资产必须先搜后下**：禁止猜 asset_id，调 `search_polyhaven_assets` → 用真实 asset_id 调 `import_polyhaven_model` / `set_world_hdri`
3. **小步迭代**：每次只做 1~3 个原子操作（`add_primitive` / `set_material` / `update_object` / `add_light`），然后用 `get_scene_info` 或 `get_viewport_screenshot` 看效果，再决定下一步
4. **单步失败立刻换策略**：工具返回 `{ok:false, error}` 时不要重试一模一样的参数，要换 asset_id / 改 scale / 改 location
5. **完成判定明确**：当 LLM 认为场景满足需求时，输出**纯文本最终总结**（不再调用任何工具），循环就会自动结束
6. **不要写大段 bpy 代码**：除非真没合适原子工具，否则一律用 `add_primitive` + `set_material` 这种小步操作（`exec_python` 只是兜底）

**6 项场景质量硬性要求**：
- 物体 ≥ 6 个（含地板、墙、主要家具、装饰）
- 灯光 ≥ 3 盏（key + fill + rim 三点布光）
- 必须有 1 台 Camera，location 在 (5~10, -5~-10, 1.5~3)，朝向场景中心
- World 背景必须设（HDRI 优先，否则纯色 + 强度 0.5~1.0）
- 所有物体必须贴地（Z 坐标合理，不穿模不飞起）

**工具选择决策树**：把 8 类场景需求分别映射到具体工具（看场景 / 简单几何 / 灯光 / 相机 / 写实资产 / 修改 / 删 / 兜底），LLM 不会迷茫。

**4 条严禁**：编造不存在的 asset_id / 一次输出大段 bpy 代码 / 跳过观察直接连续操作 / 在 final summary 里继续调工具。

---

### 5. 🛠 工具调用历史面板

**位置**：智能 Agent UI 右列「🕒 推送时间轴」面板下方，紫色边框 `rgba(139, 92, 246, 0.4)`

**默认隐藏**，进入 MCP 模式时通过 `agentRunMCPMode` 内的 `histPanel.style.display = 'block'` 显示。

**每条调用记录**：

```html
<details style="border-left:2px solid var(--accent2)|var(--danger); ...">
  <summary>
    #1 ✅ <code>get_scene_info</code> (123ms) result_summary...
  </summary>
  <div>
    <b>args:</b> <code>{"include_objects": true}</code>
    <b>result:</b> <pre>{完整 JSON，最多 1500 字符}</pre>
  </div>
</details>
```

**显示逻辑**：
- 状态图标 `✅`（`ok !== false && !error_type`）/ `❌`（其他）
- 工具名用紫色 `<code>` 标记（紫色与 MCP 模式同色调）
- 时间 `123ms` 右侧灰色小字
- 单行 result 摘要：自动抠出 key=value 关键字段，超长截断（让用户扫一眼就知道这步干了啥）
- 展开后看完整 args + result（result pre 块 max 1500 字符，防 DOM 爆）
- 按调用顺序编号 `#1 #2 #3...`
- **只渲染最近 50 条**（防止长任务 200+ 调用把 DOM 撑爆）
- 「🗑 清空」按钮清空历史 + 重置计数

---

## 🧪 测试场景（端到端）

**输入**：「画一间日式禅意茶室，下午阳光从纸窗斜射进来，靠墙摆古琴和书架，地上放蒲团和茶具，整体氛围温暖宁静。」

**期望 LLM 工具调用顺序**（理想情况）：

| 步 | 工具 | args 关键字段 | 期望结果 |
|----|------|-------------|---------|
| 1 | `clear_scene` | `{}` | `{ok:true}` 清空 |
| 2 | `get_scene_info` | `{}` | `{ok:true, stats:{mesh_count:0,light_count:0,...}}` 确认场景空 |
| 3 | `search_polyhaven_assets` | `{query:'tatami', asset_type:'models'}` | `{ok:true, results:[...]}` 拿到候选 |
| 4 | `search_polyhaven_assets` | `{query:'window light interior', asset_type:'hdris'}` | 拿 HDRI 候选 |
| 5 | `set_world_hdri` | `{asset_id:'xxx', strength:1.0}` | `{ok:true}` 设环境光 |
| 6 | `add_primitive` | `{type:'plane', name:'floor', dimensions:[6,5,0]}` | `{ok:true, name:'floor'}` 地板 |
| 7 | `set_material` | `{object_name:'floor', base_color:[0.4,0.3,0.2,1], roughness:0.7}` | 木地板 |
| 8 | `import_polyhaven_model` | `{asset_id:'guzheng_or_similar', location:[1,-1,0]}` | 古琴（如有） |
| 9~15 | `add_primitive` × N | 书架/蒲团/茶具/桌子等 | 主要家具 |
| 16 | `add_light` × 3 | key + fill + rim | 三点布光 |
| 17 | `set_camera` | `{location:[5,-5,1.7], rotation:[63,0,45], lens:50}` | 相机 |
| 18 | `quality_check` | `{}` | 4 维度报告 |
| 19 | `get_viewport_screenshot` | `{max_size:600}` | 视觉确认 |
| 20 | （无 tool_calls） | content: "场景已完成..." | **结束** |

**用户视觉反馈**：「🛠 工具调用历史」面板上 20 个 `<details>` 条目实时出现，每条带 ✓/✗ 状态 + 用时 + 单行摘要，全过程透明可审计。

---

## 📋 兼容性

- **零破坏**：所有 v1.x 端点 / 老 radio 选项 / 工作流 / 思维导图 / 普通对话 / 一键3D 流水线**完全不动**
- **零新依赖**：纯前端 + server.js 增量改造，无 `npm install` 需要
- **MCP 模式硬依赖**：
  - `aichat_bridge` ≥ 2.0.0（Phase 1 已发，桌面有 zip 一键导出）
  - 推荐 Claude Sonnet 4 / Claude Opus 4 / GPT-4o / GPT-4-turbo / Gemini 2.5 Pro 这种原生支持 OpenAI tool calling 的模型
- **老插件用户友好提示**：Phase 1 网关层 `/api/mcp/ping` 对老 v1.2.0 插件返回 `mcp_ready=false + upgrade_hint`，前端会显示明确的升级方法（导出 zip + Add-ons 安装 + 重启 Blender 三步走）

---

## 🚧 v2.0.0 正式发版前还需要

1. **端到端真实测试**：跑 3~5 个典型场景（客厅 / 摄影棚 / 户外日落 / 卧室 / 餐厅）确认 Agent 循环每步都对，工具调用历史面板展开看 args/result 都合理
2. **欢迎弹窗重写**：把 v1.9.7 视口监测 + v1.10.0 MCP Agent 两个大特性合并写成 v2.0.0 综合发布说明（`hasLaunched_v2.0.0` key）
3. **`electron-builder` 打包**：macOS arm64 + Windows x64 dmg/exe，发到 GitHub Releases
4. **录 ≤60s 演示视频**：用户说一句话 → 屏幕分两半（左 Blender 实时变化 / 右工具调用历史滚动）→ 突出「边看边干」的价值
5. **README 加 v2.0 章节**：把 MCP Agent 模式作为头号卖点放在「⚡ AI 从零生成」「🎨 PolyHaven」之后

---

## 📈 ROADMAP 完成度

参考 [`RELEASE_v2.0_MCP_ROADMAP.md`](./RELEASE_v2.0_MCP_ROADMAP.md)：

- [x] **Phase 1 / 3**：Blender 插件 `aichat_bridge` 2.0.0（16 个 `/mcp/*` 端点，4 天）→ `RELEASE_v2.0_PHASE1.md`
- [x] **Phase 2 / 3**：server.js MCP 工具网关（4 个 `/api/mcp/*` 透传 + 错误归一化，1 天）→ `RELEASE_v2.0_PHASE2.md`
- [x] **Phase 3 / 3**：前端 Agent 循环 + UI 集成（3 天）→ **本文档**

**总开发时间**：8 天（设计 + 编码），与原估时 8~12 天一致，且每阶段都向后兼容，老用户零迁移成本。

---

## 🙏 致谢

- [blender-mcp](https://github.com/ahujasid/blender-mcp) 项目为 MCP 工具集设计和 Agent 工作范式提供参考
- OpenAI tool calling 流式协议（[文档](https://platform.openai.com/docs/guides/function-calling)）作为 `delta.tool_calls` 累加规则的标准
- v1.6.6 起的智能 Agent 实时渲染累积的 5 阶段进度条 / 推送时间轴 / 思考过程折叠区 / 实时视口监测等 UI 框架直接被 MCP 模式复用，零新组件成本

---

**v2.0.0 正式发版倒计时：剩 1~2 天端到端测试 + 打包**
