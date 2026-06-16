# v2.1.0 Phase B + D 完成报告

> 2026-05-18 · 接力 v2.1.0 Phase A（Plan-Execute-Reflect）后，本次会话一次性把 **Phase B（真·文件系统）+ Phase D（多角色专家协作）** 两个 Phase 全部做完，工具数从 21 → 26（+10），CHANGELOG 顶部 [2.1.0] 段已合并这两个 Phase 的所有 Added 段，ROADMAP 里 A/B/D 标 ✅。

## 📊 完成度速览

| Phase | 内容 | 状态 |
|---|---|---|
| **A** | Plan-Execute-Reflect 三段循环 + 5 客户端工具 | ✅ 上一会话已完成 |
| **B** | 真·文件系统 + session 子目录 + 5 客户端工具 + 6 HTTP 端点 | ✅ **本会话** |
| **C** | bpy API 实时检索 cheatsheet | ⏳ 排队 |
| **D** | 多角色专家协作 Planner/Modeler/Critic | ✅ **本会话** |
| **E** | bmesh / Geometry Nodes 模板库 | ⏳ 排队 |
| **F** | aichat_bridge 插件升级 2.0.4 → 2.1.0（snapshot） | ⏳ 排队 |
| **G** | 欢迎弹窗 + README + 打包发版 | ⏳ 排队 |

剩 C / E / F / G 四个 Phase，估计还需 6~7 天分 3 次会话做完。

---

## 🎯 Phase B：暴露真·文件系统（核心 ⭐）

### 设计意图

Plan-Execute-Reflect（Phase A）让 AI 有了"任务清单"，但仍然飘在 LLM 上下文里。一旦 round > 30 / 用户中途中止 / 跨会话续跑，那些艰难拆出来的 plan 步骤、反思笔记、中间 bpy 脚本就消失了。Phase B 让 AI **把每一步的产物都真的写到磁盘上**——用户可以随时打开 Finder / Explorer 看见、改、复用、跨会话继承。

借鉴 Claude Code / Codex CAD / Anthropic Computer Use 的 agentic 范式：**给 Agent 一个真实的工作目录而不是虚拟黑盒**，让 AI 的每一个决策和产物都可观测、可干预、可复用。

### 文件系统结构

```
~/Desktop/ai-chat-workspace/                      ← AICHAT_HOME（工作根目录）
├── README.txt                                    ← 自动生成的根目录说明
├── livingroom_2026-05-18_124530/                 ← session 1
│   ├── README.md                                 ← 自动生成的 session README
│   ├── plan.md                                   ← AI 写的任务清单
│   ├── reflections.jsonl                         ← AI 反思日志（每行一个 JSON）
│   ├── scripts/
│   │   ├── build_floor.py                        ← AI 写的 bpy 草稿
│   │   └── build_walls.py
│   └── outputs/
│       └── final_render.png                      ← 渲染产物（未来扩展）
├── kitchen_2026-05-18_153012/                    ← session 2（独立工作目录）
│   └── ...
└── default_2026-05-18_201530/                    ← AI 自动建的 fallback session
```

### 5 个新客户端工具

工具调用平均耗时 5~50ms（前端 JS → server.js HTTP 端点 → 本地文件系统），所有工具都在 `agentRunMCPMode` 主循环的 `_isClientTool` 分流里走 async 路径：

| 工具 | 关键参数 | 用途 |
|---|---|---|
| `workspace_create_session` | `name?` | 用户/AI 任一可触发，时间戳化命名防冲突 |
| `workspace_write_file` | `path, content, append?` | 写文件，支持子目录（自动 mkdir）+ append jsonl 模式 |
| `workspace_read_file` | `path` | UTF-8 读出来直塞回 LLM |
| `workspace_list_files` | `path?, recursive?` | 列文件清单 + 大小 + 修改时间 |
| `workspace_delete_file` | `path` | AI 主动清理冗余产物 |

**关键设计**：

