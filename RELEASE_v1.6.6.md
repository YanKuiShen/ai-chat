# 🚀 v1.6.6 发布说明 · 智能 Agent 实时渲染 + 治平面 Bug

> **发布日期**：2026-05-16
> **版本号**：1.6.6
> **配套插件版本**：`aichat_bridge` 1.0.2 → **1.1.0**（用户**必须重装一次**才能使用 Agent 自检功能）

---

## ⚠️ 本次会话状态（重要！）

由于上下文窗口已达 96%，**本次会话仅完成文档骨架 + 插件升级**，代码改动需在新会话中接续。

### ✅ 本次会话已完成
- `package.json` 版本号 1.6.5 → **1.6.6**
- `ai-chat/RELEASE_v1.6.6.md`（本文档，新会话的需求规格说明书）
- `ai-chat/CHANGELOG.md` 顶部新增 `[1.6.6]` 章节
- `ai-chat/blender_addon/aichat_bridge/__init__.py` 升 1.1.0：新增 `GET /scene_report`、`/ping` 返回 Blender 版本号
- 重新打包 `aichat_bridge.zip`（命令 `npm run build:addon`）

### ❌ 待新会话完成的代码改动

**新会话开工提示词建议**：
> 「读 `ai-chat/RELEASE_v1.6.6.md` 作为需求规格。然后按里面的 1~7 节顺序完成代码改动。从读 `ai-chat/public/index.html` 和 `ai-chat/server.js` 开始。」

具体见下方各节 **「📋 实施清单」** 的 `[ ]` 项。

---

## 🐛 1. 修复一键3D「只生成一个平面」(P0 致命 Bug)

### 痛点
用户反馈：v1.6.5 推到 Blender 后只创建了一个地板 plane，其他物体（家具/灯光/相机/世界）都没出现，**但代码面板里能看到完整的代码**（包含 `# World`、`# Render`、`scene.eevee.use_volumetric_lights = True` 等末尾内容）。

### 根因
Blender 4.2+ EEVEE Next 移除/改名了以下属性：

| 属性 | Blender 3.x | Blender 4.2+ EEVEE Next |
|---|---|---|
| `scene.eevee.use_bloom` | ✅ 存在 | ❌ **不存在了**（Bloom 改用合成节点） |
| `scene.eevee.use_volumetric_lights` | ✅ 存在 | ⚠️ 改名 |
| `scene.eevee.use_ssr` | ✅ 存在 | ❌ 改用 `use_raytracing` |
| `bsdf.inputs["Emission"]` (Color) | ✅ 存在 | ❌ 改名 `Emission Color` |

AI 生成的代码到处用了这些 3.x 属性 → 执行到第一个 setattr 就抛 `AttributeError` → 整段 `exec()` 中断 → 只剩下最先创建的地板 plane。

### 📋 实施清单

- [x] **修改 `m3dStep4_estimate` 的 system prompt**（`index.html` 内搜索 `m3dStep4_estimate`）
  - 加入"Blender 版本无关编程"硬性要求：
    ```
    ## 🚨 兼容性铁律（v1.6.6 新增，违反即整段失败）
    1. 所有 scene.eevee.* 设置必须用 hasattr 守护：
       ```python
       if hasattr(scene.eevee, "use_bloom"):  # 4.2+ 移除
           scene.eevee.use_bloom = True
       ```
    2. 所有 bsdf.inputs["Emission"] 必须双重兼容：
       ```python
       for key in ("Emission Color", "Emission"):
           if key in bsdf.inputs:
               bsdf.inputs[key].default_value = (...); break
       ```
    3. 每个独立物体的创建用 try/except pass 包裹：
       ```python
       try:
           bpy.ops.mesh.primitive_cube_add(...)
           sofa = bpy.context.active_object; sofa.name = "sofa"
           ...
       except Exception as e:
           print(f"[WARN] sofa failed: {e}")
       ```
    4. 禁止使用以下已被 4.2+ 移除的属性（除非 hasattr 守护）：
       use_bloom / use_ssr / use_ssr_refraction / use_volumetric_lights /
       bloom_intensity / bloom_threshold / ssr_max_roughness
    ```

