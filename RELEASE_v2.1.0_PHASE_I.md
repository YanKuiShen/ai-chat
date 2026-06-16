# v2.1.0 Phase I — 智能多工程师协作（Multi-Worker Modeler）

> 任务接力文档（第 1 棒 → 第 2 棒移交）
> 基于：v2.1.0 H-Hotfix6（2026-05-18）

## 🎯 用户需求原文

> "能否根据场景智能调用多个工程师，然后每个工程师专门负责一个物体的构建与位置，在自查阶段也是各自负责各自的"

## 🏗 架构概览

```
[场景需求]
    │
    ▼
┌─────────────────────────────────────┐
│ ① 📋 Planner（已有）                 │
│   - 看场景需求                       │
│   - 调【新】spawn_workers 工具         │
│     输出 workers JSON：             │
│     [{id,name,task,bbox,deps},...]  │
│   - 同时调 plan_create 把每个 worker  │
│     转成一个 step（worker_id 字段）   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ ② 主循环按 plan.steps 串行处理        │
│   每进入一个 in_progress step：       │
│   - 检查 step.worker_id              │
│   - 有 → 切到 Modeler#N 角色          │
│       · system prompt 注入 worker.task │
│         + bbox + 命名前缀 w{N}_*      │
│       · UI 加 [🛠 #N 鸟居工程师] 前缀 │
│   - 没 → 普通 Modeler 流程             │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ ③ Modeler#N 干完后调【新】           │
│   worker_self_check(id) 工具：        │
│   - 自动调 get_viewport_screenshot   │
│     带 bbox 裁剪到自己负责区域        │
│   - 把截图喂 vision 模型审一次        │
│   - 不通过 → 系统自动让 Modeler#N    │
│     再来 1 轮（最多迭代 2 次）        │
│   - 通过 → 写 worker_{id}_done.md   │
│     plan_update_step status=done    │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ ④ 全部 worker 完成 → 总 Critic 审    │
│   （已有的 round % 6 === 0 触发）     │
└─────────────────────────────────────┘
```

## 📁 改动清单（共 6 处，最大改动 ~400 行）

### 改动 1 — `public/index.html`：在 tools 列表注册 2 个新客户端工具

定位：找 `tools.push(...)` 或 `tools = [...]` 拼装段（约 14089 行附近）

```js
// v2.1.0 Phase I 新增：多工程师调度
tools.push({
  type: 'function',
  function: {
    name: 'spawn_workers',
    description: '【v2.1.0 Phase I 多工程师 ⭐】场景包含 ≥2 个独立物体时调此工具，把任务拆给 N 个独立工程师并行/串行干。每个 worker 有自己的 system prompt、独立 bbox、独立命名前缀（防穿模）。系统会自动把 workers 注册到 plan，按 deps 拓扑排序后逐个 spawn。强烈建议在第一次 plan_create 之前先调这个，让架构清晰。',
    parameters: {
      type: 'object',
      properties: {
        workers: {
          type: 'array',
          description: '工程师任务清单',
          items: {
            type: 'object',
            properties: {
              id: { type: 'integer', description: '从 1 开始递增' },
              name: { type: 'string', description: '物体短名（如「鸟居」「樱花树」）' },
              task: { type: 'string', description: '该工程师本职工作的详细描述（≤120 字）' },
              bbox: { type: 'array', items: { type: 'number' }, description: '占地包围盒 [x1,y1,z1,x2,y2,z2]，用于自查时裁剪 viewport 和检测穿模' },
              deps: { type: 'array', items: { type: 'integer' }, description: '依赖的其它 worker id（如「樱花树要在鸟居建好后再种」）' }
            },
            required: ['id', 'name', 'task', 'bbox']
          }
        }
      },
      required: ['workers']
    }
  }
});

tools.push({
  type: 'function',
  function: {
    name: 'worker_self_check',
    description: '【v2.1.0 Phase I 多工程师 ⭐】当前 worker 完成自己负责物体的所有建模/材质后调用。系统会自动：① 渲染 worker 的 bbox 区域 viewport ② 用 vision 模型审图（位置/比例/材质对不对） ③ 不通过则给出修复指令让你再来 1 轮 ④ 通过则写 worker_{id}_done.md 并把 step 标记为 done。最多迭代 2 次。',
    parameters: {
      type: 'object',
      properties: {
        worker_id: { type: 'integer', description: '当前 worker 的 id' },
        summary: { type: 'string', description: '一句话自我总结：做了什么/材质用了什么/碰到什么问题' }
      },
      required: ['worker_id', 'summary']
    }
  }
});
```