- AI 第一次调 workspace 工具时**自动建一个 `default_{timestamp}` session**（不报错，对 token 友好）
- 用户也可以在 UI **一键建 session** 并切换
- `workspace_create_session` 调用后，session 名持久化到 `agentState.workspaceSession`，后续工具不需要重复传 session 参数

### 6 个新 server.js HTTP 端点

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/workspace/list-sessions` | GET | 列出所有 session 子目录 + 各自 mtime/ctime/文件数 |
| `/api/workspace/root` | GET | 返回 `AICHAT_HOME` 绝对路径（供 UI 显示） |
| `/api/workspace/create-session` | POST | body `{ name? }` → 返回 `{ session, path }` |
| `/api/workspace/file/read` | POST | body `{ session, path }` |
| `/api/workspace/file/write` | POST | body `{ session, path, content, append? }` |
| `/api/workspace/file/list` | POST | body `{ session, path?, recursive? }` |
| `/api/workspace/file/delete` | POST | body `{ session, path }` |

### 安全设计：路径穿越拦截

`server.js` 新增 `_resolveSessionPath(sessionName, relPath)` helper（约 30 行核心安全逻辑）：

1. **`..` 检测**：`relPath.includes('..')` → HTTP 400 + "包含 .. 路径穿越被拒"
2. **绝对路径检测**：`path.isAbsolute(relPath)` → HTTP 400 + "禁止绝对路径"
3. **session 名白名单**：`/^[a-zA-Z0-9_\-]+$/`，防止 `../sibling-session`
4. **resolve 后二次校验**：`path.resolve(sessionDir, relPath).startsWith(sessionDir)`，防止符号链接逃逸

### 端到端测试结果（30/30 全过 ✅）

测试脚本 `/tmp/_test_phaseB.js`，启动真实 server.js 跑 11 组场景：

```
=== TEST 1: list-sessions (空状态) ===                ✅ HTTP 200 / sessions[] 是数组
=== TEST 2: create-session ===                          ✅ session 名带时间戳 / 目录已建出来
=== TEST 3: write file (覆盖模式) ===                   ✅ size > 0
=== TEST 4: read file 验证内容 ===                      ✅ 完整内容回读
=== TEST 5: list files ===                              ✅ 含 plan.md + README.md
=== TEST 6: append 模式（追加 reflections.jsonl）===   ✅ 2 行 jsonl 累计写入正确
=== TEST 7: 路径穿越攻击防护 ===                        ✅ HTTP 400 + 错误提示包含 ..
=== TEST 8: 子目录写入（不被路径穿越拦截）===           ✅ scripts/build_floor.py 子目录自动创建
=== TEST 9: delete file ===                             ✅ deleted=true，再读 404
=== TEST 10: 不存在的 session ===                       ✅ HTTP 400 拒绝
=== TEST 11: list-sessions（新建后能看到）===           ✅ 列表里出现刚建的 session