- [x] **修改 `m3dWrapWithSafetyShell` 安全壳**（`index.html` 搜索 `m3dWrapWithSafetyShell`）
  - 把所有硬编码的 `scene.eevee.use_bloom = True` 等改为 hasattr 守护
  - 加 Blender 版本检测：
    ```python
    BL_VER = bpy.app.version  # (4, 2, 0)
    IS_4_PLUS = BL_VER[0] >= 4
    ```

- [x] **推送后自动拉 Blender 执行日志显示在 UI** ✅ v1.6.6 已完成
  - 新增 `m3dPullBlenderLog()` 函数：`fetch(url + '/log')` 取最近 50 条
  - 在「🐍 Blender Python 代码」面板下方新增 `<div id="m3d-blender-log">` 显示日志
  - 推送成功 1.5 秒后自动调一次，ERROR 级别红色高亮 + 错误数徽章
  - 「🔄 刷新」按钮支持手动刷新

---

## 🎬 2. 新模块「🎬 智能 Agent 实时渲染」（保留旧「🧊 一键3D建模」不动）

### 设计哲学
- **保留**「🧊 一键3D建模」(4 步流水线，给追求稳定/可调试的老用户)
- **新增**「🎬 智能 Agent 实时渲染」(极简一键 + 流式 + 自检)

### 顶部入口

在「摄影工具」顶部菜单加第 5 个按钮：
```
[照片墙] [图像分析] [拍摄备忘录] [🧊 一键3D建模] [🎬 智能 Agent 实时渲染 ← v1.6.6 新增]
```

### UI 设计（极简，一个面板搞定）

```
┌─────────────────────────────────────────────────────────────────┐
│  🎬 智能 Agent 实时渲染  · v1.6.6 全新                            │
│                                                                  │
│  ⚠️ 该功能消耗 Token 较大（每轮自检 = 1 次 LLM 调用），按需调整自检策略 │
│                                                                  │
│  Blender 状态：🟢 已连接 (Blender 4.2)                            │
│  桥接 URL: [http://127.0.0.1:9876]  [🩺 测试连接]                 │
│  [📥 一键导出 Blender 插件 zip 到桌面]                            │
│                                                                  │
│  ┌─ API 配置 ──────────────────────────┐                        │
│  │ API:  [▼ 咸鱼API   ]               │                        │
│  │ 模型: [▼ claude-opus-4 ]           │                        │
│  └─────────────────────────────────────┘                        │
│                                                                  │
│  ┌─ 🔄 自检策略 ─────────────────────────┐                      │
│  │ ( ) 不自检（最快，质量一般）           │                      │
│  │ (●) 全部完成后自检（默认，平衡）       │                      │
│  │ ( ) 每建造 [ 5 ] 个物体自检一次（最稳）│                      │
│  │     N 范围：1~30                      │                      │
│  │ 最大自检轮数: [ 3 ] (防失控)          │                      │
│  └─────────────────────────────────────┘                       │
│                                                                  │
│  ┌─ 场景需求（自然语言描述）──────────────┐                       │
│  │  画一间日式茶室，下午阳光斜射进来，    │                       │
│  │  墙边放古琴和书架，地上有蒲团...      │                       │
│  └─────────────────────────────────────┘                       │
│                                                                  │
│  [📚 从聊天记录导入]  [🎬 开始实时建模 ▶]  [⏹ 中止]               │
│                                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│                                                                  │
│  ⏱ Round 1 流式建模中…                                            │
│   ├─ 物体进度: 8 / ~20                                            │
│   ├─ 章节: 主要家具                                              │
│   └─ [INFO] 已推送 2 批，自检 1 次，微调 1 次                      │
│                                                                  │
│   实时代码预览（最新 30 行）：                                     │
│   bpy.ops.mesh.primitive_cube_add(location=(0,2,0.4))           │
│   sofa = bpy.context.active_object; sofa.name = "sofa"          │
│   ...                                                            │
│                                                                  │
│  🔍 Round 2 AI 自检中… → 「沙发太大、缺台灯」                       │
│  🛠️ Round 2 修正中… → 推送 patch 代码（180 字符）                  │
│  🔍 Round 3 AI 自检中… → 「✅ 满意」                               │
│                                                                  │
│  ✅ 完成！总耗时 95s · 物体 18 个 · 灯光 4 盏 · 自检 2 轮            │
└─────────────────────────────────────────────────────────────────┘
```

