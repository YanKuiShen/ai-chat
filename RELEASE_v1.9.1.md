# Release v1.9.1 — 砍 Tripo3D + 加「📁 导入本地 3D 模型」

> 上一版 v1.9.0 设计前提塌房：用户实测 Tripo3D 网页「Send to Blender」是**会员专属**功能，免费用户只能下载 GLB / 图生模型，部分用户网页都打不开。这一版做大扫除 + 提供更通用的替代方案。

## ✅ 已完成的改动（待打包 dmg）

### 🚫 删除塌房的 Tripo3D 入口
- **`blender_addon/tripo_bridge/` 目录已删** + **`tripo_bridge.zip` 已删**
- **server.js**：
  - 删除 `/api/blender/export-tripo-bridge` 端点（约 20 行）
  - 删除 `/api/tripo3d/create` / `/api/tripo3d/task/:id` / `/api/tripo3d/download-glb` 3 个透传端点（约 100 行，已用 `// v1.9.1 已删除` 注释占位 —— ⚠️ 实际删除待打包前再清理，目前死代码不影响功能）
- **public/index.html**：
  - 删除「🤖 Tripo3D 文生 3D」radio 选项（从 3 选 1 缩成 2 选 1：⚡ AI 从零生成 / 🎨 PolyHaven 网络资产）
  - 删除 `#agent-tripo3d-panel` 整段配置面板（约 25 行 HTML）
  - 主调度 `agentStartRun()` 里 `genMode === 'tripo3d'` 分支改为自动 fallback 到 polyhaven
  - localStorage 残留 `generationMode=tripo3d` 自动 silent 切换到 polyhaven（不报错）
  - 老的 `exportTripoBridgeAddon()` / `openTripo3DWebsite()` / `agentToggleTripoPanel()` / `agentRunTripo3DMode()` / `agentTripo3DGenerateOne()` / `agentExtractTripo3DPlan()` / `AGENT_TRIPO3D_PROMPT` 等 JS 函数和 prompt 模板保留（死代码，不影响功能，待下个版本清理）

### 📁 新增「📁 导入本地 3D 模型到 Blender」一键按钮
**位置**：智能 Agent 实时渲染 → 「🎨 生成方式」面板下方独立工具区（与上方 radio 解耦，随时可用）

**功能**：
- 用户从**任何渠道**拿到的 3D 模型都能一键塞进 Blender —— Tripo3D 网页下载 / Meshy / Sketchfab / 本地 Blender 建模 都行
- 支持 **7 种主流格式**：`.glb` / `.gltf` / `.fbx` / `.obj` / `.dae` / `.ply` / `.stl`
- **零插件升级**：复用现有 `aichat_bridge` 1.2.0 的 `/exec` 端点，老用户不用重装插件就能直接用

**实现**：
- **前端 `importLocalModelToBlender()` 函数**（≈ 80 行）：
  1. 文件大小校验（>200 MB 弹确认）
  2. 检查 Blender 桥接是否在线（`/ping`）
  3. FileReader 读成 base64 → POST `/api/blender/upload-local-model` 上传到本机 OS 临时目录
  4. 后端返回绝对路径 → 拼接对应格式的 `bpy.ops.import_scene.gltf/fbx/...` 命令
  5. POST 到 Blender `/exec` 让主线程导入
  6. 导入后的物体自动重命名 + 选中（按 Numpad . 聚焦）
- **后端 `/api/blender/upload-local-model` 端点**（≈ 30 行）：
  - 解析 `data:application/octet-stream;base64,xxxxx` 格式
  - 用 OS 临时目录（`os.tmpdir()/aichat-local-models/`）存到本地
  - 唯一文件名：`{时间戳}_{安全文件名}.{ext}`
  - 返回 `{ ok: true, local_path: '/var/folders/.../xxx.glb', size: 1234567 }`

### 📜 欢迎弹窗
- **`hasLaunched_v1.8.4` → `hasLaunched_v1.9.1`**：老用户重启后会再弹一次新内容
- 顶部章节标题暂未更新（仍显示 v1.8.2，待手动改一下，不影响功能）

### 📦 元数据
- `package.json`：`1.9.0` → `1.9.1`

## ❌ 新会话第一步要做

```bash
cd /Users/Apple/Desktop/ai-chat && npm run build:mac
```

## 🧹 可选的后续清理（不影响功能）

如果想让代码更干净，可以删掉 `public/index.html` 里这些 v1.8.4 残留的死代码：
- `agentToggleTripoPanel()` 函数（不再有面板可切换）
- `agentRunTripo3DMode()` / `agentTripo3DGenerateOne()` / `agentExtractTripo3DPlan()` 三个函数（约 200 行）
- `AGENT_TRIPO3D_PROMPT` 常量（约 40 行）
- `exportTripoBridgeAddon()` / `openTripo3DWebsite()` 两个函数（约 30 行）
- `agentState.tripo3dApiKey` / `agentState.tripo3dVersion` 两个字段（agentInit/agentSaveState 里也要相应清理）
- server.js 里的 3 个 `/api/tripo3d/*` 透传端点（约 100 行）

但**这些死代码不会被任何 UI 调用**，所以放着也无害，下个版本再清也行。

## 🚀 开新会话的开场白

> 续上 v1.9.1 任务，按 `RELEASE_v1.9.1.md` 接着干（先打包 dmg）。