==================================================
✅ Phase B 端到端测试完成：30 pass / 0 fail
==================================================
```

### UI 新增「📂 v2.1.0 Phase B：AI 工作目录」卡片

绿色边框，智能 Agent 实时渲染面板内：

- 头部：绝对路径显示 + 「📂 打开」按钮（调 Electron `shell.showItemInFolder`，能直接唤起 Finder/Explorer）
- 当前 session 名 + 「🆕 新建 session」按钮
- 「📋 查看历史 session」折叠区（最近 10 个）
- 「🗑 清理空 session」按钮（防 workspace 被废弃试验目录撑爆）

---

## 🎭 Phase D：多角色专家协作（核心 ⭐⭐）

### 设计意图

单一 AI 既要做拆任务的"规划师"又要做写代码的"建模师"还要做审图的"审图师"——三种能力对模型的要求差异巨大：

- **拆任务**：需要强推理能力（Claude Opus 4 / DeepSeek-R1 / GPT-5）
- **写代码**：需要强 tool calling 能力（Claude Sonnet 4 / GPT-4o / DeepSeek-V3）
- **审图**：需要强视觉理解能力（Gemini 2.5 Pro / Qwen-VL-Max / GPT-4o）

单一模型永远是短板拖后腿。Phase D 让用户**给三个角色配三个不同强项的模型**，主循环按角色切换 system prompt 和 LLM 端点，AI 们"分工"完成一次建模任务——这就是 **Mixture-of-Agents（MoA）** 范式在 3D 建模场景的落地。

### `agentState.multiRole` 字段（默认 enabled=true）

```javascript
agentState.multiRole = {
  enabled: true,  // ⭐ 默认开启全套模式
  planner: { configId: '', model: '' },  // 推荐 Claude Opus 4 / DeepSeek-R1 / GPT-5
  modeler: { configId: '', model: '' },  // 推荐 Claude Sonnet 4 / GPT-4o / DeepSeek-V3
  critic:  { configId: '', model: '' }   // 推荐 Gemini 2.5 Pro / Qwen-VL-Max / GPT-4o
}
```

任一角色的 `configId` / `model` 为空时，主循环自动 fallback 到「主 Agent 配置」（顶部那个 API 下拉），保证不破坏老用户体验。

### 主循环按 round 切换角色

```
┌─────────────┬──────────────────────────────────────────────────┐
│ Round       │ 角色 + system prompt 注入                         │
├─────────────┼──────────────────────────────────────────────────┤
│ Round 1     │ 🧠 Planner — 拆任务 / 出 plan.md / 严禁直接调建模工具  │
│ Round 2~N-2 │ 🛠 Modeler — 按 plan 调原子工具实现 / 每完成 update_step │
│ Round N-1   │ 👁 Critic — 调 get_viewport_screenshot 审图 + 写反思 │
│ Round N     │ 🛠 Modeler 修复轮 — 按反思清单修问题                  │
└─────────────┴──────────────────────────────────────────────────┘
```

每个角色的 system prompt 在 `AGENT_ROLE_PROMPTS` 常量中，包含明确的 DO / DON'T 指令清单。例如 Planner 的 prompt 严禁调 `add_primitive` / `set_material` 等建模工具，强制只能调 `plan_create + workspace_write_file（写 plan.md）+ mark_done(交接给 Modeler)`。

### UI 新增「🎭 v2.1.0 Phase D：多角色专家协作」折叠卡片

绿色边框，仅 MCP 模式可见：

- 顶部「☑ 启用多角色协作（关闭 = 单 AI 老模式回退）」全局开关
- 三个独立子卡片（蓝 / 黄 / 紫三色边框对应 🧠 / 🛠 / 👁 三角色）：
  - **🧠 Planner**：API + 模型独立下拉，副标题「推荐：Claude Opus 4 / DeepSeek-R1 / GPT-5（强推理）」
  - **🛠 Modeler**：副标题「推荐：Claude Sonnet 4 / GPT-4o / DeepSeek-V3（强工具调用）」
  - **👁 Critic**：副标题「推荐：Gemini 2.5 Pro / Qwen-VL-Max / GPT-4o（强视觉理解）」

### 工具调用历史面板增强

每条记录前缀加角色 badge：

```
[🧠 Planner] #1 plan_create ✓ 12ms · 5 步任务清单
[🧠 Planner] #2 workspace_write_file ✓ 23ms · plan.md (1.2 KB)
[🧠 Planner] #3 mark_done ✓ 8ms · 交接给 Modeler
[🛠 Modeler] #4 add_primitive ✓ 145ms · cube_floor
[🛠 Modeler] #5 add_primitive ✓ 132ms · cube_wall_north
... (更多工具调用)
[👁 Critic] #18 get_viewport_screenshot ✓ 320ms · 1024x768
[👁 Critic] #19 reflect ✓ 11ms · 沙发位置偏左 0.5m / 玻璃 Roughness 太高
[🛠 Modeler] #20 update_object ✓ 89ms · sofa.location.x = -0.5
[🛠 Modeler] #21 set_material ✓ 76ms · glass.roughness = 0.05
```

用户能一眼看出：① 哪一步是哪个角色做的 ② 模型选的对不对（如果某角色经常报错，说明该角色的模型选错了）

### AI 看到的工具表

| 工具来源 | 数量 | 名称 |
|---|---|---|
| **CLIENT_TOOLS（Phase A）** | 5 | plan_create / plan_update_step / plan_get / reflect / mark_done |
| **WORKSPACE_TOOLS（Phase B）** | 5 | workspace_create_session / write_file / read_file / list_files / delete_file |
| **Blender 原子工具（v2.0）** | 16 | get_scene_info / add_primitive / add_light / set_camera / set_material / update_object / delete_object / clear_scene / list_objects / get_object_info / get_viewport_screenshot / search_polyhaven_assets / set_world_hdri / import_polyhaven_model / exec_python / quality_check |
| **总计** | **26** | （从 v2.1.0 Phase A 的 21 → 26，+5） |

---

## 📁 改动文件清单

| 文件 | 改动 |
|---|---|
| `public/index.html` | ~+800 行：CLIENT_TOOLS 数组扩到 10 个 / `_runClientTool` 改 async + workspace 分支 / `AGENT_ROLE_PROMPTS` 三角色 prompt / `agentState.workspaceSession` + `multiRole` 字段 / `#agent-workspace-panel` + `#agent-multi-role-panel` 两块新 UI 卡片 / 工具历史角色 badge 渲染 / Planner-Modeler-Critic 角色 round 切换主循环 |
| `server.js` | ~+200 行：`AICHAT_HOME` 计算 + 自动 mkdir + `_resolveSessionPath` 路径穿越拦截 helper + 6 个 `/api/workspace/*` HTTP 端点 + README.md 自动写入 |
| `CHANGELOG.md` | 顶部 [2.1.0] 段合并 Phase B + Phase D 全部 Added 段 + Compatibility + Files / 末尾 ROADMAP 里 Phase B / Phase D 标 ✅ + 接力 prompt 更新为 C/E/F/G |
| `RELEASE_v2.1.0_PHASE_BD.md` | 本文件（新增） |