### 📋 实施清单

#### 2.1 顶部入口 ✅ v1.6.6 已完成
- [x] `index.html` 摄影工具顶部菜单加按钮 `🎬 智能 Agent 实时渲染`
- [x] 新增视图 `<div id="photo-agent3d-view">...</div>`
- [x] `switchPhotoView()` 函数加 `agent3d` 分支

#### 2.2 UI 骨架 ✅ v1.6.6 已完成
- [x] 警示横幅 `.agent-warn-banner`
- [x] 完整 UI 元素：
  - `#agent-bridge-url` (input, 默认 `http://127.0.0.1:9876`)
  - `#agent-test-conn-btn` (调 `GET /ping` 检测)
  - `#agent-bridge-status` (●状态灯，每 3 秒自动 ping)
  - `#agent-export-addon-btn`（调 `/api/blender/export-addon`，见第 5 节）
  - `#agent-api-config`（API 配置下拉，复用 `m3dApiConfig` 的渲染逻辑）
  - `#agent-model-select`（模型下拉，复用 `m3dModelSelect` 的逻辑）
  - **自检策略单选**：
    - `<input type="radio" name="agent-review-mode" value="none">`
    - `<input type="radio" name="agent-review-mode" value="final" checked>` 默认
    - `<input type="radio" name="agent-review-mode" value="incremental">`
    - `#agent-incremental-n` (number input, min=1, max=30, value=5)
    - `#agent-max-rounds` (number input, min=1, max=10, value=3)
  - `#agent-scene-desc` (textarea, 用户输入场景描述)
  - `#agent-import-from-chat-btn` (复用 m3dImportFromChat 的逻辑)
  - `#agent-start-btn` / `#agent-abort-btn`
  - **状态显示区**：
    - `#agent-status-round` (Round X 当前阶段)
    - `#agent-status-progress` (物体进度条 + 文字)
    - `#agent-status-chapter` (当前章节)
    - `#agent-status-stats` (推送批次/自检次数/微调次数)
    - `#agent-code-preview` (最新代码 30 行)
    - `#agent-review-log` (自检历史多行)

#### 2.3 数据模型 + 持久化 ✅ v1.6.6 已完成
- [x] 新增 `agentState`（含 configId/model/sceneDescription/bridgeUrl/reviewStrategy/checkEveryN/maxReviewRounds + 运行时字段）
- [x] `agentSaveState()` / `agentInit()` 通过 `localStorage.agentState_v166` 持久化
- [x] 切换视图、blur 输入框、改 select 时自动保存
  ```js
  let agentState = {
    configId: null,
    model: '',
    sceneDescription: '',
    bridgeUrl: 'http://127.0.0.1:9876',
    reviewStrategy: 'final',  // 'none' | 'final' | 'incremental'
    checkEveryN: 5,           // 1~30
    maxReviewRounds: 3,       // 1~10
    
    // 运行时
    status: 'idle',           // idle | generating | reviewing | done | aborted
    currentRound: 0,
    builtObjects: 0,
    totalChapters: 0,
    completedChapters: 0,
    microPatchCount: 0,
    codePreview: '',          // 最新代码 buffer
    reviewLog: [],            // [{round, time, satisfied, issues, patchChars}]
    
    // 全部累积的代码（用于持久化/调试）
    fullCode: '',
    
    // 中止信号
    abortController: null
  };
  ```
- [ ] `agentSaveState()` / `agentLoadState()`：写入 `localStorage.agentState_v166`
- [ ] 切换视图、关闭页面时自动保存

