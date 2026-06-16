# v1.9.0 接力进度文档（context 满了，新会话用这个续）

**当前状态**：所有代码改动都已落盘，**就差最后一步 `npm run build:mac` 打包 dmg**。

---

## 🎯 本次任务背景（用户原话）

1. **v1.8.5**：约束窗口大小不能超过屏幕 + Tripo3D 403 报错信息要详细
2. **v1.8.5 增补**：用户说免费版只能并行 1 个任务（所以加了串行+2s 间隔+熔断）
3. **v1.9.0 转向**：用户告知**只有 Tripo3D 网页积分、没有 API 积分**。原 A 路径（直连 HTTP API）走不通，必须用网页积分。解决方案：集成 Tripo 官方 Blender 插件「Tripo3d_Blender_Bridge」（WebSocket 服务端，监听 60600 端口接收网页推送的 GLB）到 ai-chat 里一键导出。

---

## ✅ 已完成的代码改动

### 1. `main.js` — 窗口约束（v1.8.5）
- 引入 `screen.getPrimaryDisplay().workAreaSize`
- 窗口尺寸 = `min(1200, sw)` × `min(800, sh)`
- 加 `minWidth: 900 / minHeight: 600 / maxWidth: sw / maxHeight: sh`
- `center: true` + `useContentSize: true` + `setMaximumSize(sw, sh)`
- require 处加了 `screen`：`const { app, BrowserWindow, dialog, screen } = require('electron');`

### 2. `server.js` — Tripo3D 错误信息友好化（v1.8.5）+ 新增 Tripo Bridge 导出端点（v1.9.0）

**v1.8.5 错误信息**：`/api/tripo3d/create` 失败时把 Tripo 真实的 `code/message/suggestion` 拼成 friendly 错误，并对 401/403/429 加专属提示（403 直接告诉用户三种原因：免费版并发限制/中文 prompt/余额不足）

**v1.9.0 新端点**：
- 重构出 `exportAddonZipImpl(zipName, res)` 通用函数
- 新增 `GET /api/blender/export-tripo-bridge` → 导出 `tripo_bridge.zip` 到桌面
- 老的 `/api/blender/export-addon` 保持不变

### 3. 文件移动 — Tripo Bridge 已集成到 blender_addon/

```bash
mv ai-chat/Tripo3d_Blender_Bridge ai-chat/blender_addon/tripo_bridge
cd ai-chat/blender_addon && zip -rq tripo_bridge.zip tripo_bridge -x '*.DS_Store' '*__pycache__*'
```

结果：
- `ai-chat/blender_addon/aichat_bridge.zip` (13K)
- `ai-chat/blender_addon/tripo_bridge.zip` (201K) ← 新增

`package.json` 的 `extraResources` 已经包含整个 `blender_addon` 目录，所以打包时两个 zip 都会被打进 dmg。**不需要改 package.json 的 extraResources**。

### 4. `public/index.html` — Tripo3D 面板大改造（v1.9.0）

**改动位置 1**：radio 选项的文案
- 之前：`🤖 Tripo3D 文生 3D（用户自带 key · 付费）...platform.tripo3d.ai...`
- 现在：`🤖 Tripo3D 文生 3D（v1.9.0 改走网页积分）· 不用 API key 也能用 · 通过 Tripo Bridge 插件自动导入 Blender`

**改动位置 2**：`#agent-tripo3d-panel` 面板内容整段替换
- 之前：API key 输入框 + 模型版本下拉
- 现在：5 步工作流说明 + 两个按钮
  - `📥 一键导出 Tripo Bridge 插件到桌面` → `exportTripoBridgeAddon()`
  - `🌐 打开 Tripo3D 网页（用网页积分）` → `openTripo3DWebsite()`
- 底部加蓝色提示框，说明本模式下「开始实时建模」按钮不会自动批量生成（因为网页积分必须手动确认）

**改动位置 3**：新增两个 JS 函数（在 `exportBlenderAddon()` 后面）
```javascript
async function exportTripoBridgeAddon() {
  // 调 /api/blender/export-tripo-bridge → 桌面
  // 提示 5 步安装：1) Edit → Preferences → Add-ons 2) Install... 3) 启用 Tripo Bridge
  // 4) N 面板点 Start Server 5) 回 ai-chat 点「打开网页」
}

function openTripo3DWebsite() {
  // 优先用 Electron shell.openExternal('https://www.tripo3d.ai/app/')
  // 兜底 window.open
}
```

### 5. `package.json` — 版本号升到 1.9.0
- `"version": "1.9.0"` ✅
- description 还是 v1.8.3 的老描述，**没改**（不影响功能，可选优化）

---

## ❌ 还没做的（**新会话第一步就干这个**）

### 1. **打包 dmg**（最关键！）
```bash
cd /Users/Apple/Desktop/ai-chat && npm run build:mac 2>&1 | tail -15
```
预期产物：
- `dist/白歌的AI讨论组-1.9.0-arm64.dmg`
- `dist/白歌的AI讨论组-1.9.0-x64.dmg`

### 2. 欢迎弹窗 key 是否要升级（可选）
当前是 `hasLaunched_v1.8.4`，是否要升到 `hasLaunched_v1.9.0` 让老用户重启后再看一次欢迎弹窗？
- 弹窗内容是否需要加一段 v1.9.0 的更新说明？
- 决策由用户自己定，可以问一下；如果用户没说就先保持 v1.8.4 别动。

### 3. 测试场景（用户自己跑）
- 装 `tripo_bridge.zip` 到 Blender，启用插件
- 在 ai-chat 切到 Tripo3D radio，点「📥 导出 Tripo Bridge 插件」（验证后端端点）
- 点「🌐 打开 Tripo3D 网页」（验证 Electron shell.openExternal 跳转）
- 在 Tripo3D 网页生成模型，点 Send to Blender，看 Blender 那边是否自动导入

---

## 📦 文件改动清单（git diff 可看）

```
M  ai-chat/main.js                                    (窗口约束)
M  ai-chat/server.js                                  (错误友好化 + export-tripo-bridge 端点)
M  ai-chat/public/index.html                          (Tripo3D 面板改造 + 两个新函数)
M  ai-chat/package.json                               (version: 1.8.5 → 1.9.0)
R  ai-chat/Tripo3d_Blender_Bridge → ai-chat/blender_addon/tripo_bridge
A  ai-chat/blender_addon/tripo_bridge.zip             (201K，已打包)
A  ai-chat/RELEASE_v1.9.0.md                          (本文档)
```

---

## 🚀 新会话的开场白模板

> 我开了新会话，请帮我把 ai-chat 项目打包成 dmg。所有代码改动都已落盘，详见 `/Users/Apple/Desktop/ai-chat/RELEASE_v1.9.0.md`。只需要 `cd ai-chat && npm run build:mac`，然后用 attempt_completion 给我看产物路径就行。

或者更宽松一点：

> 续上 v1.9.0 任务，按 RELEASE_v1.9.0.md 接着干（先打包 dmg）。