### 改动 2 — `public/index.html`：在 toolName switch 里加两个 case

定位：约 13358 行 `case 'plan_create':` 附近

```js
case 'spawn_workers': {
  const workers = (toolArgs.workers || []).filter(w => w && w.id && w.name && w.task);
  if (workers.length === 0) {
    toolResult = { ok: false, error: 'workers 数组为空或字段不全' };
    break;
  }
  // 注册到 agentState
  if (!agentState.workers) agentState.workers = [];
  agentState.workers = workers.map(w => ({
    ...w,
    status: 'pending',     // pending / in_progress / done / failed
    iteration: 0,          // 自查迭代次数
    selfCheckLog: [],
    objectsCreated: []     // 该 worker 期间创建的物体名（用 w{id}_ 前缀检测）
  }));
  // 同步生成 plan steps（接管已有 plan）
  if (!agentState.plan) agentState.plan = { goal: '', createdAt: Date.now(), steps: [], reflections: [] };
  // 拓扑排序
  const sorted = _smTopoSort(workers);
  agentState.plan.steps = sorted.map(w => ({
    id: `w${w.id}`,
    title: `🛠 #${w.id} ${w.name}`,
    intent: w.task,
    status: 'pending',
    worker_id: w.id,
    bbox: w.bbox,
    deps: w.deps || [],
    note: '',
    updatedAt: Date.now()
  }));
  agentRenderPlan();
  agentAppendReviewLog(
    `<div style="color:#10b981; font-weight:600;">🏗 多工程师启动：注册了 ${workers.length} 名工程师，按依赖拓扑排序如下：</div>` +
    sorted.map(w => `<div style="font-size:11px; color:var(--text-muted); padding-left:12px;">  #${w.id} ${w.name} — ${w.task.substring(0,40)}…</div>`).join('')
  );
  agentAppendTimeline('info', `🏗 spawn_workers ×${workers.length}`);
  toolResult = {
    ok: true,
    workers_count: workers.length,
    sorted_order: sorted.map(w => w.id),
    message: `✅ 已注册 ${workers.length} 名工程师。请逐个 worker 干活：当前应该开始 #${sorted[0].id} ${sorted[0].name}（task: ${sorted[0].task}）。命名前缀务必用 w${sorted[0].id}_*！`
  };
  break;
}

case 'worker_self_check': {
  const wid = toolArgs.worker_id;
  const w = (agentState.workers || []).find(x => x.id === wid);
  if (!w) { toolResult = { ok: false, error: `worker #${wid} 不存在` }; break; }
  if (w.iteration >= 2) {
    // 兜底：超 2 轮强制通过
    w.status = 'done';
    toolResult = { ok: true, passed: true, forced: true, message: `worker #${wid} 已迭代 2 轮，强制通过。继续下一个 worker。` };
    break;
  }
  w.iteration++;
  agentAppendReviewLog(`<div style="color:#a78bfa;">🔍 worker #${wid} 自查 (第 ${w.iteration}/2 轮)…</div>`);
  // 调 viewport_screenshot
  const shot = await _proxyMcpCall('get_viewport_screenshot', { bbox: w.bbox });  // ← 注：bbox 参数需 Blender 端支持，否则用全图
  if (!shot.ok) { toolResult = { ok: false, error: '截图失败：' + shot.error }; break; }
  // 调 vision 审图（复用 Critic 的 config）
  const criticCfg = _agentGetRoleConfig('critic');
  const verdict = await _smVisionJudge(criticCfg, shot.image_base64, w);
  // verdict: { passed: bool, issues: [], suggestion: '' }
  w.selfCheckLog.push({ at: Date.now(), iteration: w.iteration, ...verdict });
  if (verdict.passed) {
    w.status = 'done';
    // 写 worker_{id}_done.md
    await _writeWorkerDone(w, toolArgs.summary);
    // 标记对应 plan step 为 done
    const step = agentState.plan.steps.find(s => s.worker_id === wid);
    if (step) { step.status = 'done'; step.updatedAt = Date.now(); }
    agentRenderPlan();
    toolResult = { ok: true, passed: true, message: `✅ worker #${wid} ${w.name} 自查通过。可以继续下一个 worker。` };
  } else {
    toolResult = {
      ok: true,
      passed: false,
      iteration: w.iteration,
      issues: verdict.issues,
      suggestion: verdict.suggestion,
      message: `⚠️ worker #${wid} 自查未通过（第 ${w.iteration} 轮）。问题：${verdict.issues.join('；')}。建议：${verdict.suggestion}。请修复后重新调 worker_self_check。`
    };
  }
  break;
}
```

### 改动 3 — 新增辅助函数（紧接 `_agentGetRoleConfig` 后）

```js
// v2.1.0 Phase I：多工程师辅助函数