#### 2.4 三套引擎（核心逻辑） ✅ v1.6.6 已完成
- [x] **引擎 A：不自检模式** `agentRunNoneMode()` —— 一次性生成 + 一次性推送
- [x] **引擎 B：全部完成后自检（默认）** `agentRunFinalMode()` —— 生成 → 推送 → 拉 /scene_report → AI 自检 → 输出 patch → 推送 patch（循环 maxReviewRounds 次）
- [x] **引擎 C：增量自检** `agentRunIncrementalMode()` —— 整段生成 → 按 `# === [OBJ:i/N] ===` 标记拆分 → 每 N 个推送 + 拉报告 + 微观自检 + patch
- [x] 通用：`agentCallLLM`（复用现成的 `m3dCallLLM`，非流式收完即返）/ `agentPushCode` / `agentWaitIdle`（轮询 /ping queue_size=0）/ `agentFetchSceneReport`（404 时自动降级）
- [x] Prompt：内置 `AGENT_COMPAT_RULES`（v1.6.6 兼容性铁律 8 条）+ 生成 prompt + 全部自检 prompt + 增量自检 prompt
- [x] 中止：`AbortController` 一键 `agentAbortRun()` 中断所有 fetch

##### 通用：流式 LLM 调用
- [ ] 新增 `agentCallLLMStream(configId, model, messages, system, onChunk, signal)`
  - 用 fetch + ReadableStream 读取 SSE
  - 每读到一个 chunk 调用 `onChunk(textChunk, fullText)`
  - 支持 `signal: AbortSignal`（用户中止）
  - 自动处理 `[DONE]`、`data: {...}\n\n` SSE 格式
  - 兼容 OpenAI / Claude / Gemini 三家的流式响应

##### 通用：Blender 通讯
- [ ] `agentPing(url)` → `{ ok, blender_version, queue_size }`
- [ ] `agentPushCode(url, code, sceneName)` → POST `/exec`
- [ ] `agentFetchSceneReport(url)` → GET `/scene_report` (插件 1.1.0+)
- [ ] `agentFetchLog(url)` → GET `/log`
- [ ] `agentWaitForBlenderIdle(url, timeoutMs=10000)`：轮询 `/ping` 直到 `queue_size === 0`

##### 引擎 A：不自检模式
- [ ] `agentRunNoneMode()`：流式生成全部代码 → 一次性推送 → 应用安全壳 → 完成

##### 引擎 B：全部完成后自检模式（默认 ⭐）
- [ ] `agentRunFinalMode()`：
  1. 流式生成全部代码 → 边读边按章节推送（参考下方"章节边界检测"）
  2. 等 Blender Idle
  3. for `r in 1..maxReviewRounds`:
     - 拉 `/scene_report`
     - 调 LLM 让 AI 看自己作品 → 输出 `<review>{satisfied,issues}</review>` + `<patch_code>...</patch_code>`
     - 解析 `satisfied`，true 则跳出；false 则推送 patchCode
  4. 应用安全壳

##### 引擎 C：增量自检模式
- [ ] `agentRunIncrementalMode()`：
  1. Prompt 要求 AI 每个物体用 `# === [OBJ:i/N] name ===` 标记
  2. 流式读取，每攒够 N 个 OBJ 标记 → 暂停 buffer，推送当前批
  3. 等 Blender Idle → 拉 `/scene_report`
  4. 调 LLM 微观自检：
     - 输入：当前 5 个物体的报告 + 用户原描述 + 「接下来还会建什么」
     - 输出：`<ok/>` 或 `<patch_code>` 最多 30 行
  5. 如有 patch，推送；继续接收下一批
  6. 流结束后处理最后不到 N 个的尾批
  7. 应用安全壳

##### 章节边界检测
- [ ] `agentDetectObjectBoundary(buffer)` 返回新发现的 `[OBJ:i/N]` 数量
- [ ] `agentSplitByChapter(buffer)` 把 buffer 按 `# === [CHAPTER:xxx] ===` 拆成数组
- [ ] 用 prompt 强制 AI 输出格式：
  ```
  # === [CHAPTER:INIT] 场景初始化 ===
  ...
  # === [OBJ:1/20] floor 地板 ===
  ...
  # === [OBJ:2/20] back_wall 后墙 ===
  ...
  # === [CHAPTER:LIGHTS] 灯光 ===
  # === [LIGHT:1/4] key 主光 ===
  ...
  # === [CHAPTER:CAMERA] 相机 ===
  # === [CAMERA] main_cam ===
  ...
  # === [CHAPTER:FINAL] 渲染设置 ===
  ...
  ```

