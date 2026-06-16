# 🏗 多工程师协作（v2.1.0 Phase I · Multi-Worker Modeler）

> 在「🎬 智能 Agent 实时渲染」面板中，让 N 个 Modeler 子工程师**串行**地各负责一个物体。

## 1. 概念

**痛点（旧版单 Modeler）**：场景包含多个独立物体（鸟居 + 樱花树 + 石灯笼）时，单一 Modeler 在 30 轮里要回不停切换 3 个物体上下文，常出现「建到一半忘了之前是怎么布的局」「沙发挪一下把茶几顶穿了模」等问题。

**新版（多工程师）**：Planner 第 1 轮就调 `spawn_workers` 把任务拆给 N 个独立工程师，每人专注一个物体（≤8 名），主循环按依赖拓扑顺序串行 spawn 他们：

| 维度 | 单 Modeler | 多工程师 |
|---|---|---|
| 单物体上下文 | 30 轮里被稀释 | 6~8 轮聚焦 |
| 命名冲突 | 容易 `sofa.001` / `sofa.002` 混淆 | 每人 `w{id}_*` 前缀，隔离 |
| 穿模检测 | 全局只能靠 Critic | 每个 worker 自查 bbox 区域 |
| 修复迭代 | 不针对单物体 | 单物体最多 2 轮迭代，第 3 次强制通过 |

**关键约束**：
- ⛔ **串行** 而非并行 —— Blender 的 `exec_python` 抢锁，并行会立刻打架
- ⛔ **不动 server.js** —— 全部编排在前端 `public/index.html` 完成
- ⛔ worker 上限 8、自查迭代上限 2 轮 —— 防爆 token、防死循环
- ⛔ 命名前缀 `w{id}_*` —— 防穿模、便于后续 Critic 按前缀过滤

## 2. 工作流（4 阶段）

```
[场景需求]
    │
    ▼
┌─────────────────────────────────────┐
│ ① 📋 Planner（Round 1）              │
│   - 看场景需求                       │
│   - ≥2 个独立物体 → 调 spawn_workers │
│     输出 workers JSON：              │
│     [{id,name,task,bbox,deps}, ...] │
│   - 系统自动转成 plan.steps          │
│     （每个 step 带 worker_id）       │
│   - 拓扑排序后按 deps 顺序串行       │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ ② 🛠 Modeler#N（多轮 Round）         │
│   每轮看 plan_get 找当前 in_progress │
│   step.worker_id → 进入「单物体专注模式」│
│   - 命名前缀 w{N}_*（防穿模）       │
│   - 把物体放在 step.bbox 范围内      │
│   - 调实际 Blender 工具完成建模      │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ ③ 自查（worker_self_check）          │
│   - 自动调 get_viewport_screenshot   │
│   - 喂 vision 模型（继承 Critic 配置）│
│   - 通过 → 写 worker_{id}_done.md    │
│           标记 plan.step done        │
│           进入下一个 worker          │
│   - 不通过 → 给修复建议，再来 1 轮   │
│             最多 2 轮，第 3 次强制通过│
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ ④ 总 Critic 审图（已有，每 6 轮）    │
│   全局质量把关                       │
└─────────────────────────────────────┘
```

## 3. 工具说明（2 个新客户端工具）

### `spawn_workers({ workers })`

**调用时机**：第 1 轮 Planner 决策树，场景含 ≥2 个独立物体时。

**参数**：
```ts
workers: [
  {
    id: 1,                                  // 从 1 起递增
    name: "鸟居",                          // 物体短名
    task: "建一座朱红色日式鸟居...",       // ≤120 字详细描述
    bbox: [-3, -1, 0, 3, 1, 5],            // [x1,y1,z1,x2,y2,z2] 占地包围盒
    deps: []                                // 依赖的其它 worker id（可空）
  },
  { id: 2, name: "樱花树", task: "...", bbox: [...], deps: [1] },
  // ...上限 8 个
]
```

**返回**：
```ts
{
  ok: true,
  workers_count: 3,
  sorted_order: [1, 2, 3],   // 拓扑排序后的 id 顺序
  message: "✅ 已注册 3 名工程师..."
}
```

**副作用**：
- 把 workers 注册到 `agentState.workers`（含 status / iteration / selfCheckLog）
- 同步生成 `agentState.plan.steps`（每个 step 带 worker_id / bbox / deps）
- UI 立刻显示「📋 Plan-Execute-Reflect 进度」面板
- 落盘 `workers/_index.md` 到 workspace（用户能在 Finder 看到）

### `worker_self_check({ worker_id, summary })`

**调用时机**：Modeler#N 完成自己负责物体的建模 + 材质后。

**参数**：
```ts
{
  worker_id: 1,
  summary: "建好朱红鸟居 4 根立柱 + 横梁 + 屋顶...材质用 Principled BSDF Base Color (0.7, 0.15, 0.1)"
}
```