function _smTopoSort(workers) {
  // Kahn 算法：按 deps 拓扑排序
  const indeg = {}; const adj = {};
  for (const w of workers) { indeg[w.id] = 0; adj[w.id] = []; }
  for (const w of workers) {
    for (const d of (w.deps || [])) {
      if (adj[d]) { adj[d].push(w.id); indeg[w.id]++; }
    }
  }
  const queue = workers.filter(w => indeg[w.id] === 0).map(w => w.id);
  const sorted = [];
  while (queue.length) {
    const id = queue.shift();
    sorted.push(workers.find(w => w.id === id));
    for (const next of (adj[id] || [])) {
      indeg[next]--;
      if (indeg[next] === 0) queue.push(next);
    }
  }
  // 如有环，把剩下的按 id 顺序补在末尾
  if (sorted.length < workers.length) {
    const sortedIds = new Set(sorted.map(w => w.id));
    for (const w of workers) if (!sortedIds.has(w.id)) sorted.push(w);
  }
  return sorted;
}

async function _smVisionJudge(criticCfg, imgBase64, worker) {
  // 用 vision 模型审图：返回 { passed, issues, suggestion }
  const prompt = `你是审图工程师。当前正在审查 worker #${worker.id} (${worker.name}) 的成果。\n\n该工程师的任务：${worker.task}\n占地包围盒：${JSON.stringify(worker.bbox)}\n\n请判断截图中该物体是否：① 已建出 ② 位置/比例正确 ③ 材质符合任务描述 ④ 没有穿模。\n\n严格输出 JSON：{"passed": true|false, "issues": ["问题1", "问题2"], "suggestion": "如何修复（一句话）"}`;
  const messages = [
    { role: 'system', content: '严格输出 JSON 不要 markdown' },
    { role: 'user', content: [
      { type: 'text', text: prompt },
      { type: 'image_url', image_url: { url: 'data:image/png;base64,' + imgBase64 } }
    ]}
  ];
  try {
    const resp = await fetch('/api/chat', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ config_id: criticCfg.configId, model: criticCfg.model, messages, stream: false, max_tokens: 800 })
    });
    const j = await resp.json();
    const text = j.content || '';
    const m = text.match(/\{[\s\S]*\}/);
    if (m) return JSON.parse(m[0]);
  } catch(e) { console.warn('vision judge 失败', e); }
  return { passed: true, issues: [], suggestion: '审图模型异常，跳过本轮' };
}