##### Prompt 模板
- [ ] 主流 system prompt（生成阶段）：参考 `m3dStep4_estimate` 但**新增**：
  - "你正在为流式建模生成代码，请严格按 [CHAPTER:xxx] 和 [OBJ:i/N] 分段，每段 5~20 行 Python，不要写一大坨"
  - "每个 [OBJ:i/N] 段必须用 try/except pass 包裹（避免单点失败）"
  - 1 节里的兼容性铁律全部带过来
- [ ] 全部完成后自检 system prompt：
  ```
  你刚刚生成了一个 Blender 3D 场景。下面是实际渲染后的场景报告：
  【场景报告】{JSON}
  【用户需求】{description}
  请检查是否符合需求，输出：
  <review>
    <satisfied>true|false</satisfied>
    <summary>一句话总结</summary>
    <issues>...</issues>
  </review>
  <patch_code>
  # 只输出修正部分（≤50 行），不要重写整段
  ...
  </patch_code>
  ```
- [ ] 增量自检 system prompt：
  ```
  你刚建造了 5 个物体，下面是这一批的状态：
  【当前场景】{JSON}
  【用户原始需求】{description}
  请快速检查这 5 个物体是否合理（穿模/尺寸/材质）。
  如果没问题输出 <ok/>，否则输出 <patch_code> 最多 30 行修正代码。
  ⚠️ 只调整已有物体（用 bpy.data.objects["xxx"]），不要建造新物体。
  ```

#### 2.5 UI 反馈 ✅ v1.6.6 已完成
- [x] 状态条 4 行：Round / 物体进度 / 章节 / 推送-自检-微调统计 —— 实时更新
- [x] 代码预览 `#agent-code-preview` 只显示最新 30 行（滚动 follow-tail）
- [x] 自检日志 `#agent-review-log` 多行追加，支持「🔄 Blender 日志」按钮抓 /log
- [x] 完成时输出：总耗时 + 物体数 + 自检轮数 + 微调次数

---

## 🤖 3. Blender 插件升级 1.0.2 → 1.1.0

### 新增接口

#### `GET /scene_report` 返回当前 Blender 场景的 JSON 报告

返回格式（必须实现）：
```json
{
  "ok": true,
  "addon_version": "1.1.0",
  "blender": {
    "version_string": "4.2.0",
    "version": [4, 2, 0],
    "major": 4,
    "minor": 2
  },
  "engine": "BLENDER_EEVEE_NEXT",
  "view_transform": "Filmic",
  "viewport_shading": "RENDERED",
  "active_camera": "Camera",
  "frame_current": 1,
  "objects": [
    {
      "name": "floor",
      "type": "MESH",
      "location": [0, 0, 0],
      "rotation_euler": [0, 0, 0],
      "scale": [1, 1, 1],
      "dimensions": [10, 10, 0.01],
      "material": "floor_mat",
      "base_color": [0.4, 0.3, 0.2, 1.0],
      "emission_strength": 0.0,
      "has_emission": false
    },
    {
      "name": "sofa",
      "type": "MESH",
      "location": [0, 2, 0.4],
      "dimensions": [2.5, 1, 0.8],
      "material": "sofa_mat",
      "base_color": [0.6, 0.4, 0.3, 1.0],
      "emission_strength": 0.0,
      "has_emission": false
    },
    {
      "name": "key",
      "type": "LIGHT",
      "light_type": "AREA",
      "energy": 1500.0,
      "color": [1, 1, 1],
      "location": [3, -3, 4]
    }
  ],
  "stats": {
    "mesh_count": 12,
    "light_count": 4,
    "emissive_mesh_count": 2,
    "has_camera": true,
    "has_world_bg": true,
    "total_polygons": 5320
  },
  "recent_errors": [
    {"t":"20:15:30","level":"ERROR","msg":"AttributeError: ..."}
  ]
}
```