**自动流程**：
1. 调 `get_viewport_screenshot` 拉视口截图（失败时退化到 Blender bridge 直连）
2. 用 vision 模型审图 —— 复用 Critic 配置（`agentState.multiRole.critic`），缺失时回落到主 Agent
3. vision 输出 JSON：`{passed, issues:[], suggestion:""}`
4. 通过 → 写 `workers/worker_{id}_done.md` + 标记 plan.step done
5. 不通过 → 把 issues + suggestion 返回给 Modeler，自动迭代下一轮
6. 第 3 次还不通过 → 强制通过（防死循环）

## 4. 调试技巧

### 在 UI 上观察
- **📋 Plan 面板**：每个 step 的 title 是 `🛠 #{id} {name}`，状态 badge 按 worker 进度变色
- **🔍 自检日志**：每轮自查会显示「`🔍 worker #1 鸟居 自查 (第 1/2 轮)…`」
- **🕒 推送时间轴**：可以看到 `spawn_workers ×3` / `worker #1 self_check r1` / `worker #1 ✅ passed` 等事件

### 在 workspace 看落盘
打开 `~/Desktop/ai-chat-workspace/{session}/workers/` 目录：
- `_index.md` —— spawn_workers 的全清单（任务/bbox/依赖）
- `worker_{id}_done.md` —— 每个 worker 自查通过后写的总结，含自查日志（每轮的 issues / suggestion）

### 常见排查

| 现象 | 排查 |
|---|---|
| `worker #N 不存在` | Modeler 用错了 worker_id（不在 spawn_workers 返回的 sorted_order 里）。让它先调 plan_get 拿正确 worker_id |
| 自查反复不通过 | vision 模型可能选了非视觉模型。检查「🧠 多 AI 协作」面板里 Critic 角色配的是不是 GPT-4o / Claude / Gemini-2 等视觉模型 |
| 物体穿模 | bbox 设的太小、worker 之间 bbox 重叠。在 Planner prompt 里强调「相邻 worker bbox 留 0.5m 空隙」 |
| 命名冲突 `Cube.001` | Modeler 没用 `w{id}_*` 前缀。检查 system appendix 是不是正确注入了 multi-worker 模式 |

## 5. 扩展

### 加自查维度
当前 `_smVisionJudge` 只让 vision 判 4 项（建出 / 位置 / 比例 / 穿模）。如果想加「色彩搭配 / 风格一致性」，改 `public/index.html` 中 `_smVisionJudge` 函数的 prompt：

```js
// public/index.html ~line 14906
const prompt = `你是审图工程师。当前正在审查 worker #${worker.id} (${worker.name}) 的成果。\n\n` +
  `该工程师的任务：${worker.task}\n` +
  // 在这后面加你想检查的维度
  `⑤ 色调是否符合「日式神社」整体风格（朱红/木色为主）` +
  ...
```

### 改并行
**不推荐**（Blender exec_python 互斥锁会卡住），但如果真的想试：
1. 把 `spawn_workers` case 的拓扑排序去掉，改成同时把所有 step 标 `in_progress`
2. 主循环 round loop 需要按 worker_id 分发到独立的子 LLM 调用
3. Blender 端需要把 `/exec` 改成 worker_id 级别的锁（而不是全局锁）

### 改自查迭代上限
当前是 2 轮（第 3 次强制通过）。改 `public/index.html` 中 `case 'worker_self_check'`：

```js
if (w.iteration >= 2) {   // ← 改成 3 或 4
  w.status = 'done';
  ...
}
```

注意：太高的迭代上限会让单 worker 烧大量 token，建议保持 2~3。

### 改 worker 上限
当前是 8 个（在 `case 'spawn_workers'`）：

```js
if (workers.length > 8) {
  workers = workers.slice(0, 8);
}
```

超过 8 个 worker 容易爆 LLM 上下文。需要更多物体时建议分批：先跑前 8 个，跑完手动二次启动追加。

---

**📦 改动文件清单**（v2.1.0 Phase I）：
- `public/index.html` ~13340（CLIENT_TOOLS 数组追加 2 个工具）
- `public/index.html` ~13813（toolName switch 追加 2 个 case）
- `public/index.html` ~14878（辅助函数 `_smTopoSort` / `_smVisionJudge` / `_writeWorkerDone`）
- `public/index.html` ~14851（AGENT_ROLE_SYSTEM_APPENDIX 增强 planner / modeler）
- `tools/multi_worker/README.md`（本文件）

**🚧 已对齐的约束**（不要改！）：
- 不动 server.js（全部前端编排）
- 串行而非并行（Blender exec_python 抢锁）
- worker 间靠文件系统通信（`workers/worker_{id}_done.md`）
- 自查迭代上限 2 轮、worker 上限 8、命名前缀 `w{id}_*` 防穿模