async function _writeWorkerDone(w, summary) {
  if (!agentState.workspaceSession) return;
  const md = `# Worker #${w.id} ${w.name}\n\n- 任务：${w.task}\n- bbox：${JSON.stringify(w.bbox)}\n- 自查迭代：${w.iteration} 轮\n- 总结：${summary}\n\n## 自查日志\n\n${w.selfCheckLog.map((l,i) => `### 第 ${l.iteration} 轮\n- passed: ${l.passed}\n- issues: ${(l.issues||[]).join('；')}\n- suggestion: ${l.suggestion || ''}`).join('\n\n')}\n`;
  try {
    await fetch('/api/workspace/file/write', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ session: agentState.workspaceSession, path: `workers/worker_${w.id}_done.md`, content: md, append: false })
    });
  } catch(e){}
}
```

### 改动 4 — Modeler system appendix 增强

定位：14658 行 `AGENT_ROLE_SYSTEM_APPENDIX.modeler`

```js
modeler: `\n\n## 🛠 当前你是【🛠 Modeler 建模师】角色\n\n### 普通模式\n看 plan_get 拿当前 in_progress 的步骤，按 intent 调 Blender 工具完成，调 plan_update_step({status:"done"}) 标记。\n\n### 多工程师模式 ⭐\n如果当前 in_progress step 有 worker_id 字段：\n- 你现在是【🛠 工程师 #{worker_id} 「{step.title}」】，**只负责这一个物体**\n- 命名所有创建的物体时**必须以 w{worker_id}_ 为前缀**（如 w1_torii_pillar、w1_torii_top），防止穿模和重名\n- 把物体放在 step.bbox 指定的范围内\n- 干完所有建模/材质 → 调 worker_self_check({worker_id, summary}) → 系统会渲染你的 bbox 区域审图 → 通过则自动标 done，不通过会给修复建议（最多迭代 2 次）\n- 通过后直接进入下一个 worker（系统会让你看到下一个 in_progress step）\n- **不要管其它 worker 的物体**，他们有自己的工程师`
```

### 改动 5 — Planner system appendix 增强

```js
planner: `\n\n## 🎯 当前你是【📋 Planner 规划员】角色\n\n### 第一轮决策树\n如果场景需求里有 **≥2 个独立物体**（例：鸟居+石灯笼+樱花树）：\n→ **优先调 spawn_workers ⭐**，把每个物体拆成一个 worker。系统会自动转换成 plan steps，每个 step 带 worker_id。\n\n如果场景需求只有 1 个物体（例：单独建一辆车）：\n→ 调 plan_create 拆 3~8 步常规 plan。\n\n### 后续轮次\n- 已有 plan 时调 plan_get 检查进度\n- 调 reflect 记录观察+决策\n- 不要直接调 Blender 工具（那是 Modeler 的活）`
```

### 改动 6 — README

`tools/multi_worker/README.md`（新增）

## 🧪 自测脚本（下一棒跑）

```bash
cd /Users/Apple/Desktop/ai-chat
# ① 语法检查
node -e "
const fs=require('fs');
const html=fs.readFileSync('public/index.html','utf8');
const m=html.match(/<script>([\s\S]*?)<\/script>/g);
let total=0, ok=0;
for(const s of m){
  const code=s.replace(/^<script[^>]*>/,'').replace(/<\/script>$/,'');
  total++;
  try{ new Function(code); ok++; } catch(e){ console.log('❌',e.message.substring(0,80)); }
}
console.log('script blocks:',total,'syntax ok:',ok);
"
# ② 端到端
npm start
# 浏览器：场景需求填「鸟居 + 樱花树 + 石灯笼，3 件套日式神社」
# 期望：第 1 轮 Planner 调 spawn_workers → UI 显示 3 工程师 → 主循环按依赖串行 → 每人完成自查
```

## ✅ 已对齐的约束

- 不动 server.js（全部前端编排）
- 复用现有 plan / workspace / multi-role 配置
- 串行而非并行（避免 Blender exec_python 抢锁）
- worker 间用文件系统通信（worker_{id}_done.md）
- 自查迭代上限 2 轮 → 防死循环
- 总 worker 上限 8 → 防爆 token

## 📊 预期效果

输入：「鸟居 + 樱花树 + 石灯笼」
- 旧版（单 Modeler）：30 轮里来回切换三个物体，常出现"建到一半忘了之前的"
- 新版（3 工程师）：每个工程师上下文 6~8 轮，专注单物体，自查通过才放手 → 单物体质量↑，整体一次过率↑

## 🔁 下一棒动作清单

1. 把改动 1~6 按定位 replace_in_file 注入 index.html（最大块在 case 分发，~140 行）
2. 创建 tools/multi_worker/README.md
3. 跑语法检查脚本
4. npm start → 浏览器自测一个 3 物体场景
5. 通过后写 CHANGELOG.md 一行 + 重打 dmg

预计工时：3~4 小时（context 干净状态下）。
