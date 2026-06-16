# v1.9.3 修复智能 Agent 两个体验 bug

> 发布日期：2026/5/17
> 上游版本：v1.9.2
> 关键词：**死锁修复 + 四宫格参考图一键导入**

---

## 🐛 bug 1：任务失败后再次启动报「Agent 正在运行中」死锁

### 现场
用户报告：实时渲染中任务失败或结束后，再点「🎬 开始实时建模」会弹出 `Agent 正在运行中，请先停止`，但停止按钮已经消失，无法继续。

### 根因
`agentStartRun()` 的 `finally` 块只重置了 UI（隐藏停止按钮、显示开始按钮），但**漏了把 `agentState.status` 从 `'generating'` / `'reviewing'` 重置回 `'aborted'`**。

下次启动时入口检查：
```js
if (agentState.status === 'generating' || agentState.status === 'reviewing') {
  alert('Agent 正在运行中，请先中止'); return;
}
```
而 `'⏹ 中止'` 按钮的 onclick 已经在 finally 里被隐藏了 → 死锁。

### 修复
`finally` 块结尾追加：
```js
// v1.9.3：finally 必须重置 status，否则失败后再点开始会卡在「Agent 正在运行中」死锁
if (agentState.status === 'generating' || agentState.status === 'reviewing') {
  agentState.status = 'aborted';
}
```

只在还停留在运行态时重置（`'done'` / `'aborted'` 状态保持不变，避免覆盖正常完成的状态字段）。

---

## 🐛 bug 2：一键3D 四宫格参考图无法一键导入到智能 Agent

### 现场
用户已经在「🧊 一键3D建模」面板的 Step 3 用 GPT-Image-2 / DALL-E-3 生成了一张 1024×1024 四宫格参考图（含前/侧/顶/45° 四个视角），但在「🎬 智能 Agent 实时渲染」的参考图区只能手动重新上传图片，无法直接复用。

### 修复
**UI 层**：在智能 Agent 参考图区新增「📋 从一键3D导入四宫格」按钮（绿色边框，与上传按钮并排）：

```html
<button class="btn-icon" onclick="agentImportFromM3dGrid()" 
  style="font-size: 11px; padding: 3px 8px; background: rgba(16,185,129,0.1); 
         border-color: rgba(16,185,129,0.4); color: var(--accent2);" 
  title="把【一键3D建模 → Step 3】生成的四宫格参考图一键导入到这里">
  📋 从一键3D导入四宫格
</button>
```

**逻辑层**：新增 `agentImportFromM3dGrid()` 函数：
1. 读取 `m3dState.views._grid`（v1.6.1 起 Step 3 升级为单图四宫格，4 个视角全在一张正方形大图里）
2. 校验：`m3dState` 是否存在、`views` 是否非空、是否已导入过（防重复）
3. 如果参考图区已满 4 张，弹确认替换
4. push 到 `agentState.referenceImages` → 触发 `agentRenderRefImages()` 重渲染缩略图 → `agentSaveState()` 持久化
5. 友好 alert 提示导入成功，AI 视觉模型可以"看到"这张图辅助理解空间布局

### 兜底场景
- 用户没在同项目下跑过 Step 3 → 提示先去一键3D 完成 Step 1~3
- 数据为空 → 提示重新生成
- 已存在该图 → 提示无需重复导入

---

## 📝 修改清单

| 文件 | 改动 |
|------|------|
| `package.json` | 版本 1.9.2 → **1.9.3** + 更新 description |
| `public/index.html` | ① `agentStartRun()` finally 重置 status 防死锁<br>② 智能 Agent 参考图区新增「📋 从一键3D导入四宫格」按钮<br>③ 新增 `agentImportFromM3dGrid()` 函数 |
| `RELEASE_v1.9.3.md` | 本文件 |
| `CHANGELOG.md` | 新增 v1.9.3 段落 |

---

## 🧪 测试

### bug 1：失败后死锁
1. 在智能 Agent 选个不正确的 API（如 key 已过期）→ 点「🎬 开始实时建模」
2. 等到失败弹错误日志后再次点开始
3. ✅ 期望：能正常启动；❌ 之前：弹「Agent 正在运行中」无法继续

### bug 2：四宫格导入
1. 在某摄影项目下：完成「🧊 一键3D建模」Step 1（选聊天记录）→ Step 2（生成场景描述）→ Step 3（生成 1024×1024 四宫格参考图）
2. 切到「🎬 智能 Agent 实时渲染」面板
3. 点参考图区的「📋 从一键3D导入四宫格」按钮
4. ✅ 期望：alert 「✅ 已导入...」+ 参考图区出现一张缩略图
5. 重复点 → ✅ 期望：alert「已经导入过这张...」

---

## 🚀 下一步（新会话）

```bash
cd /Users/Apple/Desktop/ai-chat && npm run build:mac
```

打包成功后 `dist/白歌的AI讨论组-1.9.3-arm64.dmg` + `dist/白歌的AI讨论组-1.9.3-x64.dmg`。