---

## 🧪 验收测试

### Phase B 后端（自动化）

```
✅ Phase B 端到端测试完成：30 pass / 0 fail
```

详见 `/tmp/_test_phaseB.js`。

### Phase D（手动验证流程）

1. 启动 server.js → 浏览器打开 → 切到「🎬 智能 Agent 实时渲染」
2. 配三套 API + 模型（Planner / Modeler / Critic）
3. 输入场景需求「画一间日式茶室，下午阳光斜射进来」
4. 启动 Agent，观察工具历史面板：
   - Round 1 应该都是 `[🧠 Planner]` 标签的工具调用
   - Round 2~N-2 应该都是 `[🛠 Modeler]`
   - Round N-1 应该出现 `[👁 Critic]` + `get_viewport_screenshot`
   - Round N 回到 `[🛠 Modeler]` 修复

### 兼容性回归

- ✅ v1.11.x 用户的 localStorage（无 plan / workspaceSession / multiRole 字段）→ 自动初始化为默认值，不报错
- ✅ MCP 模式之外（ai-only / polyhaven）完全不受影响
- ✅ 多角色协作可被一键关闭回到单 AI 老模式（顶部勾选框 unchecked）
- ✅ `aichat_bridge` 插件版本不变（仍是 2.0.4）

---

## 🚧 下一步（Phase C / E / F / G）

详见 CHANGELOG 末尾 ROADMAP 段，简要：

1. **Phase C + E 一次会话**（3 天）：bpy 检索 cheatsheet（300 条）+ bmesh 模板库（10 个），工具数 26 → 28
2. **Phase F 一次会话**（1 天）：插件升级 2.0.4 → 2.1.0（blend_summary / bookmark_state / restore_state 三个新端点）
3. **Phase G 一次会话**（1 天）：欢迎弹窗 + README + 打包发版（4 个 dmg/exe）

接力会话 prompt 已写在 CHANGELOG 末尾，复制即可秒续。