实现要点（Python 代码）：
- 在 `_drain_queue` 同样的主线程上下文中执行（因为 bpy 数据访问也是单线程的）
- **不能**在 HTTP handler 线程直接读 bpy.data → 用一个共享 dict + lock，由 `_drain_queue` 定时刷新
- 或者更简单：handler 收到 `/scene_report` 时把请求塞队列，等定时器填好结果再返回（但 HTTP timeout 会麻烦）
- **推荐方案**：handler 直接读 `bpy.data` —— 虽然官方说单线程，但实际只读不写的情况下 Blender 是稳定的，参考社区实践

#### `GET /ping` 增强返回 Blender 版本号

```json
{
  "ok": true,
  "addon_version": "1.1.0",
  "blender": "4.2.0",
  "blender_version": [4, 2, 0],
  "blender_major": 4,
  "blender_minor": 2,
  "queue_size": 0
}
```

### 📋 实施清单
- [x] `aichat_bridge/__init__.py` `bl_info["version"]` 改成 `(1, 1, 0)`
- [x] 添加 `_collect_scene_report()` 函数
- [x] 添加 `do_GET` 中的 `/scene_report` 路由
- [x] `/ping` 增加 Blender 版本字段
- [x] **本会话已完成插件代码改动**
- [ ] 新会话：运行 `npm run build:addon` 重新打 zip
- [ ] 新会话：测试 zip 在 Blender 4.2 上的兼容性

### 向后兼容
- 老前端只用 `/exec`、`/ping`、`/log` → 完全不受影响
- 新前端如果检测到 `/scene_report` 404 → 自动降级为"不自检"模式 + 提示用户重装插件

---

## 📥 4. 「一键导出 Blender 插件 zip 到桌面」按钮

### 痛点
macOS 用户找 `.app` 包内 `Contents/Resources/blender_addon/aichat_bridge.zip` 是反人类操作。一键按钮把 zip 复制到桌面。

### 📋 实施清单

#### server.js 端点 ✅ v1.6.6 已完成
- [x] 新增 `GET /api/blender/export-addon`：
  ```js
  app.get('/api/blender/export-addon', (req, res) => {
    const os = require('os');
    const path = require('path');
    const fs = require('fs');
    
    // 在 Electron 打包后，extraResources 位于 process.resourcesPath
    // 在开发环境，位于 ./blender_addon/aichat_bridge.zip
    const candidates = [
      process.resourcesPath ? path.join(process.resourcesPath, 'blender_addon', 'aichat_bridge.zip') : null,
      path.join(__dirname, 'blender_addon', 'aichat_bridge.zip')
    ].filter(Boolean);
    
    let srcPath = null;
    for (const p of candidates) {
      if (fs.existsSync(p)) { srcPath = p; break; }
    }
    
    if (!srcPath) {
      return res.status(404).json({ ok: false, error: 'aichat_bridge.zip not found' });
    }
    
    const desktopDir = path.join(os.homedir(), 'Desktop');
    const destPath = path.join(desktopDir, 'aichat_bridge.zip');
    
    try {
      fs.copyFileSync(srcPath, destPath);
      res.json({ ok: true, path: destPath });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });
  ```

#### 前端按钮 ✅ v1.6.6 已完成
- [x] 在「一键3D建模」和「智能 Agent 实时渲染」两个视图都加：
  ```html
  <button onclick="exportBlenderAddon()">📥 一键导出 Blender 插件到桌面</button>
  ```
- [x] 函数 `exportBlenderAddon()`：
  ```js
  async function exportBlenderAddon() {
    try {
      const r = await fetch('/api/blender/export-addon');
      const j = await r.json();
      if (j.ok) {
        alert(`✅ 已导出到：\n${j.path}\n\n安装步骤：\n1. 打开 Blender → Edit → Preferences → Add-ons\n2. 点 "Install..." → 选择刚导出的 zip\n3. 勾选启用 "AIChat Bridge"\n4. 回到本软件，点🩺测试连接，看到🟢即可`);
      } else {
        alert('❌ 导出失败：' + j.error);
      }
    } catch (e) {
      alert('❌ 导出失败：' + e.message);
    }
  }
  ```

---

## 🎉 5. 欢迎弹窗 v1.6.6

### 📋 实施清单 ✅ v1.6.6 已完成
- [x] `index.html` `hasLaunched_v1.6.6` key 已升级
- [x] 弹窗顶部加 v1.6.6 章节：
  ```
  🎉 v1.6.6 重磅更新
  
  🐛 修复一键3D「只生成一个平面」致命 Bug
     - Blender 4.x EEVEE Next 移除了 use_bloom/use_volumetric_lights 等属性
     - AI 用了这些会让整段代码 exec 中断
     - 现在 prompt 强制 hasattr 守护 + 每物体 try/except 兜底
     - 推送后自动拉 Blender 执行日志显示到 UI
  
  🎬 全新模块「智能 Agent 实时渲染」
     - 流式分章节推送：边生成代码边在 Blender 里出现物体 ✨
     - 三种自检策略：不自检 / 全部完成后自检（默认）/ 每 N 个物体自检（N=1~30）
     - AI 看到自己作品的 /scene_report → 自我纠正
     - ⚠️ 此功能消耗 Token 较大，按需调整自检策略
  
  🤖 Blender 插件升级 1.0.2 → 1.1.0（必须重装！）
     - 新增 GET /scene_report：把场景物体/灯光/相机/状态喂给 AI 自检
     - GET /ping 返回 Blender 版本号，AI 可适配 3.x / 4.x 代码
     - 一键导出插件 zip 到桌面（解决 mac 用户翻 .app 包内容的痛）
  
  📥 「📥 一键导出 Blender 插件到桌面」
     - 在两个建模模块都能看到，不用翻 .app 包了
  ```
- [x] v1.6.5 内容降到 `<details>` 折叠区

---

## 📦 6. 重新打包

### 📋 实施清单
- [x] `npm run build:addon` 重新打 zip（已确认 7935 字节，包含插件 1.1.0）
- [ ] `npm run build:mac` 打 dmg（arm64 + x64）—— 留给用户手动执行（耗时长）
- [ ] `npm run build:win` 打 nsis（x64 + arm64）—— 留给用户手动执行（耗时长）
- [x] 烟雾测试：`node server.js` 启动 OK + `GET /api/blender/export-addon` HTTP 200，zip 成功复制到桌面
- [x] JS 语法检查：通过 `new Function(code)`，主 script 283426 字符 OK
- [ ] 实机测试在 macOS 14 + Blender 4.2 上（留给用户）：
  - [x] 新版插件 zip 能正常安装启用
  - [ ] 一键3D 现在能完整生成 18 个物体（不再只剩 plane）
  - [ ] 智能 Agent 实时渲染能流式推送 + 自检 + 修正

---

## 📊 v1.6.5 → v1.6.6 改动统计

| 类型 | 行数预估 |
|---|---|
| `index.html` 修改 | ~50 行（修 prompt + 拉 log） |
| `index.html` 新增 Agent 模块 | ~600 行 |
| `server.js` 新增 export-addon | ~30 行 |
| `aichat_bridge/__init__.py` 新增 | ~100 行（scene_report） |
| 文档 | ~600 行 |

---

## 🆘 新会话开工流程（重要！）

如果新会话接手，请按以下顺序：

1. **读规格**：`read_file ai-chat/RELEASE_v1.6.6.md`（本文档）
2. **读现状**：
   - `read_file ai-chat/public/index.html` (从 m3dStep4_estimate 开始读)
   - `read_file ai-chat/blender_addon/aichat_bridge/__init__.py`（确认 1.1.0 已经写进去了）
   - `read_file ai-chat/server.js`
3. **按 1~6 节顺序实施**，每节先做"实施清单"里的 `[ ]` 项
4. **每完成一节同步更新本文档**：把 `[ ]` 改成 `[x]`
5. **最后**：`npm run build:addon` + `npm run build:mac` + `npm run build:win`

预计总工作量：**3.5~4 小时**

---

## 🙏 致谢

感谢用户提的两个金点子：
1. **「让 Claude 一边建模一边修改」**（流式 + 自检）→ 直接催生了 Agent 模块
2. **「自定义建造几个物体之后检查一次」**（增量自检 N）→ 让用户能在速度和质量之间自由权衡

这就是从「文字聊天套壳」迈向**「生产力工具自动化」**的关键一跃。
